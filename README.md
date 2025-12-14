# Telegram Бот для Українських Шашок

Легкий PvP Telegram-бот для гри в українські шашки, що працює у контейнерах Podman.

**🎮 Публічний бот доступний тут:** [`@checkers_ua_bot`](https://t.me/checkers_ua_bot)

## Можливості

- 🎮 **Правила українських шашок**
  - Прості шашки б'ють вперед І назад
  - Дамки мають "літаючу" ходу (на будь-яку відстань)
  - Обов'язкове взяття (биття)
  - Серійне взяття з миттєвим перетворенням у дамку
- 🇺🇦 **Повна українська локалізація**
- 📦 **Контейнеризація** за допомогою Podman
- ⚡ **Управління станом через Redis** з автоматичним очищенням (TTL)
- 🔗 **Режим Webhook** для розгортання у продакшн

## Архітектура

- **Рушій:** Логіка гри на чистому Python (`engine.py`)
- **Стан:** Redis для збереження даних гри (`repository.py`)
- **Бот:** `python-telegram-bot` v20+ async (`main.py`, `handlers.py`)
- **Інфраструктура:** Podman та будь-який Reverse Proxy (Nginx, Caddy тощо)

## Налаштування

### 1. Вимоги

- Podman та Podman Compose
- Токен Telegram-бота (від [@BotFather](https://t.me/BotFather))
- Зворотний проксі (Reverse Proxy), налаштований на переадресацію вашого домену на порт `8787` (або інший, вказаний у конфігурації)

### 2. Конфігурація

Створіть файл `.env`:

```bash
cp .env.example .env
```

Відредагуйте `.env` та вкажіть ваш токен:

```env
TOKEN=ваш_справжній_токен_бота
REDIS_URL=redis://redis:6379/0
PORT=8787
WEBHOOK_URL=[https://ваше-посилання.com](https://ваше-посилання.com)
```

### 3. Збірка та запуск

```bash
# Збірка контейнерів
podman-compose build

# Запуск сервісів
podman-compose up -d

```markdown
# Checkers UA — Telegram бот для українських шашок

Легкий PvP Telegram-бот для гри в українські шашки з підтримкою контейнерів (Podman/Docker), локалізації та збереження стану гри.

**🎮 Публічний бот:** [`@checkers_ua_bot`](https://t.me/checkers_ua_bot)

Документація

- Повна документація знаходиться в папці `docs/`. Почніть з `docs/index.md` для огляду та посилань на інші розділи.

Швидкий старт

1. Скопіюйте `.env.example` у `.env` та вкажіть ваш `TOKEN`:

```bash
cp .env.example .env
# Відредагуйте .env, вкажіть TELEGRAM токен і при необхідності REDIS_URL
```

2. Збірка і запуск через podman-compose (або docker-compose):

```bash
podman-compose build
podman-compose up -d
podman-compose logs -f bot
```

3. Локальний запуск (без контейнерів):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export TELEGRAM_TOKEN=ваш_токен_бота
export REDIS_URL=redis://localhost:6379/0
python main_polling.py
```

Основні можливості

- Правила українських шашок (обов'язкове взяття, «літаючі» дамки, серійні взяття)
- Українська локалізація
- Контейнерна розгортка (Podman/Docker)
- Збереження станів (через Redis або інший бекенд, залежить від `repository.py`)

Архітектура (коротко)

- `main.py`, `main_polling.py` — точки входу
- `handlers.py` — Telegram-обробники
- `engine.py` — логіка гри
- `game_data.py` — моделі стану гри
- `repository.py` — збереження стану (Redis / інше)
- `ratings.py` — оновлення рейтингу гравців
- `locales.py` — локалізація

Детальна документація

- installation.md — інструкції встановлення
- usage.md — як запускати та взаємодіяти з ботом
- architecture.md — опис архітектури
- development.md — налаштування робочого середовища
- testing.md — як запускати тести
- deployment.md — розгортання в контейнерах
- contributing.md — як робити внески
- localization.md — робота з локалізацією

Структура репозиторію

```
checkers_bot/
├── main.py
├── main_polling.py
├── engine.py
├── handlers.py
├── repository.py
├── game_data.py
├── ratings.py
├── locales.py
├── requirements.txt
├── Containerfile
├── compose.yaml
├── .env.example
└── docs/          # Додаткова документація
```

Тестування

Запустіть юніт-тести за допомогою `pytest`:

```bash
pip install -r requirements.txt
pytest -q
```

Проблеми та підтримка

Якщо виникають проблеми — перегляньте `docs/faq.md` або відкрийте issue у репозиторії з лого та кроками для відтворення.

Ліцензія

MIT

````
