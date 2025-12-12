# Ukrainian Checkers Telegram Bot (Шашки)

A lightweight PvP Telegram bot for Ukrainian Checkers running in Podman containers.

## Features

- 🎮 **Ukrainian Checkers Rules** (Russian Drafts)
  - Men can capture forward AND backward
  - Kings have "flying" movement (any distance)
  - Mandatory capture enforcement
  - Multi-capture sequences with instant promotion
- 🇺🇦 **Full Ukrainian Localization**
- 📦 **Containerized** with Podman
- ⚡ **Redis State Management** with TTL-based cleanup
- 🔗 **Webhook Mode** for production deployment

## Architecture

- **Engine:** Pure Python game logic (`engine.py`)
- **State:** Redis for game persistence (`repository.py`)
- **Bot:** `python-telegram-bot` v20+ async (`main.py`, `handlers.py`)
- **Infrastructure:** Podman with Nginx Proxy Manager

## Setup

### 1. Prerequisites

- Podman and Podman Compose
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Nginx Proxy Manager configured to forward `https://checkers.dobrovolskyi.xyz` to port `8787`

### 2. Configuration

Create `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and set your bot token:

```env
TOKEN=your_actual_bot_token_here
REDIS_URL=redis://redis:6379/0
PORT=8787
WEBHOOK_URL=https://checkers.dobrovolskyi.xyz
```

### 3. Build and Run

```bash
# Build containers
podman-compose build

# Start services
podman-compose up -d

# Check logs
podman-compose logs -f bot
```

### 4. Verify

1. Open Telegram
2. Find your bot
3. Send `/checkersplay`
4. Expected response:
   ```
   👋 Вітаю! Хочете зіграти в Шашки?
   
   🔴 **Виклик!**
   
   {Your Name} викликає на партію в Шашки!
   Хто зіграє за Білих (⚪)?
   
   [⚔️ До бою!]
   ```

## Game Rules

Ukrainian Checkers (Russian Drafts) follows these rules:

1. **Board:** 8x8 with dark squares playable
2. **Men:** Move forward diagonally, **capture forward AND backward**
3. **Kings:** Move and capture any distance diagonally (flying)
4. **Mandatory Capture:** Must capture if possible
5. **Multi-Capture:** Continue capturing in one turn if possible
6. **Instant Promotion:** Man becomes king immediately upon reaching far edge during a jump sequence

## Project Structure

```
checkers_bot/
├── main.py              # Application entry point
├── engine.py            # Game logic
├── handlers.py          # Telegram handlers
├── repository.py        # Redis state management
├── locales.py           # Ukrainian strings
├── requirements.txt     # Python dependencies
├── Containerfile        # Podman image definition
├── compose.yaml         # Multi-container setup
├── .env.example         # Environment template
└── .gitignore          # Git ignore rules
```

## Development

### Run Locally (without containers)

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export TOKEN=your_bot_token
export REDIS_URL=redis://localhost:6379/0
export PORT=8787
export WEBHOOK_URL=https://checkers.dobrovolskyi.xyz

# Start Redis (if not running)
redis-server

# Run bot
python main.py
```

### Testing Game Engine

```python
from engine import CheckersEngine

engine = CheckersEngine()
moves = engine.get_legal_moves(engine.current_turn)
print(f"Legal moves: {len(moves)}")
```

## Deployment

The bot runs behind Nginx Proxy Manager:

- **Public URL:** `https://checkers.dobrovolskyi.xyz/{TOKEN}`
- **Container Port:** `8787` (mapped to host)
- **Webhook Mode:** Telegram sends updates to the webhook URL

Ensure Nginx is configured to proxy traffic to `localhost:8787`.

## License

MIT

## Credits

Built by a Principal Python Engineer specializing in Containerized Systems and Game Development.
