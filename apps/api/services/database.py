"""Provider-neutral, database-first bibliography storage.

PostgreSQL is the production target. A SQLite database outside the repository
is the zero-configuration development fallback. BibTeX is always a derived
export, except for an explicit or one-time legacy import.
"""

import json
import os
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

import bibtexparser
import toon
from alembic import command
from alembic.config import Config
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from dotenv import load_dotenv
from rapidfuzz import fuzz
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    delete,
    event,
    func,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Connection, Engine, RowMapping

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
API_ROOT = Path(__file__).parent.parent
LITERATURE_ROOT = PROJECT_ROOT.parent / "literature"
BIB_PATH = LITERATURE_ROOT / "references" / "bibliography.bib"
LEGACY_NOTES_PATH = PROJECT_ROOT / "bib-manager" / "data" / "notes.toon"
load_dotenv(PROJECT_ROOT / "bib-manager" / ".env.local")

_STANDARD_FIELDS = ("title", "author", "year", "journal", "publisher")
_schema = MetaData()

settings_table = Table(
    "library_settings",
    _schema,
    Column("key", String(100), primary_key=True),
    Column("value", Text, nullable=False),
)

entries_table = Table(
    "entries",
    _schema,
    Column("key", String(255), primary_key=True),
    Column("entry_type", String(50), nullable=False),
    Column("title", Text, nullable=False, default=""),
    Column("author", Text, nullable=False, default=""),
    Column("year", String(50), nullable=False, default=""),
    Column("journal", Text, nullable=False, default=""),
    Column("publisher", Text, nullable=False, default=""),
    Column("fields", JSON, nullable=False),
    Column("notes", Text, nullable=False, default=""),
    Column("sort_order", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

summaries_table = Table(
    "entry_summaries",
    _schema,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "entry_key",
        String(255),
        ForeignKey("entries.key", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("kind", String(50), nullable=False, default="abstract"),
    Column("language", String(20), nullable=False, default="zh-TW"),
    Column("content", Text, nullable=False),
    Column("model", String(255), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("entry_key", "kind", "language", name="uq_entry_summary"),
)

blog_posts_table = Table(
    "blog_posts",
    _schema,
    Column("slug", String(255), primary_key=True),
    Column("title", Text, nullable=False, default=""),
    Column("url", Text, nullable=False, default=""),
    Column("source_path", Text, nullable=False, default=""),
    Column("published_at", DateTime(timezone=True), nullable=True),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

entry_blog_posts_table = Table(
    "entry_blog_posts",
    _schema,
    Column(
        "entry_key",
        String(255),
        ForeignKey("entries.key", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "blog_slug",
        String(255),
        ForeignKey("blog_posts.slug", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("relation_type", String(50), nullable=False, default="cited-by"),
    Column("notes", Text, nullable=False, default=""),
)


def _default_database_url() -> str:
    data_home = Path(
        os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
    )
    database_path = data_home / "knowledge-base" / "library.sqlite3"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{database_path}"


def _normalise_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def _build_engine(url: str) -> Engine:
    url = _normalise_database_url(url)
    options: dict[str, Any] = {"pool_pre_ping": True}
    if url.startswith("sqlite:"):
        options["connect_args"] = {"check_same_thread": False, "timeout": 10}
    elif url.startswith("postgresql+"):
        # Fail promptly on broken VPN/DNS/routes instead of hanging API startup.
        options["connect_args"] = {"connect_timeout": 10}
        options["pool_timeout"] = 10
    created_engine = create_engine(url, **options)
    if url.startswith("sqlite:"):

        @event.listens_for(created_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.close()

    return created_engine


DATABASE_URL = (
    os.environ.get("BIB_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or _default_database_url()
)
MIGRATION_DATABASE_URL = os.environ.get("DATABASE_URL_UNPOOLED") or DATABASE_URL
engine = _build_engine(DATABASE_URL)
migration_engine = _build_engine(MIGRATION_DATABASE_URL)


def configure_database(url: str) -> None:
    """Replace the engine, primarily for tests and local tooling."""
    global DATABASE_URL, MIGRATION_DATABASE_URL, engine, migration_engine
    engine.dispose()
    migration_engine.dispose()
    DATABASE_URL = url
    MIGRATION_DATABASE_URL = url
    engine = _build_engine(url)
    migration_engine = _build_engine(url)


def database_backend() -> str:
    return engine.dialect.name


def _parse_bibtex(text: str) -> list[dict[str, str]]:
    parser = BibTexParser(common_strings=True)
    parser.customization = convert_to_unicode
    parsed = bibtexparser.loads(text, parser=parser)
    return [dict(entry) for entry in parsed.entries]


def _normalise_entry(entry: Mapping[str, Any]) -> tuple[str, str, dict[str, str]]:
    key = str(entry.get("ID") or entry.get("key") or "").strip()
    if not key:
        raise ValueError("Bibliography entry is missing a citation key")
    entry_type = str(
        entry.get("ENTRYTYPE") or entry.get("entry_type") or "misc"
    ).strip().lower()
    fields: dict[str, str] = {}
    supplied_fields = entry.get("fields")
    if isinstance(supplied_fields, Mapping):
        fields.update(
            {
                str(field).lower(): str(value)
                for field, value in supplied_fields.items()
                if value is not None and str(value) != ""
            }
        )
    reserved = {"ID", "ENTRYTYPE", "key", "entry_type", "fields", "notes", "content"}
    for field, value in entry.items():
        if field not in reserved and value is not None and str(value) != "":
            fields[str(field).lower()] = str(value)
    return key, entry_type, fields


def _entry_to_bibtex(key: str, entry_type: str, fields: Mapping[str, str]) -> str:
    preferred = [
        "author",
        "title",
        "journal",
        "booktitle",
        "publisher",
        "year",
        "volume",
        "number",
        "pages",
        "doi",
        "url",
    ]
    ordered_fields = [field for field in preferred if field in fields]
    ordered_fields.extend(sorted(set(fields) - set(ordered_fields)))
    lines = [f"@{entry_type}{{{key},"]
    lines.extend(f"  {field} = {{{fields[field]}}}," for field in ordered_fields)
    lines.append("}")
    return "\n".join(lines)


def _row_to_entry(row: RowMapping) -> dict[str, Any]:
    fields = row["fields"]
    if isinstance(fields, str):
        fields = json.loads(fields)
    return {
        "key": row["key"],
        "entry_type": row["entry_type"],
        **{field: row[field] for field in _STANDARD_FIELDS},
        "fields": fields,
        "content": _entry_to_bibtex(row["key"], row["entry_type"], fields),
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _attach_blog_posts(
    connection: Connection, entries: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Attach bibliography-linked public blog posts to entry dictionaries."""
    if not entries:
        return entries
    by_key = {entry["key"]: entry for entry in entries}
    for entry in entries:
        entry["blog_posts"] = []

    blog_rows = connection.execute(
        select(
            entry_blog_posts_table.c.entry_key,
            entry_blog_posts_table.c.relation_type,
            blog_posts_table.c.slug,
            blog_posts_table.c.title,
            blog_posts_table.c.url,
            blog_posts_table.c.published_at,
        )
        .join(
            blog_posts_table,
            entry_blog_posts_table.c.blog_slug == blog_posts_table.c.slug,
        )
        .where(entry_blog_posts_table.c.entry_key.in_(by_key))
        .order_by(blog_posts_table.c.published_at.desc())
    ).mappings()
    for row in blog_rows:
        by_key[row["entry_key"]]["blog_posts"].append(
            {
                "slug": row["slug"],
                "title": row["title"],
                "url": row["url"],
                "published_at": row["published_at"],
                "relation_type": row["relation_type"],
            }
        )
    return entries


def _next_sort_order(connection: Connection) -> int:
    value = connection.execute(select(func.max(entries_table.c.sort_order))).scalar()
    return 0 if value is None else value + 1


def _upsert_with_connection(
    connection: Connection,
    entry: Mapping[str, Any],
    *,
    sort_order: int | None = None,
) -> dict[str, Any]:
    key, entry_type, fields = _normalise_entry(entry)
    now = datetime.now(UTC)
    existing = connection.execute(
        select(entries_table).where(entries_table.c.key == key)
    ).mappings().first()
    order = existing["sort_order"] if existing else sort_order
    if order is None:
        order = _next_sort_order(connection)
    notes = (
        str(entry["notes"])
        if "notes" in entry and entry["notes"] is not None
        else (existing["notes"] if existing else "")
    )
    values = {
        "entry_type": entry_type,
        **{field: fields.get(field, "") for field in _STANDARD_FIELDS},
        "fields": fields,
        "notes": notes,
        "sort_order": order,
        "updated_at": now,
    }
    if existing:
        connection.execute(
            update(entries_table).where(entries_table.c.key == key).values(**values)
        )
    else:
        connection.execute(
            insert(entries_table).values(
                key=key,
                created_at=now,
                **values,
            )
        )
    row = connection.execute(
        select(entries_table).where(entries_table.c.key == key)
    ).mappings().one()
    return _row_to_entry(row)


def _set_setting(connection: Connection, key: str, value: str) -> None:
    exists = connection.execute(
        select(settings_table.c.key).where(settings_table.c.key == key)
    ).first()
    if exists:
        connection.execute(
            update(settings_table).where(settings_table.c.key == key).values(value=value)
        )
    else:
        connection.execute(insert(settings_table).values(key=key, value=value))


def _migrate_legacy_notes(connection: Connection) -> None:
    if not LEGACY_NOTES_PATH.exists():
        return
    content = LEGACY_NOTES_PATH.read_text(encoding="utf-8").strip()
    if not content:
        return
    notes = toon.decode(content)
    if not isinstance(notes, Mapping):
        return
    for key, note in notes.items():
        connection.execute(
            update(entries_table)
            .where(entries_table.c.key == str(key))
            .values(notes=str(note), updated_at=datetime.now(UTC))
        )


def init_db() -> None:
    """Create tables and perform the one-time legacy BibTeX import."""
    alembic_config = Config(str(API_ROOT / "alembic.ini"))
    command.upgrade(alembic_config, "head")
    with engine.connect() as connection:
        bootstrapped = connection.execute(
            select(settings_table.c.value).where(
                settings_table.c.key == "bootstrap_completed"
            )
        ).first()
    if bootstrapped:
        return
    if BIB_PATH.exists():
        import_bibtex(BIB_PATH, replace=True)
    with engine.begin() as connection:
        _migrate_legacy_notes(connection)
        _set_setting(
            connection, "bootstrap_completed", datetime.now(UTC).isoformat()
        )


def upsert_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    with engine.begin() as connection:
        return _upsert_with_connection(connection, entry)


def upsert_entries(entries: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    with engine.begin() as connection:
        return [_upsert_with_connection(connection, entry) for entry in entries]


def _require_entry_keys(connection: Connection, keys: set[str]) -> None:
    if not keys:
        return
    existing = set(
        connection.execute(
            select(entries_table.c.key).where(entries_table.c.key.in_(keys))
        ).scalars()
    )
    missing = sorted(keys - existing)
    if missing:
        raise KeyError(f"Unknown citation keys: {', '.join(missing)}")


def sync_blog_posts(posts: Iterable[Mapping[str, Any]]) -> tuple[int, int]:
    """Replace bibliography-linked public blog metadata in one transaction."""
    items = [dict(post) for post in posts]
    slugs = [str(item["slug"]) for item in items]
    if len(set(slugs)) != len(slugs):
        raise ValueError("Blog post payload contains duplicate slugs")
    keys = {
        str(key)
        for item in items
        for key in item.get("bib_keys", [])
    }
    now = datetime.now(UTC)
    relations = 0
    with engine.begin() as connection:
        _require_entry_keys(connection, keys)
        connection.execute(delete(blog_posts_table))
        for item, slug in zip(items, slugs):
            connection.execute(
                insert(blog_posts_table).values(
                    slug=slug,
                    title=str(item["title"]),
                    url=str(item["url"]),
                    source_path=str(item["source_path"]),
                    published_at=item.get("published_at"),
                    updated_at=now,
                )
            )
            for key in dict.fromkeys(str(key) for key in item["bib_keys"]):
                connection.execute(
                    insert(entry_blog_posts_table).values(
                        entry_key=key,
                        blog_slug=slug,
                        relation_type="cited-by",
                        notes="",
                    )
                )
                relations += 1
    return len(items), relations


def import_bibtex(bib_path: Path = BIB_PATH, *, replace: bool = False) -> int:
    """Explicitly import BibTeX into the DB; normal startup never resyncs it."""
    parsed_entries = _parse_bibtex(bib_path.read_text(encoding="utf-8"))
    keys = [str(entry.get("ID", "")) for entry in parsed_entries]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise ValueError(f"Duplicate citation keys: {', '.join(duplicates)}")
    with engine.begin() as connection:
        if replace:
            connection.execute(delete(entries_table))
        for index, entry in enumerate(parsed_entries):
            _upsert_with_connection(
                connection, entry, sort_order=index if replace else None
            )
    return len(parsed_entries)


def export_bibtex(
    keys: Sequence[str] | None = None,
    *,
    output_path: Path | None = None,
) -> str:
    """Render a full or selected BibTeX export from the canonical DB."""
    with engine.connect() as connection:
        if keys is None:
            rows = connection.execute(
                select(entries_table).order_by(entries_table.c.sort_order)
            ).mappings().all()
        else:
            rows = []
            missing = []
            for key in keys:
                row = connection.execute(
                    select(entries_table).where(entries_table.c.key == key)
                ).mappings().first()
                if row is None:
                    missing.append(key)
                else:
                    rows.append(row)
            if missing:
                raise KeyError(f"Unknown citation keys: {', '.join(missing)}")
    rendered = "\n\n".join(
        _entry_to_bibtex(row["key"], row["entry_type"], row["fields"])
        for row in rows
    )
    if rendered:
        rendered += "\n"
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_name(f".{output_path.name}.tmp")
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(output_path)
    return rendered


def get_entries(page: int = 1, per_page: int = 50) -> tuple[list[dict], int]:
    offset = (page - 1) * per_page
    with engine.connect() as connection:
        total = connection.execute(
            select(func.count()).select_from(entries_table)
        ).scalar_one()
        rows = connection.execute(
            select(entries_table)
            .order_by(entries_table.c.sort_order)
            .limit(per_page)
            .offset(offset)
        ).mappings().all()
        entries = _attach_blog_posts(
            connection, [_row_to_entry(row) for row in rows]
        )
    return entries, total


def search_entries(query: str, limit: int = 50, threshold: int = 55) -> list[dict]:
    with engine.connect() as connection:
        rows = connection.execute(
            select(entries_table).order_by(entries_table.c.sort_order)
        ).mappings().all()
        entries = _attach_blog_posts(
            connection, [_row_to_entry(row) for row in rows]
        )
    query_lower = query.lower().strip()
    if not query_lower:
        return entries[:limit]
    scored_entries = []
    for entry in entries:
        fields = [
            str(entry.get(field, "")).lower()
            for field in ("key", "title", "author", "notes")
        ]
        searchable = " ".join(fields)
        if query_lower in searchable:
            scored_entries.append((entry, 100))
            continue
        scores = [
            score
            for field in fields
            if field
            for score in (
                fuzz.partial_ratio(query_lower, field),
                fuzz.ratio(query_lower, field),
                fuzz.token_set_ratio(query_lower, field),
            )
        ]
        score = max([fuzz.partial_ratio(query_lower, searchable), *scores])
        if score >= threshold:
            scored_entries.append((entry, score))
    scored_entries.sort(key=lambda item: item[1], reverse=True)
    return [entry for entry, _ in scored_entries[:limit]]


def get_entry(key: str) -> Optional[dict]:
    with engine.connect() as connection:
        row = connection.execute(
            select(entries_table).where(entries_table.c.key == key)
        ).mappings().first()
        entries = _attach_blog_posts(
            connection, [_row_to_entry(row)] if row else []
        )
    return entries[0] if entries else None


def update_notes(key: str, notes: str) -> bool:
    with engine.begin() as connection:
        result = connection.execute(
            update(entries_table)
            .where(entries_table.c.key == key)
            .values(notes=notes, updated_at=datetime.now(UTC))
        )
        return result.rowcount > 0


def get_stats() -> dict:
    with engine.connect() as connection:
        rows = connection.execute(
            select(entries_table.c.key, entries_table.c.entry_type, entries_table.c.notes)
        ).mappings().all()
    types: dict[str, int] = {}
    for row in rows:
        types[row["entry_type"]] = types.get(row["entry_type"], 0) + 1
    return {
        "total_entries": len(rows),
        "entries_with_notes": sum(bool(row["notes"]) for row in rows),
        "entry_types": types,
        "duplicate_keys": {},
        "duplicate_count": 0,
    }
