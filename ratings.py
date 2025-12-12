"""
ELO Rating System for Checkers Bot
Persistent SQLite database tracking player ratings across all chats.
"""

import aiosqlite
from typing import Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

# ELO Constants
INITIAL_RATING = 1200  # Standard starting rating for beginners
K_FACTOR = 32  # Higher K-factor for casual play (makes rating changes more responsive)


class RatingSystem:
    """Async ELO rating system with SQLite persistence."""
    
    def __init__(self, db_path: str = "/data/ratings.db"):
        """Initialize rating system with database path."""
        self.db_path = db_path
    
    async def initialize(self):
        """Create database tables if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    rating INTEGER DEFAULT 1200,
                    games_played INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    draws INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
            logger.info(f"Rating database initialized at {self.db_path}")
    
    async def get_player(self, user_id: int, username: str = None) -> dict:
        """
        Get player rating data, create if doesn't exist.
        
        Returns:
            dict with user_id, username, rating, games_played, wins, losses, draws
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            async with db.execute(
                "SELECT * FROM players WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
            
            if row:
                # Update username if provided and different
                if username and row["username"] != username:
                    await db.execute(
                        "UPDATE players SET username = ? WHERE user_id = ?",
                        (username, user_id)
                    )
                    await db.commit()
                
                return dict(row)
            else:
                # Create new player
                await db.execute(
                    """INSERT INTO players (user_id, username, rating)
                       VALUES (?, ?, ?)""",
                    (user_id, username or "Unknown", INITIAL_RATING)
                )
                await db.commit()
                
                return {
                    "user_id": user_id,
                    "username": username or "Unknown",
                    "rating": INITIAL_RATING,
                    "games_played": 0,
                    "wins": 0,
                    "losses": 0,
                    "draws": 0
                }
    
    @staticmethod
    def calculate_elo_change(
        winner_rating: int,
        loser_rating: int,
        k_factor: int = K_FACTOR
    ) -> tuple[int, int]:
        """
        Calculate ELO rating changes for a game using standard formula.
        
        Formula: R_new = R_old + K × (Actual - Expected)
        
        Args:
            winner_rating: Current rating of winner
            loser_rating: Current rating of loser
            k_factor: K-factor (higher = more volatile, default 32 for casual play)
        
        Returns:
            Tuple of (winner_new_rating, loser_new_rating)
        """
        # Calculate expected scores (probability of winning)
        expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
        expected_loser = 1 / (1 + 10 ** ((winner_rating - loser_rating) / 400))
        
        # Actual scores: 1.0 for win, 0.0 for loss
        # Rating change = K × (Actual - Expected)
        winner_change = round(k_factor * (1.0 - expected_winner))
        loser_change = round(k_factor * (0.0 - expected_loser))
        
        new_winner_rating = winner_rating + winner_change
        new_loser_rating = loser_rating + loser_change
        
        return new_winner_rating, new_loser_rating
    
    async def record_game(
        self,
        winner_id: int,
        winner_name: str,
        loser_id: int,
        loser_name: str
    ) -> Tuple[dict, dict]:
        """
        Record a game result and update ELO ratings.
        
        Returns:
            Tuple of (winner_data, loser_data) with updated ratings
        """
        # Get current ratings
        winner = await self.get_player(winner_id, winner_name)
        loser = await self.get_player(loser_id, loser_name)
        
        # Calculate new ratings
        new_winner_rating, new_loser_rating = self.calculate_elo_change(
            winner["rating"], loser["rating"]
        )
        
        # Update database
        async with aiosqlite.connect(self.db_path) as db:
            # Update winner
            await db.execute(
                """UPDATE players 
                   SET rating = ?,
                       games_played = games_played + 1,
                       wins = wins + 1,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = ?""",
                (new_winner_rating, winner_id)
            )
            
            # Update loser
            await db.execute(
                """UPDATE players 
                   SET rating = ?,
                       games_played = games_played + 1,
                       losses = losses + 1,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = ?""",
                (new_loser_rating, loser_id)
            )
            
            await db.commit()
        
        # Calculate rating changes
        winner_change = new_winner_rating - winner["rating"]
        loser_change = new_loser_rating - loser["rating"]
        
        logger.info(
            f"Game recorded: {winner_name} ({winner['rating']} → {new_winner_rating}, "
            f"{'+' if winner_change >= 0 else ''}{winner_change}) defeats "
            f"{loser_name} ({loser['rating']} → {new_loser_rating}, "
            f"{'+' if loser_change >= 0 else ''}{loser_change})"
        )
        
        return {
            **winner,
            "rating": new_winner_rating,
            "rating_change": winner_change,
            "games_played": winner["games_played"] + 1,
            "wins": winner["wins"] + 1
        }, {
            **loser,
            "rating": new_loser_rating,
            "rating_change": loser_change,
            "games_played": loser["games_played"] + 1,
            "losses": loser["losses"] + 1
        }
    
    async def get_leaderboard(self, limit: int = 10) -> List[dict]:
        """
        Get top players by rating.
        
        Args:
            limit: Number of top players to return
        
        Returns:
            List of player dicts ordered by rating
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            async with db.execute(
                """SELECT * FROM players 
                   WHERE games_played > 0
                   ORDER BY rating DESC 
                   LIMIT ?""",
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_player_rank(self, user_id: int) -> Optional[int]:
        """
        Get player's rank (1-indexed).
        
        Returns:
            Rank number or None if player not found
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """SELECT COUNT(*) + 1 as rank
                   FROM players
                   WHERE rating > (
                       SELECT rating FROM players WHERE user_id = ?
                   ) AND games_played > 0""",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
