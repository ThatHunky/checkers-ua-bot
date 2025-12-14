"""
Ukrainian Checkers Telegram Bot - Main Entry Point
Supports both polling and webhook modes via USE_WEBHOOK env variable.
"""

import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    ChosenInlineResultHandler,
    ContextTypes,
)


from repository import GameRepository
from handlers import GameHandlers
from ratings import RatingSystem
from game_data import GameDataRepository
from engine import RED, WHITE

# Load environment variables
load_dotenv()

# Configuration
TOKEN = os.getenv("TOKEN")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
PORT = int(os.getenv("PORT", "8787"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://checkers.dobrovolskyi.xyz")
WEBHOOK_LISTEN = os.getenv("WEBHOOK_LISTEN", "0.0.0.0")
DB_PATH = os.getenv("DB_PATH", "/data/ratings.db")
GAMEDATA_DB_PATH = os.getenv("GAMEDATA_DB_PATH", "/data/gamedata.db")
USE_WEBHOOK = os.getenv("USE_WEBHOOK", "false").lower() == "true"
GAME_TIMEOUT_MINUTES = int(os.getenv("GAME_TIMEOUT_MINUTES", "10"))

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global references for timeout job
_repository = None
_rating_system = None


async def check_game_timeouts(context: ContextTypes.DEFAULT_TYPE):
    """Background job to check for timed out games."""
    global _repository, _rating_system

    if not _repository:
        return

    now = datetime.utcnow()
    timeout_delta = timedelta(minutes=GAME_TIMEOUT_MINUTES)

    # Check regular games (group chats, private matches)
    for chat_id, message_id, game_state in _repository.get_all_games():
        # Skip games without activity tracking (old games)
        if "last_activity" not in game_state:
            continue

        # Check if game has timed out
        last_activity = datetime.fromisoformat(game_state["last_activity"])
        if now - last_activity < timeout_delta:
            continue

        # Game timed out! Current player loses
        current_turn = game_state["current_turn"]

        if current_turn == RED:
            loser_id = game_state["red_player_id"]
            loser_name = game_state["red_player_name"]
            winner_id = game_state["white_player_id"]
            winner_name = game_state["white_player_name"]
        else:
            loser_id = game_state["white_player_id"]
            loser_name = game_state["white_player_name"]
            winner_id = game_state["red_player_id"]
            winner_name = game_state["red_player_name"]

        logger.info(
            f"Game timeout: {loser_name} loses (chat={chat_id}, msg={message_id})"
        )

        # Update ratings
        rating_msg = ""
        if _rating_system and game_state.get("move_count", 0) > 0:
            try:
                changes = await _rating_system.record_game(
                    winner_id, winner_name, loser_id, loser_name
                )
                rating_msg = (
                    f"\n\n📊 Рейтинг:\n"
                    f"{winner_name}: {changes['winner']['rating']} ({changes['winner']['change']:+d})\n"
                    f"{loser_name}: {changes['loser']['rating']} ({changes['loser']['change']:+d})"
                )
            except Exception as e:
                logger.error(f"Error updating ratings: {e}")

        # Send timeout message
        timeout_text = (
            f"⏰ Час вийшов!\n\n"
            f"🏆 {winner_name} перемагає!\n"
            f"❌ {loser_name} програв через бездіяльність.{rating_msg}"
        )

        try:
            # For private matches, update both players' messages
            if game_state.get("is_private_match"):
                try:
                    await context.bot.edit_message_text(
                        chat_id=game_state["opponent_chat_id"],
                        message_id=game_state["opponent_message_id"],
                        text=timeout_text,
                    )
                except Exception:
                    pass  # Ignore errors

                try:
                    await context.bot.edit_message_text(
                        chat_id=game_state["challenger_chat_id"],
                        message_id=game_state["challenger_message_id"],
                        text=timeout_text,
                    )
                except Exception:
                    pass  # Ignore errors
            else:
                # Regular group chat game
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id, text=timeout_text
                )
        except Exception as e:
            logger.error(f"Error sending timeout message: {e}")

        # Delete game
        _repository.delete_game(chat_id, message_id)

    # Check inline games
    inline_games = _repository.get_all_inline_games()
    logger.info(f"Checking {len(inline_games)} inline games for timeout")

    for inline_message_id, game_state in inline_games:
        # Skip games without activity tracking
        if "last_activity" not in game_state:
            logger.info(f"Inline game {inline_message_id}: no last_activity")
            continue

        # Check if game has timed out
        last_activity = datetime.fromisoformat(game_state["last_activity"])
        time_since_activity = now - last_activity
        logger.info(
            f"Inline game {inline_message_id}: {time_since_activity.total_seconds()/60:.1f} mins since activity"
        )

        if time_since_activity < timeout_delta:
            continue

        # Game timed out! Current player loses
        current_turn = game_state["current_turn"]

        if current_turn == RED:
            loser_id = game_state["red_player_id"]
            loser_name = game_state["red_player_name"]
            winner_id = game_state["white_player_id"]
            winner_name = game_state["white_player_name"]
        else:
            loser_id = game_state["white_player_id"]
            loser_name = game_state["white_player_name"]
            winner_id = game_state["red_player_id"]
            winner_name = game_state["red_player_name"]

        logger.info(
            f"Inline game timeout: {loser_name} loses (inline_msg={inline_message_id})"
        )

        # Update ratings
        rating_msg = ""
        if _rating_system and game_state.get("move_count", 0) > 0:
            try:
                changes = await _rating_system.record_game(
                    winner_id, winner_name, loser_id, loser_name
                )
                rating_msg = (
                    f"\n\n📊 Рейтинг:\n"
                    f"{winner_name}: {changes['winner']['rating']} ({changes['winner']['change']:+d})\n"
                    f"{loser_name}: {changes['loser']['rating']} ({changes['loser']['change']:+d})"
                )
            except Exception as e:
                logger.error(f"Error updating ratings: {e}")

        # Send timeout message for inline game
        timeout_text = (
            f"⏰ Час вийшов!\n\n"
            f"🏆 {winner_name} перемагає!\n"
            f"❌ {loser_name} програв через бездіяльність.{rating_msg}"
        )

        try:
            await context.bot.edit_message_text(
                inline_message_id=inline_message_id, text=timeout_text
            )
        except Exception as e:
            logger.error(f"Error sending inline timeout message: {e}")

        # Delete inline game
        _repository.delete_inline_game(inline_message_id)


async def post_init(application: Application):
    """Post-initialization callback to set commands and initialize rating system."""
    # Initialize rating system
    logger.info(f"Initializing rating system: {DB_PATH}")
    rating_system = RatingSystem(DB_PATH)
    await rating_system.initialize()
    logger.info("Rating system initialized")

    # Initialize game data repository
    logger.info(f"Initializing game data repository: {GAMEDATA_DB_PATH}")
    # If a GameDataRepository instance was already created and placed into
    # application.bot_data (from main), initialize that instance. Otherwise,
    # create and initialize a new one.
    existing_repo = application.bot_data.get("game_data_repo")
    if existing_repo and hasattr(existing_repo, "initialize"):
        try:
            await existing_repo.initialize()
            game_data_repo = existing_repo
            logger.info("Existing game data repository initialized")
        except Exception as e:
            logger.error(f"Failed to initialize existing game data repo: {e}")
            game_data_repo = GameDataRepository(GAMEDATA_DB_PATH)
            await game_data_repo.initialize()
            logger.info("New game data repository initialized")
    else:
        game_data_repo = GameDataRepository(GAMEDATA_DB_PATH)
        await game_data_repo.initialize()
        logger.info("Game data repository initialized")

    # Store in bot_data for handler access (overwrite/ensure presence)
    application.bot_data["rating_system"] = rating_system
    application.bot_data["game_data_repo"] = game_data_repo

    # Set command hints (non-fatal if rate limited)
    try:
        commands = [
            BotCommand("checkersplay", "🎮 Почати нову гру в Шашки"),
            BotCommand("checkersreplay", "📺 Історія моїх ігор"),
            BotCommand("myrating", "📊 Показати мій рейтинг"),
            BotCommand("ratings", "🏆 Таблиця лідерів"),
        ]
        await application.bot.set_my_commands(commands)
        logger.info("Command hints set successfully")
    except Exception as e:
        logger.warning(f"Could not set command hints (rate limited?): {e}")

    # Set webhook if in webhook mode (non-fatal if rate limited)
    if USE_WEBHOOK:
        try:
            # First delete webhook to drop pending updates, then set it again
            logger.info("Deleting webhook to drop pending updates...")
            await application.bot.delete_webhook(drop_pending_updates=True)
            logger.info(f"Setting webhook: {WEBHOOK_URL}/{TOKEN}")
            await application.bot.set_webhook(
                url=f"{WEBHOOK_URL}/{TOKEN}", allowed_updates=Update.ALL_TYPES
            )
            logger.info("Webhook set successfully")
        except Exception as e:
            logger.warning(f"Could not set webhook (rate limited?): {e}")


def main():
    """Start the bot."""
    # Validate configuration
    if not TOKEN:
        raise ValueError("TOKEN environment variable not set!")

    # Initialize repository
    logger.info(f"Connecting to Redis: {REDIS_URL}")
    repository = GameRepository(REDIS_URL)

    if not repository.ping():
        raise ConnectionError("Failed to connect to Redis!")

    logger.info("Redis connection successful")

    # Initialize rating system (sync creation, async init in post_init)
    rating_system = RatingSystem(DB_PATH)

    # Initialize game data repository (sync creation, async init in post_init)
    game_data_repo = GameDataRepository(GAMEDATA_DB_PATH)

    # Initialize handlers
    handlers = GameHandlers(repository, rating_system, game_data_repo)

    # Build application
    application = Application.builder().token(TOKEN).post_init(post_init).build()
    # Provide initial instances to application.bot_data so post_init can initialize them
    # instead of creating separate instances. This ensures the same GameDataRepository
    # used by handlers gets its DB initialized and is used for saving/retrieving replays.
    application.bot_data["rating_system"] = rating_system
    application.bot_data["game_data_repo"] = game_data_repo

    # Set global references for timeout job
    global _repository, _rating_system
    _repository = repository
    _rating_system = rating_system

    # Register timeout check job (runs every 60 seconds)
    application.job_queue.run_repeating(check_game_timeouts, interval=60, first=60)
    logger.info(f"Game timeout check enabled ({GAME_TIMEOUT_MINUTES} min timeout)")

    # Register command handlers
    application.add_handler(CommandHandler("start", handlers.start_bot_command))
    application.add_handler(CommandHandler("checkersplay", handlers.start_command))
    application.add_handler(CommandHandler("checkersreplay", handlers.replay_command))
    application.add_handler(CommandHandler("cancel", handlers.cancel_command))
    application.add_handler(CommandHandler("forfeit", handlers.forfeit_command))
    application.add_handler(CommandHandler("myrating", handlers.myrating_command))
    application.add_handler(CommandHandler("ratings", handlers.ratings_command))
    application.add_handler(
        CommandHandler("resetrankings", handlers.reset_rankings_command)
    )  # Hidden admin
    application.add_handler(
        CommandHandler("addlegend", handlers.add_legend_command)
    )  # Hidden arcade mode

    # Register inline query handlers
    application.add_handler(InlineQueryHandler(handlers.inline_query_handler))
    application.add_handler(
        ChosenInlineResultHandler(handlers.chosen_inline_result_handler)
    )

    # Register callback handlers
    application.add_handler(
        CallbackQueryHandler(handlers.join_callback, pattern="^join")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.cancel_invite_callback, pattern="^cancel_invite$")
    )
    application.add_handler(
        CallbackQueryHandler(
            handlers.accept_private_invite_callback, pattern="^accept_invite_"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            handlers.decline_private_invite_callback, pattern="^decline_invite_"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            handlers.confirm_cancel_callback, pattern="^confirm_cancel_"
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            handlers.confirm_forfeit_callback, pattern="^confirm_forfeit_"
        )
    )
    application.add_handler(
        CallbackQueryHandler(handlers.cancel_abort_callback, pattern="^cancel_abort$")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.select_callback, pattern="^select_")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.move_callback, pattern="^move_")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.back_callback, pattern="^back$")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.forfeit_callback, pattern="^forfeit$")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.new_game_callback, pattern="^new_game$")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.replay_game_callback, pattern="^replay_")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.noop_callback, pattern="^noop_")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.ratings_page_callback, pattern="^ratings_page_")
    )

    # Start in appropriate mode
    if USE_WEBHOOK:
        logger.info(f"Starting bot in WEBHOOK mode on {WEBHOOK_LISTEN}:{PORT}")
        logger.info(f"Webhook URL: {WEBHOOK_URL}/{TOKEN}")
        application.run_webhook(
            listen=WEBHOOK_LISTEN,
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TOKEN}",
        )
    else:
        logger.info("Starting bot in POLLING mode...")
        logger.info("Bot is ready! Send /checkersplay to start a game.")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES, drop_pending_updates=True
        )


if __name__ == "__main__":
    main()
