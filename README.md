# Digest-Write-Deploy

Multi-agent AI system powered by **nanobot** framework for Telegram bot communication.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Telegram Group                       │
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│  │ Summary  │    │  Site    │    │  Feishu  │          │
│  │   Bot    │    │Maintainer│    │   Doc    │          │
│  └──────────┘    └──────────┘    └──────────┘          │
└─────────────────────────────────────────────────────────┘
         ▲                ▲                ▲
         │                │                │
    Docker Agent     Docker Agent     Docker Agent
    (summary:8001)  (site_main:8002)  (feishu:8003)
```

## Prerequisites

- Docker & Docker Compose
- 3 Telegram bots (created via @BotFather)
- MiniMax API key

## Setup

### 1. Create `.env` file

```bash
# Telegram Bot Tokens
TELEGRAM_BOT_TOKEN_SUMMARY=your_summary_bot_token
TELEGRAM_BOT_TOKEN_SITE=your_site_maintainer_bot_token
TELEGRAM_BOT_TOKEN_FEISHU=your_feishu_doc_bot_token

# Group Chat ID (get from @getidsbot)
GROUP_CHAT_ID=-1001234567890

# MiniMax LLM Configuration
LLM_API_KEY=your_minimax_api_key
LLM_BASE_URL=https://api.minimaxi.com/v1
LLM_MODEL=MiniMax-M2.7
```

### 2. Build & Start

```bash
docker compose up -d --build
```

### 3. Verify

```bash
# Check health endpoints
curl http://localhost:8001/health  # summary
curl http://localhost:8002/health  # site_maintainer
curl http://localhost:8003/health  # feishu_doc

# Check logs
docker compose logs --tail=30
```

Expected output:
```
OK summary
OK site_maintainer
OK feishu_doc
```

## Testing

### Telegram Bot Test

1. Add all 3 bots to your Telegram group
2. Send a message mentioning one bot:
   ```
   @summray_agent_bot hello
   ```
3. The bot should respond (if LLM is configured correctly)

### Troubleshooting LLM Errors

If you see `invalid api key` errors in logs:

```bash
docker compose logs summary | grep "api key"
```

Verify your `LLM_API_KEY` in `.env` is correct and not expired.

## Bot Configuration

Configuration files are in `configs/nanobot.*.json`. Each bot has:
- Telegram bot token
- MiniMax LLM provider settings
- System prompt

### Access Control

Default: `"allowFrom": ["*"]` (allows everyone)

To restrict to specific users, find your Telegram user ID via @userinfobot, then update config:

```json
"allowFrom": ["123456789"]
```

## Useful Commands

```bash
# View all logs
docker compose logs -f

# View specific service
docker compose logs -f summary

# Restart
docker compose restart summary

# Stop
docker compose down

# Rebuild after config changes
docker compose up -d --build
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| summary | 8001 | Summary agent - summarizes content |
| site_maintainer | 8002 | Site maintenance agent |
| feishu_doc | 8003 | Feishu document agent |
