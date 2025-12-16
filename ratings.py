"""
ELO Rating System for Checkers Bot
Persistent SQLite database tracking player ratings across all chats.
"""

import aiosqlite
from typing import Optional, List, Tuple
import logging
from ranks import get_rank, get_rank_by_name

logger = logging.getLogger(__name__)

# ELO Constants
INITIAL_RATING = 800  # Lower starting rating for more engaging progression
BASE_K_FACTOR = 32  # Base K-factor (used as fallback)


def get_k_factor(games_played: int) -> int:
    """
    Get dynamic K-factor based on number of games played.
    
    New players get higher K-factor for more exciting rating changes.
    Experienced players get lower K-factor for more stable ratings.
    
    Args:
        games_played: Number of games the player has played
        
    Returns:
        K-factor value (24-64)
    """
    if games_played <= 5:
        return 64  # Very volatile for new players
    elif games_played <= 10:
        return 48
    elif games_played <= 20:
        return 40
    elif games_played <= 30:
        return 36
    elif games_played <= 50:
        return 32  # Standard
    elif games_played <= 100:
        return 28
    else:
        return 24  # Stable for veterans


class RatingSystem:
    """Async ELO rating system with SQLite persistence."""
    
    def __init__(self, db_path: str = "/data/ratings.db"):
        """Initialize rating system with database path."""
        self.db_path = db_path
    
    async def initialize(self):
        """Create database tables if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            # Check if table exists and has new columns
            async with db.execute("PRAGMA table_info(players)") as cursor:
                columns = {row[1] for row in await cursor.fetchall()}
            
            if not columns:
                # Create new table with all fields
                await db.execute("""
                    CREATE TABLE players (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        rating INTEGER DEFAULT 800,
                        games_played INTEGER DEFAULT 0,
                        wins INTEGER DEFAULT 0,
                        losses INTEGER DEFAULT 0,
                        draws INTEGER DEFAULT 0,
                        current_streak INTEGER DEFAULT 0,
                        best_streak INTEGER DEFAULT 0,
                        best_rating INTEGER DEFAULT 800,
                        peak_rank TEXT,
                        total_rating_gained INTEGER DEFAULT 0,
                        total_rating_lost INTEGER DEFAULT 0,
                        perfect_games INTEGER DEFAULT 0,
                        comeback_wins INTEGER DEFAULT 0,
                        fastest_win INTEGER,
                        longest_game INTEGER,
                        games_this_week INTEGER DEFAULT 0,
                        games_this_month INTEGER DEFAULT 0,
                        last_game_date DATE,
                        season_rating INTEGER DEFAULT 800,
                        season_games INTEGER DEFAULT 0,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            else:
                # Add new columns if they don't exist (migration)
                new_columns = {
                    "current_streak": "INTEGER DEFAULT 0",
                    "best_streak": "INTEGER DEFAULT 0",
                    "best_rating": "INTEGER DEFAULT 800",
                    "peak_rank": "TEXT",
                    "total_rating_gained": "INTEGER DEFAULT 0",
                    "total_rating_lost": "INTEGER DEFAULT 0",
                    "perfect_games": "INTEGER DEFAULT 0",
                    "comeback_wins": "INTEGER DEFAULT 0",
                    "fastest_win": "INTEGER",
                    "longest_game": "INTEGER",
                    "games_this_week": "INTEGER DEFAULT 0",
                    "games_this_month": "INTEGER DEFAULT 0",
                    "last_game_date": "DATE",
                    "season_rating": "INTEGER DEFAULT 800",
                    "season_games": "INTEGER DEFAULT 0",
                }
                
                for col_name, col_type in new_columns.items():
                    if col_name not in columns:
                        try:
                            await db.execute(f"ALTER TABLE players ADD COLUMN {col_name} {col_type}")
                        except aiosqlite.OperationalError:
                            pass  # Column might already exist
            
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
        winner_games: int = 0,
        loser_games: int = 0,
        k_factor: Optional[int] = None
    ) -> tuple[int, int]:
        """
        Calculate ELO rating changes for a game using dynamic K-factor.
        
        Formula: R_new = R_old + K × (Actual - Expected)
        
        Args:
            winner_rating: Current rating of winner
            loser_rating: Current rating of loser
            winner_games: Number of games winner has played
            loser_games: Number of games loser has played
            k_factor: Optional fixed K-factor (uses dynamic if None)
        
        Returns:
            Tuple of (winner_new_rating, loser_new_rating)
        """
        # Use dynamic K-factor for each player, then average to maintain zero-sum
        if k_factor is None:
            winner_k = get_k_factor(winner_games)
            loser_k = get_k_factor(loser_games)
            # Use average K-factor to maintain zero-sum property
            avg_k = (winner_k + loser_k) / 2
        else:
            avg_k = k_factor
        
        # Calculate expected score for winner (probability of winning)
        # expected_winner + expected_loser must equal 1.0
        expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
        expected_loser = 1 - expected_winner  # Derive from winner to ensure they sum to 1.0
        
        # Actual scores: 1.0 for win, 0.0 for loss
        # Rating change = K × (Actual - Expected)
        winner_change = round(avg_k * (1.0 - expected_winner))
        # Ensure zero-sum property: loser loses exactly what winner gains
        loser_change = -winner_change
        
        new_winner_rating = winner_rating + winner_change
        new_loser_rating = loser_rating + loser_change
        
        return new_winner_rating, new_loser_rating
    
    async def record_game(
        self,
        winner_id: int,
        winner_name: str,
        loser_id: int,
        loser_name: str,
        move_count: int = 0,
        winner_pieces_lost: int = 0,
        loser_pieces_lost: int = 0
    ) -> Tuple[dict, dict]:
        """
        Record a game result and update ELO ratings with dynamic K-factor and statistics.
        
        Args:
            winner_id: User ID of winner
            winner_name: Name of winner
            loser_id: User ID of loser
            loser_name: Name of loser
            move_count: Number of moves in the game (optional)
            winner_pieces_lost: Number of pieces winner lost (optional, for perfect game tracking)
            loser_pieces_lost: Number of pieces loser lost (optional)
        
        Returns:
            Tuple of (winner_data, loser_data) with updated ratings and statistics
        """
        from datetime import date
        
        # Get current ratings and statistics
        winner = await self.get_player(winner_id, winner_name)
        loser = await self.get_player(loser_id, loser_name)
        
        winner_games = winner.get("games_played", 0)
        loser_games = loser.get("games_played", 0)
        
        # Calculate new ratings with dynamic K-factor
        new_winner_rating, new_loser_rating = self.calculate_elo_change(
            winner["rating"],
            loser["rating"],
            winner_games,
            loser_games
        )
        
        # Calculate rating changes
        winner_change = new_winner_rating - winner["rating"]
        loser_change = new_loser_rating - loser["rating"]
        
        # Update streaks
        winner_streak = winner.get("current_streak", 0) + 1
        winner_best_streak = max(winner.get("best_streak", 0), winner_streak)
        loser_streak = 0  # Reset on loss
        loser_best_streak = loser.get("best_streak", 0)  # Keep best
        
        # Update best rating
        winner_best_rating = max(winner.get("best_rating", new_winner_rating), new_winner_rating)
        loser_best_rating = loser.get("best_rating", new_loser_rating)  # Only update if increased
        
        # Check for rank changes
        old_winner_rank = get_rank(winner["rating"])
        new_winner_rank = get_rank(new_winner_rating)
        rank_changed = old_winner_rank["min_rating"] != new_winner_rank["min_rating"]
        
        # Update peak rank
        winner_peak_rank = winner.get("peak_rank")
        if winner_peak_rank:
            old_peak_rank_info = get_rank_by_name(winner_peak_rank)
            if old_peak_rank_info and new_winner_rank["min_rating"] > old_peak_rank_info["min_rating"]:
                winner_peak_rank = new_winner_rank["name_uk"]
        else:
            winner_peak_rank = new_winner_rank["name_uk"]
        
        # Track rating changes
        winner_total_gained = winner.get("total_rating_gained", 0) + max(0, winner_change)
        winner_total_lost = winner.get("total_rating_lost", 0) + max(0, -winner_change)
        loser_total_gained = loser.get("total_rating_gained", 0) + max(0, loser_change)
        loser_total_lost = loser.get("total_rating_lost", 0) + max(0, -loser_change)
        
        # Check for perfect game (no pieces lost)
        winner_perfect = winner_pieces_lost == 0
        if winner_perfect:
            winner_perfect_games = winner.get("perfect_games", 0) + 1
        else:
            winner_perfect_games = winner.get("perfect_games", 0)
        
        # Check for comeback win (winning from rating deficit)
        rating_deficit = winner["rating"] - loser["rating"]
        if rating_deficit < -100:  # Winner was 100+ rating lower
            winner_comeback_wins = winner.get("comeback_wins", 0) + 1
        else:
            winner_comeback_wins = winner.get("comeback_wins", 0)
        
        # Update fastest/slowest games
        winner_fastest = winner.get("fastest_win")
        if move_count > 0 and (winner_fastest is None or move_count < winner_fastest):
            winner_fastest = move_count
        
        loser_longest = loser.get("longest_game", 0)
        if move_count > loser_longest:
            loser_longest = move_count
        
        # Update weekly/monthly counters (simplified - would need date tracking)
        today = date.today()
        last_game_date = winner.get("last_game_date")
        if last_game_date:
            try:
                if isinstance(last_game_date, str):
                    last_date = date.fromisoformat(last_game_date)
                else:
                    last_date = last_game_date
                # Reset weekly/monthly if needed (simplified logic)
                winner_games_week = winner.get("games_this_week", 0) + 1
                winner_games_month = winner.get("games_this_month", 0) + 1
            except:
                winner_games_week = 1
                winner_games_month = 1
        else:
            winner_games_week = 1
            winner_games_month = 1
        
        loser_games_week = loser.get("games_this_week", 0) + 1
        loser_games_month = loser.get("games_this_month", 0) + 1
        
        # Update database
        async with aiosqlite.connect(self.db_path) as db:
            # Update winner with all new fields
            await db.execute("""
                UPDATE players 
                SET rating = ?,
                    games_played = games_played + 1,
                    wins = wins + 1,
                    current_streak = ?,
                    best_streak = ?,
                    best_rating = ?,
                    peak_rank = ?,
                    total_rating_gained = ?,
                    total_rating_lost = ?,
                    perfect_games = ?,
                    comeback_wins = ?,
                    fastest_win = ?,
                    games_this_week = ?,
                    games_this_month = ?,
                    last_game_date = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (
                new_winner_rating,
                winner_streak,
                winner_best_streak,
                winner_best_rating,
                winner_peak_rank,
                winner_total_gained,
                winner_total_lost,
                winner_perfect_games,
                winner_comeback_wins,
                winner_fastest,
                winner_games_week,
                winner_games_month,
                today.isoformat(),
                winner_id
            ))
            
            # Update loser
            await db.execute("""
                UPDATE players 
                SET rating = ?,
                    games_played = games_played + 1,
                    losses = losses + 1,
                    current_streak = ?,
                    total_rating_gained = ?,
                    total_rating_lost = ?,
                    longest_game = ?,
                    games_this_week = ?,
                    games_this_month = ?,
                    last_game_date = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (
                new_loser_rating,
                loser_streak,
                loser_total_gained,
                loser_total_lost,
                loser_longest,
                loser_games_week,
                loser_games_month,
                today.isoformat(),
                loser_id
            ))
            
            await db.commit()
        
        logger.info(
            f"Game recorded: {winner_name} ({winner['rating']} → {new_winner_rating}, "
            f"{'+' if winner_change >= 0 else ''}{winner_change}, K={get_k_factor(winner_games)}) "
            f"defeats {loser_name} ({loser['rating']} → {new_loser_rating}, "
            f"{'+' if loser_change >= 0 else ''}{loser_change}, K={get_k_factor(loser_games)})"
        )
        
        # Return updated data
        return {
            **winner,
            "rating": new_winner_rating,
            "rating_change": winner_change,
            "games_played": winner_games + 1,
            "wins": winner.get("wins", 0) + 1,
            "current_streak": winner_streak,
            "best_streak": winner_best_streak,
            "best_rating": winner_best_rating,
            "peak_rank": winner_peak_rank,
            "rank_changed": rank_changed,
            "new_rank": new_winner_rank if rank_changed else None,
        }, {
            **loser,
            "rating": new_loser_rating,
            "rating_change": loser_change,
            "games_played": loser_games + 1,
            "losses": loser.get("losses", 0) + 1,
            "current_streak": loser_streak,
        }
    
    async def get_leaderboard(self, limit: int = 15, offset: int = 0) -> tuple[list, int]:
        """
        Get top players by rating with pagination.
        
        Args:
            limit: Number of players per page
            offset: Number of players to skip
        
        Returns:
            Tuple of (list of player dicts, total count of players)
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            
            # Get total count
            async with db.execute(
                "SELECT COUNT(*) FROM players WHERE games_played > 0"
            ) as cursor:
                row = await cursor.fetchone()
                total_count = row[0] if row else 0
            
            # Get paginated results
            async with db.execute(
                """SELECT * FROM players 
                   WHERE games_played > 0
                   ORDER BY rating DESC 
                   LIMIT ? OFFSET ?""",
                (limit, offset)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows], total_count
    
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
    
    async def reset_all_rankings(self) -> int:
        """
        Reset all player rankings (delete all data).
        
        Returns:
            Number of players deleted
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM players") as cursor:
                row = await cursor.fetchone()
                count = row[0] if row else 0
            
            await db.execute("DELETE FROM players")
            await db.commit()
            
            logger.warning(f"All rankings reset! Deleted {count} player records.")
            return count
    
    async def add_arcade_entry(
        self,
        name: str,
        rating: int,
        wins: int = 0,
        losses: int = 0
    ) -> int:
        """
        Add a custom arcade-style leaderboard entry (like old arcade high scores).
        Uses negative fake user IDs to avoid conflicts with real Telegram users.
        
        Args:
            name: Display name for the entry (e.g., "AAA", "PRO", "ACE")
            rating: ELO rating for the entry
            wins: Optional wins count for display
            losses: Optional losses count for display
        
        Returns:
            The fake user_id assigned to this entry
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Find the lowest existing user_id to generate a new fake one
            # Arcade entries use negative IDs to avoid conflicts with real users
            async with db.execute(
                "SELECT MIN(user_id) FROM players WHERE user_id < 0"
            ) as cursor:
                row = await cursor.fetchone()
                min_id = row[0] if row and row[0] else 0
            
            # New fake ID is one less than the minimum (or -1 if first)
            fake_user_id = min(min_id - 1, -1)
            
            games_played = wins + losses if (wins or losses) else 1
            
            await db.execute(
                """INSERT INTO players (user_id, username, rating, games_played, wins, losses)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (fake_user_id, name, rating, games_played, wins, losses)
            )
            await db.commit()
            
            logger.info(f"Arcade entry added: {name} with {rating} ELO (fake ID: {fake_user_id})")
            return fake_user_id
