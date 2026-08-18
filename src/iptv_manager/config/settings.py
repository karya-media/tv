"""Application configuration.

Centralized, environment-driven settings using pydantic-settings.
All paths, timeouts, concurrency limits, and GitHub publishing targets
are defined here so no module hardcodes a magic number or path.

Usage:
    from iptv_manager.config.settings import get_settings
    settings = get_settings()
    print(settings.data_dir / "master" / "master.m3u")
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class PublishTarget(StrEnum):
    """Where the master playlist gets published to.

    RAW_ONLY   -> only raw.githubusercontent.com
    PAGES_ONLY -> only GitHub Pages (docs/ folder)
    BOTH       -> both, so there's a fallback URL if one is unavailable
    """

    RAW_ONLY = "raw_only"
    PAGES_ONLY = "pages_only"
    BOTH = "both"


class Settings(BaseSettings):
    """Root settings object. Values are loaded, in order of precedence,
    from: explicit constructor args > environment variables > `.env`
    file > field defaults below.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="IPTV_",
        case_sensitive=False,
        extra="ignore",
    )

    # --- General ---
    environment: Environment = Environment.DEVELOPMENT
    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3])
    log_level: str = "INFO"

    # --- Filesystem layout (all relative to project_root unless absolute) ---
    data_dir: Path = Path("data")
    categories_dir_name: str = "categories"
    master_dir_name: str = "master"
    epg_dir_name: str = "epg"
    reports_dir: Path = Path("reports")
    docs_dir: Path = Path("docs")  # GitHub Pages source

    master_playlist_filename: str = "master.m3u"

    # --- Playlist parsing/repair ---
    default_encoding: str = "utf-8"
    strip_bom: bool = True

    # --- Validation / networking ---
    validation_timeout_seconds: float = 10.0
    validation_max_concurrency: int = 50
    validation_retries: int = 1
    user_agent: str = "IPTV-Playlist-Manager/0.1"

    # --- FFprobe ---
    ffprobe_binary: str = "ffprobe"
    ffprobe_timeout_seconds: float = 15.0

    # --- GitHub publishing ---
    github_repository: str | None = None  # e.g. "username/iptv-repo"
    github_branch: str = "main"
    publish_target: PublishTarget = PublishTarget.BOTH

    # --- Persistence (Phase 5: pipeline run history) ---
    database_url: str | None = None  # if unset, derived from data_dir (SQLite)

    # --- REST API & dashboard (Phase 5) ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str | None = Field(default=None, repr=False)  # required to POST /api/pipeline/run
    dashboard_username: str | None = None  # if unset (with password), dashboard is open
    dashboard_password: str | None = Field(default=None, repr=False)

    # --- Background scheduler (Phase 5) ---
    # Off by default: GitHub Actions is the primary scheduling mechanism
    # (see .github/workflows/pipeline.yml). Enable this only for
    # self-hosted deployments that run `iptv-manager serve` standalone.
    scheduler_enabled: bool = False
    scheduler_interval_minutes: int = 360

    @field_validator("data_dir", "reports_dir", "docs_dir", mode="after")
    @classmethod
    def _no_absolute_escape(cls, value: Path) -> Path:
        # Defensive: relative paths only, so a bad .env can't point
        # writes outside the project (e.g. "../../etc").
        if value.is_absolute():
            return value
        if ".." in value.parts:
            raise ValueError(f"path must not contain '..': {value}")
        return value

    # --- Derived paths (computed, not stored) ---
    @property
    def categories_path(self) -> Path:
        return self.project_root / self.data_dir / self.categories_dir_name

    @property
    def master_path(self) -> Path:
        return self.project_root / self.data_dir / self.master_dir_name

    @property
    def epg_path(self) -> Path:
        return self.project_root / self.data_dir / self.epg_dir_name

    @property
    def master_playlist_path(self) -> Path:
        return self.master_path / self.master_playlist_filename

    @property
    def docs_master_playlist_path(self) -> Path:
        """Where the master playlist is copied for GitHub Pages."""
        return self.project_root / self.docs_dir / self.master_playlist_filename

    @property
    def resolved_database_url(self) -> str:
        """The database_url to actually connect with: the explicit
        override if set, otherwise a SQLite file under data_dir."""
        if self.database_url:
            return self.database_url
        db_path = self.project_root / self.data_dir / "iptv.db"
        return f"sqlite:///{db_path}"

    @property
    def raw_github_url(self) -> str | None:
        if not self.github_repository:
            return None
        return (
            f"https://raw.githubusercontent.com/{self.github_repository}/"
            f"{self.github_branch}/{self.data_dir}/{self.master_dir_name}/"
            f"{self.master_playlist_filename}"
        )

    @property
    def github_pages_url(self) -> str | None:
        if not self.github_repository:
            return None
        owner, _, repo = self.github_repository.partition("/")
        if not owner or not repo:
            return None
        return f"https://{owner}.github.io/{repo}/{self.master_playlist_filename}"

    def ensure_directories(self) -> None:
        """Create the data/report/docs directories if they don't exist yet.
        Safe to call multiple times (idempotent)."""
        for path in (
            self.categories_path,
            self.master_path,
            self.epg_path,
            self.project_root / self.reports_dir,
            self.project_root / self.docs_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance. Use this everywhere instead of
    instantiating Settings() directly, so the whole app shares one
    config object (and tests can override via dependency injection)."""
    return Settings()
