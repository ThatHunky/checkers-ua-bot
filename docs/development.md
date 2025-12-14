# Development

Guides for developing locally and contributing code.

Setup

1. Clone the repo and create a virtual environment:

```bash
git clone <repo_url>
cd checkers_bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. (Optional) Create `.env` with `TELEGRAM_TOKEN` and other env vars.

Running the bot locally

- Use `python main_polling.py` for development.
- Use logging output to observe handler behavior.

Code structure and style

- Keep business logic (game rules, ratings) separated from side-effect code (Telegram API calls) to make testing easier.
- Add unit tests for new logic in the `test_*.py` files.

Making changes

- Create feature branches from `main`.
- Write tests that cover the behavior you change or add.
- Run tests locally with `pytest` (see `testing.md`).

Debugging tips

- Use print/logging in handlers to trace update handling.
- Run `test_engine.py` frequently when changing rules in `engine.py` or `game_data.py`.

Dependencies

- Use `requirements.txt` to manage pinned dependencies. Run `pip freeze > requirements.txt` only when intentionally updating versions.
