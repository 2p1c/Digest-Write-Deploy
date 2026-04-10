"""Feishu Doc Agent - handles Feishu document tasks via Telegram with LLM."""

import os
import logging
import asyncio
from telegram import Update, Message

from common.telegram_client import TelegramAgent, chat_with_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN_FEISHU", "")
BOT_TOKEN_SUMMARY = os.getenv("TELEGRAM_BOT_TOKEN_SUMMARY", "")
BOT_TOKEN_SITE = os.getenv("TELEGRAM_BOT_TOKEN_SITE", "")


async def handle_message(
    agent: TelegramAgent,
    update: Update,
    message: Message,
    conv_id: str,
    depth: int,
):
    """Handle incoming messages with LLM."""
    text = message.text or ""
    text = text.replace(f"@{agent.bot.username}", "").strip()

    if text.startswith("[conv_"):
        end_idx = text.index("] ")
        text = text[end_idx + 2:].strip()

    logger.info(f"Feishu Doc agent (conv={conv_id[:8]}, depth={depth}): {text[:50]}...")

    messages = [
        {
            "role": "system",
            "name": "system",
            "content": """You are Feishu Doc Agent, a helpful AI assistant.

Your responsibilities:
- Help with Feishu (Lark) document management
- Assist with creating, editing, and organizing documents
- Provide guidance on document workflows

Be helpful, organized, and clear. Keep responses short."""
        },
        {"role": "user", "name": message.from_user.username or "user", "content": text}
    ]

    response = await chat_with_llm(messages, agent_name="Feishu Doc Agent")
    escaped = agent.escape_markdown_v2(response)

    await agent.send_to_group(escaped, reply_to_message_id=message.message_id)


async def main():
    """Main entry point."""
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN_FEISHU not set!")
        return

    agent = TelegramAgent(
        bot_token=BOT_TOKEN,
        agent_name="feishu_doc",
        other_bot_tokens={
            "summary": BOT_TOKEN_SUMMARY,
            "site_maintainer": BOT_TOKEN_SITE,
        },
    )

    agent.register_handler(handle_message)
    await agent.start()


if __name__ == "__main__":
    asyncio.run(main())
