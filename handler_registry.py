"""
Single source of truth for the bot's Telegram handler table.

`main.py` (webhook) and `main_polling.py` (development) previously each kept their
own hand-written copy of this list. They drifted to 47 vs 26 registrations, so
features -- including the whole inline-challenge callback payload scheme and the
in-game review pager -- existed only in webhook mode and could not be exercised in
the mode `docs/development.md` tells developers to use. Both entrypoints now call
`register_handlers`, so a handler added here is live in both.

Order matters: python-telegram-bot matches patterns with `re.match` and dispatches
the first handler in a group that matches, so more specific patterns must come
before the prefixes that would otherwise swallow them (`^replaylist_` before
`^replay_`), and the catch-all debug handler must be registered last.
"""

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChosenInlineResultHandler,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
    MessageHandler,
    filters,
)

MENU_TEXT_PATTERN = (
    "(?i)^/?menu(@\\w+)?$|^[^\\w\\s]*\\s*меню$|^меню$|^[^\\w\\s]*\\s*menu$|^menu$"
)

# (command name, handler attribute name)
COMMAND_HANDLERS = (
    ("start", "start_bot_command"),
    ("menu", "menu_command"),
    ("checkersplay", "start_command"),
    ("checkersreplay", "replay_command"),
    ("cancel", "cancel_command"),
    ("forfeit", "forfeit_command"),
    ("myrating", "myrating_command"),
    ("ratings", "ratings_command"),
    ("achievements", "achievements_command"),
    ("join", "join_command"),
    ("resetrankings", "reset_rankings_command"),   # hidden admin
    ("addlegend", "add_legend_command"),           # hidden arcade mode
    ("blockcheckers", "blockcheckers_command"),    # hidden admin
    ("unblockcheckers", "unblockcheckers_command"),# hidden admin
)

# (handler attribute name, callback_data pattern). Order is significant.
CALLBACK_HANDLERS = (
    ("inline_challenge_join_callback", "^inline_challenge_join(?::|$)"),
    # "^join$", not "^join": the loose form swallowed "join_code" before
    # menu_callback (registered below) could ever see it.
    ("join_callback", "^join$"),
    ("menu_callback", "^(menu_|play_|invite_|join_code|mm_cancel|back_to_play)"),
    ("group_invite_mode_callback", "^group_invite_(rated|casual)_\\d+$"),
    ("group_invite_join_callback", "^group_invite_join_"),
    ("group_invite_cancel_callback", "^group_invite_cancel_"),
    ("cancel_invite_callback", "^cancel_invite$"),
    ("accept_private_invite_callback", "^accept_invite_"),
    ("accept_inline_callback", "^accept_inline(?::|$)"),
    ("decline_private_invite_callback", "^decline_invite_"),
    ("confirm_cancel_callback", "^confirm_cancel_"),
    ("confirm_forfeit_callback", "^confirm_forfeit_"),
    ("abort_forfeit_callback", "^abort_forfeit_"),
    ("confirm_restart_callback", "^confirm_restart_token_"),
    ("restart_abort_callback", "^restart_abort_token_"),
    ("cancel_abort_callback", "^cancel_abort$"),
    ("select_callback", "^select_"),
    ("move_callback", "^move_"),
    ("draw_callback", "^draw_(offer|accept|decline)$"),
    ("back_callback", "^back$"),
    ("review_callback", "^review_"),
    ("forfeit_callback", "^forfeit$"),
    ("new_game_callback", "^new_game$"),
    # Must precede "^replay_" for readability; re.match makes them disjoint anyway.
    ("replay_list_page_callback", "^replaylist_"),
    ("replay_game_callback", "^replay_"),
    ("noop_callback", "^noop_"),
    ("ratings_page_callback", "^ratings_page_"),
    ("achievement_category_callback", "^ach_category_"),
    ("achievement_back_callback", "^ach_back"),
)


async def _unmatched_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all so an unrouted button reports itself instead of hanging silently."""
    query = update.callback_query
    if query:
        await query.answer("❌ Callback не розпізнано", show_alert=True)


def register_handlers(application: Application, handlers) -> None:
    """Register every command, inline and callback handler on `application`.

    `handlers` is the GameHandlers instance. Missing attributes raise immediately at
    startup rather than producing a silently dead button.
    """
    for command, attr in COMMAND_HANDLERS:
        application.add_handler(CommandHandler(command, getattr(handlers, attr)))

    application.add_handler(
        MessageHandler(filters.Regex(MENU_TEXT_PATTERN), handlers.menu_text_handler)
    )

    application.add_handler(InlineQueryHandler(handlers.inline_query_handler))
    application.add_handler(
        ChosenInlineResultHandler(handlers.chosen_inline_result_handler)
    )

    for attr, pattern in CALLBACK_HANDLERS:
        application.add_handler(
            CallbackQueryHandler(getattr(handlers, attr), pattern=pattern)
        )

    # Must be last: matches every callback_data that nothing above claimed.
    application.add_handler(CallbackQueryHandler(_unmatched_callback))
