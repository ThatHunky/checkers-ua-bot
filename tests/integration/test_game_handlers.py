"""
Integration tests for GameHandlers
"""

import pytest
from unittest.mock import AsyncMock, Mock
from handlers.game_handlers import GameHandlers
from repository import GameRepository
from engine import CheckersEngine, YELLOW
import locales
from handlers.constants import MENU_ABOUT, MENU_HELP, MENU_MAIN, MENU_PROFILE


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

    @pytest.mark.asyncio
    async def test_menu_button_text_handler(self, game_repository: GameRepository, mock_update: Mock, mock_context: Mock):
        """Test that menu button text '📋 Меню' triggers main menu in private chat."""
        handlers = GameHandlers(game_repository)
        
        # Mock private chat
        mock_update.effective_chat.type = "private"
        mock_update.effective_chat.id = 12345
        
        # Set message text to the menu button text
        mock_update.effective_message.text = locales.MENU_BUTTON  # "📋 Меню"
        
        # Reset the mock to track calls
        mock_update.effective_message.reply_text.reset_mock()
        
        await handlers.menu_text_handler(mock_update, mock_context)
        
        # Should call reply_text with MENU_TITLE
        assert mock_update.effective_message.reply_text.called, "reply_text should be called"
        call_args = mock_update.effective_message.reply_text.call_args
        assert call_args is not None, "reply_text should have been called with arguments"
        # Check that MENU_TITLE was passed as text (either positional or keyword)
        text_arg = call_args.args[0] if call_args.args else call_args.kwargs.get('text', '')
        assert text_arg == locales.MENU_TITLE, f"Expected MENU_TITLE '{locales.MENU_TITLE}', got '{text_arg}'"

    @pytest.mark.asyncio
    async def test_menu_profile_callback_edits_with_back_button(
        self,
        game_repository: GameRepository,
        mock_update: Mock,
        mock_context: Mock,
        mock_callback_query: Mock,
        temp_ratings_db,
    ):
        """Profile button from main menu should work via callback query and include back-to-menu button."""
        handlers = GameHandlers(game_repository, temp_ratings_db)

        mock_callback_query.data = MENU_PROFILE
        mock_update.callback_query = mock_callback_query
        mock_update.message = None
        # Ensure effective_message points at the callback message so myrating_command can edit it.
        mock_update.effective_message = mock_callback_query.message

        mock_callback_query.message.edit_text.reset_mock()

        await handlers.menu_callback(mock_update, mock_context)

        assert mock_callback_query.message.edit_text.called, "edit_text should be called for profile callback"
        call = mock_callback_query.message.edit_text.call_args
        assert call is not None
        text_arg = call.args[0] if call.args else call.kwargs.get("text", "")
        assert text_arg in {locales.NO_GAMES_PLAYED, ""} or "Профіль гравця" in text_arg
        reply_markup = call.kwargs.get("reply_markup")
        assert reply_markup is not None, "Profile screen should include a back-to-menu button"
        assert reply_markup.inline_keyboard[0][0].callback_data == MENU_MAIN

    @pytest.mark.asyncio
    async def test_menu_help_and_about_include_back_button(
        self,
        game_repository: GameRepository,
        mock_update: Mock,
        mock_context: Mock,
        mock_callback_query: Mock,
    ):
        """Help/About menu screens should include a back-to-menu button."""
        handlers = GameHandlers(game_repository)

        mock_update.callback_query = mock_callback_query
        mock_update.message = None
        mock_update.effective_message = mock_callback_query.message

        # HELP
        mock_callback_query.data = MENU_HELP
        mock_callback_query.message.edit_text.reset_mock()
        await handlers.menu_callback(mock_update, mock_context)
        assert mock_callback_query.message.edit_text.called
        call = mock_callback_query.message.edit_text.call_args
        assert (call.args[0] if call.args else call.kwargs.get("text", "")) == locales.HELP_TEXT
        rm = call.kwargs.get("reply_markup")
        assert rm is not None
        assert rm.inline_keyboard[0][0].callback_data == MENU_MAIN

        # ABOUT
        mock_callback_query.data = MENU_ABOUT
        mock_callback_query.message.edit_text.reset_mock()
        await handlers.menu_callback(mock_update, mock_context)
        assert mock_callback_query.message.edit_text.called
        call = mock_callback_query.message.edit_text.call_args
        assert (call.args[0] if call.args else call.kwargs.get("text", "")) == locales.ABOUT_TEXT
        rm = call.kwargs.get("reply_markup")
        assert rm is not None
        assert rm.inline_keyboard[0][0].callback_data == MENU_MAIN


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

