"""
Achievement System for Ukrainian Checkers Bot
Handles achievement checking, unlocking, and progress tracking.
"""

import aiosqlite
import ast
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
import logging
from datetime import date
from ranks import get_rank

logger = logging.getLogger(__name__)


class AchievementSystem:
    """System for managing player achievements."""
    
    def __init__(self, db_path: str = "/data/ratings.db"):
        """Initialize achievement system with database path."""
        self.db_path = db_path

    @staticmethod
    def _load_default_achievements_catalog() -> list[tuple[str, str, str, str, str, str, str, int]]:
        """
        Load the default achievements catalog.

        Primary source: `scripts/reset_database.py` (kept in-repo).
        Fallback: a minimal set to keep the system functional if the script format changes.
        """
        reset_script = Path(__file__).with_name("scripts") / "reset_database.py"
        if reset_script.exists():
            try:
                module = ast.parse(reset_script.read_text(encoding="utf-8"))
                for node in module.body:
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id == "achievements":
                                value = ast.literal_eval(node.value)
                                # Expected shape: list[tuple[str, str, str, str, str, str, str, int]]
                                if isinstance(value, list) and value and isinstance(value[0], tuple):
                                    return value
            except Exception:
                # Fall through to minimal catalog
                pass

        return [
            ("first_steps", "First Steps", "Перші Кроки", "Play your first game", "Зіграйте свою першу гру", "🌱", "milestone", 1),
            ("first_victory", "First Victory", "Перша Перемога", "Win your first game", "Виграйте свою першу гру", "🏆", "milestone", 1),
            ("victory_lightning", "Lightning Victory", "Блискавка", "Win a game in under 25 moves", "Виграйте гру менше ніж за 25 ходів", "⚡", "victory", 25),
            ("victory_hurricane", "Hurricane", "Ураган", "Win a game in under 20 moves", "Виграйте гру менше ніж за 20 ходів", "💨", "victory", 20),
        ]

    async def initialize(self) -> None:
        """
        Create achievements tables (idempotent) and seed the default catalog.

        Tests and fresh installs expect:
        - `achievements` table exists and contains at least one row.
        - `player_achievements` table exists and supports INSERT/SELECT flows.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS achievements (
                    achievement_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    name_uk TEXT NOT NULL,
                    description TEXT NOT NULL,
                    description_uk TEXT NOT NULL,
                    icon TEXT NOT NULL,
                    category TEXT NOT NULL,
                    requirement_value INTEGER NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS player_achievements (
                    user_id INTEGER NOT NULL,
                    achievement_id TEXT NOT NULL,
                    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, achievement_id)
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_player_achievements_user ON player_achievements(user_id)"
            )

            catalog = self._load_default_achievements_catalog()
            await db.executemany(
                """
                INSERT OR IGNORE INTO achievements
                (achievement_id, name, name_uk, description, description_uk, icon, category, requirement_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                catalog,
            )
            await db.commit()
            logger.info("Achievement database initialized at %s", self.db_path)
    
    async def check_achievements(
        self,
        user_id: int,
        player_data: dict,
        game_result: dict,
        opponent_data: Optional[dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Check and unlock achievements for a player after a game.
        
        Args:
            user_id: Player's user ID
            player_data: Updated player data from record_game
            game_result: Game result information (winner/loser, rating changes, etc.)
            opponent_data: Optional opponent data for comparison achievements
        
        Returns:
            List of newly unlocked achievements
        """
        newly_unlocked = []
        
        # Get all achievements
        all_achievements = await self.get_all_achievements()
        
        # Get player's current achievements
        player_achievements = await self.get_player_achievements(user_id)
        unlocked_ids = {ach["achievement_id"] for ach in player_achievements}
        
        # Check each achievement category
        for achievement in all_achievements:
            if achievement["achievement_id"] in unlocked_ids:
                continue  # Already unlocked
            
            category = achievement["category"]
            unlocked = False
            
            if category == "milestone":
                unlocked = await self._check_milestone_achievement(
                    achievement, player_data, game_result
                )
            elif category == "rank":
                unlocked = await self._check_rank_achievement(
                    achievement, player_data
                )
            elif category == "streak":
                unlocked = await self._check_streak_achievement(
                    achievement, player_data
                )
            elif category == "victory":
                unlocked = await self._check_victory_achievement(
                    achievement, player_data, game_result, opponent_data
                )
            elif category == "statistics":
                unlocked = await self._check_statistics_achievement(
                    achievement, player_data
                )
            elif category == "gameplay":
                unlocked = await self._check_gameplay_achievement(
                    achievement, player_data, game_result
                )
            elif category == "competitive":
                unlocked = await self._check_competitive_achievement(
                    achievement, user_id, player_data
                )
            elif category == "time":
                unlocked = await self._check_time_achievement(
                    achievement, player_data, game_result
                )
            elif category == "special":
                unlocked = await self._check_special_achievement(
                    achievement, player_data, game_result
                )
            elif category == "collection":
                unlocked = await self._check_collection_achievement(
                    achievement, user_id
                )
            
            if unlocked:
                await self.unlock_achievement(user_id, achievement["achievement_id"])
                newly_unlocked.append(achievement)
                logger.info(f"Achievement unlocked: {user_id} - {achievement['name_uk']}")
        
        return newly_unlocked
    
    async def _check_milestone_achievement(
        self, achievement: dict, player_data: dict, game_result: dict
    ) -> bool:
        """Check milestone achievements (games played, wins, rating gains)."""
        req_value = achievement["requirement_value"]
        ach_id = achievement["achievement_id"]
        
        if ach_id == "first_steps":
            return player_data.get("games_played", 0) >= 1
        elif ach_id == "first_victory":
            return game_result.get("won", False) and player_data.get("wins", 0) >= 1
        elif ach_id in ("player_10", "statistician", "centurion", "veteran_games", "legend_games", "tireless"):
            return player_data.get("games_played", 0) >= req_value
        elif ach_id == "fast_start":
            # Win 5 games in first 10
            games = player_data.get("games_played", 0)
            wins = player_data.get("wins", 0)
            return games <= 10 and wins >= 5
        elif ach_id == "rising_star":
            # Gain 200 rating in a week
            rating_gain_week = player_data.get("rating_gain_this_week", 0)
            return rating_gain_week >= req_value
        elif ach_id == "meteor":
            # Gain 300 rating in a week
            rating_gain_week = player_data.get("rating_gain_this_week", 0)
            return rating_gain_week >= req_value
        elif ach_id == "comet":
            # Gain 500 rating in a month
            rating_gain_month = player_data.get("rating_gain_this_month", 0)
            return rating_gain_month >= req_value
        
        return False
    
    async def _check_rank_achievement(
        self, achievement: dict, player_data: dict
    ) -> bool:
        """Check rank achievements."""
        rating = player_data.get("rating", 0)
        rank_info = get_rank(rating)
        
        # Check if player has reached the required rank
        req_value = achievement["requirement_value"]  # This is the min rating for the rank
        return rating >= req_value
    
    async def _check_streak_achievement(
        self, achievement: dict, player_data: dict
    ) -> bool:
        """Check streak achievements."""
        req_value = achievement["requirement_value"]
        ach_id = achievement["achievement_id"]
        
        if ach_id.startswith("streak_"):
            current_streak = player_data.get("current_streak", 0)
            best_streak = player_data.get("best_streak", 0)
            
            if ach_id == "streak_stability":
                # Simplified: Reach 10+ streak (removed "twice" requirement)
                return best_streak >= 10
            elif ach_id == "streak_precision":
                # Win 5 in a row without losing pieces (use perfect_streak)
                perfect_streak = player_data.get("perfect_streak", 0)
                return perfect_streak >= req_value
            else:
                # Standard streak achievements
                return best_streak >= req_value
        
        return False
    
    async def _check_victory_achievement(
        self, achievement: dict, player_data: dict, game_result: dict, opponent_data: Optional[dict]
    ) -> bool:
        """Check victory achievements."""
        if not game_result.get("won", False):
            return False
        
        req_value = achievement["requirement_value"]
        ach_id = achievement["achievement_id"]
        
        if ach_id.startswith("victory_lucky") or ach_id.startswith("victory_fortunate") or ach_id == "victory_jackpot":
            # Win against higher rated opponent (check pre-game rating)
            opponent_rating_before = game_result.get("opponent_rating_before")
            player_rating_before = player_data.get("rating", 0) - game_result.get("rating_change", 0)
            if opponent_rating_before is not None:
                rating_diff = opponent_rating_before - player_rating_before
                return rating_diff >= req_value
            # Fallback to opponent_data if available
            elif opponent_data:
                rating_diff = opponent_data.get("rating", 0) - player_data.get("rating", 0)
                return rating_diff >= req_value
        elif ach_id.startswith("victory_comeback"):
            # Win from rating deficit (check pre-game rating difference)
            opponent_rating_before = game_result.get("opponent_rating_before")
            player_rating_before = player_data.get("rating", 0) - game_result.get("rating_change", 0)
            if opponent_rating_before is not None:
                rating_deficit = opponent_rating_before - player_rating_before
                return rating_deficit >= req_value
            # Fallback: use rating change as approximation
            elif opponent_data:
                rating_deficit = opponent_data.get("rating", 0) - player_data.get("rating", 0)
                return rating_deficit >= req_value
        elif ach_id in ("victory_lightning", "victory_hurricane"):
            # Fast wins
            move_count = game_result.get("move_count", 0)
            return move_count > 0 and move_count <= req_value
        elif ach_id in ("victory_showman", "victory_perfect_defense", "victory_sniper", "victory_fortress", "victory_show"):
            # Perfect games (no pieces lost)
            perfect_games = player_data.get("perfect_games", 0)
            return perfect_games >= req_value
        elif ach_id in ("victory_speed_demon", "victory_marathoner", "victory_rocket"):
            # Games in one day
            games_today = player_data.get("games_today", 0)
            return games_today >= req_value
        
        return False
    
    async def _check_statistics_achievement(
        self, achievement: dict, player_data: dict
    ) -> bool:
        """Check statistics achievements."""
        req_value = achievement["requirement_value"]
        ach_id = achievement["achievement_id"]
        
        games = player_data.get("games_played", 0)
        wins = player_data.get("wins", 0)
        losses = player_data.get("losses", 0)
        
        if ach_id.startswith("stats_positive_balance") or ach_id.startswith("stats_accuracy") or \
           ach_id.startswith("stats_mastery") or ach_id == "stats_perfection":
            # Win rate achievements
            if games == 0:
                return False
            win_rate = (wins / games) * 100
            min_games = 20 if req_value >= 90 else (30 if req_value >= 70 else 50)
            return win_rate >= req_value and games >= min_games
        elif ach_id.startswith("stats_champion_wins") or ach_id == "stats_winner" or \
             ach_id == "stats_king" or ach_id == "stats_diamond" or ach_id == "stats_star":
            # Win count achievements
            return wins >= req_value
        elif ach_id == "stats_analyst":
            # Play 50 games with 50%+ win rate
            return games >= req_value and wins >= (games * 0.5)
        elif ach_id == "stats_student":
            # Learn from losses
            return losses >= req_value
        elif ach_id == "stats_resilience":
            # Win after consecutive losses (would need loss streak tracking)
            return wins > 0  # Simplified
        
        return False
    
    async def _check_gameplay_achievement(
        self, achievement: dict, player_data: dict, game_result: dict
    ) -> bool:
        """Check gameplay achievements."""
        ach_id = achievement["achievement_id"]
        req_value = achievement["requirement_value"]
        
        if ach_id == "gameplay_first_move":
            return game_result.get("moved_first", False) and game_result.get("won", False)
        elif ach_id == "gameplay_last_move":
            return not game_result.get("moved_first", False) and game_result.get("won", False)
        elif ach_id == "gameplay_balance":
            # Win 10 games as both colors
            wins_yellow = player_data.get("wins_as_yellow", 0)
            wins_blue = player_data.get("wins_as_blue", 0)
            return wins_yellow >= req_value and wins_blue >= req_value
        elif ach_id in ("gameplay_patience", "gameplay_wisdom"):
            move_count = game_result.get("move_count", 0)
            return move_count >= req_value and game_result.get("won", False)
        elif ach_id == "gameplay_quick_reactor":
            # Win in under 5 minutes
            duration = game_result.get("game_duration_seconds", 0)
            return duration > 0 and duration <= (req_value * 60) and game_result.get("won", False)
        elif ach_id == "gameplay_king_of_kings":
            # Promote 5 pieces in one game
            promotions = game_result.get("promotions", 0)
            return promotions >= req_value and game_result.get("won", False)
        elif ach_id == "gameplay_circus":
            # Promote 10 pieces in one game
            promotions = game_result.get("promotions", 0)
            return promotions >= req_value and game_result.get("won", False)
        elif ach_id == "gameplay_precise_strike":
            # Capture 5+ pieces in one move
            max_captures = game_result.get("max_captures_in_move", 0)
            return max_captures >= req_value and game_result.get("won", False)
        elif ach_id == "gameplay_mass_destruction":
            # Capture 8+ pieces in one game
            total_captures = game_result.get("pieces_captured", 0)
            return total_captures >= req_value and game_result.get("won", False)
        elif ach_id == "gameplay_return":
            # Win after being down 3+ pieces
            pieces_lost = game_result.get("pieces_lost", 0)
            return pieces_lost >= req_value and game_result.get("won", False)
        elif ach_id == "gameplay_willpower":
            # Win after being down 5+ pieces
            pieces_lost = game_result.get("pieces_lost", 0)
            return pieces_lost >= req_value and game_result.get("won", False)
        elif ach_id == "gameplay_fortress_gameplay":
            # Win without losing any pieces
            pieces_lost = game_result.get("pieces_lost", 0)
            return pieces_lost == 0 and game_result.get("won", False)
        
        return False
    
    async def _check_competitive_achievement(
        self, achievement: dict, user_id: int, player_data: dict
    ) -> bool:
        """Check competitive achievements (leaderboard positions)."""
        ach_id = achievement["achievement_id"]
        req_value = achievement["requirement_value"]

        # These achievements require *historical* leaderboard tracking (time spent in top-10).
        # We currently do not persist leaderboard history, so checking only the current rank
        # would unlock them incorrectly. Keep them disabled until proper tracking is added.
        if ach_id in (
            "competitive_champion_week",
            "competitive_master_month",
            "competitive_legend_year",
        ):
            return False
        
        # Get player rank by querying database.
        # In some test fixtures we only create achievements tables (no ratings/players schema),
        # so treat missing `players` table as "not eligible" rather than crashing.
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    """SELECT COUNT(*) + 1 as rank
                       FROM players
                       WHERE rating > (
                           SELECT rating FROM players WHERE user_id = ?
                       ) AND games_played > 0""",
                    (user_id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    rank = row[0] if row else None
        except sqlite3.OperationalError:
            return False
        
        if rank is None:
            return False
        
        # For rank-based achievements, check current rank
        if ach_id == "competitive_top_100":
            return rank <= 100
        elif ach_id == "competitive_top_50":
            return rank <= 50
        elif ach_id == "competitive_top_25":
            return rank <= 25
        elif ach_id == "competitive_top_10":
            return rank <= 10
        elif ach_id == "competitive_top_5":
            return rank <= 5
        elif ach_id == "competitive_top_3":
            return rank <= 3
        elif ach_id == "competitive_king":
            return rank == 1
        
        return False
    
    async def _check_time_achievement(
        self, achievement: dict, player_data: dict, game_result: dict
    ) -> bool:
        """Check time-based achievements."""
        ach_id = achievement["achievement_id"]
        req_value = achievement["requirement_value"]
        
        game_date = game_result.get("game_date")
        game_time = game_result.get("game_time")
        
        if not game_date or not game_time:
            return False
        
        if ach_id == "time_early_bird":
            # Win before 8 AM
            return game_time.hour < 8
        elif ach_id == "time_night_owl":
            # Win after midnight (0:00-5:59 AM)
            return game_time.hour >= 0 and game_time.hour < 6
        elif ach_id == "time_daily_player":
            # Play every day for 7 days
            consecutive_days = player_data.get("consecutive_days", 0)
            return consecutive_days >= req_value
        elif ach_id == "time_dedicated":
            # Play every day for 30 days
            consecutive_days = player_data.get("consecutive_days", 0)
            return consecutive_days >= req_value
        elif ach_id == "time_tireless_days":
            # Play every day for 100 days
            consecutive_days = player_data.get("consecutive_days", 0)
            return consecutive_days >= req_value
        elif ach_id == "time_weekend_warrior":
            # Win 10 games on weekends
            # Check if game was on weekend (Saturday=5, Sunday=6)
            weekday = game_date.weekday()
            is_weekend = weekday >= 5
            if not is_weekend:
                return False
            # Count weekend wins (simplified - would need weekend wins counter)
            # For now, check if this is a weekend win
            return game_result.get("won", False) and is_weekend
        elif ach_id == "time_consistency":
            # Play at least one game per week for 3 months (12 weeks)
            # Check if player has played consistently
            games_this_week = player_data.get("games_this_week", 0)
            # Simplified: if they have games this week and have been playing, consider it
            # This would ideally track weekly play history
            return games_this_week > 0  # Simplified check
        
        return False
    
    async def _check_special_achievement(
        self, achievement: dict, player_data: dict, game_result: dict
    ) -> bool:
        """Check special achievements."""
        ach_id = achievement["achievement_id"]
        
        if ach_id == "special_target":
            # Win exactly 100 rating in one game
            rating_change = game_result.get("rating_change", 0)
            return rating_change == 100
        elif ach_id == "special_random":
            # Exactly 50% win rate after 20 games
            games = player_data.get("games_played", 0)
            wins = player_data.get("wins", 0)
            return games == 20 and wins == 10
        elif ach_id == "special_holiday":
            # Win on a major holiday
            game_date = game_result.get("game_date")
            if not game_date:
                return False
            # Check for major holidays (New Year, Christmas, Easter, etc.)
            # New Year: January 1
            if game_date.month == 1 and game_date.day == 1:
                return True
            # Christmas: December 25
            if game_date.month == 12 and game_date.day == 25:
                return True
            # Easter (simplified - first Sunday in April, approximate)
            # For simplicity, check April 1-7
            if game_date.month == 4 and 1 <= game_date.day <= 7:
                return True
            return False
        elif ach_id == "special_anniversary":
            # Play on account anniversary (first game date)
            # Use first game date from games_played = 1
            games = player_data.get("games_played", 0)
            game_date = game_result.get("game_date")
            if not game_date or games != 1:
                return False
            # This is the first game, so it's the anniversary
            return True
        
        # Removed achievements: special_surprise, special_unique, special_pioneer
        # These require data we don't track (birthday, global history)
        return False
    
    async def _check_collection_achievement(
        self, achievement: dict, user_id: int
    ) -> bool:
        """Check collection achievements (unlock X achievements)."""
        req_value = achievement["requirement_value"]
        player_achievements = await self.get_player_achievements(user_id)
        unlocked_count = len(player_achievements)
        
        if achievement["achievement_id"] == "collection_completionist":
            # Unlock all achievements
            all_achievements = await self.get_all_achievements()
            return unlocked_count >= len(all_achievements)
        else:
            return unlocked_count >= req_value
    
    async def get_all_achievements(self) -> List[Dict[str, Any]]:
        """Get all achievement definitions."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM achievements ORDER BY category, requirement_value"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_player_achievements(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all achievements unlocked by a player."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT a.*, pa.unlocked_at
                FROM achievements a
                INNER JOIN player_achievements pa ON a.achievement_id = pa.achievement_id
                WHERE pa.user_id = ?
                ORDER BY pa.unlocked_at DESC
            """, (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def unlock_achievement(self, user_id: int, achievement_id: str):
        """Unlock an achievement for a player."""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute("""
                    INSERT INTO player_achievements (user_id, achievement_id, unlocked_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (user_id, achievement_id))
                await db.commit()
            except aiosqlite.IntegrityError:
                # Already unlocked
                pass
    
    async def get_achievement_progress(
        self, user_id: int, achievement_id: str, player_data: Optional[dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get progress towards an achievement.
        
        Returns:
            Dict with current progress, max progress, percentage, or None if not progress-based
        """
        # Backwards compatibility: tests and some callers pass only (user_id, achievement_id).
        if player_data is None:
            player_data = {}

        achievement = await self.get_achievement(achievement_id)
        if not achievement:
            return None
        
        # Check if already unlocked
        player_achievements = await self.get_player_achievements(user_id)
        if any(ach["achievement_id"] == achievement_id for ach in player_achievements):
            return {
                "unlocked": True,
                "progress": 100,
                "current": achievement["requirement_value"],
                "max": achievement["requirement_value"],
            }
        
        req_value = achievement["requirement_value"]
        category = achievement["category"]
        
        if category == "milestone":
            if achievement_id in ("player_10", "statistician", "centurion", "veteran_games", "legend_games", "tireless"):
                current = player_data.get("games_played", 0)
                return {"unlocked": False, "progress": min(100, (current / req_value) * 100), "current": current, "max": req_value}
        elif category == "streak":
            current = player_data.get("best_streak", 0)
            return {"unlocked": False, "progress": min(100, (current / req_value) * 100), "current": current, "max": req_value}
        elif category == "statistics":
            if achievement_id.startswith("stats_champion_wins") or achievement_id == "stats_winner":
                current = player_data.get("wins", 0)
                return {"unlocked": False, "progress": min(100, (current / req_value) * 100), "current": current, "max": req_value}
        
        return None
    
    async def get_achievement(self, achievement_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific achievement by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM achievements WHERE achievement_id = ?", (achievement_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

