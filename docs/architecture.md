# Architecture

This section describes the main components and how they interact.

Core modules

- `main.py` / `main_polling.py` — application entry points. They bootstrap the bot, load configuration, and start the event loop (webhook or polling).
- `handlers.py` — contains Telegram update handlers: commands, callback query handlers, and message processing.
- `engine.py` — the game engine implementing checkers rules, move validation, and game state transitions.
- `game_data.py` — data models and helpers for game representation (board layout, serialization/deserialization).
- `matchmaking.py` — handles the matchmaking queue logic and pairing players.
- `repository.py` — persistence layer for saving games, players, and ratings; abstracts storage details.
- `ratings.py` — rating system utilities to update player rankings after games.
- `locales.py` — localization helper for translating bot messages; used in UI/handlers.

Flow (high level)

1. A user sends a command or interacts with a button.
2. `handlers.py` dispatches the update to the appropriate function.
3. The handler uses `repository.py` to fetch or persist relevant data.
4. The handler calls `engine.py` to apply game rules and compute new state.
5. The handler formats messages (via `locales.py`) and sends updates to Telegram.
6. Ratings are updated by `ratings.py` when a game finishes.

Data formats

- Game state is stored in a compact JSON-friendly structure. See `game_data.py` for details.

Tests

- Game logic is tested in `test_engine.py` to ensure move validation and game outcomes are correct.

Extensibility

- Handlers are modular — adding new commands or interactions means adding functions to `handlers.py` and wiring them when bootstrapping.
- The repository abstraction makes it straightforward to swap storage backends (SQLite, Postgres, etc.).
