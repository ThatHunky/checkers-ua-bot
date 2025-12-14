# Usage

This document explains how to run and use the bot.

Entrypoints

- `main.py` — typically used for webhooks / advanced setups
- `main_polling.py` — run the bot in long-polling mode (useful for development)

Run with virtualenv active:

```bash
# run in polling mode (development)
python main_polling.py

# run a production/service mode (check your environment / webhook config)
python main.py
```

Environment variables

- `TELEGRAM_TOKEN` — token for the Telegram bot
- `DATABASE_URL` — optional custom DB connection
- Other configuration is loaded from environment or default values in code

Interacting with the bot

- The bot supports playing checkers games with commands and inline interactions (see `inline-mode-implementation.md`).
- Handlers are implemented in `handlers.py` — user commands, buttons, and gameplay flows.

Common operations

- Restarting the bot when running under compose:

```bash
podman-compose restart bot
```

- Inspect logs (podman):

```bash
podman logs -f <container-name>
```

Tips

- Use `test_engine.py` to validate game logic locally before running a full integration session.
- If the bot fails to connect to Telegram, ensure `TELEGRAM_TOKEN` is set and the network allows outbound requests.
