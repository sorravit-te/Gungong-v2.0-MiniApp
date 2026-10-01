"""Configuration settings for the backend application."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from typing import Literal, Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Google Gemini API
    google_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash-lite"

    # LINE Bot
    line_channel_access_token: Optional[str] = None
    line_channel_secret: Optional[str] = None
    # LINE Login channel owning the existing LIFF app (not Messaging API).
    line_login_channel_id: str = "2008548759"

    # Application
    app_name: str = "GunGong (กันโกง)"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # VirusTotal API
    virustotal_api_key: Optional[str] = None
    virustotal_submit_unknown_urls: bool = False

    # Explicit opt-in: never reuse the Gemini key or enable paid services.
    url_reputation_provider: Literal["disabled", "safe_browsing", "web_risk"] = "disabled"
    url_reputation_api_key: Optional[str] = None

    # Honest automated-client identification, never browser impersonation.
    url_fetch_user_agent: str = (
        "GunGong-URLVerifierBot/1.0 "
        "(+https://github.com/sorravit-te/gungong-v2.0-MiniApp)"
    )

    # Anonymous passive SPA fallback, never CAPTCHA/anti-bot bypass. Docker
    # installs Chromium; local testing can explicitly select installed Chrome.
    # Opt in only after the deployment supports the mandatory browser sandbox
    # and isolated resource limits. Never silently disable Chromium's sandbox.
    url_render_enabled: bool = False
    url_render_browser_channel: Optional[str] = None
    # Local prototype only: numeric loopback endpoint, separate credential-free
    # container. Never use a user URL or send any provider keys to this worker.
    url_render_worker_url: Optional[str] = None
    url_render_worker_token: Optional[SecretStr] = None

    # Exact HTTPS origins; no wildcard/subdomain inheritance. Each request
    # still requires resolved public DNS and sufficient clean page evidence.
    url_trusted_origins: str = (
        "https://www.youtube.com,https://youtube.com,"
        "https://www.wikipedia.org,https://en.wikipedia.org,https://th.wikipedia.org"
    )

    # Database (Google Cloud Firestore)
    google_application_credentials: Optional[str] = None
    # Optional server-only credential transport for hosts without secret files.
    # ADC/file-based local configurations remain supported.
    google_service_account_json: Optional[SecretStr] = None
    firestore_project_id: Optional[str] = None


# Singleton instance
settings = Settings()

#เพิ่มใหม่
def get_settings() -> Settings:
    """Get the singleton settings instance."""
    return settings
