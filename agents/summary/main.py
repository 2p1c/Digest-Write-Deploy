"""Summary Agent - handles summarization tasks via Telegram with LLM."""

import os
import logging
import asyncio
from telegram import Update, Message

from common.telegram_client import TelegramAgent, chat_with_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_SUMMARY", "")
BOT_TOKEN_SITE = os.getenv("TELEGRAM_BOT_TOKEN_SITE", "")
BOT_TOKEN_FEISHU = os.getenv("TELEGRAM_BOT_TOKEN_FEISHU", "")


async def handle_message(
    agent: TelegramAgent,
    update: Update,
    message: Message,
    conv_id: str,
    depth: int,
):
    """Handle incoming messages with LLM."""
    text = message.text or ""

    # Remove @mention prefix
    text = text.replace(f"@{agent.bot.username}", "").strip()

    # Remove conversation marker if present
    if text.startswith("[conv_"):
        end_idx = text.index("] ")
        text = text[end_idx + 2:].strip()

    logger.info(f"Summary agent (conv={conv_id[:8]}, depth={depth}): {text[:50]}...")

    # Build LLM prompt
    system_prompt = """You are Summary Agent, a helpful AI assistant.

Your responsibilities:
- Summarize content, articles, or discussions
- Provide concise overviews of complex topics
- Extract key points from messages

Be friendly, helpful, and concise. Keep responses short."""

    messages = [
        {"role": "system", "name": "system", "content": system_prompt},
        {"role": "user", "name": message.from_user.username or "user", "content": text}
    ]

    response = await chat_with_llm(messages, agent_name="Summary Agent")
    escaped = agent.escape_markdown_v2(response)

    await agent.send_to_group(escaped, reply_to_message_id=message.message_id)


async def main():
    """Main entry point."""
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN_SUMMARY not set!")
        return

    agent = TelegramAgent(
        bot_token=BOT_TOKEN,
        agent_name="summary",
        other_bot_tokens={
            "site_maintainer": BOT_TOKEN_SITE,
            "feishu_doc": BOT_TOKEN_FEISHU,
        },
    )

    agent.register_handler(handle_message)
    await agent.start()


if __name__ == "__main__":
    asyncio.run(main())
