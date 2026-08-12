# Deployment

This guide explains how to build and run the bot in containers and with compose.

## Topology

Compose runs exactly two services: **bot** and **redis**. TLS is terminated by a
**Caddy that runs on the host** (systemd `caddy.service`), *not* by a compose
service — there is no `caddy` service and no `caddy_data` volume.

```
Internet ──443──▶ host Caddy ──▶ 127.0.0.1:8787 ──▶ bot container ──▶ redis container
                (systemd)          (published on          (compose)        (compose)
                                    loopback only)
```

The bot publishes its port as `127.0.0.1:8787:8787`, so only the host can reach it.

## Build image

```bash
podman build -t checkers-ua-bot -f Containerfile .
```

```bash
docker build -t checkers-ua-bot -f Containerfile .
```

## Webhook Mode Setup (Production)

### Prerequisites

1. **Domain name**: point `checkers.dobrovolskyi.com.ua` (or your domain) at the server's IP
2. **Ports**: 80 and 443 open to the internet, so Caddy can complete the ACME challenge
3. **Caddy installed on the host** (`sudo apt install caddy`)

### Environment variables

Copy `.env.example` to `.env` and fill it in. See that file for the full list and
defaults; the webhook-relevant ones are:

```bash
TOKEN=your_telegram_bot_token
USE_WEBHOOK=true
WEBHOOK_URL=https://checkers.dobrovolskyi.com.ua
PORT=8787
WEBHOOK_LISTEN=0.0.0.0
```

`WEBHOOK_PATH` and `WEBHOOK_SECRET` are optional. Left unset, both are derived
deterministically from `TOKEN` (SHA-256), which keeps the URL stable across restarts
without extra configuration and keeps the bot token out of the URL, the logs and any
proxy access log. Two consequences worth knowing:

- **Rotating `TOKEN` also rotates the webhook path and secret.** That is safe — the
  bot calls `setWebhook` with the new values on every startup — but Telegram will
  briefly POST to the old path until that call lands.
- Set both explicitly if you want the path pinned independently of the token.

`WEBHOOK_SECRET` is sent to Telegram as `secret_token`; Telegram echoes it back in the
`X-Telegram-Bot-Api-Secret-Token` header on every update and python-telegram-bot
rejects requests that do not carry it. Without it, anyone who learns the URL can POST
forged updates.

### Caddy configuration

The repo's `Caddyfile` is the host config. Install it:

```bash
sudo cp Caddyfile /etc/caddy/Caddyfile
```

```bash
sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy
```

If you already serve other sites from `/etc/caddy/Caddyfile`, append the site block
rather than overwriting the file. To use a different domain, edit the hostname:

```
your-domain.com {
    reverse_proxy localhost:8787 {
        header_up Host {host}
        header_up X-Real-IP {remote}
        header_up X-Forwarded-For {remote}
        header_up X-Forwarded-Proto {scheme}
    }
}
```

Use `localhost:8787`, not `bot:8787` — the container hostname only resolves inside
the compose network, which the host Caddy is not on.

### Run with compose

```bash
docker compose up -d
```

Startup order: redis starts first, and the bot waits for redis to pass its health
check (`depends_on: condition: service_healthy`). Caddy is independent — it is a host
service and can be started or reloaded at any time.

### Verify

Confirm the bot set its webhook:

```bash
docker compose logs bot | grep -i webhook
```

You should see the path redacted — the bot never logs the token or the derived path:

```
Setting webhook: https://checkers.dobrovolskyi.com.ua/<redacted>
Webhook set successfully
```

To check what Telegram actually holds, ask the API directly (this prints the real
URL, so do not paste the output anywhere public):

```bash
curl -s "https://api.telegram.org/bot$(grep '^TOKEN=' .env | cut -d= -f2-)/getWebhookInfo"
```

Look for `"pending_update_count": 0` and an empty `last_error_message`.

## Polling Mode (Development)

Set `USE_WEBHOOK=false` in `.env`. The bot uses long polling and binds no port, so no
Caddy config is needed. `main_polling.py` is a polling-only entrypoint; both it and
`main.py` register the same handler table from `handler_registry.py`, so behaviour is
identical between the two modes.

## Restarting and logs

```bash
docker compose restart bot
```

```bash
docker compose logs -f bot
```

Caddy is a host service, so its logs come from journald:

```bash
sudo journalctl -u caddy -f
```

## Health checks

- **redis**: `redis-cli ping` every 10s
- **bot**: every 30s. In webhook mode it checks that `PORT` is listening; in polling
  mode nothing binds a port, so the probe reports healthy rather than failing forever.
- **caddy**: not a compose service — use `systemctl status caddy`

## Production considerations

- `restart: always` handles crashes; it does **not** react to an unhealthy status
- Provide `TOKEN` and `ADMIN_ID` via `.env` (git-ignored) or a secret manager
- Firewall must allow 80 and 443 inbound for Caddy's certificate renewal
- DNS must point at the server before the first start, or the ACME challenge fails
- `compose.yaml` bind-mounts the repo at `/app` for hot reload, so the running code is
  the working tree, not the image. For an immutable production deployment, drop that
  mount and rebuild the image on each release.
- Persistent data lives on the host at `/mnt/ssd1/checkers_data` (`/data` in the
  container): `ratings.db` and `gamedata.db`. Back it up.
