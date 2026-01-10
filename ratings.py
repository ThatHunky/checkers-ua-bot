"""
ELO Rating System for Checkers Bot
Persistent SQLite database tracking player ratings across all chats.
"""

import aiosqlite
import sqlite3
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
                        last_played_date DATE,
                        consecutive_days INTEGER DEFAULT 0,
                        games_today INTEGER DEFAULT 0,
                        wins_as_yellow INTEGER DEFAULT 0,
                        wins_as_blue INTEGER DEFAULT 0,
                        rating_gain_this_week INTEGER DEFAULT 0,
                        rating_gain_this_month INTEGER DEFAULT 0,
                        perfect_streak INTEGER DEFAULT 0,
                        last_week_reset DATE,
                        last_month_reset DATE,
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
                    "last_played_date": "DATE",
                    "consecutive_days": "INTEGER DEFAULT 0",
                    "games_today": "INTEGER DEFAULT 0",
                    "wins_as_yellow": "INTEGER DEFAULT 0",
                    "wins_as_blue": "INTEGER DEFAULT 0",
                    "rating_gain_this_week": "INTEGER DEFAULT 0",
                    "rating_gain_this_month": "INTEGER DEFAULT 0",
                    "perfect_streak": "INTEGER DEFAULT 0",
                    "last_week_reset": "DATE",
                    "last_month_reset": "DATE",
                }
                
                for col_name, col_type in new_columns.items():
                    if col_name not in columns:
                        try:
                            await db.execute(f"ALTER TABLE players ADD COLUMN {col_name} {col_type}")
                        except aiosqlite.OperationalError:
                            pass  # Column might already exist

            # Ensure match_history exists and supports idempotent game recording via game_key.
            # Some deployments create match_history elsewhere; we still migrate it here.
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS match_history (
                    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player1_id INTEGER,
                    player2_id INTEGER,
                    winner_id INTEGER,
                    player1_rating_before INTEGER,
                    player1_rating_after INTEGER,
                    player2_rating_before INTEGER,
                    player2_rating_after INTEGER,
                    move_count INTEGER,
                    game_duration INTEGER,
                    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    game_key TEXT
                )
                """
            )

            async with db.execute("PRAGMA table_info(match_history)") as cursor:
                mh_columns = {row[1] for row in await cursor.fetchall()}
            if "game_key" not in mh_columns:
                try:
                    await db.execute("ALTER TABLE match_history ADD COLUMN game_key TEXT")
                except aiosqlite.OperationalError:
                    pass

            # Enforce uniqueness for non-null game_key values (allows legacy rows with NULL key).
            await db.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_match_history_game_key
                ON match_history(game_key)
                """
            )
            
            # Create blocked_users table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS blocked_users (
                    user_id INTEGER PRIMARY KEY,
                    blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.commit()
            logger.info(f"Rating database initialized at {self.db_path}")

    async def _get_player_in_tx(self, db: aiosqlite.Connection, user_id: int, username: Optional[str] = None) -> dict:
        """
        Transaction-scoped variant of get_player() using an existing DB connection.
        Must be called from within an open transaction to guarantee consistency.
        """
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM players WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        if row:
            if username and row["username"] != username:
                await db.execute(
                    "UPDATE players SET username = ? WHERE user_id = ?",
                    (username, user_id),
                )
                row_dict = dict(row)
                row_dict["username"] = username
                return row_dict
            return dict(row)

        await db.execute(
            """INSERT INTO players (user_id, username, rating)
               VALUES (?, ?, ?)""",
            (user_id, username or "Unknown", INITIAL_RATING),
        )
        async with db.execute("SELECT * FROM players WHERE user_id = ?", (user_id,)) as cursor:
            row2 = await cursor.fetchone()
        return dict(row2) if row2 else {
            "user_id": user_id,
            "username": username or "Unknown",
            "rating": INITIAL_RATING,
            "games_played": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
        }
    
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

                    row_dict = dict(row)
                    row_dict["username"] = username
                    return row_dict

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
                    "draws": 0,
                    "last_played_date": None,
                    "consecutive_days": 0,
                    "games_today": 0,
                    "wins_as_yellow": 0,
                    "wins_as_blue": 0,
                    "rating_gain_this_week": 0,
                    "rating_gain_this_month": 0,
                    "perfect_streak": 0,
                    "last_week_reset": None,
                    "last_month_reset": None,
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

    @staticmethod
    def calculate_elo_draw_change(
        player1_rating: int,
        player2_rating: int,
        player1_games: int = 0,
        player2_games: int = 0,
        k_factor: Optional[int] = None,
    ) -> tuple[int, int]:
        """
        Calculate ELO rating changes for a draw (0.5 / 0.5) using dynamic K-factor.

        Formula: R_new = R_old + K × (Actual - Expected)
        For draw: Actual = 0.5 for both players.
        """
        if k_factor is None:
            p1_k = get_k_factor(player1_games)
            p2_k = get_k_factor(player2_games)
            avg_k = (p1_k + p2_k) / 2
        else:
            avg_k = k_factor

        expected_p1 = 1 / (1 + 10 ** ((player2_rating - player1_rating) / 400))
        # Ensure zero-sum by deriving player2 change from player1 change.
        p1_change = round(avg_k * (0.5 - expected_p1))
        p2_change = -p1_change

        return player1_rating + p1_change, player2_rating + p2_change

    async def record_draw(
        self,
        player1_id: int,
        player1_name: str,
        player2_id: int,
        player2_name: str,
        *,
        game_key: Optional[str] = None,
        move_count: int = 0,
        game_duration: int = 0,
    ) -> Tuple[dict, dict]:
        """
        Record a draw result and update ELO ratings + draw statistics.

        Idempotent when game_key is provided (same semantics as record_game).
        """
        from datetime import date

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            try:
                await db.execute("BEGIN IMMEDIATE")

                if game_key:
                    async with db.execute(
                        "SELECT player1_id, player2_id, winner_id, "
                        "player1_rating_before, player1_rating_after, "
                        "player2_rating_before, player2_rating_after "
                        "FROM match_history WHERE game_key = ?",
                        (game_key,),
                    ) as cursor:
                        existing = await cursor.fetchone()

                    if existing:
                        p1_row = await self._get_player_in_tx(db, player1_id, player1_name)
                        p2_row = await self._get_player_in_tx(db, player2_id, player2_name)

                        # Changes relative to requested IDs, regardless of stored ordering.
                        if int(existing["player1_id"]) == int(player1_id):
                            p1_change = int(existing["player1_rating_after"] - existing["player1_rating_before"])
                        elif int(existing["player2_id"]) == int(player1_id):
                            p1_change = int(existing["player2_rating_after"] - existing["player2_rating_before"])
                        else:
                            p1_change = 0

                        if int(existing["player1_id"]) == int(player2_id):
                            p2_change = int(existing["player1_rating_after"] - existing["player1_rating_before"])
                        elif int(existing["player2_id"]) == int(player2_id):
                            p2_change = int(existing["player2_rating_after"] - existing["player2_rating_before"])
                        else:
                            p2_change = 0

                        await db.commit()
                        return (
                            {**p1_row, "rating_change": p1_change, "rank_changed": False, "new_rank": None},
                            {**p2_row, "rating_change": p2_change, "rank_changed": False, "new_rank": None},
                        )

                p1 = await self._get_player_in_tx(db, player1_id, player1_name)
                p2 = await self._get_player_in_tx(db, player2_id, player2_name)

                p1_games = int(p1.get("games_played", 0) or 0)
                p2_games = int(p2.get("games_played", 0) or 0)

                new_p1_rating, new_p2_rating = self.calculate_elo_draw_change(
                    int(p1["rating"]),
                    int(p2["rating"]),
                    p1_games,
                    p2_games,
                )

                p1_change = int(new_p1_rating - int(p1["rating"]))
                p2_change = int(new_p2_rating - int(p2["rating"]))

                today = date.today()

                def parse_date(d):
                    if d is None:
                        return None
                    if isinstance(d, str):
                        try:
                            return date.fromisoformat(d)
                        except (ValueError, TypeError):
                            return None
                    return d

                def compute_counters(
                    player_row: dict, rating_change: int
                ) -> tuple[int, int, int, int, int, int, Optional[date], Optional[date]]:
                    last_played = parse_date(player_row.get("last_played_date"))
                    last_week_reset = parse_date(player_row.get("last_week_reset"))
                    last_month_reset = parse_date(player_row.get("last_month_reset"))

                    # Weekly
                    if last_week_reset is None or (today - last_week_reset).days >= 7:
                        games_week = 1
                        gain_week = rating_change
                        last_week_reset = today
                    else:
                        games_week = int(player_row.get("games_this_week", 0) or 0) + 1
                        gain_week = int(player_row.get("rating_gain_this_week", 0) or 0) + rating_change

                    # Monthly
                    if last_month_reset is None or (today.year != last_month_reset.year or today.month != last_month_reset.month):
                        games_month = 1
                        gain_month = rating_change
                        last_month_reset = today
                    else:
                        games_month = int(player_row.get("games_this_month", 0) or 0) + 1
                        gain_month = int(player_row.get("rating_gain_this_month", 0) or 0) + rating_change

                    # Daily streak tracking
                    if last_played is None:
                        consecutive_days = 1
                        games_today = 1
                    else:
                        delta_days = (today - last_played).days
                        if delta_days == 0:
                            consecutive_days = int(player_row.get("consecutive_days", 0) or 0) or 1
                            games_today = int(player_row.get("games_today", 0) or 0) + 1
                        elif delta_days == 1:
                            consecutive_days = int(player_row.get("consecutive_days", 0) or 0) + 1
                            games_today = 1
                        else:
                            consecutive_days = 1
                            games_today = 1

                    return (
                        games_week,
                        games_month,
                        gain_week,
                        gain_month,
                        consecutive_days,
                        games_today,
                        last_week_reset,
                        last_month_reset,
                    )

                (
                    p1_games_week,
                    p1_games_month,
                    p1_gain_week,
                    p1_gain_month,
                    p1_consec,
                    p1_games_today,
                    p1_wk_reset,
                    p1_mo_reset,
                ) = compute_counters(p1, p1_change)
                (
                    p2_games_week,
                    p2_games_month,
                    p2_gain_week,
                    p2_gain_month,
                    p2_consec,
                    p2_games_today,
                    p2_wk_reset,
                    p2_mo_reset,
                ) = compute_counters(p2, p2_change)

                p1_total_gained = int(p1.get("total_rating_gained", 0) or 0) + max(0, p1_change)
                p1_total_lost = int(p1.get("total_rating_lost", 0) or 0) + max(0, -p1_change)
                p2_total_gained = int(p2.get("total_rating_gained", 0) or 0) + max(0, p2_change)
                p2_total_lost = int(p2.get("total_rating_lost", 0) or 0) + max(0, -p2_change)

                # Longest game tracking (keep semantics: maximum move_count observed)
                p1_longest = int(p1.get("longest_game") or 0)
                p2_longest = int(p2.get("longest_game") or 0)
                if move_count and int(move_count) > p1_longest:
                    p1_longest = int(move_count)
                if move_count and int(move_count) > p2_longest:
                    p2_longest = int(move_count)

                # Best rating tracking
                p1_best_rating = max(int(p1.get("best_rating", int(new_p1_rating)) or int(new_p1_rating)), int(new_p1_rating))
                p2_best_rating = max(int(p2.get("best_rating", int(new_p2_rating)) or int(new_p2_rating)), int(new_p2_rating))

                await db.execute(
                    """
                    UPDATE players
                    SET rating = ?,
                        games_played = games_played + 1,
                        draws = draws + 1,
                        current_streak = 0,
                        best_rating = ?,
                        total_rating_gained = ?,
                        total_rating_lost = ?,
                        longest_game = ?,
                        games_this_week = ?,
                        games_this_month = ?,
                        last_game_date = ?,
                        last_played_date = ?,
                        consecutive_days = ?,
                        games_today = ?,
                        rating_gain_this_week = ?,
                        rating_gain_this_month = ?,
                        perfect_streak = 0,
                        last_week_reset = ?,
                        last_month_reset = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                    """,
                    (
                        int(new_p1_rating),
                        p1_best_rating,
                        p1_total_gained,
                        p1_total_lost,
                        p1_longest,
                        p1_games_week,
                        p1_games_month,
                        today.isoformat(),
                        today.isoformat(),
                        p1_consec,
                        p1_games_today,
                        p1_gain_week,
                        p1_gain_month,
                        p1_wk_reset.isoformat() if p1_wk_reset else None,
                        p1_mo_reset.isoformat() if p1_mo_reset else None,
                        player1_id,
                    ),
                )

                await db.execute(
                    """
                    UPDATE players
                    SET rating = ?,
                        games_played = games_played + 1,
                        draws = draws + 1,
                        current_streak = 0,
                        best_rating = ?,
                        total_rating_gained = ?,
                        total_rating_lost = ?,
                        longest_game = ?,
                        games_this_week = ?,
                        games_this_month = ?,
                        last_game_date = ?,
                        last_played_date = ?,
                        consecutive_days = ?,
                        games_today = ?,
                        rating_gain_this_week = ?,
                        rating_gain_this_month = ?,
                        perfect_streak = 0,
                        last_week_reset = ?,
                        last_month_reset = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                    """,
                    (
                        int(new_p2_rating),
                        p2_best_rating,
                        p2_total_gained,
                        p2_total_lost,
                        p2_longest,
                        p2_games_week,
                        p2_games_month,
                        today.isoformat(),
                        today.isoformat(),
                        p2_consec,
                        p2_games_today,
                        p2_gain_week,
                        p2_gain_month,
                        p2_wk_reset.isoformat() if p2_wk_reset else None,
                        p2_mo_reset.isoformat() if p2_mo_reset else None,
                        player2_id,
                    ),
                )

                await db.execute(
                    """
                    INSERT INTO match_history
                        (player1_id, player2_id, winner_id,
                         player1_rating_before, player1_rating_after,
                         player2_rating_before, player2_rating_after,
                         move_count, game_duration, game_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        player1_id,
                        player2_id,
                        None,
                        int(p1["rating"]),
                        int(new_p1_rating),
                        int(p2["rating"]),
                        int(new_p2_rating),
                        int(move_count or 0),
                        int(game_duration or 0),
                        game_key,
                    ),
                )

                await db.commit()
            except Exception:
                try:
                    await db.rollback()
                except Exception:
                    pass
                raise

        logger.info(
            f"Draw recorded: {player1_name} ({p1['rating']} → {new_p1_rating}, "
            f"{'+' if p1_change >= 0 else ''}{p1_change}) draws {player2_name} "
            f"({p2['rating']} → {new_p2_rating}, {'+' if p2_change >= 0 else ''}{p2_change})"
        )

        # Return fresh rows (not strictly required, but consistent with record_game).
        p1_out = await self.get_player(player1_id, player1_name)
        p2_out = await self.get_player(player2_id, player2_name)
        p1_out["rating_change"] = p1_change
        p2_out["rating_change"] = p2_change
        p1_out["rank_changed"] = False
        p1_out["new_rank"] = None
        p2_out["rank_changed"] = False
        p2_out["new_rank"] = None
        return p1_out, p2_out
    
    async def record_game(
        self,
        winner_id: int,
        winner_name: str,
        loser_id: int,
        loser_name: str,
        *,
        game_key: Optional[str] = None,
        move_count: int = 0,
        winner_pieces_lost: Optional[int] = None,
        loser_pieces_lost: Optional[int] = None,
        winner_color: Optional[str] = None,
        game_duration: int = 0,
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

        winner: dict
        loser: dict
        winner_games: int
        loser_games: int
        new_winner_rating: int
        new_loser_rating: int
        winner_change: int
        loser_change: int
        winner_streak: int
        winner_best_streak: int
        loser_streak: int
        winner_best_rating: int
        winner_peak_rank: Optional[str]
        rank_changed: bool
        new_winner_rank: dict

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            try:
                await db.execute("BEGIN IMMEDIATE")

                # Idempotency: if this exact game_key was already recorded, return current stats.
                if game_key:
                    async with db.execute(
                        "SELECT player1_id, player2_id, winner_id, "
                        "player1_rating_before, player1_rating_after, player2_rating_before, player2_rating_after "
                        "FROM match_history WHERE game_key = ?",
                        (game_key,),
                    ) as cursor:
                        existing = await cursor.fetchone()
                    if existing:
                        winner_row = await self._get_player_in_tx(db, winner_id, winner_name)
                        loser_row = await self._get_player_in_tx(db, loser_id, loser_name)

                        # Compute changes relative to the IDs passed in, regardless of how rows are stored.
                        if int(existing["player1_id"]) == int(winner_id):
                            winner_change = int(existing["player1_rating_after"] - existing["player1_rating_before"])
                        elif int(existing["player2_id"]) == int(winner_id):
                            winner_change = int(existing["player2_rating_after"] - existing["player2_rating_before"])
                        else:
                            winner_change = 0

                        if int(existing["player1_id"]) == int(loser_id):
                            loser_change = int(existing["player1_rating_after"] - existing["player1_rating_before"])
                        elif int(existing["player2_id"]) == int(loser_id):
                            loser_change = int(existing["player2_rating_after"] - existing["player2_rating_before"])
                        else:
                            loser_change = 0

                        await db.commit()
                        return {
                            **winner_row,
                            "rating_change": winner_change,
                            "rank_changed": False,
                            "new_rank": None,
                        }, {
                            **loser_row,
                            "rating_change": loser_change,
                        }

                # Get current ratings and statistics inside this transaction
                winner = await self._get_player_in_tx(db, winner_id, winner_name)
                loser = await self._get_player_in_tx(db, loser_id, loser_name)

                winner_games = int(winner.get("games_played", 0) or 0)
                loser_games = int(loser.get("games_played", 0) or 0)

                # Calculate new ratings with dynamic K-factor
                new_winner_rating, new_loser_rating = self.calculate_elo_change(
                    int(winner["rating"]),
                    int(loser["rating"]),
                    winner_games,
                    loser_games,
                )

                # Calculate rating changes
                winner_change = int(new_winner_rating - int(winner["rating"]))
                loser_change = int(new_loser_rating - int(loser["rating"]))

                # Update streaks
                winner_streak = int(winner.get("current_streak", 0) or 0) + 1
                winner_best_streak = max(int(winner.get("best_streak", 0) or 0), winner_streak)
                loser_streak = 0  # Reset on loss

                # Update best rating
                winner_best_rating = max(int(winner.get("best_rating", new_winner_rating) or new_winner_rating), new_winner_rating)

                # Check for rank changes
                old_winner_rank = get_rank(int(winner["rating"]))
                new_winner_rank = get_rank(int(new_winner_rating))
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
                winner_total_gained = int(winner.get("total_rating_gained", 0) or 0) + max(0, winner_change)
                winner_total_lost = int(winner.get("total_rating_lost", 0) or 0) + max(0, -winner_change)
                loser_total_gained = int(loser.get("total_rating_gained", 0) or 0) + max(0, loser_change)
                loser_total_lost = int(loser.get("total_rating_lost", 0) or 0) + max(0, -loser_change)

                # Check for perfect game (no pieces lost) - only when we have reliable piece-loss input.
                winner_perfect = (winner_pieces_lost == 0) if winner_pieces_lost is not None else False
                winner_perfect_games = int(winner.get("perfect_games", 0) or 0) + (1 if winner_perfect else 0)

                # Check for comeback win (winning from rating deficit)
                rating_deficit = int(winner["rating"]) - int(loser["rating"])
                if rating_deficit < -100:  # Winner was 100+ rating lower
                    winner_comeback_wins = int(winner.get("comeback_wins", 0) or 0) + 1
                else:
                    winner_comeback_wins = int(winner.get("comeback_wins", 0) or 0)

                # Update fastest/slowest games
                winner_fastest = winner.get("fastest_win")
                if move_count > 0 and (winner_fastest is None or int(move_count) < int(winner_fastest)):
                    winner_fastest = int(move_count)

                loser_longest = loser.get("longest_game") or 0
                loser_longest = int(loser_longest)
                if move_count and int(move_count) > loser_longest:
                    loser_longest = int(move_count)

                # Date tracking and counter management
                today = date.today()

                def parse_date(d):
                    if d is None:
                        return None
                    if isinstance(d, str):
                        try:
                            return date.fromisoformat(d)
                        except (ValueError, TypeError):
                            return None
                    return d

                # Winner date tracking
                winner_last_played = parse_date(winner.get("last_played_date"))
                winner_last_week_reset = parse_date(winner.get("last_week_reset"))
                winner_last_month_reset = parse_date(winner.get("last_month_reset"))

                # Reset weekly counter if new week
                if winner_last_week_reset is None or (today - winner_last_week_reset).days >= 7:
                    winner_games_week = 1
                    winner_rating_gain_week = winner_change
                    winner_last_week_reset = today
                else:
                    winner_games_week = int(winner.get("games_this_week", 0) or 0) + 1
                    winner_rating_gain_week = int(winner.get("rating_gain_this_week", 0) or 0) + winner_change

                # Reset monthly counter if new month
                if winner_last_month_reset is None or (today.year != winner_last_month_reset.year or today.month != winner_last_month_reset.month):
                    winner_games_month = 1
                    winner_rating_gain_month = winner_change
                    winner_last_month_reset = today
                else:
                    winner_games_month = int(winner.get("games_this_month", 0) or 0) + 1
                    winner_rating_gain_month = int(winner.get("rating_gain_this_month", 0) or 0) + winner_change

                # Reset daily counter if new day
                if winner_last_played is None or winner_last_played != today:
                    winner_games_today = 1
                    winner_consecutive_days = 1 if winner_last_played is None or (today - winner_last_played).days == 1 else 0
                else:
                    winner_games_today = int(winner.get("games_today", 0) or 0) + 1
                    winner_consecutive_days = int(winner.get("consecutive_days", 0) or 0)

                # Update wins by color
                winner_wins_yellow = int(winner.get("wins_as_yellow", 0) or 0)
                winner_wins_blue = int(winner.get("wins_as_blue", 0) or 0)
                if winner_color == "yellow":
                    winner_wins_yellow += 1
                elif winner_color == "blue":
                    winner_wins_blue += 1

                # Update perfect streak
                if winner_perfect:
                    winner_perfect_streak = int(winner.get("perfect_streak", 0) or 0) + 1
                else:
                    winner_perfect_streak = 0

                # Loser date tracking (simpler - just update counters)
                loser_last_played = parse_date(loser.get("last_played_date"))
                loser_last_week_reset = parse_date(loser.get("last_week_reset"))
                loser_last_month_reset = parse_date(loser.get("last_month_reset"))

                # Reset weekly counter if new week
                if loser_last_week_reset is None or (today - loser_last_week_reset).days >= 7:
                    loser_games_week = 1
                    loser_rating_gain_week = loser_change
                    loser_last_week_reset = today
                else:
                    loser_games_week = int(loser.get("games_this_week", 0) or 0) + 1
                    loser_rating_gain_week = int(loser.get("rating_gain_this_week", 0) or 0) + loser_change

                # Reset monthly counter if new month
                if loser_last_month_reset is None or (today.year != loser_last_month_reset.year or today.month != loser_last_month_reset.month):
                    loser_games_month = 1
                    loser_rating_gain_month = loser_change
                    loser_last_month_reset = today
                else:
                    loser_games_month = int(loser.get("games_this_month", 0) or 0) + 1
                    loser_rating_gain_month = int(loser.get("rating_gain_this_month", 0) or 0) + loser_change

                # Reset daily counter if new day
                if loser_last_played is None or loser_last_played != today:
                    loser_games_today = 1
                    loser_consecutive_days = 0  # Loser doesn't get consecutive days
                else:
                    loser_games_today = int(loser.get("games_today", 0) or 0) + 1
                    loser_consecutive_days = int(loser.get("consecutive_days", 0) or 0)

                # Loser perfect streak resets
                loser_perfect_streak = 0

                # Update database rows
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
                        last_played_date = ?,
                        consecutive_days = ?,
                        games_today = ?,
                        wins_as_yellow = ?,
                        wins_as_blue = ?,
                        rating_gain_this_week = ?,
                        rating_gain_this_month = ?,
                        perfect_streak = ?,
                        last_week_reset = ?,
                        last_month_reset = ?,
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
                    today.isoformat(),
                    winner_consecutive_days,
                    winner_games_today,
                    winner_wins_yellow,
                    winner_wins_blue,
                    winner_rating_gain_week,
                    winner_rating_gain_month,
                    winner_perfect_streak,
                    winner_last_week_reset.isoformat() if winner_last_week_reset else None,
                    winner_last_month_reset.isoformat() if winner_last_month_reset else None,
                    winner_id,
                ))

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
                        last_played_date = ?,
                        consecutive_days = ?,
                        games_today = ?,
                        rating_gain_this_week = ?,
                        rating_gain_this_month = ?,
                        perfect_streak = ?,
                        last_week_reset = ?,
                        last_month_reset = ?,
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
                    today.isoformat(),
                    loser_consecutive_days,
                    loser_games_today,
                    loser_rating_gain_week,
                    loser_rating_gain_month,
                    loser_perfect_streak,
                    loser_last_week_reset.isoformat() if loser_last_week_reset else None,
                    loser_last_month_reset.isoformat() if loser_last_month_reset else None,
                    loser_id,
                ))

                await db.execute(
                    """
                    INSERT INTO match_history
                        (player1_id, player2_id, winner_id,
                         player1_rating_before, player1_rating_after,
                         player2_rating_before, player2_rating_after,
                         move_count, game_duration, game_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        winner_id,
                        loser_id,
                        winner_id,
                        int(winner["rating"]),
                        int(new_winner_rating),
                        int(loser["rating"]),
                        int(new_loser_rating),
                        int(move_count or 0),
                        int(game_duration or 0),
                        game_key,
                    ),
                )

                await db.commit()
            except Exception:
                try:
                    await db.rollback()
                except Exception:
                    pass
                raise

        logger.info(
            f"Game recorded: {winner_name} ({winner['rating']} → {new_winner_rating}, "
            f"{'+' if winner_change >= 0 else ''}{winner_change}, K={get_k_factor(winner_games)}) "
            f"defeats {loser_name} ({loser['rating']} → {new_loser_rating}, "
            f"{'+' if loser_change >= 0 else ''}{loser_change}, K={get_k_factor(loser_games)})"
        )

        return {
            **winner,
            "rating": new_winner_rating,
            "rating_change": winner_change,
            "games_played": winner_games + 1,
            "wins": int(winner.get("wins", 0) or 0) + 1,
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
            "losses": int(loser.get("losses", 0) or 0) + 1,
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
    
    async def block_user(self, user_id: int) -> bool:
        """
        Block a user by adding them to the blocked_users table.
        
        Args:
            user_id: Telegram user ID to block
        
        Returns:
            True if successful, False otherwise
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO blocked_users (user_id) VALUES (?)",
                    (user_id,)
                )
                await db.commit()
                logger.info(f"User {user_id} blocked")
                return True
        except Exception as e:
            logger.error(f"Error blocking user {user_id}: {e}")
            return False
    
    async def unblock_user(self, user_id: int) -> bool:
        """
        Unblock a user by removing them from the blocked_users table.
        
        Args:
            user_id: Telegram user ID to unblock
        
        Returns:
            True if successful, False otherwise
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "DELETE FROM blocked_users WHERE user_id = ?",
                    (user_id,)
                )
                await db.commit()
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info(f"User {user_id} unblocked")
                return deleted
        except Exception as e:
            logger.error(f"Error unblocking user {user_id}: {e}")
            return False
    
    async def is_user_blocked(self, user_id: int) -> bool:
        """
        Check if a user is blocked.
        
        Args:
            user_id: Telegram user ID to check
        
        Returns:
            True if user is blocked, False otherwise
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    "SELECT 1 FROM blocked_users WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    return row is not None
        except Exception as e:
            logger.error(f"Error checking if user {user_id} is blocked: {e}")
            return False
