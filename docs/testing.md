# Testing

This repository includes unit tests for the game engine and related logic.

Run tests

With the virtualenv active:

```bash
pip install -r requirements.txt
pytest -q
```

Test files

- `test_engine.py` — tests covering move validation and game outcomes.

Writing tests

- Prefer unit tests for deterministic logic (e.g., `engine.py`, `game_data.py`).
- Use small, focused test cases that assert expected board states and move results.

Continuous testing

- Add tests for any bug fixes and feature additions.
- Ensure tests pass locally before opening a pull request.
