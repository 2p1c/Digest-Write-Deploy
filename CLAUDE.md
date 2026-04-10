# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent AI system with **Telegram Bot-to-Bot** communication. Three Docker agents interact via Telegram bots in a group chat, and also expose HTTP health endpoints.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Telegram Group                       │
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐          │
│  │ Summary  │◄──►│  Site    │◄──►│  Feishu  │          │
│  │   Bot    │    │Maintainer│    │   Doc    │          │
│  └──────────┘    └──────────┘    └──────────┘          │
└─────────────────────────────────────────────────────────┘
         ▲                ▲                ▲
         │                │                │
    Docker Agent     Docker Agent     Docker Agent
    (summary:8001)  (site_main:8002)  (feishu:8003)
```

## Quick Start

1. **Create 3 Telegram bots** via @BotFather
2. **Enable Bot-to-Bot mode** for each via `/setio`
3. **Create a group** and add all 3 bots
4. **Get group Chat ID** using @getidsbot
5. **Configure .env** with tokens and group ID
6. **Run:** `docker compose up -d --build`

See [SETUP_TELEGRAM_BOT_TO_BOT.md](./SETUP_TELEGRAM_BOT_TO_BOT.md) for detailed setup.

## Commands

### Docker
```bash
docker compose up -d --build    # Start all agents
docker compose down             # Stop all agents
docker compose logs -f [service] # Follow logs
```

### Health Checks
```bash
curl http://localhost:8001/health  # summary
curl http://localhost:8002/health  # site_maintainer
curl http://localhost:8003/health  # feishu_doc

./scripts/check_cluster_health.sh  # Full cluster check
```

### Telegram Commands
```
@summarize_bot hello
@site_maintainer_bot status
@feishu_doc_bot help
```

## File Structure

```
├── agents/
│   ├── summary/main.py         # Summary agent with Telegram bot
│   ├── site_maintainer/main.py # Site maintainer with Telegram bot
│   └── feishu_doc/main.py      # Feishu doc agent with Telegram bot
├── common/
│   └── telegram_client.py      # Shared Telegram bot utilities
├── scripts/
│   └── check_cluster_health.sh # Health check script
├── docker-compose.yml          # Multi-agent orchestration
├── Dockerfile                  # Agent container image
└── SETUP_TELEGRAM_BOT_TO_BOT.md # Detailed setup guide
```

## Key Files

- `common/telegram_client.py` - Base class `TelegramAgent` with rate limiting, deduplication, and bot-to-bot messaging
- `agents/*/main.py` - Each agent implements `handle_message()` to process commands
- `docker-compose.yml` - All `TELEGRAM_BOT_TOKEN_*` and `GROUP_CHAT_ID` env vars

## Environment Variables

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN_SUMMARY` | Bot token for summary agent |
| `TELEGRAM_BOT_TOKEN_SITE` | Bot token for site_maintainer |
| `TELEGRAM_BOT_TOKEN_FEISHU` | Bot token for feishu_doc |
| `GROUP_CHAT_ID` | Telegram group ID (e.g., -1001234567890) |
| `AGENT_PORT` | HTTP server port (default: 8000) |

## Agent Architecture

Each agent runs two processes in its container:
1. **nanobot gateway** (`nanobot gateway`) - handles Telegram bot polling
2. **Health check server** - Python HTTP server on port 8000 returning `OK`

The `scripts/start_nanobot.sh` launches both and substitutes env vars into `configs/nanobot.{AGENT_NAME}.json` → `/root/.nanobot/config.json`.

Each agent has a local workspace at `agents/{name}/.nanobot/` (gitignored) containing:
- `workspace/SOUL.md` - agent persona
- `workspace/USER.md` - user context
- `workspace/TOOLS.md` - available tools
- `workspace/AGENTS.md` - agent coordination rules
- `workspace/memory/` - conversation history

## Loop Prevention

Built-in safeguards in `TelegramAgent`:
- **Max Depth**: 3 bot-to-bot hops per conversation
- **Rate Limit**: 3 messages per 30 seconds per sender
- **Per-Bot Processing**: Each bot processes a conversation chain only once
- **TTL**: 300 seconds conversation chain expiration

## LLM Integration

`common/telegram_client.py` provides `chat_with_llm()` which calls:
- Endpoint: `POST {LLM_BASE_URL}/text/chatcompletion_v2`
- Model from `LLM_MODEL` env var (default: `MiniMax-M2.7`)
- Any OpenAI-compatible API provider can be used
