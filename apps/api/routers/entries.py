from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from models.entry import Entry, EntryList, NoteUpdate, CiteFormat, Stats
from services import database as db

router = APIRouter(prefix="/entries", tags=["entries"])


@router.get("", response_model=EntryList)
def list_entries(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200)
):
    """List all entries with pagination."""
    entries, total = db.get_entries(page, per_page)
    return EntryList(
        entries=[Entry(**e) for e in entries],
        total=total,
        page=page,
        per_page=per_page
    )


@router.get("/search")
def search_entries(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200)
):
    """Search entries by keyword."""
    entries = db.search_entries(q, limit)
    return {"entries": [Entry(**e) for e in entries], "query": q}


@router.get("/{key}", response_model=Entry)
def get_entry(key: str):
    """Get single entry by key."""
    entry = db.get_entry(key)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return Entry(**entry)


@router.get("/{key}/cite", response_model=CiteFormat)
def get_cite_format(key: str):
    """Get citation formats for an entry."""
    entry = db.get_entry(key)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    # Generate APA format
    author = entry.get("author", "Unknown")
    year = entry.get("year", "n.d.")
    title = entry.get("title", "Untitled")

    # Simple APA format
    apa = f"{author} ({year}). {title}."

    return CiteFormat(
        typst=f"@{key}",
        bibtex=entry["content"],
        apa=apa
    )


@router.get("/{key}/notes")
def get_notes(key: str):
    """Get notes for an entry."""
    entry = db.get_entry(key)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"key": key, "notes": entry.get("notes", "")}


@router.patch("/{key}/notes")
def update_notes(key: str, note_update: NoteUpdate):
    """Update notes for an entry."""
    if not db.update_notes(key, note_update.notes):
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"key": key, "notes": note_update.notes, "updated": True}


@router.get("/stats/summary", response_model=Stats)
def get_stats():
    """Get database statistics."""
    return Stats(**db.get_stats())
