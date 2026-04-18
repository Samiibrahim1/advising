from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

from app.core.config import get_settings


class StorageService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.local_root = Path(self.settings.local_storage_path).resolve()
        self.local_root.mkdir(parents=True, exist_ok=True)
        self._client = None
        if self.settings.r2_account_id and self.settings.r2_access_key_id and self.settings.r2_secret_access_key and self.settings.r2_bucket:
            import boto3
            endpoint = f"https://{self.settings.r2_account_id}.r2.cloudflarestorage.com"
            self._client = boto3.client(
                's3',
                endpoint_url=endpoint,
                aws_access_key_id=self.settings.r2_access_key_id,
                aws_secret_access_key=self.settings.r2_secret_access_key,
                region_name='auto',
            )

    @property
    def bucket(self) -> Optional[str]:
        return self.settings.r2_bucket

    def _safe_local_path(self, key: str) -> Path:
        """Resolve a storage key to a local path, rejecting traversal attempts."""
        path = (self.local_root / key).resolve()
        if not str(path).startswith(str(self.local_root)):
            raise ValueError(f'Invalid storage key: path escapes storage root')
        return path

    def put_bytes(self, key: str, content: bytes, content_type: Optional[str] = None) -> str:
        if self._client and self.bucket:
            self._client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type or mimetypes.guess_type(key)[0] or 'application/octet-stream',
            )
            return key

        path = self._safe_local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return key

    def get_bytes(self, key: str) -> bytes:
        if self._client and self.bucket:
            try:
                response = self._client.get_object(Bucket=self.bucket, Key=key)
                return response['Body'].read()
            except self._client.exceptions.NoSuchKey:
                raise FileNotFoundError(f'Object not found in R2: {key}')
        path = self._safe_local_path(key)
        if not path.exists():
            raise FileNotFoundError(f'File not found in local storage: {key}')
        return path.read_bytes()

    def public_url(self, key: str) -> Optional[str]:
        if self.settings.r2_public_base_url:
            return urljoin(self.settings.r2_public_base_url.rstrip('/') + '/', key)
        if self._client and self.bucket:
            return None
        return str(self._safe_local_path(key))
