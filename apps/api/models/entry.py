from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RelatedBlogPost(BaseModel):
    slug: str
    title: str
    url: str
    published_at: Optional[datetime] = None
    relation_type: str


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
    blog_posts: list[RelatedBlogPost] = Field(default_factory=list)
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


class BlogPostUpsert(BaseModel):
    slug: str
    title: str
    url: str
    source_path: str
    published_at: Optional[datetime] = None
    bib_keys: list[str] = Field(min_length=1)


class BlogPostSync(BaseModel):
    posts: list[BlogPostUpsert]


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
