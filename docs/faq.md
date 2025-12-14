# FAQ & Troubleshooting

Q: The bot doesn't respond after starting. What should I check?

- Verify `TELEGRAM_TOKEN` is set and valid.
- Check network connectivity and that outbound requests to Telegram are allowed.
- Inspect logs for exceptions: `podman logs -f <container-name>` or local console output.

Q: Tests are failing after I change `engine.py`.

- Run `pytest -q` to see failing tests.
- Add or update unit tests in `test_engine.py` to reflect intended behavior.

Q: How do I add a new command or button?

- Add a handler in `handlers.py` and wire it in the bot initialization (see `main.py`/`main_polling.py`).
- Add localized text in `locales.py` if needed.

Q: Where is game state stored?

- The repository layer (`repository.py`) abstracts storage. By default it may use a local file or SQLite; check implementation for details.

If you can't resolve an issue, open an issue in the repository with logs and steps to reproduce.
