"""
Redis-based state management for Checkers games.
"""

import json
from typing import Optional
from datetime import datetime
import redis


class GameRepository:
    """Manages game state persistence in Redis."""
    
    def __init__(self, redis_url: str):
        """Initialize Redis connection."""
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.ttl = 3600  # 1 hour
    
    @staticmethod
    def _make_key(chat_id: int, message_id: int) -> str:
        """Generate Redis key for a game."""
        return f"checkers:game:{chat_id}:{message_id}"
    
    def save_game(self, chat_id: int, message_id: int, game_state: dict) -> bool:
        """
        Save game state to Redis.
        
        Args:
            chat_id: Telegram chat ID
            message_id: Telegram message ID
            game_state: Dictionary containing:
                - board: List[int]
                - current_turn: int
                - red_player_id: int
                - red_player_name: str
                - white_player_id: int
                - white_player_name: str
                - created_at: str (ISO format)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            key = self._make_key(chat_id, message_id)
            value = json.dumps(game_state)
            self.redis_client.setex(key, self.ttl, value)
            return True
        except Exception as e:
            print(f"Error saving game: {e}")
            return False
    
    def get_game(self, chat_id: int, message_id: int) -> Optional[dict]:
        """
        Retrieve game state from Redis.
        
        Returns:
            Game state dictionary or None if not found
        """
        try:
            key = self._make_key(chat_id, message_id)
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Error retrieving game: {e}")
            return None
    
    def delete_game(self, chat_id: int, message_id: int) -> bool:
        """
        Delete game state from Redis.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            key = self._make_key(chat_id, message_id)
            self.redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Error deleting game: {e}")
            return False
    
    def ping(self) -> bool:
        """Test Redis connection."""
        try:
            return self.redis_client.ping()
        except Exception as e:
            print(f"Redis connection error: {e}")
            return False
    
    def get_all_games(self) -> list:
        """
        Get all active game states.
        
        Returns:
            List of tuples: (chat_id, message_id, game_state)
        """
        games = []
        try:
            # Scan for all game keys
            for key in self.redis_client.scan_iter("checkers:game:*"):
                value = self.redis_client.get(key)
                if value:
                    # Parse key: checkers:game:{chat_id}:{message_id}
                    parts = key.split(":")
                    if len(parts) == 4:
                        chat_id = int(parts[2])
                        message_id = int(parts[3])
                        game_state = json.loads(value)
                        games.append((chat_id, message_id, game_state))
        except Exception as e:
            print(f"Error getting all games: {e}")
        return games

