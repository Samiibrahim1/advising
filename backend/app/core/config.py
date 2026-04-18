from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'Advising V2 API'
    app_env: str = Field(default='development', alias='APP_ENV')
    database_url: str = Field(default='sqlite:///./advising_v2.db', alias='DATABASE_URL')
    jwt_secret: str = Field(default='change-me', alias='JWT_SECRET')
    jwt_expiry_minutes: int = Field(default=480, alias='JWT_EXPIRY_MINUTES')
    cors_origins_raw: str = Field(default='http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175,http://localhost:5176,http://127.0.0.1:5176', alias='CORS_ORIGINS')
    r2_account_id: Optional[str] = Field(default=None, alias='R2_ACCOUNT_ID')
    r2_access_key_id: Optional[str] = Field(default=None, alias='R2_ACCESS_KEY_ID')
    r2_secret_access_key: Optional[str] = Field(default=None, alias='R2_SECRET_ACCESS_KEY')
    r2_bucket: Optional[str] = Field(default=None, alias='R2_BUCKET')
    r2_public_base_url: Optional[str] = Field(default=None, alias='R2_PUBLIC_BASE_URL')
    local_storage_path: str = Field(default='./local-storage', alias='LOCAL_STORAGE_PATH')
    legacy_imports_path: str = Field(default='../../', alias='LEGACY_IMPORTS_PATH')
    legacy_snapshot_export_path: str = Field(default='./legacy-snapshots', alias='LEGACY_SNAPSHOT_EXPORT_PATH')
    google_client_id: Optional[str] = Field(default=None, alias='GOOGLE_CLIENT_ID')
    google_client_secret: Optional[str] = Field(default=None, alias='GOOGLE_CLIENT_SECRET')
    google_refresh_token: Optional[str] = Field(default=None, alias='GOOGLE_REFRESH_TOKEN')
    google_folder_id: Optional[str] = Field(default=None, alias='GOOGLE_FOLDER_ID')
    brevo_api_key: Optional[str] = Field(default=None, alias='BREVO_API_KEY')
    graph_tenant_id: Optional[str] = Field(default=None, alias='GRAPH_TENANT_ID')
    graph_client_id: Optional[str] = Field(default=None, alias='GRAPH_CLIENT_ID')
    graph_client_secret: Optional[str] = Field(default=None, alias='GRAPH_CLIENT_SECRET')

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(',') if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
