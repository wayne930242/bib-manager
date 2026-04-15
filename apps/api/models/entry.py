from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EntryBase(BaseModel):
    key: str
    entry_type: str
    title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[str] = None
    journal: Optional[str] = None
    publisher: Optional[str] = None
    content: str


class Entry(EntryBase):
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EntryList(BaseModel):
    entries: list[Entry]
    total: int
    page: int
    per_page: int


class NoteUpdate(BaseModel):
    notes: str


class CiteFormat(BaseModel):
    typst: str  # @key
    bibtex: str  # full entry
    apa: Optional[str] = None


class Stats(BaseModel):
    total_entries: int
    entries_with_notes: int
    entry_types: dict[str, int]
    duplicate_keys: dict[str, int] = {}
    duplicate_count: int = 0
