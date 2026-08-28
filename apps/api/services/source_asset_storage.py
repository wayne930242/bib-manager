"""Private source-asset storage behind an R2-compatible interface."""

import os
from functools import lru_cache
from typing import Protocol
from urllib.parse import quote

PRESIGNED_URL_TTL_SECONDS = 300


class SourceAssetStorageConfigurationError(RuntimeError):
    pass


class SourceAssetStorage(Protocol):
    def presign_upload(
        self,
        *,
        storage_key: str,
        media_type: str,
        byte_size: int,
        sha256: str,
    ) -> tuple[str, dict[str, str]]: ...

    def verify_object(
        self, *, storage_key: str, byte_size: int, sha256: str
    ) -> bool: ...

    def presign_get(
        self,
        *,
        storage_key: str,
        filename: str,
        disposition: str,
    ) -> str: ...


class R2SourceAssetStorage:
    def __init__(self) -> None:
        endpoint_url = os.environ.get("BIB_R2_ENDPOINT_URL", "")
        access_key = os.environ.get("BIB_R2_ACCESS_KEY_ID", "")
        secret_key = os.environ.get("BIB_R2_SECRET_ACCESS_KEY", "")
        bucket = os.environ.get("BIB_R2_BUCKET", "")
        if not all((endpoint_url, access_key, secret_key, bucket)):
            raise SourceAssetStorageConfigurationError(
                "Private R2 source-asset storage is not configured"
            )
        try:
            import boto3
        except ImportError as error:
            raise SourceAssetStorageConfigurationError(
                "boto3 is required for private R2 storage"
            ) from error
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )

    def presign_upload(
        self,
        *,
        storage_key: str,
        media_type: str,
        byte_size: int,
        sha256: str,
    ) -> tuple[str, dict[str, str]]:
        metadata = {"sha256": sha256, "byte-size": str(byte_size)}
        url = self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": storage_key,
                "ContentType": media_type,
                "Metadata": metadata,
            },
            ExpiresIn=PRESIGNED_URL_TTL_SECONDS,
        )
        return (
            url,
            {
                "Content-Type": media_type,
                "x-amz-meta-sha256": sha256,
                "x-amz-meta-byte-size": str(byte_size),
            },
        )

    def verify_object(self, *, storage_key: str, byte_size: int, sha256: str) -> bool:
        try:
            response = self.client.head_object(
                Bucket=self.bucket,
                Key=storage_key,
            )
        except self.client.exceptions.ClientError:
            return False
        metadata = response.get("Metadata", {})
        return (
            int(response.get("ContentLength", -1)) == byte_size
            and metadata.get("sha256") == sha256
            and metadata.get("byte-size") == str(byte_size)
        )

    def presign_get(
        self,
        *,
        storage_key: str,
        filename: str,
        disposition: str,
    ) -> str:
        safe_filename = filename.replace("\r", "").replace("\n", "")
        content_disposition = f"{disposition}; filename*=UTF-8''{quote(safe_filename)}"
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": storage_key,
                "ResponseContentDisposition": content_disposition,
            },
            ExpiresIn=PRESIGNED_URL_TTL_SECONDS,
        )


@lru_cache(maxsize=1)
def get_source_asset_storage() -> SourceAssetStorage:
    return R2SourceAssetStorage()
