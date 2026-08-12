# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

A Telegram bot for **Ukrainian checkers** (українські шашки), live at
[@checkers_ua_bot](https://t.me/checkers_ua_bot). Python 3.11, python-telegram-bot
20.7, Redis for live game state, SQLite (aiosqlite) for ratings and achievements.

**All player-facing strings are Ukrainian.** Every user-visible string belongs in
`locales.py`, not inline in a handler. Code, comments and docs are English.

## Commands

Run tests (328 tests, ~3s):

```bash
.venv/bin/python -m pytest -q
```

Run a single test file:

```bash
.venv/bin/python -m pytest tests/unit/test_engine.py -q
```

Run the bot locally in polling mode (no webhook, no reverse proxy needed):

```bash
.venv/bin/python main_polling.py
```

Deploy (host runs Docker; Caddy is a **host** systemd service, not a container):

```bash
docker compose up -d --build
```

Tail production logs:

```bash
docker compose logs -f bot
```

## Architecture

```
main.py ─────────┐                    ┌─▶ engine.py       pure rules, no I/O
                 ├─▶ handler_registry ┤
main_polling.py ─┘   (shared table)   └─▶ handlers/game_handlers.py
                                             │
                            ┌────────────────┼────────────────┐
                            ▼                ▼                ▼
                      repository.py     ratings.py      achievements.py
                        (Redis)          (SQLite)          (SQLite)
```

| Module | Role |
| --- | --- |
| `engine.py` | Rules only: move generation, mandatory/maximum capture, flying kings, win detection. No Telegram, no I/O. |
| `handlers/game_handlers.py` | Every command and callback (~5.7k lines). The bulk of the app. |
| `handlers/board_renderer.py` | Board text + inline keyboard. Decides which squares are tappable. |
| `handlers/message_updater.py` | Edits live game messages (group, private, inline). |
| `handler_registry.py` | **The** handler table. Both entrypoints call `register_handlers`. |
| `repository.py` | Redis: live games, inline games, challenges, matchmaking, confirm tokens. |
| `ratings.py` | ELO, streaks, per-player counters. |
| `achievements.py` | Achievement catalog + unlock checks. |
| `game_data.py` | Completed-game archive for `/checkersreplay`. |
| `locales.py` | All Ukrainian strings + `normalize_mode`. |
| `handlers.py` | Backward-compat shim re-exporting `GameHandlers`. Do not add code here. |

`main.py` is webhook mode (production), `main_polling.py` is polling (development).
They differ **only** in startup; handlers come from `handler_registry.py`.

## Things that will bite you

**Add handlers to `handler_registry.py`, never to an entrypoint.** The two
entrypoints previously kept separate copies and drifted to 47 vs 26 registrations —
whole features were dead in polling mode. One table now, used by both.

**Every message is `parse_mode=HTML`.** Telegram display names are attacker-controlled
and a name containing `<` or `&` makes the whole send fail with `BadRequest: Can't
parse entities`. Wrap user-controlled text in `html.escape()` **at the render site**,
never at storage — the same names are also sent to plain-text messages and to inline
button labels, where escaping would show literal `&amp;`.

**The engine has two capture paths and they must agree.**
`get_legal_moves()` enumerates whole sequences; the UI walks them one hop at a time
via `get_legal_single_hop_moves()` / `must_continue_capturing()`. Under the Turkish
strike rule a captured piece stays on the board as a blocker until the sequence ends,
which the search models with the `CAPTURED = -1` sentinel. `apply_move` writes `EMPTY`,
so the interactive path must be handed `captured_so_far` (carried in
`game_state["pending_capture"]["captured"]`) or it silently plays different rules than
the move list advertises. `tests/unit/test_engine_capture_rules.py` pins this.

**`CAPTURED` must never reach a real board.** It lives only in search tuples. Anything
that reads `engine.board` assumes values in `{0,1,2,3,4}`.

**`check_winner()` only checks the side to move.** A player loses when *they* have no
move on *their* turn — checking the idle side ends the game a ply early. It is called
once, in `move_callback`, after the turn is finalised.

**Redis calls are synchronous** (`redis.from_url`, not `redis.asyncio`) inside async
handlers, so every repository call blocks the event loop. Don't add gratuitous ones on
hot paths; put cheap rejects before expensive work.

**`locales.normalize_mode()` on every read of `game_state["mode"]`.** Legacy rows say
`"ranked"`; canonical is `"rated"`. Unknown/missing normalises to `"casual"` (unrated),
which is the safe default — never settle a rating on a guess.

**Callback payloads are capped at 64 bytes** by Telegram, and buttons live forever in
chat history. Anything reconstructed from a payload alone (see
`_build_inline_challenge_from_callback_payload`) is deliberately forced unrated: the
payload has no timestamp, so a months-old button is indistinguishable from a fresh one.

**`compose.yaml` bind-mounts the repo at `/app`.** The running container executes the
working tree, not the image, so `.dockerignore` does not protect the container — and
a `git pull` changes live code without a rebuild.

## Conventions

- Comments explain **why**, not what. The existing code does this well — match it.
- New tests go under `tests/unit/` or `tests/integration/`. Root-level `test_*.py`
  files are legacy but are collected and must keep passing.
- `scripts/` holds non-pytest tooling. `scripts/diagnose_check_winner.py` is an
  exploratory script whose expectations are **untriaged** — a failure there is not
  automatically a regression.
- `scripts/reset_database.py` is parsed at startup by `achievements.py` to load the
  100-entry achievement catalog. Keep `achievements = [...]` a plain literal.
- Never commit `.env`, `*.db`, `.coverage`, or `.specstory/` — all git-ignored.
- Secrets never go in a URL or a log line. `httpx`/`httpcore` are pinned to WARNING
  because they log full Telegram API URLs, which embed the bot token.

## Verifying a change

Tests are fast; run them. For anything touching the engine, also confirm the two
capture paths still agree — `TestInteractiveWalkMatchesEnumerator` covers this. For
handler changes, remember polling and webhook now share one table, so testing under
`main_polling.py` is representative.
