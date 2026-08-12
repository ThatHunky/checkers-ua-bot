# Installation

Two ways to run the bot: locally with Python (development), or with compose
(production). For the full production setup — TLS, webhooks, health checks — see
[deployment.md](deployment.md).

## Requirements

- Linux
- Python 3.11 (the image is `python:3.11-slim`)
- Redis
- Docker with the compose plugin, if you want the containerised setup
- A bot token from [@BotFather](https://t.me/BotFather)

## Configuration

Every setting comes from the environment; `.env` in the repo root is loaded at
startup. Copy the template and fill it in:

```bash
cp .env.example .env
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `TOKEN` | — | **Required.** Bot token from @BotFather. |
| `USE_WEBHOOK` | `false` | `true` = webhook mode, `false` = long polling. |
| `PORT` | `8787` | Webhook listen port. |
| `WEBHOOK_LISTEN` | `0.0.0.0` | Webhook bind address. |
| `WEBHOOK_URL` | `https://checkers.dobrovolskyi.com.ua` | Public HTTPS base URL. |
| `WEBHOOK_PATH` | derived from `TOKEN` | Optional. URL path segment. |
| `WEBHOOK_SECRET` | derived from `TOKEN` | Optional. Telegram `secret_token`. |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection. |
| `DB_PATH` | `/data/ratings.db` | Ratings + achievements SQLite file. |
| `GAMEDATA_DB_PATH` | `/data/gamedata.db` | Completed-game archive. |
| `GAME_TIMEOUT_MINUTES` | `10` | Inactivity before a game is timed out. |
| `ADMIN_ID` | — | Telegram user id allowed to run hidden admin commands. |

`.env` is git-ignored and excluded from the image by `.dockerignore`; the container
receives it at runtime via `env_file`.

Leaving `WEBHOOK_PATH` and `WEBHOOK_SECRET` unset derives both deterministically from
`TOKEN` (SHA-256), which keeps the URL stable across restarts without extra config and
keeps the token out of URLs and logs. Rotating `TOKEN` therefore also rotates the path
and secret — safe, because the bot re-registers the webhook on every start.

## Local Python setup

```bash
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python main_polling.py
```

Polling mode needs no public URL and no reverse proxy.

## Containerised setup

```bash
docker compose up -d --build
```

This starts two services: `bot` and `redis`. There is **no** Caddy container — TLS is
terminated by a Caddy running on the host. Persistent data is bind-mounted from
`/mnt/ssd1/checkers_data` to `/data`; change that path in `compose.yaml` to match your
server.

Check it came up:

```bash
docker compose ps && docker compose logs --tail 30 bot
```

## Next steps

- [deployment.md](deployment.md) — webhooks, Caddy, health checks, backups
- [development.md](development.md) — local workflow and house rules
- [administration.md](administration.md) — admin commands
