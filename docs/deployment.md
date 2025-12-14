# Deployment

This guide explains how to build and run the bot in containers and with compose.

Build image

```bash
podman build -t checkers-ua-bot -f Containerfile .
# or: docker build -t checkers-ua-bot -f Containerfile .
```

Run with compose

```bash
podman-compose up -d
# or: docker-compose up -d
```

Restarting and logs

```bash
podman-compose restart bot
podman logs -f <container-name>
```

Production considerations

- Use a process manager or system service (systemd) to ensure containers restart on failure.
- Securely provide `TELEGRAM_TOKEN` and other secrets via environment variables or secret manager.
- Monitor logs and add structured logging if needed.
