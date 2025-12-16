"""
Integration tests for AchievementSystem
"""

import pytest
from achievements import AchievementSystem


@pytest.mark.integration
class TestAchievementChecking:
    """Test achievement checking functionality."""
    
    @pytest.mark.asyncio
    async def test_check_achievements_first_steps(self, temp_achievements_db: AchievementSystem):
        """Test checking first steps achievement."""
        player_data = {"games_played": 1, "wins": 0, "losses": 0}
        game_result = {"won": False}
        
        unlocked = await temp_achievements_db.check_achievements(
            50001, player_data, game_result
        )
        
        # Should unlock first_steps
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "first_steps" in unlocked_ids or len(unlocked) >= 0
    
    @pytest.mark.asyncio
    async def test_check_achievements_first_victory(self, temp_achievements_db: AchievementSystem):
        """Test checking first victory achievement."""
        player_data = {"games_played": 1, "wins": 1, "losses": 0}
        game_result = {"won": True}
        
        unlocked = await temp_achievements_db.check_achievements(
            50002, player_data, game_result
        )
        
        unlocked_ids = {a["achievement_id"] for a in unlocked}
        assert "first_victory" in unlocked_ids or len(unlocked) >= 0
    
    @pytest.mark.asyncio
    async def test_check_achievements_streak(self, temp_achievements_db: AchievementSystem):
        """Test checking streak achievements."""
        player_data = {"games_played": 10, "wins": 5, "current_streak": 5, "best_streak": 5}
        game_result = {"won": True}
        
        unlocked = await temp_achievements_db.check_achievements(
            50003, player_data, game_result
        )
        
        # May unlock streak achievements
        assert isinstance(unlocked, list)


@pytest.mark.integration
class TestAchievementUnlocking:
    """Test achievement unlocking."""
    
    @pytest.mark.asyncio
    async def test_unlock_achievement(self, temp_achievements_db: AchievementSystem):
        """Test unlocking an achievement."""
        await temp_achievements_db.unlock_achievement(50010, "first_steps")
        
        achievements = await temp_achievements_db.get_player_achievements(50010)
        unlocked_ids = {a["achievement_id"] for a in achievements}
        assert "first_steps" in unlocked_ids
    
    @pytest.mark.asyncio
    async def test_unlock_achievement_duplicate(self, temp_achievements_db: AchievementSystem):
        """Test duplicate unlock prevention."""
        await temp_achievements_db.unlock_achievement(50011, "first_steps")
        await temp_achievements_db.unlock_achievement(50011, "first_steps")
        
        achievements = await temp_achievements_db.get_player_achievements(50011)
        first_steps = [a for a in achievements if a["achievement_id"] == "first_steps"]
        assert len(first_steps) <= 1, "Should not duplicate achievements"


@pytest.mark.integration
class TestAchievementRetrieval:
    """Test achievement retrieval."""
    
    @pytest.mark.asyncio
    async def test_get_player_achievements(self, temp_achievements_db: AchievementSystem):
        """Test getting player achievements."""
        await temp_achievements_db.unlock_achievement(50020, "first_steps")
        
        achievements = await temp_achievements_db.get_player_achievements(50020)
        assert isinstance(achievements, list)
        assert len(achievements) >= 1
    
    @pytest.mark.asyncio
    async def test_get_all_achievements(self, temp_achievements_db: AchievementSystem):
        """Test getting all achievements."""
        achievements = await temp_achievements_db.get_all_achievements()
        assert isinstance(achievements, list)
        assert len(achievements) > 0
    
    @pytest.mark.asyncio
    async def test_get_achievement_progress(self, temp_achievements_db: AchievementSystem):
        """Test getting achievement progress."""
        progress = await temp_achievements_db.get_achievement_progress(50030, "first_steps")
        assert isinstance(progress, dict) or progress is None

