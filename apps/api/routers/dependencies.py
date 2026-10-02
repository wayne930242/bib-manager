"""Request dependencies shared by routers."""

from typing import Annotated

from fastapi import Header, HTTPException, status

from services import admin_session


def require_admin_session(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Accept only a bearer token minted by POST /api/admin/session."""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not admin_session.verify_session(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid admin session required",
        )
