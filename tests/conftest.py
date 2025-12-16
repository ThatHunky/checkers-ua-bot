"""
Shared pytest fixtures for Ukrainian Checkers Bot tests
"""

import pytest
import tempfile
import os
import aiosqlite
import fakeredis
from pathlib import Path
from typing import Generator
from unittest.mock import Mock, AsyncMock, MagicMock

from engine import CheckersEngine, YELLOW, BLUE
from repository import GameRepository
from ratings import RatingSystem
from achievements import AchievementSystem
from game_data import GameDataRepository
from matchmaking import MatchmakingService


@pytest.fixture
def temp_db_path() -> Generator[str, None, None]:
    """Create a temporary SQLite database file."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
async def temp_ratings_db(temp_db_path: str):
    """Create a RatingSystem with temporary database."""
    rating_system = RatingSystem(db_path=temp_db_path)
    await rating_system.initialize()
    yield rating_system


@pytest.fixture
async def temp_achievements_db(temp_db_path: str):
    """Create an AchievementSystem with temporary database."""
    achievement_system = AchievementSystem(db_path=temp_db_path)
    await achievement_system.initialize()
    yield achievement_system


@pytest.fixture
async def temp_game_data_db(temp_db_path: str):
    """Create a GameDataRepository with temporary database."""
    game_data_repo = GameDataRepository(db_path=temp_db_path)
    await game_data_repo.initialize()
    yield game_data_repo


@pytest.fixture
def fake_redis() -> fakeredis.FakeRedis:
    """Create a fake Redis instance for testing."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def game_repository(fake_redis: fakeredis.FakeRedis) -> GameRepository:
    """Create a GameRepository with fake Redis."""
    repo = GameRepository("redis://localhost/0")
    repo.redis_client = fake_redis
    return repo


@pytest.fixture
def checkers_engine() -> CheckersEngine:
    """Create a fresh CheckersEngine instance."""
    return CheckersEngine()


@pytest.fixture
def empty_engine() -> CheckersEngine:
    """Create an engine with empty board."""
    engine = CheckersEngine()
    engine.board = [0] * 64
    return engine


@pytest.fixture
def sample_game_state() -> dict:
    """Create a sample game state dictionary."""
    from datetime import datetime, timezone
    engine = CheckersEngine()
    return {
        "board": engine.board,
        "current_turn": YELLOW,
        "blue_player_id": 12345,
        "blue_player_name": "BluePlayer",
        "blue_player_username": "blueplayer",
        "yellow_player_id": 67890,
        "yellow_player_name": "YellowPlayer",
        "yellow_player_username": "yellowplayer",
        "move_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_activity": datetime.now(timezone.utc).isoformat(),
        "mode": "rated",
        "is_inline": False,
    }


@pytest.fixture
def inline_game_state() -> dict:
    """Create a sample inline game state dictionary."""
    from datetime import datetime, timezone
    engine = CheckersEngine()
    return {
        "board": engine.board,
        "current_turn": YELLOW,
        "blue_player_id": 11111,
        "blue_player_name": "Creator",
        "blue_player_username": "creator",
        "yellow_player_id": 22222,
        "yellow_player_name": "Accepter",
        "yellow_player_username": "accepter",
        "move_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_activity": datetime.now(timezone.utc).isoformat(),
        "is_inline": True,
        "inline_message_id": "test_inline_123",
        "mode": "casual",
    }


@pytest.fixture
def matchmaking_service(game_repository: GameRepository, temp_ratings_db: RatingSystem) -> MatchmakingService:
    """Create a MatchmakingService with test dependencies."""
    return MatchmakingService(game_repository, temp_ratings_db)


@pytest.fixture
def mock_bot() -> Mock:
    """Create a mock Telegram bot."""
    bot = Mock()
    bot.edit_message_text = AsyncMock()
    bot.send_message = AsyncMock()
    bot.answer_callback_query = AsyncMock()
    bot.edit_message_reply_markup = AsyncMock()
    return bot


@pytest.fixture
def mock_update() -> Mock:
    """Create a mock Telegram Update object."""
    update = Mock()
    update.effective_user = Mock()
    update.effective_user.id = 12345
    update.effective_user.first_name = "Test"
    update.effective_user.username = "testuser"
    update.effective_chat = Mock()
    update.effective_chat.id = 12345
    update.effective_chat.type = "private"
    update.effective_message = Mock()
    update.effective_message.text = None
    update.effective_message.reply_text = AsyncMock()
    update.effective_message.edit_text = AsyncMock()
    update.callback_query = None
    return update


@pytest.fixture
def mock_callback_query() -> Mock:
    """Create a mock Telegram CallbackQuery object."""
    query = Mock()
    query.id = "test_callback_123"
    query.from_user = Mock()
    query.from_user.id = 12345
    query.from_user.first_name = "Test"
    query.from_user.username = "testuser"
    query.data = "test_data"
    query.message = Mock()
    query.message.chat_id = 12345
    query.message.message_id = 1
    query.message.edit_text = AsyncMock()
    query.answer = AsyncMock()
    return query


@pytest.fixture
def mock_context() -> Mock:
    """Create a mock Telegram Context object."""
    context = Mock()
    context.bot = Mock()
    context.bot.edit_message_text = AsyncMock()
    context.bot.send_message = AsyncMock()
    context.bot.answer_callback_query = AsyncMock()
    context.job_queue = Mock()
    return context


@pytest.fixture
def sample_player_data() -> dict:
    """Create sample player data dictionary."""
    return {
        "user_id": 12345,
        "username": "testplayer",
        "rating": 1200,
        "games_played": 10,
        "wins": 6,
        "losses": 4,
        "draws": 0,
        "current_streak": 2,
        "best_streak": 3,
        "best_rating": 1250,
        "peak_rank": "Гравець",
        "total_rating_gained": 150,
        "total_rating_lost": 100,
        "perfect_games": 1,
        "comeback_wins": 0,
        "fastest_win": 5,
        "longest_game": 50,
        "games_this_week": 3,
        "games_this_month": 10,
        "last_game_date": "2025-01-15",
        "season_rating": 1200,
        "season_games": 10,
    }


@pytest.fixture
def sample_game_result() -> dict:
    """Create sample game result dictionary."""
    return {
        "winner_id": 12345,
        "loser_id": 67890,
        "winner_rating_before": 1200,
        "winner_rating_after": 1220,
        "loser_rating_before": 1180,
        "loser_rating_after": 1160,
        "rating_change_winner": 20,
        "rating_change_loser": -20,
        "move_count": 25,
        "game_duration": 300,
        "winner_color": "YELLOW",
    }

