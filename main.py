"""
Ukrainian Checkers Telegram Bot - Main Entry Point
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
PORT = int(os.getenv("PORT", "8787"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://checkers.dobrovolskyi.xyz")
DB_PATH = os.getenv("DB_PATH", "/data/ratings.db")

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def post_init(application: Application):
    """Post-initialization callback to set webhook and commands."""
    # Set command hints
    commands = [
        BotCommand("checkersplay", "🎮 Почати нову гру в Шашки"),
        BotCommand("myrating", "📊 Показати мій рейтинг"),
        BotCommand("ratings", "🏆 Таблиця лідерів")
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Command hints set successfully")
    
    # Set webhook
    logger.info(f"Setting webhook: {WEBHOOK_URL}/{TOKEN}")
    await application.bot.set_webhook(
        url=f"{WEBHOOK_URL}/{TOKEN}",
        allowed_updates=Update.ALL_TYPES
    )


async def main():
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
    
    # Initialize rating system
    logger.info(f"Initializing rating system: {DB_PATH}")
    rating_system = RatingSystem(DB_PATH)
    await rating_system.initialize()
    logger.info("Rating system initialized")
    
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
    
    # Register callback handlers
    application.add_handler(CallbackQueryHandler(handlers.join_callback, pattern="^join$"))
    application.add_handler(CallbackQueryHandler(handlers.select_callback, pattern="^select_"))
    application.add_handler(CallbackQueryHandler(handlers.move_callback, pattern="^move_"))
    application.add_handler(CallbackQueryHandler(handlers.back_callback, pattern="^back$"))
    application.add_handler(CallbackQueryHandler(handlers.forfeit_callback, pattern="^forfeit$"))
    application.add_handler(CallbackQueryHandler(handlers.new_game_callback, pattern="^new_game$"))
    
    # Start webhook
    logger.info(f"Starting webhook on 0.0.0.0:{PORT}")
    logger.info(f"Webhook URL: {WEBHOOK_URL}/{TOKEN}")
    
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
