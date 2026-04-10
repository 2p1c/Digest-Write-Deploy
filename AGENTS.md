# AGENTS.md

## Repo Reality (verified from code)
- This repo is Docker-first: there is no root Python package/lockfile or test runner config; runtime behavior is defined by `docker-compose.yml`, `Dockerfile`, and shell scripts.
- Each service starts via `scripts/start_nanobot.sh`, which does `envsubst` from `configs/nanobot.${AGENT_NAME}.json` into `/root/.nanobot/config.json`, then runs two long-lived processes: `nanobot gateway` and an inline Python `/health` server on port `8000`.
- The three agents are thin wrappers (`agents/summary/main.py`, `agents/site_maintainer/main.py`, `agents/feishu_doc/main.py`) around shared logic in `common/telegram_client.py`.

## Commands You Should Actually Use
- Start/rebuild stack: `docker compose up -d --build`
- Restart after config/env edits: `docker compose restart <service>` (or restart all services)
- Service logs: `docker compose logs -f <service>`
- Full health + cross-container connectivity: `./scripts/check_cluster_health.sh`
- Quick host health checks: `curl http://localhost:8001/health`, `curl http://localhost:8002/health`, `curl http://localhost:8003/health`

## Behavior Constraints That Matter
- Loop prevention is enforced in `common/telegram_client.py` (`LoopPrevention`): `max_depth=3`, `ttl_seconds=300`, `rate_limit=3` per `30s`. Prefer these code values over prose docs if they diverge.
- Outbound Telegram messages use `ParseMode.MARKDOWN_V2` (`send_to_group`, `send_to_bot`), so text must be escaped with `escape_markdown_v2` before sending.
- LLM calls are centralized in `chat_with_llm()` and target `POST {LLM_BASE_URL}/text/chatcompletion_v2` with `LLM_MODEL`.

## Editing Guidance For Future Agents
- Treat `configs/nanobot.*.json` as templates; do not hardcode secrets there. Keep `${...}` env placeholders intact.
- Do not edit agent runtime state under `agents/*/.nanobot/` unless the task is explicitly about local nanobot workspace state; these folders are mounted runtime data.
- If docs conflict, trust executable sources (`docker-compose.yml`, `scripts/*.sh`, `common/telegram_client.py`) and update docs only after verifying behavior.

## Verification Expectations
- There is no established unit/integration test suite in this repo today; validate changes with compose health checks, targeted service logs, and an end-to-end Telegram message in the group.
