from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EntryBase(BaseModel):
    key: str
    entry_type: str
    title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[str] = None
    journal: Optional[str] = None
    publisher: Optional[str] = None
    fields: dict[str, str] = Field(default_factory=dict)
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


class EntryUpsert(BaseModel):
    key: str
    entry_type: str = "misc"
    fields: dict[str, str] = Field(default_factory=dict)
    title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[str] = None
    journal: Optional[str] = None
    publisher: Optional[str] = None
    notes: Optional[str] = None


class EntryBatchUpsert(BaseModel):
    entries: list[EntryUpsert]


class BibExportRequest(BaseModel):
    keys: Optional[list[str]] = None


class CiteFormat(BaseModel):
    typst: str  # @key
    bibtex: str  # full entry
    apa: Optional[str] = None


class Stats(BaseModel):
    total_entries: int
    entries_with_notes: int
    entry_types: dict[str, int]
    duplicate_keys: dict[str, int] = Field(default_factory=dict)
    duplicate_count: int = 0
