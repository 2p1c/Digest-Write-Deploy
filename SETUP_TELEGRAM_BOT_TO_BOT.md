# Telegram Bot-to-Bot Setup Guide

## Overview

This guide explains how to set up 3 Telegram bots that can communicate with each other in a group chat, enabling your Docker agents to interact via Telegram with LLM-powered responses.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                     Telegram Group                     │
│                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │ Summary  │◄──►│  Site    │◄──►│  Feishu  │      │
│  │   Bot    │    │Maintainer│    │   Doc    │      │
│  └──────────┘    └──────────┘    └──────────┘      │
└─────────────────────────────────────────────────────┘
         ▲                ▲                ▲
         │                │                │
    Docker Agent     Docker Agent     Docker Agent
```

## Step 1: Create Telegram Bots

### 1.1 Create each bot via @BotFather

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Follow the prompts to create each bot:

```
Bot 1:
  - Name: SummaryAgent
  - Username: summary_agent_bot

Bot 2:
  - Name: SiteMaintainerAgent
  - Username: site_maintainer_bot

Bot 3:
  - Name: FeishuDocAgent
  - Username: feishu_doc_bot
```

4. **Copy the HTTP API tokens** for each bot (you'll need them later)

### 1.2 Enable Bot-to-Bot Communication Mode

**Important:** This step is required for full bot-to-bot functionality.

1. Open a chat with **@BotFather**
2. Send `/setio` (or navigate via menu)
3. Select the bot you want to enable
4. Choose "Enable" for Bot-to-Bot Communication

### 1.3 Get Group Chat ID

1. Create a new Telegram group:
   - Click "New Group"
   - Name it something like "AI Agents"
   - Add all three bots to the group

2. Get the group chat ID:
   - Add **@userinfobot** or **@getidsbot** to the group
   - The bot will reply with the group ID (e.g., `-1001234567890`)
   - Remove the helper bot after getting the ID

## Step 2: Configure Environment Variables

Create a `.env` file in the project root:

```bash
# ============================================
# Telegram Bot Tokens (from Step 1.1)
# ============================================
TELEGRAM_BOT_TOKEN_SUMMARY=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_BOT_TOKEN_SITE=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_BOT_TOKEN_FEISHU=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# ============================================
# Telegram Group (from Step 1.3)
# ============================================
GROUP_CHAT_ID=-1001234567890

# ============================================
# LLM Configuration (Minimax as default)
# ============================================
LLM_API_KEY=your_minimax_api_key_here
LLM_BASE_URL=https://api.minimaxi.com/v1
LLM_MODEL=MiniMax-M2.7
```

### Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN_SUMMARY` | Yes | - | Bot token for summary agent |
| `TELEGRAM_BOT_TOKEN_SITE` | Yes | - | Bot token for site_maintainer |
| `TELEGRAM_BOT_TOKEN_FEISHU` | Yes | - | Bot token for feishu_doc |
| `GROUP_CHAT_ID` | Yes | - | Telegram group ID (e.g., -1001234567890) |
| `LLM_API_KEY` | Yes | - | API key for LLM provider |
| `LLM_BASE_URL` | No | `https://api.minimaxi.com/v1` | LLM API base URL |
| `LLM_MODEL` | No | `MiniMax-M2.7` | LLM model name |

### Supported LLM Providers

The system supports any OpenAI-compatible API. Examples:

| Provider | Base URL | Model Example |
|----------|---------|---------------|
| Minimax | `https://api.minimaxi.com/v1` | `MiniMax-M2.7` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.1-70b-versatile` |
| Custom | `http://your-ollama:11434/v1` | `llama3` |

## Step 3: Configure Bot Privacy Settings

For bots to receive messages in groups:

1. For each bot, run `/setprivacy` in @BotFather
2. Select the bot
3. Choose **"Disable"** (to allow receiving all messages, not just @mentions)

**Alternative:** Keep privacy enabled and always @mention the bots.

## Step 4: Build and Run

```bash
# Build and start all agents
docker compose up -d --build

# Check logs
docker compose logs -f summary
docker compose logs -f site_maintainer
docker compose logs -f feishu_doc
```

## Step 5: Test

In your Telegram group:

### Direct Commands
```
@summarize_bot 你好，你是谁？
@site_maintainer_bot 网站状态怎么样？
@feishu_doc_bot 帮我创建一个文档
```

### Bot-to-Bot Communication
```
@summarize_bot @site_maintainer 请帮我总结一下网站部署的最佳实践
```

The bots will collaborate automatically - when one bot mentions another, the conversation chain continues.

### Health Check
Each agent still exposes HTTP health endpoints:
```bash
curl http://localhost:8001/health  # summary
curl http://localhost:8002/health  # site_maintainer
curl http://localhost:8003/health  # feishu_doc
```

## Bot Commands Reference

### Summary Bot
- Responds to general questions
- Can forward to `@site_maintainer` or `@feishu_doc` for specialized topics

### Site Maintainer Bot
- Responds to technical and deployment questions
- Can forward to `@summary` or `@feishu_doc` as needed

### Feishu Doc Bot
- Responds to document-related questions
- Can forward to `@summary` or `@site_maintainer` as needed

## Loop Prevention

The system has robust built-in protection against infinite loops:

| Protection | Value | Description |
|------------|-------|-------------|
| Max Depth | 3 | Maximum bot-to-bot hops per conversation |
| Rate Limit | 3 msg/30s | Per-sender message rate limit |
| TTL | 300s | Conversation chain expiration |
| Per-Bot Processing | 1x | Each bot processes a conversation only once |

## Troubleshooting

### Bots not responding in group
1. Check privacy settings: `/setprivacy` → Disable
2. Enable Bot-to-Bot mode: `/setio` → Enable
3. Make sure `GROUP_CHAT_ID` is correct
4. Verify `LLM_API_KEY` is set in `.env`

### Infinite message loops
The agents have robust loop prevention built in. If issues persist:
1. Check logs: `docker compose logs`
2. Verify no other bots in the group are causing loops
3. Reduce `max_depth` in `LoopPrevention` class if needed

### Permission denied errors
1. Make sure bots are admins in the group OR
2. Disable privacy mode via `/setprivacy`

## Quick Reference

| Task | Command |
|------|---------|
| Create bot | `/newbot` in @BotFather |
| Get token | Copy from @BotFather after creation |
| Enable B2B mode | `/setio` → select bot → Enable |
| Disable privacy | `/setprivacy` → select bot → Disable |
| Get group ID | Add @getidsbot to group |
