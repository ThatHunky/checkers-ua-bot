"""
Ukrainian Checkers Telegram Bot - Main Entry Point
Supports both polling and webhook modes via USE_WEBHOOK env variable.
"""

import os
import hashlib
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, BotCommand
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


from repository import GameRepository
from handlers import GameHandlers
from ratings import RatingSystem
from game_data import GameDataRepository
from achievements import AchievementSystem
from engine import BLUE, YELLOW
from handler_registry import register_handlers
import locales

# Load environment variables
load_dotenv()

# Configuration
TOKEN = os.getenv("TOKEN")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
PORT = int(os.getenv("PORT", "8787"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://checkers.dobrovolskyi.com.ua")
WEBHOOK_LISTEN = os.getenv("WEBHOOK_LISTEN", "0.0.0.0")
DB_PATH = os.getenv("DB_PATH", "/data/ratings.db")
GAMEDATA_DB_PATH = os.getenv("GAMEDATA_DB_PATH", "/data/gamedata.db")
USE_WEBHOOK = os.getenv("USE_WEBHOOK", "false").lower() == "true"
GAME_TIMEOUT_MINUTES = int(os.getenv("GAME_TIMEOUT_MINUTES", "10"))

# Webhook authentication. Telegram echoes WEBHOOK_SECRET back in the
# X-Telegram-Bot-Api-Secret-Token header, which PTB verifies on every request;
# without it anyone who learns the URL can POST forged updates. Both values
# default to a deterministic, non-reversible derivation of the token so an
# existing deployment keeps a stable URL without new .env entries -- and so the
# bot token itself never appears in a URL, a log line, or a proxy access log.
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") or (
    hashlib.sha256(f"{TOKEN}:webhook-secret".encode()).hexdigest() if TOKEN else None
)
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH") or (
    hashlib.sha256(f"{TOKEN}:webhook-path".encode()).hexdigest()[:32] if TOKEN else "telegram"
)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# httpx logs the full request URL at INFO, and every Telegram API URL embeds the
# bot token (https://api.telegram.org/bot<TOKEN>/sendMessage). At INFO that
# writes the token to the container log on every single API call.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
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
    processed_game_keys: set[str] = set()

    # Check regular games (group chats, private matches)
    for chat_id, message_id, game_state in _repository.get_all_games():
        # Stable per-game key to prevent double-processing (private matches are stored twice in Redis).
        if (
            game_state.get("is_private_match")
            and game_state.get("challenger_chat_id")
            and game_state.get("challenger_message_id")
        ):
            game_key = f"priv:{game_state['challenger_chat_id']}:{game_state['challenger_message_id']}"
        else:
            game_key = f"chat:{chat_id}:{message_id}"

        if game_key in processed_game_keys:
            continue
        processed_game_keys.add(game_key)

        # Skip games without activity tracking (old games)
        if "last_activity" not in game_state:
            continue

        # Check if game has timed out
        try:
            last_activity = datetime.fromisoformat(game_state["last_activity"])
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Invalid last_activity format for game {chat_id}:{message_id}: {game_state.get('last_activity')}"
            )
            continue
        if now - last_activity < timeout_delta:
            continue

        # Game timed out! Current player loses
        current_turn = game_state["current_turn"]

        if current_turn == BLUE:
            loser_id = game_state["blue_player_id"]
            loser_name = game_state["blue_player_name"]
            winner_id = game_state["yellow_player_id"]
            winner_name = game_state["yellow_player_name"]
        else:
            loser_id = game_state["yellow_player_id"]
            loser_name = game_state["yellow_player_name"]
            winner_id = game_state["blue_player_id"]
            winner_name = game_state["blue_player_name"]

        logger.info(
            f"Game timeout: {loser_name} loses (chat={chat_id}, msg={message_id})"
        )

        # Update ratings (only for rated games)
        rating_msg = ""
        # Same normalization/default as every other reader of game_state["mode"]:
        # a game with no recorded mode is shown as unrated, so it settles unrated.
        mode = locales.normalize_mode(game_state.get("mode"))
        move_count = int(game_state.get("move_count", 0) or 0)
        if _rating_system and mode == "rated" and move_count > 0:
            try:
                winner_color = (
                    "yellow"
                    if winner_id == game_state.get("yellow_player_id")
                    else "blue"
                )
                winner_data, loser_data = await _rating_system.record_game(
                    winner_id,
                    winner_name,
                    loser_id,
                    loser_name,
                    game_key=game_key,
                    move_count=move_count,
                    winner_pieces_lost=None,
                    loser_pieces_lost=None,
                    winner_color=winner_color,
                )
                rating_msg = (
                    f"\n\n📊 Рейтинг:\n"
                    f"{winner_name}: {winner_data['rating']} ({winner_data['rating_change']:+d})\n"
                    f"{loser_name}: {loser_data['rating']} ({loser_data['rating_change']:+d})"
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
        if game_state.get("is_private_match"):
            try:
                _repository.delete_game(
                    game_state["opponent_chat_id"], game_state["opponent_message_id"]
                )
                _repository.delete_game(
                    game_state["challenger_chat_id"],
                    game_state["challenger_message_id"],
                )
            except Exception:
                _repository.delete_game(chat_id, message_id)
        else:
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
        try:
            last_activity = datetime.fromisoformat(game_state["last_activity"])
            time_since_activity = now - last_activity
            logger.info(
                f"Inline game {inline_message_id}: {time_since_activity.total_seconds()/60:.1f} mins since activity"
            )
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Invalid last_activity format for inline game {inline_message_id}: {game_state.get('last_activity')}"
            )
            continue

        if time_since_activity < timeout_delta:
            continue

        # Game timed out! Current player loses
        current_turn = game_state["current_turn"]

        if current_turn == BLUE:
            loser_id = game_state["blue_player_id"]
            loser_name = game_state["blue_player_name"]
            winner_id = game_state["yellow_player_id"]
            winner_name = game_state["yellow_player_name"]
        else:
            loser_id = game_state["yellow_player_id"]
            loser_name = game_state["yellow_player_name"]
            winner_id = game_state["blue_player_id"]
            winner_name = game_state["blue_player_name"]

        logger.info(
            f"Inline game timeout: {loser_name} loses (inline_msg={inline_message_id})"
        )

        # Update ratings (only for rated games)
        rating_msg = ""
        # Same normalization/default as every other reader of game_state["mode"]:
        # a game with no recorded mode is shown as unrated, so it settles unrated.
        mode = locales.normalize_mode(game_state.get("mode"))
        move_count = int(game_state.get("move_count", 0) or 0)
        if _rating_system and mode == "rated" and move_count > 0:
            try:
                game_key = f"inline:{inline_message_id}"
                winner_color = (
                    "yellow"
                    if winner_id == game_state.get("yellow_player_id")
                    else "blue"
                )
                winner_data, loser_data = await _rating_system.record_game(
                    winner_id,
                    winner_name,
                    loser_id,
                    loser_name,
                    game_key=game_key,
                    move_count=move_count,
                    winner_pieces_lost=None,
                    loser_pieces_lost=None,
                    winner_color=winner_color,
                )
                rating_msg = (
                    f"\n\n📊 Рейтинг:\n"
                    f"{winner_name}: {winner_data['rating']} ({winner_data['rating_change']:+d})\n"
                    f"{loser_name}: {loser_data['rating']} ({loser_data['rating_change']:+d})"
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
    # Get rating system from bot_data (created in main)
    rating_system = application.bot_data.get("rating_system")
    if rating_system:
        logger.info(f"Initializing rating system: {DB_PATH}")
        await rating_system.initialize()
        logger.info("Rating system initialized")

    # Get achievement system from bot_data (created in main)
    achievement_system = application.bot_data.get("achievement_system")
    if achievement_system:
        if hasattr(achievement_system, "initialize"):
            try:
                await achievement_system.initialize()
                logger.info("Achievement system initialized")
            except Exception as e:
                logger.error(f"Failed to initialize achievement system: {e}")
        else:
            logger.info("Achievement system initialized (no initialize() method)")

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
    # achievement_system is already stored in bot_data from main()
    application.bot_data["game_data_repo"] = game_data_repo

    # Set command hints (non-fatal if rate limited)
    try:
        commands = [
            BotCommand("checkersplay", "🎮 Почати нову гру в Шашки"),
            BotCommand("checkersreplay", "📺 Історія моїх ігор"),
            BotCommand("myrating", "📊 Показати мій рейтинг"),
            BotCommand("ratings", "🏆 Таблиця лідерів"),
            BotCommand("achievements", "🏆 Показати досягнення"),
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
            logger.info(f"Setting webhook: {WEBHOOK_URL}/<redacted>")
            await application.bot.set_webhook(
                url=f"{WEBHOOK_URL}/{WEBHOOK_PATH}",
                allowed_updates=Update.ALL_TYPES,
                secret_token=WEBHOOK_SECRET,
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

    # Initialize achievement system (no async init needed)
    achievement_system = AchievementSystem(DB_PATH)

    # Initialize game data repository (sync creation, async init in post_init)
    game_data_repo = GameDataRepository(GAMEDATA_DB_PATH)

    # Initialize handlers
    handlers = GameHandlers(repository, rating_system, game_data_repo)
    handlers.achievement_system = achievement_system

    # Build application
    application = Application.builder().token(TOKEN).post_init(post_init).build()
    # Provide initial instances to application.bot_data so post_init can initialize them
    # instead of creating separate instances. This ensures the same GameDataRepository
    # used by handlers gets its DB initialized and is used for saving/retrieving replays.
    application.bot_data["rating_system"] = rating_system
    application.bot_data["achievement_system"] = achievement_system
    application.bot_data["game_data_repo"] = game_data_repo

    # Set global references for timeout job
    global _repository, _rating_system
    _repository = repository
    _rating_system = rating_system

    # Register timeout check job (runs every 60 seconds)
    application.job_queue.run_repeating(check_game_timeouts, interval=60, first=60)
    application.job_queue.run_repeating(handlers.matchmaking_tick, interval=5, first=5)
    logger.info(f"Game timeout check enabled ({GAME_TIMEOUT_MINUTES} min timeout)")

    # Register every command / inline / callback handler. The table lives in
    # handler_registry so main.py and main_polling.py cannot drift apart again.
    register_handlers(application, handlers)

    # Start in appropriate mode
    if USE_WEBHOOK:
        logger.info(f"Starting bot in WEBHOOK mode on {WEBHOOK_LISTEN}:{PORT}")
        logger.info(f"Webhook URL: {WEBHOOK_URL}/<redacted>")
        application.run_webhook(
            listen=WEBHOOK_LISTEN,
            port=PORT,
            url_path=WEBHOOK_PATH,
            webhook_url=f"{WEBHOOK_URL}/{WEBHOOK_PATH}",
            secret_token=WEBHOOK_SECRET,
        )
    else:
        logger.info("Starting bot in POLLING mode...")
        logger.info("Bot is ready! Send /checkersplay to start a game.")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES, drop_pending_updates=True
        )


if __name__ == "__main__":
    main()
