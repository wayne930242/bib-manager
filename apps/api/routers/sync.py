"""Protected publication metadata synchronization endpoints."""

import hmac
import os

from fastapi import APIRouter, Header, HTTPException, status

from models.entry import BlogPostSync
from services import database as db

router = APIRouter(prefix="/sync", tags=["sync"])


def _authorize(authorization: str | None = Header(default=None)) -> None:
    expected = os.environ.get("BIB_SYNC_TOKEN", "")
    supplied = ""
    if authorization and authorization.startswith("Bearer "):
        supplied = authorization.removeprefix("Bearer ")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Publication sync is not configured",
        )
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid sync token",
        )


@router.post("/blog-posts", dependencies=[])
def sync_blog_posts(payload: BlogPostSync, authorization: str | None = Header(None)):
    """Replace bibliography-linked posts managed by the blog repository."""
    _authorize(authorization)
    try:
        posts, relations = db.sync_blog_posts(
            post.model_dump(exclude_none=True) for post in payload.posts
        )
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"posts": posts, "relations": relations, "source": "blog"}
