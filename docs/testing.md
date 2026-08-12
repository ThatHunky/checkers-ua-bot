# Testing

The suite is **328 tests** and runs in roughly three seconds. There is no excuse for
not running it.

## Running

```bash
.venv/bin/python -m pytest -q
```

A single file, or a single test:

```bash
.venv/bin/python -m pytest tests/unit/test_engine.py -q
```

```bash
.venv/bin/python -m pytest tests/unit/test_engine_capture_rules.py -k turkish -q
```

`pytest.ini` forces coverage (`--cov=.`, terminal + `htmlcov/`). To skip it while
iterating:

```bash
.venv/bin/python -m pytest -q --no-cov
```

## Layout

```
tests/
  conftest.py          shared fixtures; also pins env vars (see below)
  unit/                pure logic — engine, locales, ranks, renderer, achievements
  integration/         handlers, repository, ratings, matchmaking, game data
  utils/               test helpers
test_engine.py         legacy root-level tests; still collected, still must pass
test_inline_challenges.py
test_inline_handler.py
test_matchmaking.py
```

`pytest.ini` sets `testpaths = tests .` so the four legacy root-level files are
collected too (299 from `tests/` + 25 from the root). `norecursedirs` keeps `.venv`,
`htmlcov`, `data` and `scripts` out.

Prefer `tests/unit/` or `tests/integration/` for new tests. The root-level files are
kept because they pass and cover real behaviour, not because the layout is good.

## Fixtures

`tests/conftest.py` pins `TOKEN`, `ADMIN_ID`, `REDIS_URL`, `DB_PATH` and friends into
`os.environ` **before** any test imports `main` or `main_polling`. Those modules call
`load_dotenv()` at import time, which would otherwise pull the developer's real `.env`
— the live bot token and the real `ADMIN_ID` — into the test process. It also means an
admin-authorization test cannot pass by accidentally matching the developer's own id.

Redis is faked with `fakeredis`, so no server is required. SQLite uses temporary files.

## What to test

- **Engine changes**: assert the board state and the move list explicitly. Ukrainian
  capture rules are subtle; derive the expectation from the rule, not from what the
  engine currently returns.
- **Engine capture changes**: `get_legal_moves()` (whole sequences) and the
  hop-by-hop UI path must agree.
  `TestInteractiveWalkMatchesEnumerator` in `tests/unit/test_engine_capture_rules.py`
  asserts exactly that; extend it rather than writing a one-off.
- **Handler changes**: build a `Mock` update/query and assert on `query.answer` and
  `bot.edit_message_text` call counts. Give mock users a real integer `id` — a `Mock`
  id makes `_is_user_blocked` bail out and the test then asserts nothing.
- **Never** write `assert x or True`. Two such no-op assertions were live in this repo
  for months and hid real failures.

## Diagnostic scripts

`scripts/diagnose_check_winner.py` is **not** a test and is not collected. Its
expectations are untriaged and some encode rules the engine deliberately does not
implement. Run it by hand for exploration; do not read a failure there as a regression
without first checking the scenario against the rules.
