# Development

## Setup

```bash
git clone git@github.com:ThatHunky/checkers-ua-bot.git
```

```bash
cd checkers-ua-bot && python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set at least `TOKEN` (get one from
[@BotFather](https://t.me/BotFather) — use a **separate test bot**, never the
production token). Leave `USE_WEBHOOK=false` for development.

## Running locally

```bash
.venv/bin/python main_polling.py
```

Polling needs no public URL, no reverse proxy and binds no port. It registers the same
handler table as the webhook entrypoint (`handler_registry.py`), so what you exercise
locally is what production serves.

Redis is required. Either point `REDIS_URL` at a local install, or:

```bash
docker run -d --name checkers-redis -p 6379:6379 redis:alpine
```

...and set `REDIS_URL=redis://localhost:6379/0`.

## Testing

```bash
.venv/bin/python -m pytest -q
```

See [testing.md](testing.md). Run the suite before every commit — it takes ~3 seconds.

## Where code goes

| Change | Goes in |
| --- | --- |
| New command or button | a method on `GameHandlers`, plus one row in `handler_registry.py` |
| Game rule | `engine.py` only |
| User-visible text | `locales.py` — never inline in a handler |
| Redis access | `repository.py` |
| Board or keyboard layout | `handlers/board_renderer.py` |
| Non-pytest tooling | `scripts/` |

Do not add code to `handlers.py`; it is a compatibility shim.

Keep rules (`engine.py`) free of Telegram types and I/O. That separation is what makes
the engine testable, and it is the single most valuable structural property this
codebase has.

## House rules

- Comments explain **why**, not what. Match the density of the surrounding code.
- All user-facing strings are Ukrainian and live in `locales.py`.
- Every message is sent with `parse_mode=HTML`. Any Telegram-controlled value
  (`first_name`, `username`, stored player names) must be `html.escape()`d **at the
  render site** — not at storage, because the same values also go to plain-text
  messages and inline button labels, where escaping would show literal `&amp;`.
- Never put a secret in a URL or a log line. `httpx`/`httpcore` are pinned to WARNING
  precisely because they log full Telegram API URLs, which embed the bot token.

## Debugging

- Bot logging is INFO; `httpx`/`httpcore` are WARNING on purpose. Do not raise them
  without first checking what they print.
- An unrouted button answers "❌ Callback не розпізнано" — that means no pattern in
  `handler_registry.py` matched, not that the handler crashed.
- Handler exceptions are often caught and logged rather than raised, so check the logs
  before concluding that nothing happened.
- To inspect live state: `redis-cli --scan --pattern 'checkers:*'`.

## Dependencies

Pinned in `requirements.txt`. Update deliberately, one package at a time, and run the
suite. Do not `pip freeze >` over it — that would capture transitive pins and local
noise.
