from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AdminCredential(BaseModel):
    credential: str


class AdminSession(BaseModel):
    token: str
    expires_at: datetime


class SourceAsset(BaseModel):
    id: str
    entry_key: str
    kind: Literal[
        "published-pdf",
        "author-manuscript-pdf",
        "source-document",
        "extracted-text",
        "reading-notes",
        "reading-summary",
        "supplement",
    ]
    filename: str
    media_type: str
    byte_size: int
    sha256: str
    storage_key: str
    source_url: str | None = None
    status: Literal["pending", "ready", "failed"]
    created_at: datetime
    updated_at: datetime


class SourceAssetList(BaseModel):
    assets: list[SourceAsset]


class SourceAssetUploadRequest(BaseModel):
    kind: Literal[
        "published-pdf",
        "author-manuscript-pdf",
        "source-document",
        "extracted-text",
        "reading-notes",
        "reading-summary",
        "supplement",
    ]
    filename: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    byte_size: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_url: str | None = None


class SourceAssetUpload(BaseModel):
    asset: SourceAsset
    upload_url: str | None
    upload_headers: dict[str, str]
    deduplicated: bool


class SourceAssetAccess(BaseModel):
    url: str
    expires_at: datetime
