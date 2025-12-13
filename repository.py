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
    
    def get_user_game(self, user_id: int) -> Optional[tuple]:
        """
        Find an active game where the user is a player.
        
        Args:
            user_id: Telegram user ID
        
        Returns:
            Tuple of (chat_id, message_id, game_state) or None if no active game
        """
        for chat_id, message_id, game_state in self.get_all_games():
            if game_state.get("red_player_id") == user_id or game_state.get("white_player_id") == user_id:
                return (chat_id, message_id, game_state)
        return None

    # ============ User Registry ============
    
    def register_user(self, user_id: int, username: Optional[str], first_name: str) -> bool:
        """
        Register or update a user in the registry.
        Called whenever a user interacts with the bot.
        
        Args:
            user_id: Telegram user ID
            username: Telegram username (without @), can be None
            first_name: User's first name
        
        Returns:
            True if successful
        """
        try:
            user_ttl = 60 * 60 * 24 * 30  # 30 days
            
            # Store user info
            user_data = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "updated_at": datetime.utcnow().isoformat()
            }
            user_key = f"checkers:user:{user_id}"
            self.redis_client.setex(user_key, user_ttl, json.dumps(user_data))
            
            # Store username -> user_id mapping (if username exists)
            if username:
                username_key = f"checkers:username:{username.lower()}"
                self.redis_client.setex(username_key, user_ttl, str(user_id))
            
            return True
        except Exception as e:
            print(f"Error registering user: {e}")
            return False
    
    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """Get user info by user ID."""
        try:
            key = f"checkers:user:{user_id}"
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Error getting user by ID: {e}")
            return None
    
    def get_user_by_username(self, username: str) -> Optional[dict]:
        """
        Get user info by username.
        
        Args:
            username: Username without @ prefix
        
        Returns:
            User data dict or None if not found
        """
        try:
            # First get user_id from username mapping
            username_key = f"checkers:username:{username.lower()}"
            user_id_str = self.redis_client.get(username_key)
            
            if not user_id_str:
                return None
            
            # Then get full user info
            return self.get_user_by_id(int(user_id_str))
        except Exception as e:
            print(f"Error getting user by username: {e}")
            return None

    # ============ Pending Invites ============
    
    def create_invite(self, invite_id: str, challenger_id: int, challenger_name: str,
                      challenger_username: Optional[str], challenger_chat_id: int, 
                      opponent_id: int, opponent_username: str) -> bool:
        """
        Create a pending game invite.
        
        Args:
            invite_id: Unique invite identifier (UUID)
            challenger_id: Telegram user ID of challenger
            challenger_name: First name of challenger
            challenger_username: Username of challenger (optional)
            challenger_chat_id: Chat ID where game will be played
            opponent_id: Telegram user ID of opponent
            opponent_username: Username of opponent
        
        Returns:
            True if successful
        """
        try:
            invite_ttl = 60 * 5  # 5 minutes
            
            invite_data = {
                "challenger_id": challenger_id,
                "challenger_name": challenger_name,
                "challenger_username": challenger_username,
                "challenger_chat_id": challenger_chat_id,
                "opponent_id": opponent_id,
                "opponent_username": opponent_username,
                "created_at": datetime.utcnow().isoformat()
            }
            
            key = f"checkers:invite:{invite_id}"
            self.redis_client.setex(key, invite_ttl, json.dumps(invite_data))
            return True
        except Exception as e:
            print(f"Error creating invite: {e}")
            return False
    
    def get_invite(self, invite_id: str) -> Optional[dict]:
        """Get pending invite by ID."""
        try:
            key = f"checkers:invite:{invite_id}"
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Error getting invite: {e}")
            return None
    
    def delete_invite(self, invite_id: str) -> bool:
        """Delete a pending invite."""
        try:
            key = f"checkers:invite:{invite_id}"
            self.redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Error deleting invite: {e}")
            return False
