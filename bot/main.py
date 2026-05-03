"""Entry point: build the PTB Application and start polling."""

from __future__ import annotations

import logging
import sys

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from .config import BotConfig, ConfigError, load_config
from .handlers import cmd_audio, cmd_help, cmd_start, on_url_message


def build_app(cfg: BotConfig) -> Application:
    """Create the PTB Application with all handlers registered."""
    app = Application.builder().token(cfg.telegram_bot_token).build()
    app.bot_data["config"] = cfg

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("audio", cmd_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_url_message))
    return app


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Quiet noisy libraries.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext.Application").setLevel(logging.INFO)


def main() -> None:
    """Entrypoint: load config, build the app, run polling."""
    _configure_logging()
    log = logging.getLogger(__name__)
    try:
        cfg = load_config()
    except ConfigError as exc:
        log.error("configuration error: %s", exc)
        sys.exit(2)

    log.info(
        "starting bot (download_dir=%s, max_file_size=%s MB, max_height=%sp, "
        "allowed_users=%s, cookies=%s)",
        cfg.download_dir,
        cfg.max_file_size_mb,
        cfg.max_video_height,
        "open" if not cfg.allowed_user_ids else len(cfg.allowed_user_ids),
        cfg.cookies_file or "none",
    )

    app = build_app(cfg)
    app.run_polling(allowed_updates=None)
