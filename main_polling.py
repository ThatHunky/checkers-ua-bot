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
from handlers import GameHandlers
from ratings import RatingSystem

# Load environment variables
load_dotenv()

# Configuration
TOKEN = os.getenv("TOKEN")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DB_PATH = os.getenv("DB_PATH", "/data/ratings.db")

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def post_init(application: Application):
    """Post-initialization callback to set commands and initialize rating system."""
    # Initialize rating system
    logger.info(f"Initializing rating system: {DB_PATH}")
    rating_system = RatingSystem(DB_PATH)
    await rating_system.initialize()
    logger.info("Rating system initialized")
    
    # Store in bot_data for handler access
    application.bot_data["rating_system"] = rating_system
    
    # Set command hints
    commands = [
        BotCommand("checkersplay", "🎮 Почати нову гру в Шашки"),
        BotCommand("myrating", "📊 Показати мій рейтинг"),
        BotCommand("ratings", "🏆 Таблиця лідерів")
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
    
    # Create rating system instance (initialized in post_init)
    rating_system = RatingSystem(DB_PATH)
    
    # Initialize handlers
    handlers = GameHandlers(repository, rating_system)
    
    # Build application
    application = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )
    
    # Register command handlers
    application.add_handler(CommandHandler("checkersplay", handlers.start_command))
    application.add_handler(CommandHandler("myrating", handlers.myrating_command))
    application.add_handler(CommandHandler("ratings", handlers.ratings_command))
    application.add_handler(CommandHandler("resetrankings", handlers.reset_rankings_command))  # Hidden admin command
    application.add_handler(CommandHandler("addlegend", handlers.add_legend_command))  # Hidden arcade mode command
    
    # Register callback handlers
    application.add_handler(CallbackQueryHandler(handlers.join_callback, pattern="^join$"))
    application.add_handler(CallbackQueryHandler(handlers.cancel_invite_callback, pattern="^cancel_invite$"))
    application.add_handler(CallbackQueryHandler(handlers.select_callback, pattern="^select_"))
    application.add_handler(CallbackQueryHandler(handlers.move_callback, pattern="^move_"))
    application.add_handler(CallbackQueryHandler(handlers.back_callback, pattern="^back$"))
    application.add_handler(CallbackQueryHandler(handlers.forfeit_callback, pattern="^forfeit$"))
    application.add_handler(CallbackQueryHandler(handlers.new_game_callback, pattern="^new_game$"))
    application.add_handler(CallbackQueryHandler(handlers.noop_callback, pattern="^noop_"))
    application.add_handler(CallbackQueryHandler(handlers.ratings_page_callback, pattern="^ratings_page_"))
    
    # Start POLLING mode (no webhook needed)
    logger.info("Starting bot in POLLING mode...")
    logger.info("Bot is ready! Send /checkersplay to start a game.")
    
    # Drop pending updates from before bot started to avoid spam
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
