import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from models.source_asset import (
    AdminCredential,
    AdminSession,
    SourceAsset,
    SourceAssetAccess,
    SourceAssetList,
    SourceAssetUpload,
    SourceAssetUploadRequest,
)
from services import admin_session
from services import database as db
from services.source_asset_storage import (
    PRESIGNED_URL_TTL_SECONDS,
    SourceAssetStorage,
    SourceAssetStorageConfigurationError,
    get_source_asset_storage,
)

router = APIRouter(prefix="/admin", tags=["private source assets"])


def require_admin_session(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not admin_session.verify_session(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid private asset session required",
        )


@router.post("/session", response_model=AdminSession)
def create_admin_session(payload: AdminCredential):
    try:
        session = admin_session.create_session(payload.credential)
    except admin_session.AdminSessionConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if session is None:
        raise HTTPException(status_code=401, detail="Invalid credential")
    token, expires_at = session
    return AdminSession(token=token, expires_at=expires_at)


@router.get(
    "/entries/{key}/assets",
    response_model=SourceAssetList,
    dependencies=[Depends(require_admin_session)],
)
def list_source_assets(key: str):
    if db.get_entry(key) is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return SourceAssetList(
        assets=[SourceAsset(**asset) for asset in db.get_source_assets(key)]
    )


def _safe_filename(filename: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip(".-")
    return safe or "source-asset"


def _storage_key(entry_key: str, asset_id: str, filename: str) -> str:
    return f"bibliography/{entry_key}/{asset_id}/{_safe_filename(filename)}"


@router.post(
    "/entries/{key}/assets/uploads",
    response_model=SourceAssetUpload,
    dependencies=[Depends(require_admin_session)],
)
def start_source_asset_upload(
    key: str,
    payload: SourceAssetUploadRequest,
    storage: Annotated[SourceAssetStorage, Depends(get_source_asset_storage)],
):
    if db.get_entry(key) is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    existing = next(
        (
            asset
            for asset in db.get_source_assets(key)
            if asset["sha256"] == payload.sha256
        ),
        None,
    )
    if existing is not None:
        if existing["status"] == "ready":
            return SourceAssetUpload(
                asset=SourceAsset(**existing),
                upload_url=None,
                upload_headers={},
                deduplicated=True,
            )
        existing = db.mark_source_asset_pending(existing["id"])
        upload_url, upload_headers = storage.presign_upload(
            storage_key=existing["storage_key"],
            media_type=existing["media_type"],
            byte_size=existing["byte_size"],
            sha256=existing["sha256"],
        )
        return SourceAssetUpload(
            asset=SourceAsset(**existing),
            upload_url=upload_url,
            upload_headers=upload_headers,
            deduplicated=True,
        )
    asset_id = str(uuid.uuid4())
    asset = db.create_source_asset(
        asset_id=asset_id,
        entry_key=key,
        kind=payload.kind,
        filename=payload.filename,
        media_type=payload.media_type,
        byte_size=payload.byte_size,
        sha256=payload.sha256,
        storage_key=_storage_key(key, asset_id, payload.filename),
        source_url=payload.source_url,
    )
    try:
        upload_url, upload_headers = storage.presign_upload(
            storage_key=asset["storage_key"],
            media_type=asset["media_type"],
            byte_size=asset["byte_size"],
            sha256=asset["sha256"],
        )
    except SourceAssetStorageConfigurationError as error:
        db.mark_source_asset_failed(asset["id"])
        raise HTTPException(status_code=503, detail=str(error)) from error
    return SourceAssetUpload(
        asset=SourceAsset(**asset),
        upload_url=upload_url,
        upload_headers=upload_headers,
        deduplicated=False,
    )


@router.post(
    "/assets/{asset_id}/complete",
    response_model=SourceAsset,
    dependencies=[Depends(require_admin_session)],
)
def complete_source_asset_upload(
    asset_id: str,
    storage: Annotated[SourceAssetStorage, Depends(get_source_asset_storage)],
):
    asset = db.get_source_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Source asset not found")
    if asset["status"] == "ready":
        return SourceAsset(**asset)
    if not storage.verify_object(
        storage_key=asset["storage_key"],
        byte_size=asset["byte_size"],
        sha256=asset["sha256"],
    ):
        db.mark_source_asset_failed(asset_id)
        raise HTTPException(
            status_code=409,
            detail="Stored object does not match expected size and SHA-256 metadata",
        )
    return SourceAsset(**db.mark_source_asset_ready(asset_id))


def _access_response(
    asset: dict,
    disposition: Literal["inline", "attachment"],
    storage: SourceAssetStorage,
) -> SourceAssetAccess:
    if asset["status"] != "ready":
        raise HTTPException(status_code=409, detail="Source asset is not ready")
    url = storage.presign_get(
        storage_key=asset["storage_key"],
        filename=asset["filename"],
        disposition=disposition,
    )
    return SourceAssetAccess(
        url=url,
        expires_at=datetime.now(UTC) + timedelta(seconds=PRESIGNED_URL_TTL_SECONDS),
    )


@router.get(
    "/assets/{asset_id}/access",
    response_model=SourceAssetAccess,
    dependencies=[Depends(require_admin_session)],
)
def access_source_asset(
    asset_id: str,
    storage: Annotated[SourceAssetStorage, Depends(get_source_asset_storage)],
    disposition: Literal["inline", "attachment"] = "inline",
):
    asset = db.get_source_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Source asset not found")
    return _access_response(asset, disposition, storage)


@router.get(
    "/entries/{key}/preferred-pdf/access",
    response_model=SourceAssetAccess,
    dependencies=[Depends(require_admin_session)],
)
def access_preferred_pdf(
    key: str,
    storage: Annotated[SourceAssetStorage, Depends(get_source_asset_storage)],
    disposition: Literal["inline", "attachment"] = "inline",
):
    asset = db.get_preferred_pdf(key)
    if asset is None:
        raise HTTPException(status_code=404, detail="Ready PDF not found")
    return _access_response(asset, disposition, storage)
