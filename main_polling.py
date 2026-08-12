"""
Ukrainian Checkers Telegram Bot - Main Entry Point (POLLING MODE)
Temporary version using polling instead of webhooks for testing.
"""

import os
import logging
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

from repository import GameRepository
from handler_registry import register_handlers
from handlers import GameHandlers
from ratings import RatingSystem
from game_data import GameDataRepository

# Load environment variables
load_dotenv()

# Configuration
TOKEN = os.getenv("TOKEN")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DB_PATH = os.getenv("DB_PATH", "/data/ratings.db")
GAMEDATA_DB_PATH = os.getenv("GAMEDATA_DB_PATH", "/data/gamedata.db")

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
# See main.py: httpx logs the full Telegram API URL, which embeds the bot token.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def post_init(application: Application):
    """Post-initialization callback to set commands and initialize rating system."""
    # Initialize rating system
    logger.info(f"Initializing rating system: {DB_PATH}")
    existing_rating = application.bot_data.get("rating_system")
    if existing_rating and hasattr(existing_rating, "initialize"):
        try:
            await existing_rating.initialize()
            rating_system = existing_rating
            logger.info("Existing rating system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize existing rating system: {e}")
            rating_system = RatingSystem(DB_PATH)
            await rating_system.initialize()
    else:
        rating_system = RatingSystem(DB_PATH)
        await rating_system.initialize()
        logger.info("Rating system initialized")

    # Initialize game data repository
    logger.info(f"Initializing game data repository: {GAMEDATA_DB_PATH}")
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
    else:
        game_data_repo = GameDataRepository(GAMEDATA_DB_PATH)
        await game_data_repo.initialize()
        logger.info("Game data repository initialized")

    # Store in bot_data for handler access
    application.bot_data["rating_system"] = rating_system
    application.bot_data["game_data_repo"] = game_data_repo
    
    # Set command hints
    commands = [
        BotCommand("checkersplay", "🎮 Почати нову гру в Шашки"),
        BotCommand("checkersreplay", "📺 Історія моїх ігор"),
        BotCommand("myrating", "📊 Показати мій рейтинг"),
        BotCommand("ratings", "🏆 Таблиця лідерів"),
        BotCommand("achievements", "🏆 Показати досягнення"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Command hints set successfully")


def main():
    """Start the bot in polling mode."""
    # Validate configuration
    if not TOKEN:
        raise ValueError("TOKEN environment variable not set!")
    
    # Initialize repository
    logger.info(f"Connecting to Redis: {REDIS_URL}")
    repository = GameRepository(REDIS_URL)
    
    if not repository.ping():
        raise ConnectionError("Failed to connect to Redis!")
    
    logger.info("Redis connection successful")
    
    # Create rating system and game data repository instances (initialized in post_init)
    rating_system = RatingSystem(DB_PATH)
    game_data_repo = GameDataRepository(GAMEDATA_DB_PATH)

    # Initialize handlers
    handlers = GameHandlers(repository, rating_system, game_data_repo)
    
    # Build application
    application = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    # Expose shared instances to post_init
    application.bot_data["rating_system"] = rating_system
    application.bot_data["game_data_repo"] = game_data_repo
    
    # Register every command / inline / callback handler from the shared table,
    # so polling-mode development exercises exactly what webhook mode serves.
    register_handlers(application, handlers)

    # Start POLLING mode (no webhook needed)
    logger.info("Starting bot in POLLING mode...")
    logger.info("Bot is ready! Send /checkersplay to start a game.")
    
    # Drop pending updates from before bot started to avoid spam
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
