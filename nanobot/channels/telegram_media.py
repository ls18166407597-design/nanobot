"""Telegram media extraction helpers."""

from pathlib import Path

from loguru import logger

from nanobot.utils.helpers import get_data_path


def get_extension(media_type: str, mime_type: str | None) -> str:
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


async def build_message_content(message, app, groq_api_key: str) -> tuple[str, list[str]]:
    """Build text content and downloaded media list from Telegram message."""
    content_parts: list[str] = []
    media_paths: list[str] = []

    if message.text:
        content_parts.append(message.text)
    if message.caption:
        content_parts.append(message.caption)

    media_file = None
    media_type = None
    if message.photo:
        media_file = message.photo[-1]
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

    if media_file and app:
        try:
            file = await app.bot.get_file(media_file.file_id)
            ext = get_extension(media_type, getattr(media_file, "mime_type", None))
            media_dir = get_data_path() / "media"
            media_dir.mkdir(parents=True, exist_ok=True)
            file_path = media_dir / f"{media_file.file_id[:16]}{ext}"
            await file.download_to_drive(str(file_path))
            media_paths.append(str(file_path))

            if media_type in ("voice", "audio"):
                from nanobot.providers.transcription import GroqTranscriptionProvider

                transcriber = GroqTranscriptionProvider(api_key=groq_api_key)
                transcription = await transcriber.transcribe(Path(file_path))
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
    return content, media_paths
