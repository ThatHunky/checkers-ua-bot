"""
Unit tests for fixed achievement checking logic
Tests the achievement checking functions directly without database dependencies
"""

import pytest
from datetime import date, time
from achievements import AchievementSystem
import aiosqlite
import tempfile
import os


async def create_test_achievements_db():
    """Create a temporary achievement system with populated achievements."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    achievement_system = AchievementSystem(db_path=db_path)
    
    # Create tables
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE achievements (
                achievement_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                name_uk TEXT NOT NULL,
                description TEXT NOT NULL,
                description_uk TEXT NOT NULL,
                icon TEXT NOT NULL,
                category TEXT NOT NULL,
                requirement_value INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE player_achievements (
                user_id INTEGER NOT NULL,
                achievement_id TEXT NOT NULL,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, achievement_id)
            )
        """)
        
        # Seed from the PRODUCTION catalog rather than a hand-copied literal.
        # A test that inserts its own thresholds and then asserts them back can
        # never notice the real catalog changing -- which is the whole point of
        # the threshold assertions below.
        catalog = {
            entry[0]: entry
            for entry in AchievementSystem._load_default_achievements_catalog()
        }
        wanted_ids = (
            "victory_lightning",
            "victory_hurricane",
            "time_early_bird",
            "time_night_owl",
            "time_daily_player",
            "gameplay_king_of_kings",
            "gameplay_precise_strike",
            "gameplay_fortress_gameplay",
            "victory_comeback_100",
            "victory_speed_demon",
            "rising_star",
            "streak_precision",
            "special_holiday",
            "special_anniversary",
        )
        missing = [ach_id for ach_id in wanted_ids if ach_id not in catalog]
        assert not missing, f"achievements catalog is missing: {missing}"
        test_achievements = [catalog[ach_id] for ach_id in wanted_ids]

        for ach in test_achievements:
            await db.execute("""
                INSERT INTO achievements 
                (achievement_id, name, name_uk, description, description_uk, icon, category, requirement_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, ach)
        await db.commit()
    
    return achievement_system, db_path


@pytest.mark.asyncio
async def test_victory_lightning_new_threshold():
    """Test victory_lightning with new 25 move threshold."""
    system, db_path = await create_test_achievements_db()
    try:
        achievement = await system.get_achievement("victory_lightning")
        assert achievement is not None
        assert achievement["requirement_value"] == 25, "Should be 25 moves, not 15"
        
        # Test the check logic
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        game_result = {"won": True, "move_count": 25}
        
        unlocked = await system._check_victory_achievement(
            achievement, player_data, game_result, None
        )
        assert unlocked is True, "Should unlock with exactly 25 moves"
        
        # Test with 24 moves (should also unlock)
        game_result["move_count"] = 24
        unlocked = await system._check_victory_achievement(
            achievement, player_data, game_result, None
        )
        assert unlocked is True, "Should unlock with 24 moves"
        
        # Test with 26 moves (should NOT unlock)
        game_result["move_count"] = 26
        unlocked = await system._check_victory_achievement(
            achievement, player_data, game_result, None
        )
        assert unlocked is False, "Should NOT unlock with 26 moves"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_victory_hurricane_new_threshold():
    """Test victory_hurricane with new 20 move threshold."""
    system, db_path = await create_test_achievements_db()
    try:
        achievement = await system.get_achievement("victory_hurricane")
        assert achievement is not None
        assert achievement["requirement_value"] == 20, "Should be 20 moves, not 10"
        
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        game_result = {"won": True, "move_count": 20}
        
        unlocked = await system._check_victory_achievement(
            achievement, player_data, game_result, None
        )
        assert unlocked is True, "Should unlock with exactly 20 moves"
        
        # Test with 19 moves
        game_result["move_count"] = 19
        unlocked = await system._check_victory_achievement(
            achievement, player_data, game_result, None
        )
        assert unlocked is True, "Should unlock with 19 moves"
        
        # Test with 21 moves (should NOT unlock)
        game_result["move_count"] = 21
        unlocked = await system._check_victory_achievement(
            achievement, player_data, game_result, None
        )
        assert unlocked is False, "Should NOT unlock with 21 moves"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_time_early_bird():
    """Test time_early_bird achievement."""
    system, db_path = await create_test_achievements_db()
    try:
        achievement = await system.get_achievement("time_early_bird")
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        
        # Test before 8 AM
        game_result = {
            "won": True,
            "game_date": date.today(),
            "game_time": time(7, 30)
        }
        unlocked = await system._check_time_achievement(achievement, player_data, game_result)
        assert unlocked is True, "Should unlock before 8 AM"
        
        # Test after 8 AM
        game_result["game_time"] = time(8, 30)
        unlocked = await system._check_time_achievement(achievement, player_data, game_result)
        assert unlocked is False, "Should NOT unlock after 8 AM"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_time_night_owl():
    """Test time_night_owl achievement."""
    system, db_path = await create_test_achievements_db()
    try:
        achievement = await system.get_achievement("time_night_owl")
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        
        # Test after midnight
        game_result = {
            "won": True,
            "game_date": date.today(),
            "game_time": time(2, 30)  # 2:30 AM
        }
        unlocked = await system._check_time_achievement(achievement, player_data, game_result)
        assert unlocked is True, "Should unlock after midnight"
        
        # Test during day
        game_result["game_time"] = time(14, 30)
        unlocked = await system._check_time_achievement(achievement, player_data, game_result)
        assert unlocked is False, "Should NOT unlock during day"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_gameplay_king_of_kings():
    """Test gameplay_king_of_kings achievement."""
    system, db_path = await create_test_achievements_db()
    try:
        achievement = await system.get_achievement("gameplay_king_of_kings")
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        
        # Test with 5 promotions
        game_result = {"won": True, "promotions": 5}
        unlocked = await system._check_gameplay_achievement(achievement, player_data, game_result)
        assert unlocked is True, "Should unlock with 5 promotions"
        
        # Test with 4 promotions
        game_result["promotions"] = 4
        unlocked = await system._check_gameplay_achievement(achievement, player_data, game_result)
        assert unlocked is False, "Should NOT unlock with 4 promotions"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_gameplay_precise_strike():
    """Test gameplay_precise_strike achievement."""
    system, db_path = await create_test_achievements_db()
    try:
        achievement = await system.get_achievement("gameplay_precise_strike")
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        
        # Test with 5 captures in one move
        game_result = {"won": True, "max_captures_in_move": 5}
        unlocked = await system._check_gameplay_achievement(achievement, player_data, game_result)
        assert unlocked is True, "Should unlock with 5 captures in one move"
        
        # Test with 4 captures
        game_result["max_captures_in_move"] = 4
        unlocked = await system._check_gameplay_achievement(achievement, player_data, game_result)
        assert unlocked is False, "Should NOT unlock with 4 captures"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_victory_comeback_fixed():
    """Test victory_comeback with fixed pre-game rating logic."""
    system, db_path = await create_test_achievements_db()
    try:
        achievement = await system.get_achievement("victory_comeback_100")
        player_data = {"games_played": 10, "wins": 5, "rating": 1100}
        
        # Test with pre-game rating difference
        game_result = {
            "won": True,
            "opponent_rating_before": 1200,  # 100 point difference
            "rating_change": 25
        }
        opponent_data = {"rating": 1200}
        unlocked = await system._check_victory_achievement(
            achievement, player_data, game_result, opponent_data
        )
        assert unlocked is True, "Should unlock with 100+ rating deficit"
        
        # Test with smaller difference
        game_result["opponent_rating_before"] = 1150  # Only 50 point difference
        unlocked = await system._check_victory_achievement(
            achievement, player_data, game_result, opponent_data
        )
        assert unlocked is False, "Should NOT unlock with <100 rating deficit"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_rising_star_time_period():
    """Test rising_star with time-period rating tracking."""
    system, db_path = await create_test_achievements_db()
    try:
        achievement = await system.get_achievement("rising_star")
        player_data = {
            "games_played": 10,
            "wins": 5,
            "rating": 1200,
            "rating_gain_this_week": 200
        }
        game_result = {"won": True, "rating_change": 20}
        
        unlocked = await system._check_milestone_achievement(achievement, player_data, game_result)
        assert unlocked is True, "Should unlock with 200+ rating gain this week"
        
        # Test with less gain
        player_data["rating_gain_this_week"] = 150
        unlocked = await system._check_milestone_achievement(achievement, player_data, game_result)
        assert unlocked is False, "Should NOT unlock with <200 rating gain"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_streak_precision_perfect_streak():
    """Test streak_precision with perfect_streak counter."""
    system, db_path = await create_test_achievements_db()
    try:
        achievement = await system.get_achievement("streak_precision")
        player_data = {
            "games_played": 10,
            "wins": 8,
            "rating": 1200,
            "perfect_streak": 5
        }
        
        unlocked = await system._check_streak_achievement(achievement, player_data)
        assert unlocked is True, "Should unlock with 5 perfect games in a row"
        
        # Test with less
        player_data["perfect_streak"] = 4
        unlocked = await system._check_streak_achievement(achievement, player_data)
        assert unlocked is False, "Should NOT unlock with <5 perfect games"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_special_holiday():
    """Test special_holiday achievement."""
    system, db_path = await create_test_achievements_db()
    try:
        achievement = await system.get_achievement("special_holiday")
        player_data = {"games_played": 5, "wins": 3, "rating": 1200}
        
        # Test New Year
        game_result = {
            "won": True,
            "game_date": date(2025, 1, 1),
            "game_time": time(12, 0)
        }
        unlocked = await system._check_special_achievement(achievement, player_data, game_result)
        assert unlocked is True, "Should unlock on New Year"
        
        # Test regular day
        game_result["game_date"] = date(2025, 6, 15)
        unlocked = await system._check_special_achievement(achievement, player_data, game_result)
        assert unlocked is False, "Should NOT unlock on regular day"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.mark.asyncio
async def test_special_anniversary():
    """Test special_anniversary achievement (first game)."""
    system, db_path = await create_test_achievements_db()
    try:
        achievement = await system.get_achievement("special_anniversary")
        
        # Test first game
        player_data = {"games_played": 1, "wins": 1, "rating": 1200}
        game_result = {
            "won": True,
            "game_date": date.today(),
            "game_time": time(12, 0)
        }
        unlocked = await system._check_special_achievement(achievement, player_data, game_result)
        assert unlocked is True, "Should unlock on first game"
        
        # Test second game
        player_data["games_played"] = 2
        unlocked = await system._check_special_achievement(achievement, player_data, game_result)
        assert unlocked is False, "Should NOT unlock on second game"
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)

