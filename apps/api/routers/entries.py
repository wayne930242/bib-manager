from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from models.entry import (
    BibExportRequest,
    CiteFormat,
    Entry,
    EntryBatchUpsert,
    EntryList,
    EntryUpsert,
    NoteUpdate,
    Stats,
)
from services import database as db

router = APIRouter(prefix="/entries", tags=["entries"])


@router.post("", response_model=Entry)
def save_entry(entry: EntryUpsert):
    """Insert or update one entry in the canonical database."""
    return Entry(**db.upsert_entry(entry.model_dump(exclude_none=True)))


@router.post("/batch")
def save_entries(batch: EntryBatchUpsert):
    """Atomically insert or update selected discovery results."""
    entries = db.upsert_entries(
        entry.model_dump(exclude_none=True) for entry in batch.entries
    )
    return {"entries": [Entry(**entry) for entry in entries], "saved": len(entries)}


@router.post("/export")
def export_entries(request: BibExportRequest):
    """Render selected entries from the DB without writing a file."""
    try:
        content = db.export_bibtex(request.keys)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"content": content, "count": content.count("\n@") + bool(content)}


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
