"""
BibTeX-backed storage service.

bibliography.bib remains the single source of truth for entry data (it is
git-versioned and edited by other tooling — Typst, Zotero conversion,
fix-bib). SQLite (bib.db) is a derived, gitignored index over it: it exists
so reads (list/search/get/stats) don't have to reparse the .bib file with
bibtexparser on every request, and so the index survives process restarts.
Notes are user-authored data with no .bib equivalent, so they stay in the
git-tracked notes.toon side file, unchanged from before.
"""

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Optional
import toon
import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from rapidfuzz import fuzz

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
LITERATURE_ROOT = PROJECT_ROOT.parent / "literature"
BIB_PATH = LITERATURE_ROOT / "references" / "bibliography.bib"
NOTES_PATH = PROJECT_ROOT / "bib-manager" / "data" / "notes.toon"
DB_PATH = PROJECT_ROOT / "bib-manager" / "data" / "bib.db"

# FastAPI runs sync endpoints in a thread pool; update_notes()'s
# load-mutate-save cycle over notes.toon must be serialized or two
# concurrent PATCH /notes calls can race and one write silently wins
# over the other.
_notes_lock = threading.Lock()

_notes_cache: dict[str, str] = {}


def _load_notes() -> dict[str, str]:
    """Load notes from TOON file."""
    global _notes_cache
    if NOTES_PATH.exists():
        with open(NOTES_PATH, encoding="utf-8") as f:
            content = f.read().strip()
            _notes_cache = toon.decode(content) if content else {}
    return _notes_cache


def _save_notes() -> None:
    """Save notes to TOON file."""
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTES_PATH, "w", encoding="utf-8") as f:
        f.write(toon.encode(_notes_cache))


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _row_to_entry(row: sqlite3.Row) -> dict:
    return {
        "key": row["key"],
        "entry_type": row["entry_type"],
        "title": row["title"],
        "author": row["author"],
        "year": row["year"],
        "journal": row["journal"],
        "publisher": row["publisher"],
        "content": row["content"],
        "notes": _notes_cache.get(row["key"], ""),
    }


def init_db() -> None:
    """Create the SQLite schema (if needed) and load current data into it."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                entry_type TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                author TEXT NOT NULL DEFAULT '',
                year TEXT NOT NULL DEFAULT '',
                journal TEXT NOT NULL DEFAULT '',
                publisher TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL,
                sort_order INTEGER NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entries_key ON entries(key)")
    _load_notes()
    sync_from_bibtex()


def sync_from_bibtex(bib_path: Path = BIB_PATH) -> int:
    """Rebuild the entries table from the BibTeX file.

    This is a full delete+reinsert on every sync, not an incremental upsert
    keyed by citation key. bibliography.bib can transiently contain duplicate
    keys (that's exactly what get_stats()'s duplicate detection surfaces, and
    what fix-bib cleans up), so `key` can't be used as a uniqueness constraint
    to upsert against without silently collapsing duplicates. A full rebuild
    keeps duplicate rows intact for that detection and needs no key-matching
    logic. Notes live in notes.toon, not in this table, so a rebuild never
    touches them: an entry removed from bibliography.bib simply drops out of
    this index (rather than lingering as a "stale" row) and its note stays in
    notes.toon, reattaching automatically if the key ever reappears — nothing
    is actually lost, since bibliography.bib is itself git-versioned.
    """
    if not bib_path.exists():
        with _connect() as conn:
            conn.execute("DELETE FROM entries")
        return 0

    with open(bib_path, encoding="utf-8") as f:
        parser = BibTexParser(common_strings=True)
        parser.customization = convert_to_unicode
        bib_db = bibtexparser.load(f, parser=parser)

    rows = []
    for i, entry in enumerate(bib_db.entries):
        content_lines = [f"@{entry.get('ENTRYTYPE', 'misc')}{{{entry.get('ID', '')},"]
        for field, value in entry.items():
            if field not in ("ENTRYTYPE", "ID"):
                content_lines.append(f"  {field} = {{{value}}},")
        content_lines.append("}")
        content = "\n".join(content_lines)

        rows.append((
            entry.get("ID", ""),
            entry.get("ENTRYTYPE", "misc"),
            entry.get("title", ""),
            entry.get("author", ""),
            entry.get("year", ""),
            entry.get("journal", ""),
            entry.get("publisher", ""),
            content,
            i,
        ))

    with _connect() as conn:
        conn.execute("DELETE FROM entries")
        conn.executemany(
            """
            INSERT INTO entries
                (key, entry_type, title, author, year, journal, publisher, content, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    return len(rows)


def get_entries(page: int = 1, per_page: int = 50) -> tuple[list[dict], int]:
    """Get paginated entries, in bibliography.bib file order."""
    offset = (page - 1) * per_page
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM entries ORDER BY sort_order LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
    return [_row_to_entry(r) for r in rows], total


def search_entries(query: str, limit: int = 50, threshold: int = 55) -> list[dict]:
    """Fuzzy search entries using rapidfuzz.

    SQLite has no built-in fuzzy matching, so this loads all rows and scores
    them in Python — the same approach as the previous in-memory version,
    just sourced from SQLite instead of a module-level list.

    Args:
        query: Search query
        limit: Maximum number of results
        threshold: Minimum fuzzy match score (0-100)
    """
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM entries ORDER BY sort_order").fetchall()
    entries = [_row_to_entry(r) for r in rows]

    query_lower = query.lower().strip()
    if not query_lower:
        return entries[:limit]

    scored_entries = []
    for entry in entries:
        # Check individual fields for better fuzzy matching
        fields = [
            entry.get("key", "").lower(),
            entry.get("title", "").lower(),
            entry.get("author", "").lower(),
            entry.get("notes", "").lower(),
        ]
        searchable = " ".join(fields)

        # Exact match gets highest priority
        if query_lower in searchable:
            scored_entries.append((entry, 100))
            continue

        # Check each field separately for better typo tolerance
        max_field_score = 0
        for field in fields:
            if not field:
                continue
            # Use partial_ratio for substring matching
            partial_score = fuzz.partial_ratio(query_lower, field)
            # Use ratio for overall similarity (good for typos)
            ratio_score = fuzz.ratio(query_lower, field)
            # For short queries, token_set_ratio helps with word matching
            token_score = fuzz.token_set_ratio(query_lower, field)
            max_field_score = max(max_field_score, partial_score, ratio_score, token_score)

        # Also check against full searchable text
        full_partial = fuzz.partial_ratio(query_lower, searchable)
        score = max(max_field_score, full_partial)

        if score >= threshold:
            scored_entries.append((entry, score))

    # Sort by score descending
    scored_entries.sort(key=lambda x: x[1], reverse=True)

    return [entry for entry, _ in scored_entries[:limit]]


def get_entry(key: str) -> Optional[dict]:
    """Get single entry by key (first occurrence in file order, if duplicated)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM entries WHERE key = ? ORDER BY sort_order LIMIT 1",
            (key,),
        ).fetchone()
    return _row_to_entry(row) if row else None


def update_notes(key: str, notes: str) -> bool:
    """Update notes for an entry. Notes are stored in notes.toon, not SQLite."""
    with _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM entries WHERE key = ? LIMIT 1", (key,)
        ).fetchone()
    if not exists:
        return False

    with _notes_lock:
        _load_notes()
        _notes_cache[key] = notes
        _save_notes()
    return True


def get_stats() -> dict:
    """Get statistics including duplicate detection."""
    _load_notes()
    with _connect() as conn:
        rows = conn.execute("SELECT key, entry_type FROM entries").fetchall()

    types: dict[str, int] = {}
    with_notes = 0
    key_counts: dict[str, int] = {}

    for row in rows:
        t = row["entry_type"]
        types[t] = types.get(t, 0) + 1
        if _notes_cache.get(row["key"]):
            with_notes += 1
        key_counts[row["key"]] = key_counts.get(row["key"], 0) + 1

    # Find duplicates (keys appearing more than once)
    duplicates = {k: v for k, v in key_counts.items() if v > 1}

    return {
        "total_entries": len(rows),
        "entries_with_notes": with_notes,
        "entry_types": types,
        "duplicate_keys": duplicates,
        "duplicate_count": len(duplicates),
    }


def reload() -> None:
    """Force reload from bib file and notes into SQLite."""
    _load_notes()
    sync_from_bibtex()
