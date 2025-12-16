"""
SQLite-based repository for completed game data persistence.
Stores game replays alongside ratings.db for long-term storage.
"""

import sqlite3
import json
from typing import Optional, List, Dict, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class GameDataRepository:
    """Manages completed game data persistence in SQLite."""
    
    def __init__(self, db_path: str):
        """
        Initialize repository with database path.
        
        Args:
            db_path: Path to SQLite database file (e.g., /data/gamedata.db)
        """
        self.db_path = db_path
        
    async def initialize(self):
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Completed games table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS completed_games (
                game_id TEXT PRIMARY KEY,
                blue_player_id INTEGER NOT NULL,
                blue_player_name TEXT NOT NULL,
                yellow_player_id INTEGER NOT NULL,
                yellow_player_name TEXT NOT NULL,
                winner_id INTEGER NOT NULL,
                winner_name TEXT NOT NULL,
                winner_color TEXT NOT NULL,
                initial_board TEXT NOT NULL,
                move_history TEXT NOT NULL,
                final_board TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # User-to-game mapping table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_games (
                user_id INTEGER NOT NULL,
                game_id TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                PRIMARY KEY (user_id, game_id),
                FOREIGN KEY (game_id) REFERENCES completed_games(game_id)
            )
        """)
        
        # Index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_games_user_time 
            ON user_games(user_id, completed_at DESC)
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Game data database initialized at {self.db_path}")
    
    def save_completed_game(self, game_data: Dict) -> bool:
        """
        Save a completed game with validation and transaction handling.
        
        Args:
            game_data: Dictionary containing game info and move history
            
        Returns:
            True if successful
        """
        # Validate game data before attempting save
        is_valid, error_msg = self._validate_game_data(game_data)
        if not is_valid:
            logger.error(
                f"Game data validation failed for game {game_data.get('game_id', 'unknown')}: {error_msg}"
            )
            return False
        
        game_id = game_data.get("game_id", "unknown")
        logger.debug(f"Attempting to save game {game_id}")
        
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Serialize JSON fields before database write
            try:
                initial_board_json = json.dumps(game_data["initial_board"])
                move_history_json = json.dumps(game_data["move_history"])
                final_board_json = json.dumps(game_data["final_board"])
            except (TypeError, ValueError) as e:
                logger.error(
                    f"JSON serialization failed for game {game_id}: {type(e).__name__}: {e}"
                )
                return False
            
            # Use explicit transaction
            cursor.execute("BEGIN TRANSACTION")
            
            cursor.execute("""
                INSERT OR REPLACE INTO completed_games 
                (game_id, blue_player_id, blue_player_name, yellow_player_id, 
                 yellow_player_name, winner_id, winner_name, winner_color,
                 initial_board, move_history, final_board, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game_data["game_id"],
                game_data["blue_player_id"],
                game_data["blue_player_name"],
                game_data["yellow_player_id"],
                game_data["yellow_player_name"],
                game_data["winner_id"],
                game_data["winner_name"],
                game_data["winner_color"],
                initial_board_json,
                move_history_json,
                final_board_json,
                game_data["completed_at"]
            ))
            
            # Verify row was inserted/updated
            if cursor.rowcount == 0:
                logger.warning(f"No rows affected when saving game {game_id}")
                conn.rollback()
                conn.close()
                return False
            
            # Commit transaction
            conn.commit()
            conn.close()
            conn = None
            
            logger.debug(f"Successfully saved game {game_id}")
            return True
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                    conn.close()
                except Exception:
                    pass
            logger.error(
                f"Error saving completed game {game_id}: {type(e).__name__}: {e}",
                exc_info=True
            )
            return False
    
    def get_completed_game(self, game_id: str) -> Optional[Dict]:
        """
        Retrieve a completed game by ID.
        
        Args:
            game_id: Unique game identifier
            
        Returns:
            Game data dictionary or None if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM completed_games WHERE game_id = ?
            """, (game_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            # Parse JSON fields with specific error handling
            try:
                initial_board = json.loads(row["initial_board"])
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(
                    f"Error parsing initial_board JSON for game {game_id}: "
                    f"{type(e).__name__}: {e}. Raw data: {row['initial_board'][:100]}"
                )
                raise
            
            try:
                move_history = json.loads(row["move_history"])
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(
                    f"Error parsing move_history JSON for game {game_id}: "
                    f"{type(e).__name__}: {e}. Raw data: {row['move_history'][:100]}"
                )
                raise
            
            try:
                final_board = json.loads(row["final_board"])
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(
                    f"Error parsing final_board JSON for game {game_id}: "
                    f"{type(e).__name__}: {e}. Raw data: {row['final_board'][:100]}"
                )
                raise
            
            return {
                "game_id": row["game_id"],
                "blue_player_id": row["blue_player_id"],
                "blue_player_name": row["blue_player_name"],
                "yellow_player_id": row["yellow_player_id"],
                "yellow_player_name": row["yellow_player_name"],
                "winner_id": row["winner_id"],
                "winner_name": row["winner_name"],
                "winner_color": row["winner_color"],
                "initial_board": initial_board,
                "move_history": move_history,
                "final_board": final_board,
                "completed_at": row["completed_at"]
            }
        except KeyError as e:
            logger.error(
                f"Error retrieving game {game_id}: Missing column {e}. "
                f"Database schema may be out of date."
            )
            return None
        except Exception as e:
            logger.error(
                f"Error retrieving game {game_id}: {type(e).__name__}: {e}",
                exc_info=True
            )
            return None
    
    def add_user_game_reference(self, user_id: int, game_id: str, completed_at: str) -> bool:
        """
        Link a game to a user's history.
        
        Args:
            user_id: Telegram user ID
            game_id: Unique game identifier
            completed_at: ISO format timestamp
            
        Returns:
            True if successful
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR IGNORE INTO user_games (user_id, game_id, completed_at)
                VALUES (?, ?, ?)
            """, (user_id, game_id, completed_at))
            
            # Keep only last 50 games per user
            cursor.execute("""
                DELETE FROM user_games
                WHERE user_id = ? AND game_id NOT IN (
                    SELECT game_id FROM user_games
                    WHERE user_id = ?
                    ORDER BY completed_at DESC
                    LIMIT 50
                )
            """, (user_id, user_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(
                f"Error adding user game reference for user {user_id}, game {game_id}: "
                f"{type(e).__name__}: {e}",
                exc_info=True
            )
            return False
    
    def get_user_completed_games(self, user_id: int, limit: int = 10) -> List[str]:
        """
        Get list of game IDs for a user (most recent first).
        
        Args:
            user_id: Telegram user ID
            limit: Maximum number of games to return
            
        Returns:
            List of game_id strings
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT game_id FROM user_games
                WHERE user_id = ?
                ORDER BY completed_at DESC
                LIMIT ?
            """, (user_id, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            return [row[0] for row in rows]
        except Exception as e:
            logger.error(
                f"Error getting user games for user {user_id}: {type(e).__name__}: {e}",
                exc_info=True
            )
            return []
    
    def _validate_game_data(self, game_data: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate game data before saving. Returns (is_valid, error_message).
        
        Args:
            game_data: Dictionary containing game info and move history
            
        Returns:
            Tuple of (is_valid, error_message). error_message is None if valid.
        """
        required_fields = [
            "game_id", "blue_player_id", "blue_player_name",
            "yellow_player_id", "yellow_player_name", "winner_id",
            "winner_name", "winner_color", "initial_board",
            "move_history", "final_board", "completed_at"
        ]
        
        for field in required_fields:
            if field not in game_data:
                return False, f"Missing required field: {field}"
        
        # Validate JSON serializable
        try:
            json.dumps(game_data["initial_board"])
            json.dumps(game_data["move_history"])
            json.dumps(game_data["final_board"])
        except (TypeError, ValueError) as e:
            return False, f"JSON serialization error for field: {type(e).__name__}: {e}"
        
        # Validate data types
        if not isinstance(game_data["game_id"], str):
            return False, "game_id must be a string"
        if not isinstance(game_data["initial_board"], list):
            return False, "initial_board must be a list"
        if not isinstance(game_data["move_history"], list):
            return False, "move_history must be a list"
        if not isinstance(game_data["final_board"], list):
            return False, "final_board must be a list"
        
        return True, None
    
    def verify_game_saved(self, game_id: str) -> bool:
        """
        Verify a game was successfully saved to database.
        
        Args:
            game_id: Unique game identifier
            
        Returns:
            True if game exists in database, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM completed_games WHERE game_id = ?", (game_id,))
            count = cursor.fetchone()[0]
            conn.close()
            return count > 0
        except Exception as e:
            logger.error(
                f"Error verifying game {game_id}: {type(e).__name__}: {e}",
                exc_info=True
            )
            return False
    
    def check_database_integrity(self) -> Dict:
        """
        Check database integrity and report issues.
        
        Returns:
            Dictionary with integrity check results:
            - orphaned_references: count of orphaned references
            - total_games: total games in completed_games
            - total_references: total references in user_games
            - issues: list of issue descriptions
        """
        issues = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Count orphaned references
            cursor.execute("""
                SELECT COUNT(*) FROM user_games
                WHERE game_id NOT IN (SELECT game_id FROM completed_games)
            """)
            orphaned_count = cursor.fetchone()[0]
            
            # Count total games
            cursor.execute("SELECT COUNT(*) FROM completed_games")
            total_games = cursor.fetchone()[0]
            
            # Count total references
            cursor.execute("SELECT COUNT(*) FROM user_games")
            total_references = cursor.fetchone()[0]
            
            conn.close()
            
            if orphaned_count > 0:
                issues.append(f"Found {orphaned_count} orphaned game reference(s)")
            
            return {
                "orphaned_references": orphaned_count,
                "total_games": total_games,
                "total_references": total_references,
                "issues": issues
            }
        except Exception as e:
            logger.error(
                f"Error checking database integrity: {type(e).__name__}: {e}",
                exc_info=True
            )
            return {
                "orphaned_references": -1,
                "total_games": -1,
                "total_references": -1,
                "issues": [f"Error checking integrity: {e}"]
            }
    
    def cleanup_orphaned_references(self, user_id: Optional[int] = None) -> int:
        """
        Remove orphaned game references (game IDs in user_games without corresponding completed_games).
        
        Args:
            user_id: If provided, only clean up references for this user. Otherwise, clean all.
            
        Returns:
            Number of orphaned references removed
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if user_id is not None:
                # Clean up for specific user
                cursor.execute("""
                    DELETE FROM user_games
                    WHERE user_id = ? 
                    AND game_id NOT IN (SELECT game_id FROM completed_games)
                """, (user_id,))
            else:
                # Clean up for all users
                cursor.execute("""
                    DELETE FROM user_games
                    WHERE game_id NOT IN (SELECT game_id FROM completed_games)
                """)
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} orphaned game reference(s)" + 
                           (f" for user {user_id}" if user_id else ""))
            
            return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up orphaned references: {e}", exc_info=True)
            return 0
