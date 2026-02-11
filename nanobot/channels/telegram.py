"""Telegram channel implementation using python-telegram-bot."""

import asyncio
from datetime import datetime

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
from nanobot.channels.telegram_format import markdown_to_telegram_html, split_message
from nanobot.channels.telegram_media import build_message_content
from nanobot.config.schema import TelegramConfig
from nanobot.session.service import SessionService
from nanobot.utils.helpers import get_data_path

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
        self._session_service = SessionService(channel_name=self.name)

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
            self._app.add_handler(CommandHandler("use", self._on_use))
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
                    BotCommand("use", "切换到指定会话"),
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
            segments = split_message(msg.content, limit=3500)
            
            for i, segment in enumerate(segments):
                # Convert markdown to Telegram HTML for each segment
                html_content = markdown_to_telegram_html(segment)
                
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
            "/use <session_key> - 切换到指定会话\n"
            "/new - 开启新会话\n"
            "/clear - 清空当前会话"
        )

    async def _on_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        if not update.message:
            return
        data_dir = get_data_path()
        chat_id = str(update.message.chat_id)
        active_session = self._session_service.get_active_session_key(chat_id)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await update.message.reply_text(
            f"状态: 在线\n时间: {now}\n数据目录: {data_dir}\n当前会话: {active_session}"
        )

    async def _on_new(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /new command: switch to a brand new session key."""
        if not update.message:
            return
        chat_id = str(update.message.chat_id)
        self._session_service.open_new_session(chat_id)
        await update.message.reply_text("已开启新会话。后续消息将使用全新上下文。")

    async def _on_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /history command: list recent sessions for current chat."""
        if not update.message:
            return
        chat_id = str(update.message.chat_id)
        current = self._session_service.get_active_session_key(chat_id)
        entries = self._session_service.list_recent_sessions(chat_id, limit=10)
        if not entries:
            await update.message.reply_text("当前 chat 暂无会话历史。")
            return

        lines = ["最近会话（最多 10 条）:"]
        for key, updated in entries:
            marker = " [当前]" if key == current else ""
            ts = updated if updated else "-"
            lines.append(f"- {key}{marker} | {ts}")
        await update.message.reply_text("\n".join(lines))

    async def _on_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /clear command: delete current session file and rotate to a new session."""
        if not update.message:
            return
        chat_id = str(update.message.chat_id)
        deleted, _ = self._session_service.clear_current_session(chat_id)
        if deleted:
            await update.message.reply_text("当前会话已清空，并已切换到新会话。")
        else:
            await update.message.reply_text("当前会话文件不存在，已切换到新会话。")

    async def _on_use(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /use command: switch active session to an existing session key."""
        if not update.message:
            return
        chat_id = str(update.message.chat_id)
        args = context.args or []
        if not args:
            await update.message.reply_text("用法: /use <session_key>")
            return
        session_key = " ".join(args).strip()
        ok = self._session_service.use_session(chat_id, session_key)
        if ok:
            await update.message.reply_text("已切换到指定会话。")
        else:
            await update.message.reply_text("切换失败：会话不存在，或不属于当前 chat。")

    async def _on_unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle unknown slash commands."""
        if not update.message:
            return
        await update.message.reply_text("未识别的命令。输入 /help 查看可用命令。")

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

        content, media_paths = await build_message_content(message, self._app, self.groq_api_key)

        logger.debug(f"Telegram message from {sender_id}: {content[:50]}...")

        # Forward to the message bus
        await self._handle_message(
            sender_id=sender_id,
            chat_id=str(chat_id),
            content=content,
            media=media_paths,
            session_key_override=self._session_service.get_active_session_key(str(chat_id)),
            metadata={
                "message_id": message.message_id,
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "is_group": message.chat.type != "private",
            },
        )
