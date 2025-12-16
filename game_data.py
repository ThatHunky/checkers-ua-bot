"""
SQLite-based repository for completed game data persistence.
Stores game replays alongside ratings.db for long-term storage.
"""

import sqlite3
import json
from typing import Optional, List, Dict
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
        Save a completed game.
        
        Args:
            game_data: Dictionary containing game info and move history
            
        Returns:
            True if successful
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
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
                json.dumps(game_data["initial_board"]),
                json.dumps(game_data["move_history"]),
                json.dumps(game_data["final_board"]),
                game_data["completed_at"]
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error saving completed game: {e}")
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
            
            return {
                "game_id": row["game_id"],
                "blue_player_id": row["blue_player_id"],
                "blue_player_name": row["blue_player_name"],
                "yellow_player_id": row["yellow_player_id"],
                "yellow_player_name": row["yellow_player_name"],
                "winner_id": row["winner_id"],
                "winner_name": row["winner_name"],
                "winner_color": row["winner_color"],
                "initial_board": json.loads(row["initial_board"]),
                "move_history": json.loads(row["move_history"]),
                "final_board": json.loads(row["final_board"]),
                "completed_at": row["completed_at"]
            }
        except Exception as e:
            logger.error(f"Error retrieving game {game_id}: {e}")
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
            logger.error(f"Error adding user game reference: {e}")
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
            logger.error(f"Error getting user games: {e}")
            return []
