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
        
        # Insert key achievements for testing
        test_achievements = [
            ("victory_lightning", "Lightning Victory", "Блискавка", "Win in under 25 moves", "Виграйте менше ніж за 25 ходів", "⚡", "victory", 25),
            ("victory_hurricane", "Hurricane", "Ураган", "Win in under 20 moves", "Виграйте менше ніж за 20 ходів", "💨", "victory", 20),
            ("time_early_bird", "Early Bird", "Ранкова Пташка", "Win before 8 AM", "Виграйте до 8 ранку", "🌅", "time", 8),
            ("time_night_owl", "Night Owl", "Нічна Сова", "Win after midnight", "Виграйте після півночі", "🌙", "time", 0),
            ("time_daily_player", "Daily Player", "Щоденний Гравець", "Play 7 days", "Зіграйте 7 днів", "📅", "time", 7),
            ("gameplay_king_of_kings", "King of Kings", "Король Дамок", "Promote 5 pieces", "Перетворіть 5 фігур", "👑", "gameplay", 5),
            ("gameplay_precise_strike", "Precise Strike", "Точний Удар", "Capture 5+ in one move", "Знищіть 5+ за хід", "🎯", "gameplay", 5),
            ("gameplay_fortress_gameplay", "Fortress", "Фортеця", "Win without losing pieces", "Виграйте без втрати", "🛡️", "gameplay", 1),
            ("victory_comeback_100", "Comeback King", "Король Повернень", "Win from 100+ deficit", "Виграйте з дефіцитом 100+", "🔄", "victory", 100),
            ("victory_speed_demon", "Speed Demon", "Швидкий Демон", "Win 3 games in one day", "Виграйте 3 гри за день", "⏱️", "victory", 3),
            ("rising_star", "Rising Star", "Висхідна Зірка", "Gain 200 rating in a week", "Отримайте 200 за тиждень", "📈", "milestone", 200),
            ("streak_precision", "Precision Streak", "Точність", "Win 5 perfect games in a row", "Виграйте 5 ідеальних поспіль", "🎯", "streak", 5),
            ("special_holiday", "Holiday", "Святковий", "Win on holiday", "Виграйте на свято", "🎄", "special", 1),
            ("special_anniversary", "Anniversary", "Ювілей", "Play first game", "Зіграйте першу гру", "🎊", "special", 1),
        ]
        
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

