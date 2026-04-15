"""
BibTeX parsing and search service.
Reads directly from bibliography.bib without database.
"""

from pathlib import Path
from typing import Optional
import toon
import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from rapidfuzz import fuzz, process

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
BIB_PATH = PROJECT_ROOT / "references" / "bibliography.bib"
NOTES_PATH = PROJECT_ROOT / "bib-manager" / "data" / "notes.toon"

# In-memory cache
_entries_cache: list[dict] = []
_notes_cache: dict[str, str] = {}


def _load_notes() -> dict[str, str]:
    """Load notes from TOON file."""
    global _notes_cache
    if NOTES_PATH.exists():
        with open(NOTES_PATH, encoding="utf-8") as f:
            content = f.read().strip()
            if content:
                _notes_cache = toon.decode(content)
            else:
                _notes_cache = {}
    return _notes_cache


def _save_notes():
    """Save notes to TOON file."""
    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTES_PATH, "w", encoding="utf-8") as f:
        f.write(toon.encode(_notes_cache))


def parse_bibtex(bib_path: Path = BIB_PATH) -> list[dict]:
    """Parse BibTeX file and return entries."""
    global _entries_cache

    if not bib_path.exists():
        return []

    with open(bib_path, encoding="utf-8") as f:
        parser = BibTexParser(common_strings=True)
        parser.customization = convert_to_unicode
        bib_db = bibtexparser.load(f, parser=parser)

    _load_notes()

    entries = []
    for entry in bib_db.entries:
        # Reconstruct BibTeX content
        content_lines = [f"@{entry.get('ENTRYTYPE', 'misc')}{{{entry.get('ID', '')},"]
        for key, value in entry.items():
            if key not in ('ENTRYTYPE', 'ID'):
                content_lines.append(f"  {key} = {{{value}}},")
        content_lines.append("}")
        content = "\n".join(content_lines)

        key = entry.get("ID", "")
        entries.append({
            "key": key,
            "entry_type": entry.get("ENTRYTYPE", "misc"),
            "title": entry.get("title", ""),
            "author": entry.get("author", ""),
            "year": entry.get("year", ""),
            "journal": entry.get("journal", ""),
            "publisher": entry.get("publisher", ""),
            "content": content,
            "notes": _notes_cache.get(key, ""),
        })

    _entries_cache = entries
    return entries


def get_entries(page: int = 1, per_page: int = 50) -> tuple[list[dict], int]:
    """Get paginated entries."""
    if not _entries_cache:
        parse_bibtex()

    offset = (page - 1) * per_page
    return _entries_cache[offset:offset + per_page], len(_entries_cache)


def search_entries(query: str, limit: int = 50, threshold: int = 55) -> list[dict]:
    """Fuzzy search in entries using rapidfuzz.

    Args:
        query: Search query
        limit: Maximum number of results
        threshold: Minimum fuzzy match score (0-100)
    """
    if not _entries_cache:
        parse_bibtex()

    query_lower = query.lower().strip()
    if not query_lower:
        return _entries_cache[:limit]

    scored_entries = []
    for entry in _entries_cache:
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
    """Get single entry by key."""
    if not _entries_cache:
        parse_bibtex()

    for entry in _entries_cache:
        if entry["key"] == key:
            return entry
    return None


def update_notes(key: str, notes: str) -> bool:
    """Update notes for an entry."""
    _load_notes()
    _notes_cache[key] = notes
    _save_notes()

    # Update cache
    for entry in _entries_cache:
        if entry["key"] == key:
            entry["notes"] = notes
            return True
    return False


def get_stats() -> dict:
    """Get statistics including duplicate detection."""
    if not _entries_cache:
        parse_bibtex()

    types: dict[str, int] = {}
    with_notes = 0
    key_counts: dict[str, int] = {}

    for entry in _entries_cache:
        t = entry.get("entry_type", "misc")
        types[t] = types.get(t, 0) + 1
        if entry.get("notes"):
            with_notes += 1
        # Count duplicate keys
        key = entry.get("key", "")
        key_counts[key] = key_counts.get(key, 0) + 1

    # Find duplicates (keys appearing more than once)
    duplicates = {k: v for k, v in key_counts.items() if v > 1}

    return {
        "total_entries": len(_entries_cache),
        "entries_with_notes": with_notes,
        "entry_types": types,
        "duplicate_keys": duplicates,
        "duplicate_count": len(duplicates),
    }


def reload():
    """Force reload from bib file."""
    global _entries_cache, _notes_cache
    _entries_cache = []
    _notes_cache = {}
    parse_bibtex()


# Initialize on import
def init_db():
    """Initialize by loading entries."""
    parse_bibtex()


def sync_from_bibtex(bib_path: Path = BIB_PATH) -> int:
    """Reload entries from BibTeX file."""
    reload()
    return len(_entries_cache)
