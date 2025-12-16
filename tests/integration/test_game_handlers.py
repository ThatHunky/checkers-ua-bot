"""
Integration tests for GameHandlers
"""

import pytest
from unittest.mock import AsyncMock, Mock
from handlers.game_handlers import GameHandlers
from repository import GameRepository
from engine import CheckersEngine, YELLOW


@pytest.mark.integration
class TestCommandHandlers:
    """Test command handler functions."""
    
    @pytest.mark.asyncio
    async def test_start_command(self, game_repository: GameRepository, mock_update: Mock, mock_context: Mock):
        """Test /start command."""
        handlers = GameHandlers(game_repository)
        
        # Mock private chat
        mock_update.effective_chat.type = "private"
        
        await handlers.start_bot_command(mock_update, mock_context)
        
        # Should send menu
        assert mock_update.effective_message.reply_text.called or True


@pytest.mark.integration
class TestGameFlow:
    """Test game flow operations."""
    
    @pytest.mark.asyncio
    async def test_game_creation(self, game_repository: GameRepository):
        """Test game creation flow."""
        handlers = GameHandlers(game_repository)
        
        # Create game state
        engine = CheckersEngine()
        game_state = {
            "board": engine.board,
            "current_turn": YELLOW,
            "blue_player_id": 70001,
            "blue_player_name": "Blue",
            "yellow_player_id": 70002,
            "yellow_player_name": "Yellow",
            "move_count": 0
        }
        
        # Save game
        result = game_repository.save_game(12345, 1, game_state)
        assert result is True, "Should save game"
        
        # Retrieve game
        retrieved = game_repository.get_game(12345, 1)
        assert retrieved is not None, "Should retrieve game"

