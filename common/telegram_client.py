"""Shared Telegram bot utilities for agent communication with robust loop prevention."""

import os
import uuid
import logging
import asyncio
import threading
from dataclasses import dataclass, field
from typing import Callable
from datetime import datetime, timedelta
from collections import defaultdict

import httpx
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.ext import Application, MessageHandler, filters

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# LLM Provider configuration
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.minimaxi.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "MiniMax-M2.7")


async def chat_with_llm(messages: list[dict], agent_name: str = "agent") -> str:
    """Send messages to LLM and return the response."""
    if not LLM_API_KEY:
        return f"[{agent_name}] LLM_API_KEY not configured"

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "stream": False,
        "temperature": 0.7,
        "max_completion_tokens": 2048,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{LLM_BASE_URL}/text/chatcompletion_v2",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            if "choices" in data and data["choices"]:
                choice = data["choices"][0]
                if "messages" in choice:
                    return choice["messages"][0].get("content", "No content")
                if "message" in choice:
                    return choice["message"].get("content", "No content")
            elif "messages" in data:
                return data["messages"][0].get("content", "No content")
            elif "text" in data:
                return data["text"]

            return "No response generated"
    except Exception as e:
        logger.error(f"LLM API error: {e}")
        return f"[{agent_name}] LLM error: {str(e)[:100]}"


@dataclass
class LoopPrevention:
    """
    Robust loop prevention for bot-to-bot communication.

    Key principles:
    1. Each conversation chain has a unique ID passed through all hops
    2. Each bot processes a conversation chain only ONCE
    3. Max depth limits total hops in a chain
    4. Rate limiting prevents spam
    """

    # Max total hops across all bots in one conversation
    max_depth: int = 3

    # How long to remember processed conversations
    ttl_seconds: int = 300

    # Rate limiting: max messages per sender in time window
    rate_limit: int = 3
    rate_window_seconds: int = 30

    # Per-conversation tracking: (conversation_id, bot_name) -> timestamp
    _processed: dict = field(default_factory=lambda: {})
    _rate_counts: dict = field(default_factory=lambda: defaultdict(list))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _cleanup_expired(self, now: datetime) -> None:
        """Remove expired entries."""
        ttl_delta = timedelta(seconds=self.ttl_seconds)

        # Cleanup processed - remove expired entries
        expired_keys = [
            k for k, v in self._processed.items()
            if (now - v).total_seconds() > self.ttl_seconds
        ]
        for k in expired_keys:
            del self._processed[k]

        # Cleanup rate counts
        window_delta = timedelta(seconds=self.rate_window_seconds)
        for sender in list(self._rate_counts.keys()):
            self._rate_counts[sender] = [t for t in self._rate_counts[sender] if now - t < window_delta]
            if not self._rate_counts[sender]:
                del self._rate_counts[sender]

    def can_process(self, conversation_id: str, bot_name: str, depth: int) -> tuple[bool, str]:
        """
        Check if this bot should process this conversation.
        Returns (allowed, reason).
        """
        with self._lock:
            self._cleanup_expired(datetime.now())

            key = f"{conversation_id}:{bot_name}"

            # Already processed by this bot
            if key in self._processed:
                return False, f"Bot {bot_name} already processed conversation {conversation_id[:8]}"

            # Depth exceeded
            if depth >= self.max_depth:
                return False, f"Max depth {self.max_depth} exceeded"

            # Mark as processed
            self._processed[key] = datetime.now()
            return True, ""

    def record_processed(self, conversation_id: str, bot_name: str) -> None:
        """Record that a bot processed a conversation."""
        with self._lock:
            key = f"{conversation_id}:{bot_name}"
            self._processed[key] = datetime.now()

    def check_rate_limit(self, sender_id: str) -> tuple[bool, str]:
        """Check if sender is within rate limits."""
        with self._lock:
            now = datetime.now()
            window_delta = timedelta(seconds=self.rate_window_seconds)

            # Cleanup
            self._rate_counts[sender_id] = [t for t in self._rate_counts[sender_id] if now - t < window_delta]

            if len(self._rate_counts[sender_id]) >= self.rate_limit:
                return False, f"Rate limit exceeded: {self.rate_limit} msgs per {self.rate_window_seconds}s"

            self._rate_counts[sender_id].append(now)
            return True, ""


class TelegramAgent:
    """Base class for Telegram-enabled agents with robust loop prevention."""

    # Class-level shared state across all bot instances
    _shared_prevention: LoopPrevention | None = None
    _prevention_lock = threading.Lock()

    def __init__(
        self,
        bot_token: str,
        agent_name: str,
        other_bot_tokens: dict[str, str],
        group_chat_id: str | None = None,
    ):
        self.bot = Bot(token=bot_token)
        self.agent_name = agent_name
        self.other_bots = {
            name: Bot(token=token) for name, token in other_bot_tokens.items()
        }
        self.group_chat_id = group_chat_id or os.getenv("GROUP_CHAT_ID")

        # Shared loop prevention across all bots
        with self._prevention_lock:
            if TelegramAgent._shared_prevention is None:
                TelegramAgent._shared_prevention = LoopPrevention()
            self.loop_prevention = TelegramAgent._shared_prevention

        self._app: Application | None = None
        self._message_handlers: list[Callable] = []
        self._my_username: str | None = None

    async def _get_my_username(self) -> str:
        """Get and cache this bot's username."""
        if self._my_username:
            return self._my_username
        me = await self.bot.get_me()
        self._my_username = me.username
        return self._my_username

    def _extract_conversation_id(self, text: str) -> tuple[str | None, str | None, int]:
        """
        Extract conversation metadata from message.
        Returns (conversation_id, target_bot, depth).

        Message format for bot-to-bot: [conv_id|depth|→target] actual message
        """
        if not text.startswith("["):
            return None, None, 0

        try:
            # Find the end of the marker
            end_idx = text.index("] ")
            marker = text[1:end_idx]
            content = text[end_idx + 2:]

            parts = marker.split("|")
            if len(parts) >= 3 and parts[0].startswith("conv") and parts[2].startswith("→"):
                conv_id = parts[0]
                depth = int(parts[1])
                target = parts[2][1:]  # Remove →
                return conv_id, target, depth
        except (ValueError, IndexError):
            pass

        return None, None, 0

    def _make_marker(self, conv_id: str, depth: int, target: str) -> str:
        """Create a conversation marker for bot-to-bot messaging."""
        return f"[{conv_id}|{depth}|→{target}]"

    async def send_to_bot(
        self,
        target_bot: str,
        text: str,
        conversation_id: str,
        current_depth: int,
        reply_to_message_id: int | None = None,
    ) -> bool:
        """Send message to another bot with conversation tracking."""
        if target_bot not in self.other_bots:
            logger.warning(f"Unknown bot: {target_bot}")
            return False

        new_depth = current_depth + 1
        marker = self._make_marker(conversation_id, new_depth, target_bot)
        full_text = f"{marker} {text}"

        # Check loop prevention before sending
        allowed, reason = self.loop_prevention.can_process(conversation_id, target_bot, new_depth)
        if not allowed:
            logger.info(f"Loop prevention blocked forward to {target_bot}: {reason}")
            return False

        try:
            await self.other_bots[target_bot].send_message(
                chat_id=self.group_chat_id,
                text=f"@{target_bot} {text}",
                reply_to_message_id=reply_to_message_id,
                parse_mode=ParseMode.MARKDOWN_V2,
            )

            # Record that we sent to this bot
            self.loop_prevention.record_processed(conversation_id, target_bot)

            logger.info(f"[{self.agent_name}] Forwarded to @{target_bot} (conv={conversation_id[:8]}, depth={new_depth})")
            return True

        except Exception as e:
            logger.error(f"Failed to send message to {target_bot}: {e}")
            return False

    async def send_to_group(self, text: str, reply_to_message_id: int | None = None) -> bool:
        """Send message to the group."""
        if not self.group_chat_id:
            logger.warning("GROUP_CHAT_ID not set")
            return False

        try:
            await self.bot.send_message(
                chat_id=self.group_chat_id,
                text=text,
                reply_to_message_id=reply_to_message_id,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send to group: {e}")
            return False

    def escape_markdown_v2(self, text: str) -> str:
        """Escape text for MarkdownV2."""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f"\\{char}")
        return text

    def register_handler(self, handler: Callable):
        """Register a message handler callback."""
        self._message_handlers.append(handler)

    async def _handle_message_with_context(self, update: Update, context):
        """Wrapper to handle message with required context param."""
        await self.handle_update(update)

    async def handle_update(self, update: Update):
        """Process an incoming update with robust loop prevention."""
        if not update.message:
            return

        message = update.message
        text = message.text or ""

        if not text:
            return

        my_username = await self._get_my_username()
        sender = message.from_user
        is_from_bot = sender and sender.is_bot
        sender_username = sender.username if sender else "unknown"

        # Parse conversation marker
        conv_id, target_bot, depth = self._extract_conversation_id(text)

        # Check if this is a bot-to-bot protocol message or a reply to us
        is_reply_to_me = (
            message.reply_to_message and
            message.reply_to_message.from_user and
            message.reply_to_message.from_user.username == my_username
        )

        # Only process if:
        # 1. Private chat with user
        # 2. Direct @mention from user in group (new conversation starts)
        # 3. Bot-forwarded message with protocol marker
        has_protocol_marker = conv_id is not None
        is_private = message.chat.type == "private"
        is_direct_mention = f"@{my_username}" in text

        if is_private:
            # Always process private messages
            pass
        elif has_protocol_marker:
            # Process bot-to-bot protocol messages
            pass
        elif is_reply_to_me:
            # Process replies to our messages
            pass
        elif is_direct_mention and not is_from_bot:
            # Direct @mention from user - process (deduplicated by message_id)
            pass
        else:
            return

        # If this is a new conversation (no marker), create new ID
        if conv_id is None:
            conv_id = f"conv_{uuid.uuid4().hex[:12]}"

        # Clean text - remove marker and @mention
        clean_text = text
        if has_protocol_marker:
            try:
                marker_end = text.index("] ")
                clean_text = text[marker_end + 2:]
            except ValueError:
                pass

        if f"@{my_username}" in clean_text:
            clean_text = clean_text.replace(f"@{my_username}", "").strip()

        # Skip if we're not the target of this forwarded message
        if target_bot and target_bot.lower() != my_username.lower():
            return

        # Check if this message was sent by us (loopback prevention)
        if is_from_bot and sender_username == my_username:
            logger.debug(f"Skipping our own message")
            return

        # Rate limit check (only for human users forwarding bots)
        if not is_from_bot:
            allowed, reason = self.loop_prevention.check_rate_limit(sender_username)
            if not allowed:
                logger.info(f"Rate limited: {sender_username} - {reason}")
                return

        # Loop prevention: can this bot process this conversation?
        allowed, reason = self.loop_prevention.can_process(conv_id, self.agent_name, depth)
        if not allowed:
            logger.info(f"Loop prevention: {reason}")
            return

        # Record that we're processing this
        self.loop_prevention.record_processed(conv_id, self.agent_name)

        logger.info(f"[{self.agent_name}] Processing conv={conv_id[:12]} depth={depth} from {sender_username}")

        # Process message
        for handler in self._message_handlers:
            try:
                await handler(self, update, message, conv_id, depth)
            except Exception as e:
                logger.error(f"Handler error: {e}")

    async def start(self):
        """Start the bot."""
        self._app = Application.builder().token(self.bot.token).build()

        self._app.add_handler(MessageHandler(
            filters.ALL,
            self._handle_message_with_context
        ))

        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

        logger.info(f"{self.agent_name} bot started with robust loop prevention")

        while True:
            await asyncio.sleep(3600)
