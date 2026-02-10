"""iMessage channel implementation using local imsg CLI."""

import asyncio
import json
import subprocess
from typing import Any

from loguru import logger

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import ImessageConfig


class ImessageChannel(BaseChannel):
    """
    iMessage channel using local imsg CLI.
    
    Requires 'imsg' tool installed (brew install steipete/tap/imsg).
    Requires Full Disk Access for the terminal/app.
    """

    name = "imessage"

    def __init__(self, config: ImessageConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: ImessageConfig = config
        self._process: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        """Start watching for iMessages using 'imsg watch --json'."""
        logger.info("ImessageChannel.start() called")
        try:
            self._running = True
            
            # Start imsg watch in a subprocess
            self._process = await asyncio.create_subprocess_exec(
                "imsg", "watch", "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            logger.info("iMessage watch process started")
            
            # Read JSON objects from stdout line by line
            while self._running and self._process.stdout:
                line = await self._process.stdout.readline()
                if not line:
                    break
                
                try:
                    data = json.loads(line.decode().strip())
                    await self._process_incoming_message(data)
                except json.JSONDecodeError:
                    if line.strip():
                        logger.warning(f"Failed to decode iMessage JSON: {line.decode()}")
                except Exception as e:
                    logger.error(f"Error processing iMessage: {e}")

        except Exception as e:
            logger.exception(f"CRITICAL: iMessage initialization failed: {e}")
            self._running = False
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the iMessage watch process."""
        self._running = False
        if self._process:
            logger.info("Stopping iMessage watch process...")
            try:
                self._process.terminate()
                await self._process.wait()
            except Exception as e:
                logger.error(f"Error stopping iMessage process: {e}")
            self._process = None

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message via 'imsg send'."""
        try:
            # We use the identifier (phone/email) to send
            recipient = msg.chat_id
            
            logger.info(f"Sending iMessage to {recipient}")
            
            # Run imsg send
            process = await asyncio.create_subprocess_exec(
                "imsg", "send", "--to", recipient, "--text", msg.content,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Failed to send iMessage: {stderr.decode()}")
            else:
                logger.info(f"iMessage sent successfully to {recipient}")

        except Exception as e:
            logger.error(f"Error sending iMessage: {e}")

    async def _process_incoming_message(self, data: dict[str, Any]) -> None:
        """Parse imsg JSON output and forward to bus."""
        # Example JSON from imsg watch:
        # {"text":"hello","sender":"+861234567890","is_from_me":false,"chat_id":123,"service":"iMessage","at":"2026-02-11T00:00:00Z"}
        
        if data.get("is_from_me"):
            return # Ignore outgoing messages
        
        content = data.get("text", "")
        sender_id = data.get("sender", "unknown")
        chat_id = sender_id # For iMessage, sender identifier is typically the chat_id for replies
        
        # In a group chat, data might contain more info. For now, simple 1:1 focus.
        
        logger.info(f"Received iMessage from {sender_id}: {content[:50]}...")
        
        await self._handle_message(
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            metadata=data
        )
