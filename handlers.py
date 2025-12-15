"""
Telegram bot handlers for Ukrainian Checkers game.
Backward compatibility shim - GameHandlers is now in handlers.game_handlers module.
"""

# Re-export for backward compatibility
from handlers import GameHandlers

__all__ = ['GameHandlers']
