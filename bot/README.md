# Telegram media-download bot

A small Python Telegram bot that takes a URL (YouTube, Instagram, TikTok,
Twitter/X, Reddit, Facebook, ~1000 other sites) and replies with the video,
photo, or audio.

Built on:

- [python-telegram-bot](https://python-telegram-bot.org) v21 (async)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- `ffmpeg` (system dependency, used by yt-dlp to merge video+audio)

> The Telegram Bot API caps outbound files at **50 MB**, so the bot caps
> downloads at 720p / 50 MB. Going higher requires a self-hosted Bot API
> server (out of scope here).

## Setup

1. Talk to [@BotFather](https://t.me/BotFather) and create a bot. Save the
   token it gives you.
2. Install Python 3.11+ and ffmpeg.

   ```bash
   # Ubuntu/Debian
   sudo apt-get update && sudo apt-get install -y ffmpeg python3.11 python3.11-venv

   # macOS (Homebrew)
   brew install ffmpeg python@3.11
   ```

3. Install Python dependencies:

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r bot/requirements.txt
   ```

4. Copy `bot/.env.example` to `bot/.env` and fill in `TELEGRAM_BOT_TOKEN`,
   or export the variable in your shell.

## Run

```bash
python -m bot
```

That's it — the bot will start polling. Open Telegram, find your bot, send
it any URL.

### Commands

- `/start` — welcome message
- `/help` — usage instructions
- `/audio <url>` — download audio only as mp3
- _any URL_ — download as best-quality ≤720p video / photo

## Docker

```bash
docker build -t telegram-media-bot bot/
docker run --rm \
  -e TELEGRAM_BOT_TOKEN=xxx \
  -e ALLOWED_USER_IDS=12345,67890 \
  telegram-media-bot
```

## Configuration

All settings come from environment variables (see `bot/.env.example`):

| Variable             | Default          | Notes                                              |
| -------------------- | ---------------- | -------------------------------------------------- |
| `TELEGRAM_BOT_TOKEN` | _(required)_     | From @BotFather.                                   |
| `DOWNLOAD_DIR`       | `bot/downloads`  | Working directory for downloads (auto-cleaned).    |
| `MAX_FILE_SIZE_MB`   | `50`             | Telegram outbound cap; raise only with self-hosted Bot API. |
| `MAX_VIDEO_HEIGHT`   | `720`            | Target video resolution.                           |
| `ALLOWED_USER_IDS`   | _empty_          | Comma-separated whitelist; empty = open to anyone. |
| `COOKIES_FILE`       | _empty_          | Path to a Netscape `cookies.txt`. Required for YouTube / Instagram / Reddit on cloud IPs. |

## Making YouTube / Instagram work

YouTube and Instagram (and increasingly Reddit) detect requests coming from
datacenter IPs as bots and refuse to serve media unless you authenticate.
TikTok, Twitter/X, Vimeo, Dailymotion, and most other sites do **not** need
this.

The fix is to give yt-dlp your browser cookies via the `COOKIES_FILE` env
var.

### Easiest: use a browser extension

1. In Chrome or Firefox install **"Get cookies.txt LOCALLY"**
   ([Chrome](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) /
   [Firefox](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)).
2. Log in to YouTube / Instagram / etc. in that browser.
3. Open the site, click the extension icon, and export.
4. Save the file as `bot/cookies.txt` (or anywhere) and set:

   ```bash
   export COOKIES_FILE=bot/cookies.txt
   ```

5. Restart the bot.

### Alternative: yt-dlp's built-in extractor

From a machine where the right browser is installed:

```bash
yt-dlp --cookies-from-browser firefox --cookies cookies.txt https://youtube.com
```

Then upload `cookies.txt` to the host running the bot and point
`COOKIES_FILE` at it.

### Tips

- Use a **secondary Google / Instagram account** for the cookies — sessions
  authenticated from a new IP can occasionally trigger a security flag on
  the source account.
- `cookies.txt` contains login secrets. **Never** commit it. The repo's
  `.gitignore` already excludes `bot/cookies.txt`.
- Cookies eventually expire; if downloads start failing again with auth
  errors, re-export.

## Out of scope (for now)

- Inline keyboard format-picker (Best / 720p / Audio).
- Self-hosted Bot API server for >50 MB uploads.
- Webhook deployment.
- Persistent job queue.

## Legal note

Downloading from YouTube/Instagram/TikTok/etc. can violate their Terms of
Service depending on the content and your use of it. This bot is a tool;
using it for personal, permitted, or fair-use content is your
responsibility.
