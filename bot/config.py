"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class BotConfig:
    """All runtime config, loaded from env. Fails fast if required vars are missing."""

    telegram_bot_token: str
    download_dir: Path
    max_file_size_mb: int = 50
    max_video_height: int = 720
    allowed_user_ids: frozenset[int] = field(default_factory=frozenset)
    cookies_file: Path | None = None

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


def _try_load_dotenv() -> None:
    """Load a local .env file if python-dotenv is installed. Silent no-op otherwise."""
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return
    for candidate in (Path("bot/.env"), Path(".env")):
        if candidate.exists():
            load_dotenv(candidate, override=False)
            return


def _parse_user_ids(raw: str | None) -> frozenset[int]:
    if not raw:
        return frozenset()
    ids: set[int] = set()
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            ids.add(int(piece))
        except ValueError as exc:
            raise ConfigError(f"ALLOWED_USER_IDS contains non-integer value: {piece!r}") from exc
    return frozenset(ids)


def _parse_int(name: str, raw: str | None, default: int) -> int:
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def load_config() -> BotConfig:
    """Read env (and optional .env via python-dotenv if present)."""
    _try_load_dotenv()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise ConfigError(
            "TELEGRAM_BOT_TOKEN is not set. Get one from @BotFather and export it "
            "as an environment variable (or set it in bot/.env)."
        )

    download_dir = Path(os.environ.get("DOWNLOAD_DIR", "bot/downloads")).expanduser().resolve()
    download_dir.mkdir(parents=True, exist_ok=True)

    cookies_file = _resolve_cookies_file(os.environ.get("COOKIES_FILE"))

    return BotConfig(
        telegram_bot_token=token,
        download_dir=download_dir,
        max_file_size_mb=_parse_int("MAX_FILE_SIZE_MB", os.environ.get("MAX_FILE_SIZE_MB"), 50),
        max_video_height=_parse_int("MAX_VIDEO_HEIGHT", os.environ.get("MAX_VIDEO_HEIGHT"), 720),
        allowed_user_ids=_parse_user_ids(os.environ.get("ALLOWED_USER_IDS")),
        cookies_file=cookies_file,
    )


def _resolve_cookies_file(raw: str | None) -> Path | None:
    """Validate the optional COOKIES_FILE env var and return an absolute path."""
    if not raw or not raw.strip():
        return None
    path = Path(raw.strip()).expanduser().resolve()
    if not path.is_file():
        raise ConfigError(
            f"COOKIES_FILE is set to {raw!r} but no file exists at {path}. "
            "Export cookies with the 'Get cookies.txt LOCALLY' extension or "
            "`yt-dlp --cookies-from-browser <browser> --cookies cookies.txt`."
        )
    return path
