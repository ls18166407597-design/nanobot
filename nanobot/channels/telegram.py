"""Telegram channel implementation using python-telegram-bot."""

import asyncio
import json
import re
from datetime import datetime
from uuid import uuid4

from loguru import logger
from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import TelegramConfig
from nanobot.utils.helpers import get_data_path, get_sessions_path, safe_filename


def _markdown_to_telegram_html(text: str) -> str:
    """
    Convert markdown to Telegram-safe HTML.
    """
    if not text:
        return ""

    # 1. Extract and protect code blocks (preserve content from other processing)
    code_blocks: list[str] = []

    def save_code_block(m: re.Match) -> str:
        code_blocks.append(m.group(1))
        return f"\x00CB{len(code_blocks) - 1}\x00"

    text = re.sub(r"```[\w]*\n?([\s\S]*?)```", save_code_block, text)

    # 2. Extract and protect inline code
    inline_codes: list[str] = []

    def save_inline_code(m: re.Match) -> str:
        inline_codes.append(m.group(1))
        return f"\x00IC{len(inline_codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", save_inline_code, text)

    # 3. Headers # Title -> just the title text
    text = re.sub(r"^#{1,6}\s+(.+)$", r"\1", text, flags=re.MULTILINE)

    # 4. Blockquotes > text -> just the text (before HTML escaping)
    text = re.sub(r"^>\s*(.*)$", r"\1", text, flags=re.MULTILINE)

    # 5. Escape HTML special characters
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # 6. Links [text](url) - must be before bold/italic to handle nested cases
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    # 7. Bold **text** or __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)

    # 8. Italic _text_ (avoid matching inside words like some_var_name)
    text = re.sub(r"(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])", r"<i>\1</i>", text)

    # 9. Strikethrough ~~text~~
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)

    # 10. Bullet lists - item -> • item
    text = re.sub(r"^[-*]\s+", "• ", text, flags=re.MULTILINE)

    # 11. Restore inline code with HTML tags
    for i, code in enumerate(inline_codes):
        # Escape HTML in code content
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00IC{i}\x00", f"<code>{escaped}</code>")

    # 12. Restore code blocks with HTML tags
    for i, code in enumerate(code_blocks):
        # Escape HTML in code content
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00CB{i}\x00", f"<pre><code>{escaped}</code></pre>")

    return text


def _split_message(text: str, limit: int = 4000) -> list[str]:
    """
    Split a message into chunks within the 4096 character limit.
    Tries to split at double newlines, then single newlines.
    """
    if len(text) <= limit:
        return [text]

    chunks = []
    remaining = text
    while len(remaining) > limit:
        # Try splitting at double newline
        split_at = remaining.rfind("\n\n", 0, limit)
        if split_at == -1:
            # Try splitting at single newline
            split_at = remaining.rfind("\n", 0, limit)

        if split_at == -1:
            # Hard split at limit
            split_at = limit

        chunks.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks


class TelegramChannel(BaseChannel):
    """
    Telegram channel using long polling.

    Simple and reliable - no webhook/public IP needed.
    """

    name = "telegram"

    def __init__(self, config: TelegramConfig, bus: MessageBus, groq_api_key: str = ""):
        super().__init__(config, bus)
        self.config: TelegramConfig = config
        self.groq_api_key = groq_api_key
        self._app: Application | None = None
        self._chat_ids: dict[str, int] = {}  # Map sender_id to chat_id for replies
        self._active_sessions: dict[str, str] = {}  # chat_id -> session_key override

    async def start(self) -> None:
        """Start the Telegram bot with long polling."""
        logger.info("TelegramChannel.start() called")
        try:
            if not self.config.token:
                logger.error("Telegram bot token not configured")
                return

            self._running = True

            # Build the application with robust request settings
            logger.info("Setting up HTTPXRequest...")
            proxy_url = self.config.proxy
            # If no explicit proxy, trust environment (system) proxy settings
            trust_env = True if proxy_url is None else False
            
            request = HTTPXRequest(
                proxy=proxy_url, 
                connection_pool_size=50,      # Corrected parameter name
                connect_timeout=15.0, 
                read_timeout=15.0,
                write_timeout=15.0,
                httpx_kwargs={"trust_env": trust_env}
            )
            logger.info("Building Telegram Application...")
            self._app = Application.builder().token(self.config.token).request(request).build()

            # Add message handler for text, photos, voice, documents
            self._app.add_handler(
                MessageHandler(
                    (
                        filters.TEXT
                        | filters.PHOTO
                        | filters.VOICE
                        | filters.AUDIO
                        | filters.Document.ALL
                    )
                    & ~filters.COMMAND,
                    self._on_message,
                )
            )

            # Add command handlers
            self._app.add_handler(CommandHandler("start", self._on_start))
            self._app.add_handler(CommandHandler("help", self._on_help))
            self._app.add_handler(CommandHandler("status", self._on_status))
            self._app.add_handler(CommandHandler("history", self._on_history))
            self._app.add_handler(CommandHandler("new", self._on_new))
            self._app.add_handler(CommandHandler("clear", self._on_clear))
            self._app.add_handler(MessageHandler(filters.COMMAND, self._on_unknown_command))

            logger.info("Initializing Telegram application...")
            await self._app.initialize()
            logger.info("Starting Telegram application...")
            await self._app.start()

            # Get bot info
            logger.info("Fetching Telegram bot info (getMe)...")
            bot_info = await asyncio.wait_for(self._app.bot.get_me(), timeout=30.0)
            logger.info(f"Telegram bot @{bot_info.username} connected")
            await self._app.bot.set_my_commands(
                [
                    BotCommand("start", "开始使用"),
                    BotCommand("help", "查看可用命令"),
                    BotCommand("status", "查看机器人状态"),
                    BotCommand("history", "查看会话历史"),
                    BotCommand("new", "开启新会话"),
                    BotCommand("clear", "清空当前会话"),
                ]
            )

            # Start polling (this runs until stopped)
            logger.info("Starting long polling...")
            await self._app.updater.start_polling(
                allowed_updates=["message"],
                drop_pending_updates=False,
            )

            # Keep running until stopped
            while self._running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.exception(f"CRITICAL: Telegram initialization failed: {e}")
            self._running = False
        finally:
            if self._app and self._app.running:
                logger.info("Shutting down Telegram application...")
                await self._app.stop()
                await self._app.shutdown()

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        self._running = False

        if self._app:
            logger.info("Stopping Telegram bot...")
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            self._app = None

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Telegram with auto-segmentation and retry."""
        if not self._app:
            logger.warning("Telegram bot not running")
            return

        try:
            chat_id = int(msg.chat_id)
            # 1. Segment the message if it's too long
            # We use a conservative limit of 3500 to leave room for HTML tags
            segments = _split_message(msg.content, limit=3500)
            
            for i, segment in enumerate(segments):
                # Convert markdown to Telegram HTML for each segment
                html_content = _markdown_to_telegram_html(segment)
                
                # Basic retry logic for transient network issues
                for attempt in range(3):
                    try:
                        await self._app.bot.send_message(
                            chat_id=chat_id, 
                            text=html_content, 
                            parse_mode="HTML"
                        )
                        logger.info(f"[TraceID: {getattr(msg, 'trace_id', 'N/A')}] Telegram sent segment {i+1}/{len(segments)} to {chat_id}")
                        break
                    except Exception as e:
                        if attempt == 2:
                            logger.error(f"Failed to send segment after 3 attempts: {e}")
                            # Final fallback to plain text if HTML fails
                            await self._app.bot.send_message(chat_id=chat_id, text=segment[:4000])
                        else:
                            logger.warning(f"Telegram send attempt {attempt+1} failed, retrying: {e}")
                            await asyncio.sleep(1)

        except ValueError:
            logger.error(f"Invalid chat_id: {msg.chat_id}")
        except Exception as e:
            logger.error(f"Error orchestrating Telegram send: {e}")

    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not update.message or not update.effective_user:
            return

        user = update.effective_user
        await update.message.reply_text(
            f"你好 {user.first_name}，我是 nanobot。\n\n直接发消息即可，我会处理并回复。输入 /help 查看命令。"
        )

    async def _on_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        if not update.message:
            return
        await update.message.reply_text(
            "可用命令:\n"
            "/start - 开始使用\n"
            "/help - 查看命令说明\n"
            "/status - 查看机器人状态\n"
            "/history - 查看会话历史\n"
            "/new - 开启新会话\n"
            "/clear - 清空当前会话"
        )

    async def _on_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if not update.message:
            return
        data_dir = get_data_path()
        chat_id = str(update.message.chat_id)
        active_session = self._get_active_session_key(chat_id)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await update.message.reply_text(
            f"状态: 在线\n时间: {now}\n数据目录: {data_dir}\n当前会话: {active_session}"
        )

    async def _on_new(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /new command: switch to a brand new session key."""
        if not update.message:
            return
        chat_id = str(update.message.chat_id)
        new_key = self._new_session_key(chat_id)
        self._active_sessions[chat_id] = new_key
        await update.message.reply_text("已开启新会话。后续消息将使用全新上下文。")

    async def _on_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /history command: list recent sessions for current chat."""
        if not update.message:
            return
        chat_id = str(update.message.chat_id)
        base = safe_filename(f"{self.name}_{chat_id}")
        sessions_dir = get_sessions_path()
        current = self._get_active_session_key(chat_id)

        entries: list[tuple[str, str]] = []  # (key, updated_at)
        for path in sessions_dir.glob(f"{base}*.jsonl"):
            key = path.stem
            updated = ""
            try:
                with open(path, "r", encoding="utf-8") as f:
                    first = f.readline().strip()
                if first:
                    data = json.loads(first)
                    if data.get("_type") == "metadata":
                        key = data.get("key") or key
                        updated = data.get("updated_at") or ""
            except Exception:
                pass
            entries.append((str(key), str(updated)))

        if not entries:
            await update.message.reply_text("当前 chat 暂无会话历史。")
            return

        entries.sort(key=lambda x: x[1], reverse=True)
        lines = ["最近会话（最多 10 条）:"]
        for key, updated in entries[:10]:
            marker = " [当前]" if key == current else ""
            ts = updated if updated else "-"
            lines.append(f"- {key}{marker} | {ts}")
        await update.message.reply_text("\n".join(lines))

    async def _on_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /clear command: delete current session file and rotate to a new session."""
        if not update.message:
            return
        chat_id = str(update.message.chat_id)
        session_key = self._get_active_session_key(chat_id)
        safe_key = safe_filename(session_key.replace(":", "_"))
        session_path = get_sessions_path() / f"{safe_key}.jsonl"
        deleted = False
        if session_path.exists():
            session_path.unlink()
            deleted = True
        self._active_sessions[chat_id] = self._new_session_key(chat_id)
        if deleted:
            await update.message.reply_text("当前会话已清空，并已切换到新会话。")
        else:
            await update.message.reply_text("当前会话文件不存在，已切换到新会话。")

    async def _on_unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle unknown slash commands."""
        if not update.message:
            return
        await update.message.reply_text("未识别的命令。输入 /help 查看可用命令。")

    def _get_active_session_key(self, chat_id: str) -> str:
        """Get active session key for a chat."""
        return self._active_sessions.get(chat_id, f"{self.name}:{chat_id}")

    def _new_session_key(self, chat_id: str) -> str:
        """Create a new unique session key for a chat."""
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{self.name}:{chat_id}#s{ts}_{uuid4().hex[:6]}"

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages (text, photos, voice, documents)."""
        if not update.message or not update.effective_user:
            return

        message = update.message
        user = update.effective_user
        chat_id = message.chat_id

        # Use stable numeric ID, but keep username for allowlist compatibility
        sender_id = str(user.id)
        if user.username:
            sender_id = f"{sender_id}|{user.username}"

        # Store chat_id for replies
        self._chat_ids[sender_id] = chat_id

        # Build content from text and/or media
        content_parts = []
        media_paths = []

        # Text content
        if message.text:
            content_parts.append(message.text)
        if message.caption:
            content_parts.append(message.caption)

        # Handle media files
        media_file = None
        media_type = None

        if message.photo:
            media_file = message.photo[-1]  # Largest photo
            media_type = "image"
        elif message.voice:
            media_file = message.voice
            media_type = "voice"
        elif message.audio:
            media_file = message.audio
            media_type = "audio"
        elif message.document:
            media_file = message.document
            media_type = "file"

        # Download media if present
        if media_file and self._app:
            try:
                file = await self._app.bot.get_file(media_file.file_id)
                ext = self._get_extension(media_type, getattr(media_file, "mime_type", None))

                # Save to workspace/media/
                from pathlib import Path

                media_dir = get_data_path() / "media"
                media_dir.mkdir(parents=True, exist_ok=True)

                file_path = media_dir / f"{media_file.file_id[:16]}{ext}"
                await file.download_to_drive(str(file_path))

                media_paths.append(str(file_path))

                # Handle voice transcription
                if media_type == "voice" or media_type == "audio":
                    from nanobot.providers.transcription import GroqTranscriptionProvider

                    transcriber = GroqTranscriptionProvider(api_key=self.groq_api_key)
                    transcription = await transcriber.transcribe(file_path)
                    if transcription:
                        logger.info(f"Transcribed {media_type}: {transcription[:50]}...")
                        content_parts.append(f"[transcription: {transcription}]")
                    else:
                        content_parts.append(f"[{media_type}: {file_path}]")
                else:
                    content_parts.append(f"[{media_type}: {file_path}]")

                logger.debug(f"Downloaded {media_type} to {file_path}")
            except Exception as e:
                logger.error(f"Failed to download media: {e}")
                content_parts.append(f"[{media_type}: download failed]")

        content = "\n".join(content_parts) if content_parts else "[empty message]"

        logger.debug(f"Telegram message from {sender_id}: {content[:50]}...")

        # Forward to the message bus
        await self._handle_message(
            sender_id=sender_id,
            chat_id=str(chat_id),
            content=content,
            media=media_paths,
            metadata={
                "message_id": message.message_id,
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "is_group": message.chat.type != "private",
                "session_key": self._get_active_session_key(str(chat_id)),
            },
        )

    def _get_extension(self, media_type: str, mime_type: str | None) -> str:
        """Get file extension based on media type."""
        if mime_type:
            ext_map = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
                "audio/ogg": ".ogg",
                "audio/mpeg": ".mp3",
                "audio/mp4": ".m4a",
            }
            if mime_type in ext_map:
                return ext_map[mime_type]

        type_map = {"image": ".jpg", "voice": ".ogg", "audio": ".mp3", "file": ""}
        return type_map.get(media_type, "")
