"""Telegram update handlers."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from .config import BotConfig
from .downloader import DownloadError, DownloadResult, download_media
from .utils import extract_first_url, human_size, temp_workspace

log = logging.getLogger(__name__)

WELCOME = (
    "Hi! Send me a link from YouTube, Instagram, TikTok, Twitter/X, Reddit, "
    "Facebook, or another supported site and I'll download the media for you.\n\n"
    "Use /audio <url> to get audio only as an mp3.\n"
    "Use /help for more details."
)

HELP_TEXT = (
    "How to use this bot:\n\n"
    "• Send any video/photo URL — I'll reply with the media.\n"
    "• /audio <url> — download audio only (mp3).\n"
    "• /start — welcome message.\n"
    "• /help — this message.\n\n"
    "Notes:\n"
    "• Telegram limits bot uploads to 50 MB, so I cap downloads at 720p.\n"
    "• If a video is too big after trimming quality, I'll let you know.\n"
    "• Supported sites: anything yt-dlp supports (~1000 sites)."
)


def _config(ctx: ContextTypes.DEFAULT_TYPE) -> BotConfig:
    cfg = ctx.application.bot_data.get("config")
    if not isinstance(cfg, BotConfig):
        raise RuntimeError("BotConfig was not registered in application bot_data")
    return cfg


def _is_authorized(user_id: int | None, cfg: BotConfig) -> bool:
    if not cfg.allowed_user_ids:
        return True
    return user_id is not None and user_id in cfg.allowed_user_ids


async def _reject_if_unauthorized(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    cfg = _config(ctx)
    user = update.effective_user
    if _is_authorized(user.id if user else None, cfg):
        return False
    if update.effective_chat:
        await ctx.bot.send_message(
            update.effective_chat.id,
            "Sorry, this bot is restricted. Ask the operator to allow your Telegram user ID.",
        )
    return True


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message."""
    if await _reject_if_unauthorized(update, ctx):
        return
    if update.effective_chat:
        await ctx.bot.send_message(update.effective_chat.id, WELCOME)


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Long-form usage help."""
    if await _reject_if_unauthorized(update, ctx):
        return
    if update.effective_chat:
        await ctx.bot.send_message(update.effective_chat.id, HELP_TEXT)


async def cmd_audio(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/audio <url> — download audio only."""
    if await _reject_if_unauthorized(update, ctx):
        return
    chat = update.effective_chat
    if chat is None:
        return

    args = ctx.args or []
    url = extract_first_url(" ".join(args)) or extract_first_url(
        update.effective_message.text if update.effective_message else None
    )
    if not url:
        await ctx.bot.send_message(chat.id, "Usage: /audio <url>")
        return

    await _download_and_send(update, ctx, url=url, audio_only=True)


async def on_url_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Triggered for any non-command text message."""
    if await _reject_if_unauthorized(update, ctx):
        return
    chat = update.effective_chat
    msg = update.effective_message
    if chat is None or msg is None:
        return

    url = extract_first_url(msg.text)
    if not url:
        await ctx.bot.send_message(
            chat.id,
            "Send me a link (http/https) and I'll try to download it.",
        )
        return

    await _download_and_send(update, ctx, url=url, audio_only=False)


async def _download_and_send(
    update: Update,
    ctx: ContextTypes.DEFAULT_TYPE,
    *,
    url: str,
    audio_only: bool,
) -> None:
    cfg = _config(ctx)
    chat = update.effective_chat
    assert chat is not None  # guarded by callers

    status = await ctx.bot.send_message(chat.id, "Downloading… this can take a moment.")
    try:
        await ctx.bot.send_chat_action(chat.id, ChatAction.UPLOAD_VIDEO)
        with temp_workspace(cfg.download_dir) as workdir:
            result = await download_media(
                url,
                out_dir=workdir,
                audio_only=audio_only,
                max_height=cfg.max_video_height,
                max_filesize_bytes=cfg.max_file_size_bytes,
            )
            await _send_media(ctx, chat.id, result)
        await status.edit_text("Done.")
    except DownloadError as exc:
        log.warning("download failed for %s: %s", url, exc)
        await status.edit_text(f"Sorry, I couldn't download that link.\n\nReason: {exc}")
    except Exception as exc:  # noqa: BLE001 - keep the bot alive on unknown failures
        log.exception("unexpected error handling %s", url)
        await status.edit_text(f"Unexpected error: {exc}")


async def _send_media(
    ctx: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    result: DownloadResult,
) -> None:
    """Pick send_photo/send_video/send_audio based on result.kind."""
    path = result.file_path
    size = path.stat().st_size
    caption = f"{result.title}\n{result.source_url}\n({human_size(size)})"

    with path.open("rb") as fh:
        if result.kind == "photo":
            await ctx.bot.send_photo(chat_id, photo=fh, caption=caption)
            return
        if result.kind == "video":
            await ctx.bot.send_video(
                chat_id,
                video=fh,
                caption=caption,
                supports_streaming=True,
                filename=path.name,
            )
            return
        if result.kind == "audio":
            await ctx.bot.send_audio(
                chat_id,
                audio=fh,
                caption=caption,
                title=result.title,
                filename=path.name,
            )
            return
        await ctx.bot.send_document(chat_id, document=fh, caption=caption, filename=path.name)


# Re-export _is_authorized so tests / callers can target it directly.
def is_authorized(user_id: int | None, cfg: BotConfig) -> bool:
    return _is_authorized(user_id, cfg)


__all__ = [
    "cmd_start",
    "cmd_help",
    "cmd_audio",
    "on_url_message",
    "is_authorized",
]
