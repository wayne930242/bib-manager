import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

ACADEMIC_FIELD_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _validate_academic_fields(value: list[str]) -> list[str]:
    normalized = list(dict.fromkeys(field.strip() for field in value))
    if not normalized:
        raise ValueError("At least one academic field is required")
    invalid = [
        field for field in normalized if not ACADEMIC_FIELD_PATTERN.fullmatch(field)
    ]
    if invalid:
        raise ValueError("Academic fields must be lowercase kebab-case slugs")
    return normalized


class RelatedBlogPost(BaseModel):
    slug: str
    title: str
    url: str
    published_at: Optional[datetime] = None
    relation_type: str


class EntryBase(BaseModel):
    key: str
    entry_type: str
    academic_fields: list[str] = Field(min_length=1)
    title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[str] = None
    journal: Optional[str] = None
    publisher: Optional[str] = None
    fields: dict[str, str] = Field(default_factory=dict)
    content: str

    _normalize_academic_fields = field_validator("academic_fields")(
        _validate_academic_fields
    )


class Entry(EntryBase):
    notes: Optional[str] = None
    has_pdf: bool = False
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
    academic_fields: list[str] = Field(min_length=1)
    fields: dict[str, str] = Field(default_factory=dict)
    title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[str] = None
    journal: Optional[str] = None
    publisher: Optional[str] = None
    notes: Optional[str] = None

    _normalize_academic_fields = field_validator("academic_fields")(
        _validate_academic_fields
    )


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
