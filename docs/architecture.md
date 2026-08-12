# Architecture

How the pieces fit together, and why they are split the way they are.

## Overview

```
                    Telegram
                       │
        ┌──────────────┴──────────────┐
        │                             │
   main.py (webhook)          main_polling.py (dev)
        │                             │
        └──────────┬──────────────────┘
                   ▼
          handler_registry.py          ← single handler table
                   ▼
      handlers/game_handlers.py        ← commands + callbacks
                   │
   ┌───────────────┼───────────────┬──────────────┐
   ▼               ▼               ▼              ▼
engine.py    repository.py    ratings.py   achievements.py
 (rules)        (Redis)        (SQLite)       (SQLite)
                                    │
                              game_data.py     ← completed-game archive
```

Presentation lives in `handlers/board_renderer.py` (board text + inline keyboard) and
`handlers/message_updater.py` (editing the live message), with all strings in
`locales.py`.

## Core modules

| Module | Responsibility |
| --- | --- |
| `main.py` | Webhook entrypoint. Config, logging, timeout job, `setWebhook`. |
| `main_polling.py` | Long-polling entrypoint for development. |
| `handler_registry.py` | The command/inline/callback table, shared by both entrypoints. |
| `handlers/game_handlers.py` | `GameHandlers`: every command and callback. |
| `handlers/board_renderer.py` | Renders the board and the tappable-square keyboard. |
| `handlers/message_updater.py` | Edits game messages across group / private / inline contexts. |
| `handlers/constants.py` | `callback_data` constants and timing constants. |
| `engine.py` | `CheckersEngine`: move generation, capture rules, win detection. Pure. |
| `repository.py` | `GameRepository`: all Redis access. |
| `ratings.py` | `RatingSystem`: ELO, streaks, per-player counters (SQLite). |
| `achievements.py` | `AchievementSystem`: catalog and unlock checks (SQLite). |
| `game_data.py` | `GameDataRepository`: finished games, for replays. |
| `matchmaking.py` | Queue and invite-code logic on top of `repository.py`. |
| `ranks.py` | Maps a rating to a named rank. |
| `locales.py` | Every Ukrainian string, plus `normalize_mode()`. |
| `handlers.py` | Backward-compat shim that re-exports `GameHandlers`. |

## Two entrypoints, one handler table

`main.py` and `main_polling.py` differ only in how they receive updates. Both call
`register_handlers(application, handlers)`. They previously maintained separate copies
of the table and drifted badly enough that entire features existed in webhook mode
only; the shared table exists to make that class of bug impossible.

Handler order matters: python-telegram-bot matches `pattern` with `re.match` and
dispatches the first match in a group, so `^replaylist_` is registered before
`^replay_`, `^join$` is anchored so it cannot swallow `join_code`, and a catch-all
sits last so an unrouted button reports itself instead of hanging.

## Storage

**Redis** (`repository.py`) holds everything live and ephemeral:

| Key | Contents |
| --- | --- |
| `checkers:game:{chat_id}:{message_id}` | Active game state |
| `checkers:inline_game:{inline_message_id}` | Active inline-mode game |
| `checkers:inline_challenge:{inline_message_id}` | Pending inline challenge (5 min TTL) |
| `checkers:invite:{code}` | Private invite code |
| `checkers:user:{user_id}` / `checkers:username:{name}` | User lookup cache (30 day TTL) |
| `checkers:confirm:{token}` | One-shot confirmation tokens |
| `checkers:ratelimit:*` | Per-user rate limiting |
| `mm:ticket:{user_id}`, `mm:queue:{mode}`, `mm:match:*` | Matchmaking |

The Redis client is **synchronous** (`redis.from_url`), so every repository call from
an async handler blocks the event loop. Keep them off hot paths and put cheap rejects
before expensive ones.

**SQLite** holds everything durable: `ratings.db` (players, match history,
achievements) and `gamedata.db` (finished games for replay). Both live on the `/data`
volume in production.

## Game flow

1. A tap arrives as a `CallbackQuery`; `handler_registry` routes it by `callback_data`.
2. The handler loads `game_state` from Redis and rebuilds a `CheckersEngine` from it.
3. The engine validates and applies the move.
4. `check_winner()` runs **after** the turn is finalised.
5. If the game continues, state is written back to Redis and the message is re-rendered.
6. If it ended, `ratings.py` and `achievements.py` are updated and the game is archived
   to `game_data.py`, then removed from Redis.

## Game modes

`rated` (affects ELO), `casual`, and `practice`. The canonical spelling is `rated`;
legacy records may say `ranked`, so every read of `game_state["mode"]` goes through
`locales.normalize_mode()`, which also maps missing/unknown values to `casual` — a
game whose mode cannot be established settles **unrated**.

## Capture rules and the two paths

Ukrainian rules: captures are mandatory, the maximum-capture line must be taken, kings
fly, men capture backwards, and a captured piece stays on the board as a blocker until
the whole sequence finishes (the "Turkish strike").

The engine implements this twice, and the two must agree:

- `get_legal_moves(color)` enumerates **complete** sequences. During the search a
  captured square is set to the `CAPTURED = -1` sentinel so it blocks correctly.
- The UI walks a sequence **one hop at a time** (`get_legal_single_hop_moves`,
  `must_continue_capturing`), because each hop is a separate button press.

`apply_move` writes `EMPTY` to captured squares on the real board, so the interactive
path is handed `captured_so_far` — carried in `game_state["pending_capture"]["captured"]`
and reapplied by `board_with_sequence_blockers()`. Without it the walked line can
exceed the enumerated maximum, and a legal line can be hidden from the player.
`tests/unit/test_engine_capture_rules.py` pins both directions.

`CAPTURED` is confined to search tuples and must never reach `engine.board`, which is
serialised to Redis and rendered.

## Extending

- New command or button → add the handler method to `GameHandlers`, then one row in
  `handler_registry.py`. Both entrypoints pick it up.
- New rule → change `engine.py` only, and check both capture paths.
- New string → `locales.py`. Never inline Ukrainian text in a handler.
