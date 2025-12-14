# Installation

This guide shows options for installing and running the Checkers UA Bot.

Requirements

- Linux (development and container images supported)
- Python 3.10+ (match `requirements.txt`)
- podman / docker (optional, for containerized deployment)
- podman-compose or docker-compose (if using compose)

Local Python setup

1. Create a virtual environment and activate it:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` (optional) in the repo root with any required secrets (example):

```
# .env
TELEGRAM_TOKEN=your_bot_token_here
DATABASE_URL=sqlite:///data/bot.db
```

(See `main.py` / `main_polling.py` for environment usage.)

Containerized (Podman / Docker)

1. Build the image with the included Containerfile:

```bash
podman build -t checkers-ua-bot -f Containerfile .
# or: docker build -t checkers-ua-bot -f Containerfile .
```

2. Start services with the compose file:

```bash
podman-compose up -d
# or: docker-compose up -d
```

Notes

- The repo includes `compose.yaml` for orchestrating service(s). Use `podman-compose` with Podman or `docker-compose` with Docker.
- If you use a different DB or external services, configure connection strings in `.env` or environment variables when running containers.
