# Localization

This project supports translation and localization of bot messages.

Files and modules

- `locales.py` — translation helper used by handlers to produce localized messages.
- `data/` — may contain language resources or translation files.

Adding or updating translations

1. Locate strings in `handlers.py`, `engine.py`, or other modules.
2. Add translation entries in the data files or update `locales.py` mapping.
3. Test by running the bot and switching user language settings (if supported) or simulating localized output.

Notes

- Keep translation keys stable to avoid breaking existing stored data.
- Document any new keys in `locales.py` or a dedicated translation file for translators.
