"""Application configuration (environment-driven, no secrets in code)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_data_dir() -> Path:
    raw = os.getenv("SAFIA_DATA_DIR")
    if raw:
        p = Path(raw).expanduser()
        return p.resolve() if p.is_absolute() else (Path.cwd() / p).resolve()
    return (Path(__file__).resolve().parents[1] / "data").resolve()


def _resolve_app_base_url() -> str:
    raw = os.getenv("SAFIA_APP_URL", "http://localhost:8501").strip()
    return raw.rstrip("/")


def _resolve_database_url() -> str | None:
    for name in ("SAFIA_DATABASE_URL", "DATABASE_URL"):
        raw = os.getenv(name, "").strip()
        if raw:
            return raw
    try:
        import streamlit as st

        sec = st.secrets["database"]
        raw = str(sec.get("url", "")).strip()
        return raw or None
    except (FileNotFoundError, KeyError, TypeError, AttributeError):
        return None


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings loaded each run."""

    debug: bool
    data_dir: Path
    app_base_url: str
    database_url: str | None


def load_settings() -> Settings:
    return Settings(
        debug=_env_bool("SAFIA_DEBUG", default=False),
        data_dir=_resolve_data_dir(),
        app_base_url=_resolve_app_base_url(),
        database_url=_resolve_database_url(),
    )
