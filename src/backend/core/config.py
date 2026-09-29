"""Configuration settings for the backend application."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Google Gemini API
    google_api_key: str
    gemini_model: str = "gemini-2.5-flash-lite"

    # LINE Bot
    line_channel_access_token: Optional[str] = None
    line_channel_secret: Optional[str] = None

    # Application
    app_name: str = "GunGong (กันโกง)"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # VirusTotal API
    virustotal_api_key: Optional[str] = None

    # Database (Google Cloud Firestore)
    google_application_credentials: Optional[str] = None
    firestore_project_id: Optional[str] = None


# Singleton instance
settings = Settings()

#เพิ่มใหม่
def get_settings() -> Settings:
    """Get the singleton settings instance."""
    return settings
