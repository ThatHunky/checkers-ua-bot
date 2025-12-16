"""
Integration tests for GameDataRepository
"""

import pytest
from game_data import GameDataRepository
from engine import CheckersEngine


@pytest.mark.integration
class TestDatabaseInitialization:
    """Test database initialization."""
    
    @pytest.mark.asyncio
    async def test_initialize_creates_tables(self, temp_game_data_db: GameDataRepository):
        """Test initialize creates database tables."""
        # Database should be initialized by fixture
        # Verify by trying to save a game
        game_data = {
            "game_id": "test_game_123",
            "blue_player_id": 60001,
            "blue_player_name": "Blue",
            "yellow_player_id": 60002,
            "yellow_player_name": "Yellow",
            "winner_id": 60001,
            "winner_name": "Blue",
            "winner_color": "BLUE",
            "initial_board": CheckersEngine().board,
            "move_history": [],
            "final_board": CheckersEngine().board,
            "completed_at": "2025-01-15T12:00:00"
        }
        
        result = temp_game_data_db.save_completed_game(game_data)
        assert result is True, "Should save game"


@pytest.mark.integration
class TestGameStorage:
    """Test game storage operations."""
    
    def test_save_completed_game(self, temp_game_data_db: GameDataRepository):
        """Test saving completed game."""
        game_data = {
            "game_id": "test_game_456",
            "blue_player_id": 60010,
            "blue_player_name": "Blue",
            "yellow_player_id": 60011,
            "yellow_player_name": "Yellow",
            "winner_id": 60010,
            "winner_name": "Blue",
            "winner_color": "BLUE",
            "initial_board": CheckersEngine().board,
            "move_history": [],
            "final_board": CheckersEngine().board,
            "completed_at": "2025-01-15T12:00:00"
        }
        
        result = temp_game_data_db.save_completed_game(game_data)
        assert result is True, "Should save game successfully"
    
    def test_get_user_games(self, temp_game_data_db: GameDataRepository):
        """Test retrieving user games."""
        game_data = {
            "game_id": "test_game_789",
            "blue_player_id": 60020,
            "blue_player_name": "Blue",
            "yellow_player_id": 60021,
            "yellow_player_name": "Yellow",
            "winner_id": 60020,
            "winner_name": "Blue",
            "winner_color": "BLUE",
            "initial_board": CheckersEngine().board,
            "move_history": [],
            "final_board": CheckersEngine().board,
            "completed_at": "2025-01-15T12:00:00"
        }
        
        temp_game_data_db.save_completed_game(game_data)
        games = temp_game_data_db.get_user_games(60020, limit=10)
        
        assert isinstance(games, list)
        assert len(games) >= 1, "Should retrieve user games"

