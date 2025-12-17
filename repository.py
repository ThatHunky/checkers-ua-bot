"""
Redis-based state management for Checkers games.
"""

import json
import logging
from typing import Optional, Any, Dict
from datetime import datetime
import redis
from redis.exceptions import ResponseError

logger = logging.getLogger(__name__)


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
                - blue_player_id: int
                - blue_player_name: str
                - yellow_player_id: int
                - yellow_player_name: str
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
            logger.error(f"Error saving game: {e}")
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
            logger.error(f"Error retrieving game: {e}")
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
            logger.error(f"Error deleting game: {e}")
            return False
    
    def ping(self) -> bool:
        """Test Redis connection."""
        try:
            return self.redis_client.ping()
        except Exception as e:
            logger.error(f"Redis connection error: {e}")
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
            logger.error(f"Error getting all games: {e}")
        return games
    
    def get_all_inline_games(self) -> list:
        """
        Get all active inline game states.
        
        Returns:
            List of tuples: (inline_message_id, game_state)
        """
        games = []
        try:
            # Scan for all inline game keys
            for key in self.redis_client.scan_iter("checkers:inline_game:*"):
                value = self.redis_client.get(key)
                if value:
                    # Parse key: checkers:inline_game:{inline_message_id}
                    parts = key.split(":")
                    if len(parts) == 3:
                        inline_message_id = parts[2]
                        game_state = json.loads(value)
                        games.append((inline_message_id, game_state))
        except Exception as e:
            logger.error(f"Error getting all inline games: {e}")
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
            if game_state.get("blue_player_id") == user_id or game_state.get("yellow_player_id") == user_id:
                return (chat_id, message_id, game_state)
        return None

    def get_user_inline_game(self, user_id: int) -> Optional[tuple]:
        """
        Find an active inline game where the user is a player.

        Returns:
            Tuple of (inline_message_id, game_state) or None if no active inline game
        """
        for inline_message_id, game_state in self.get_all_inline_games():
            if game_state.get("blue_player_id") == user_id or game_state.get("yellow_player_id") == user_id:
                return (inline_message_id, game_state)
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
            logger.error(f"Error registering user: {e}")
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
            logger.error(f"Error getting user by ID: {e}")
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
            logger.error(f"Error getting user by username: {e}")
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
            logger.error(f"Error creating invite: {e}")
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
            logger.error(f"Error getting invite: {e}")
            return None
    
    def delete_invite(self, invite_id: str) -> bool:
        """Delete a pending invite."""
        try:
            key = f"checkers:invite:{invite_id}"
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting invite: {e}")
            return False
    
    # ============ Flood Control ============
    
    def check_rate_limit(self, user_id: int, action: str, max_actions: int = 5, window_seconds: int = 60):
        """
        Check if user has exceeded rate limit for an action.
        
        Args:
            user_id: Telegram user ID
            action: Action type (e.g., 'invite', 'command')
            max_actions: Maximum number of actions allowed in the window
            window_seconds: Time window in seconds
        
        Returns:
            Tuple of (is_allowed, remaining_actions)
        """
        try:
            key = f"checkers:ratelimit:{action}:{user_id}"
            current_count = self.redis_client.get(key)
            
            if current_count is None:
                # First action in this window
                self.redis_client.setex(key, window_seconds, "1")
                return (True, max_actions - 1)
            
            count = int(current_count)
            
            if count >= max_actions:
                # Rate limit exceeded
                ttl = self.redis_client.ttl(key)
                return (False, 0)
            
            # Increment counter
            self.redis_client.incr(key)
            remaining = max_actions - count - 1
            return (True, remaining)
        except Exception as e:
            logger.warning(f"Error checking rate limit: {e}")
            # On error, allow the action
            return (True, max_actions)
    
    def reset_rate_limit(self, user_id: int, action: str) -> bool:
        """Reset rate limit for a user and action."""
        try:
            key = f"checkers:ratelimit:{action}:{user_id}"
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error resetting rate limit: {e}")
            return False

    # ============ Confirmation Tokens ============

    @staticmethod
    def _make_confirm_key(token: str) -> str:
        """Generate Redis key for a short-lived confirmation token."""
        return f"checkers:confirm:{token}"

    def save_confirm_token(self, token: str, payload: Dict[str, Any], ttl_seconds: int = 300) -> bool:
        """Save a short-lived confirmation payload."""
        try:
            key = self._make_confirm_key(token)
            self.redis_client.setex(key, int(ttl_seconds), json.dumps(payload))
            return True
        except Exception as e:
            logger.error(f"Error saving confirm token: {e}")
            return False

    def get_confirm_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Retrieve a confirmation payload by token."""
        try:
            key = self._make_confirm_key(token)
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting confirm token: {e}")
            return None

    def delete_confirm_token(self, token: str) -> bool:
        """Delete a confirmation token."""
        try:
            key = self._make_confirm_key(token)
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting confirm token: {e}")
            return False

    # ============ Inline Game Storage ============
    
    @staticmethod
    def _make_inline_key(inline_message_id: str) -> str:
        """Generate Redis key for an inline message game."""
        return f"checkers:inline_game:{inline_message_id}"

    def save_inline_game(self, inline_message_id: str, game_state: dict) -> bool:
        """Save game state for inline message."""
        try:
            key = self._make_inline_key(inline_message_id)
            value = json.dumps(game_state)
            self.redis_client.setex(key, self.ttl, value)
            return True
        except Exception as e:
            logger.error(f"Error saving inline game: {e}")
            return False

    def get_inline_game(self, inline_message_id: str) -> Optional[dict]:
        """Get game state for inline message."""
        try:
            key = self._make_inline_key(inline_message_id)
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting inline game: {e}")
            return None

    def delete_inline_game(self, inline_message_id: str) -> bool:
        """Delete inline game state."""
        try:
            key = self._make_inline_key(inline_message_id)
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting inline game: {e}")
            return False

    def get_inline_challenge(self, inline_message_id: str) -> Optional[dict]:
        """Get inline challenge data."""
        try:
            key = f"checkers:inline_challenge:{inline_message_id}"
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting inline challenge: {e}")
            return None

    def save_inline_challenge(self, inline_message_id: str, challenge_data: dict) -> bool:
        """Save inline challenge data."""
        try:
            challenge_ttl = 60 * 5  # 5 minutes
            key = f"checkers:inline_challenge:{inline_message_id}"
            value = json.dumps(challenge_data)
            self.redis_client.setex(key, challenge_ttl, value)
            return True
        except Exception as e:
            logger.error(f"Error saving inline challenge: {e}")
            return False

    def delete_inline_challenge(self, inline_message_id: str) -> bool:
        """Delete inline challenge."""
        try:
            key = f"checkers:inline_challenge:{inline_message_id}"
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting inline challenge: {e}")
            return False

    # ============ Matchmaking ============

    def get_user_rating(self, user_id: int, default: int = 1200) -> int:
        """Retrieve cached rating stored in a ticket, fallback to default."""
        ticket = self.redis_client.hgetall(f"mm:ticket:{user_id}")
        if ticket and ticket.get("rating"):
            try:
                return int(float(ticket["rating"]))
            except (TypeError, ValueError):
                return default
        return default

    def mm_enqueue(self, user_id: int, chat_id: int, mode: str, rating: int) -> dict:
        """Add user to matchmaking queue. Returns ticket data."""
        now = datetime.utcnow().isoformat()
        ticket_key = f"mm:ticket:{user_id}"
        queue_key = f"mm:queue:{mode}"

        existing = self.redis_client.hgetall(ticket_key)
        if existing and existing.get("status") == "queued":
            # Normalize return shape for callers/tests.
            return {**existing, "user_id": user_id}

        # Store strings in Redis, but return typed values to callers.
        ticket_store = {
            "user_id": str(user_id),
            "mode": mode,
            "chat_id": str(chat_id),
            "created_at": now,
            "rating": str(rating),
            "status": "queued",
        }

        pipe = self.redis_client.pipeline()
        pipe.hset(ticket_key, mapping=ticket_store)
        pipe.expire(ticket_key, 900)
        pipe.zadd(queue_key, {user_id: rating})
        pipe.execute()
        return {**ticket_store, "user_id": user_id, "chat_id": chat_id, "rating": rating}

    def mm_cancel(self, user_id: int) -> bool:
        """Cancel matchmaking for a user if queued."""
        ticket_key = f"mm:ticket:{user_id}"
        ticket = self.redis_client.hgetall(ticket_key)
        if not ticket:
            return False

        if ticket.get("status") != "queued":
            self.redis_client.hset(ticket_key, "status", "cancelled")
            return False

        queue_key = f"mm:queue:{ticket['mode']}"
        pipe = self.redis_client.pipeline()
        pipe.zrem(queue_key, user_id)
        pipe.hset(ticket_key, "status", "cancelled")
        pipe.expire(ticket_key, 300)
        pipe.execute()
        return True

    def mm_status(self, user_id: int) -> Optional[dict]:
        """Return current matchmaking ticket if present."""
        ticket = self.redis_client.hgetall(f"mm:ticket:{user_id}")
        return ticket or None

    def mm_cleanup_user(self, user_id: int):
        """Remove user from queue and expire ticket."""
        ticket = self.redis_client.hgetall(f"mm:ticket:{user_id}")
        if not ticket:
            return
        queue_key = f"mm:queue:{ticket.get('mode', 'rated')}"
        pipe = self.redis_client.pipeline()
        pipe.zrem(queue_key, user_id)
        pipe.delete(f"mm:ticket:{user_id}")
        pipe.execute()

    def mm_try_match(
        self,
        mode: str,
        base_delta: int = 50,
        step: int = 50,
        step_seconds: int = 10,
        max_delta: int = 400,
    ):
        """Try to find and atomically pair two users."""
        queue_key = f"mm:queue:{mode}"
        now = datetime.utcnow()

        members = self.redis_client.zrange(queue_key, 0, -1, withscores=True)
        best_pair = None
        best_diff = None

        tickets = {}
        for user_str, score in members:
            user_id = int(user_str)
            ticket = self.redis_client.hgetall(f"mm:ticket:{user_id}")
            if not ticket or ticket.get("status") != "queued":
                continue
            tickets[user_id] = {**ticket, "rating": float(score)}

        user_ids = list(tickets.keys())
        for i, uid in enumerate(user_ids):
            t1 = tickets[uid]
            created_at = datetime.fromisoformat(t1["created_at"])
            wait_sec = (now - created_at).total_seconds()
            allowed = min(max_delta, base_delta + int(wait_sec // step_seconds) * step)
            for uid2 in user_ids[i + 1 :]:
                t2 = tickets[uid2]
                diff = abs(t1["rating"] - t2["rating"])
                if diff <= allowed:
                    if best_diff is None or diff < best_diff:
                        best_diff = diff
                        best_pair = (uid, uid2)

        if not best_pair:
            return None

        uid_a, uid_b = best_pair
        match_id = f"match:{uid_a}:{uid_b}:{int(now.timestamp())}"
        ticket_a_key = f"mm:ticket:{uid_a}"
        ticket_b_key = f"mm:ticket:{uid_b}"
        match_key = f"mm:match:{match_id}"

        script = """
        local queue = KEYS[1]
        local ticket_a = KEYS[2]
        local ticket_b = KEYS[3]
        local match_key = KEYS[4]

        local user_a = ARGV[1]
        local user_b = ARGV[2]
        local mode = ARGV[3]
        local created_at = ARGV[4]

        if redis.call('hget', ticket_a, 'status') ~= 'queued' then
            return nil
        end
        if redis.call('hget', ticket_b, 'status') ~= 'queued' then
            return nil
        end
        if not redis.call('zscore', queue, user_a) then
            return nil
        end
        if not redis.call('zscore', queue, user_b) then
            return nil
        end

        redis.call('zrem', queue, user_a, user_b)
        redis.call('hset', ticket_a, 'status', 'matched', 'opponent', user_b, 'match_id', match_key)
        redis.call('hset', ticket_b, 'status', 'matched', 'opponent', user_a, 'match_id', match_key)
        redis.call('hmset', match_key,
            'user_a', user_a,
            'user_b', user_b,
            'mode', mode,
            'created_at', created_at)
        redis.call('expire', match_key, 120)
        return {user_a, user_b, match_key}
        """

        try:
            result = self.redis_client.eval(
                script,
                4,
                queue_key,
                ticket_a_key,
                ticket_b_key,
                match_key,
                str(uid_a),
                str(uid_b),
                mode,
                now.isoformat(),
            )
        except ResponseError:
            # Fallback path for Redis backends without scripting (e.g., fakeredis)
            if (
                tickets.get(uid_a, {}).get("status") != "queued"
                or tickets.get(uid_b, {}).get("status") != "queued"
            ):
                return None
            pipe = self.redis_client.pipeline()
            pipe.zrem(queue_key, uid_a, uid_b)
            pipe.hset(ticket_a_key, mapping={"status": "matched", "opponent": uid_b, "match_id": match_key})
            pipe.hset(ticket_b_key, mapping={"status": "matched", "opponent": uid_a, "match_id": match_key})
            pipe.hset(match_key, mapping={"user_a": uid_a, "user_b": uid_b, "mode": mode, "created_at": now.isoformat()})
            pipe.expire(match_key, 120)
            pipe.execute()
            result = [str(uid_a), str(uid_b), match_key]

        if not result:
            return None

        return {
            "users": [
                {**tickets.get(uid_a, {}), "user_id": uid_a},
                {**tickets.get(uid_b, {}), "user_id": uid_b},
            ],
            "match_id": match_key,
            "mode": mode,
        }

    def mm_create_invite(
        self,
        user_id: int,
        chat_id: int,
        mode: str,
        code: str,
        creator_username: Optional[str] = None,
        creator_first_name: Optional[str] = None,
    ):
        """Create an invite code entry."""
        key = f"mm:invite:{code}"
        data = {
            "code": code,
            "creator_user_id": str(user_id),
            "creator_chat_id": str(chat_id),
            "mode": mode,
            "created_at": datetime.utcnow().isoformat(),
            "status": "open",
            "creator_username": creator_username or "",
            "creator_first_name": creator_first_name or "",
        }
        self.redis_client.hset(key, mapping=data)
        self.redis_client.expire(key, 1800)
        return data

    def mm_accept_invite(self, user_id: int, chat_id: int, code: str):
        """Accept an invite if available, return pairing info."""
        key = f"mm:invite:{code}"
        invite = self.redis_client.hgetall(key)
        if not invite or invite.get("status") != "open":
            return None

        script = """
        local invite_key = KEYS[1]
        local status = redis.call('hget', invite_key, 'status')
        if status ~= 'open' then
            return nil
        end
        redis.call('hset', invite_key, 'status', 'used', 'opponent_user_id', ARGV[1], 'opponent_chat_id', ARGV[2])
        redis.call('expire', invite_key, 600)
        return redis.call('hgetall', invite_key)
        """
        try:
            result = self.redis_client.eval(script, 1, key, str(user_id), str(chat_id))
        except ResponseError:
            status = self.redis_client.hget(key, "status")
            if status != "open":
                return None
            pipe = self.redis_client.pipeline()
            pipe.hset(key, mapping={"status": "used", "opponent_user_id": user_id, "opponent_chat_id": chat_id})
            pipe.expire(key, 600)
            pipe.execute()
            result = self.redis_client.hgetall(key)
        if not result:
            return None

        if isinstance(result, dict):
            return result

        data = {result[i]: result[i + 1] for i in range(0, len(result), 2)}
        return data

    def mm_get_invite(self, code: str) -> Optional[dict]:
        """Fetch invite metadata by code."""
        key = f"mm:invite:{code}"
        invite = self.redis_client.hgetall(key)
        return invite or None

    def mm_cancel_invite(self, code: str) -> bool:
        """Cancel an open invite."""
        key = f"mm:invite:{code}"
        invite = self.redis_client.hgetall(key)
        if not invite:
            return False
        if invite.get("status") != "open":
            return False
        self.redis_client.hset(key, mapping={"status": "cancelled"})
        self.redis_client.expire(key, 300)
        return True