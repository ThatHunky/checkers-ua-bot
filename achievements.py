"""
Achievement System for Ukrainian Checkers Bot
Handles achievement checking, unlocking, and progress tracking.
"""

import aiosqlite
from typing import Optional, Dict, List, Tuple
import logging
from datetime import datetime, date
from ranks import get_rank

logger = logging.getLogger(__name__)


class AchievementSystem:
    """System for managing player achievements."""
    
    def __init__(self, db_path: str = "/data/ratings.db"):
        """Initialize achievement system with database path."""
        self.db_path = db_path
    
    async def check_achievements(
        self,
        user_id: int,
        player_data: dict,
        game_result: dict,
        opponent_data: Optional[dict] = None
    ) -> List[Dict[str, any]]:
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
        elif ach_id in ("rising_star", "meteor", "comet"):
            # Rating gains in time periods (simplified - would need date tracking)
            # For now, check if rating increased by required amount
            rating_change = game_result.get("rating_change", 0)
            return rating_change >= req_value
        
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
                # Maintain 10+ streak twice (simplified - would need history)
                return best_streak >= 10
            elif ach_id == "streak_precision":
                # Win 5 in a row without losing pieces (would need game data)
                return current_streak >= req_value
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
            # Win against higher rated opponent
            if opponent_data:
                rating_diff = opponent_data.get("rating", 0) - player_data.get("rating", 0)
                return rating_diff >= req_value
        elif ach_id.startswith("victory_comeback"):
            # Win from rating deficit
            rating_change = game_result.get("rating_change", 0)
            return rating_change >= req_value
        elif ach_id in ("victory_lightning", "victory_hurricane"):
            # Fast wins (would need move_count from game_result)
            move_count = game_result.get("move_count", 0)
            return move_count > 0 and move_count <= req_value
        elif ach_id in ("victory_showman", "victory_perfect_defense", "victory_sniper", "victory_fortress", "victory_show"):
            # Perfect games (no pieces lost)
            perfect_games = player_data.get("perfect_games", 0)
            return perfect_games >= req_value
        elif ach_id in ("victory_speed_demon", "victory_marathoner", "victory_rocket"):
            # Games in one day (would need date tracking)
            games_today = player_data.get("games_this_week", 0)  # Simplified
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
        # These would require detailed game data (move counts, piece promotions, etc.)
        # Simplified implementation
        ach_id = achievement["achievement_id"]
        
        if ach_id == "gameplay_first_move":
            return game_result.get("moved_first", False) and game_result.get("won", False)
        elif ach_id == "gameplay_last_move":
            return not game_result.get("moved_first", False) and game_result.get("won", False)
        elif ach_id == "gameplay_balance":
            # Win 10 games as both colors (would need color tracking)
            return player_data.get("wins", 0) >= 10
        elif ach_id in ("gameplay_patience", "gameplay_wisdom"):
            move_count = game_result.get("move_count", 0)
            req_value = achievement["requirement_value"]
            return move_count >= req_value and game_result.get("won", False)
        
        return False
    
    async def _check_competitive_achievement(
        self, achievement: dict, user_id: int, player_data: dict
    ) -> bool:
        """Check competitive achievements (leaderboard positions)."""
        # Would need to query leaderboard
        # Simplified - would require leaderboard integration
        return False
    
    async def _check_time_achievement(
        self, achievement: dict, player_data: dict, game_result: dict
    ) -> bool:
        """Check time-based achievements."""
        # Would need date/time tracking
        # Simplified implementation
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
    
    async def get_all_achievements(self) -> List[Dict[str, any]]:
        """Get all achievement definitions."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM achievements ORDER BY category, requirement_value"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    
    async def get_player_achievements(self, user_id: int) -> List[Dict[str, any]]:
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
        self, user_id: int, achievement_id: str, player_data: dict
    ) -> Optional[Dict[str, any]]:
        """
        Get progress towards an achievement.
        
        Returns:
            Dict with current progress, max progress, percentage, or None if not progress-based
        """
        achievement = await self.get_achievement(achievement_id)
        if not achievement:
            return None
        
        # Check if already unlocked
        player_achievements = await self.get_player_achievements(user_id)
        if any(ach["achievement_id"] == achievement_id for ach in player_achievements):
            return {"unlocked": True, "progress": 100, "current": achievement["requirement_value"], "max": achievement["requirement_value"]}
        
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
    
    async def get_achievement(self, achievement_id: str) -> Optional[Dict[str, any]]:
        """Get a specific achievement by ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM achievements WHERE achievement_id = ?", (achievement_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

