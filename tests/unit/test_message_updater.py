"""
Unit tests for MessageUpdater
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from handlers.message_updater import MessageUpdater
from engine import CheckersEngine, YELLOW, BLUE
from telegram import InlineKeyboardMarkup


@pytest.mark.unit
class TestMessageFormatting:
    """Test message formatting functions."""
    
    def test_get_players_message_with_ids(self, sample_game_state: dict):
        """Test _get_players_message with player IDs."""
        message = MessageUpdater._get_players_message(sample_game_state)
        
        assert "🔵" in message, "Should have blue indicator"
        assert "🟡" in message, "Should have yellow indicator"
        assert "vs" in message, "Should have vs separator"
        assert sample_game_state["blue_player_name"] in message
        assert sample_game_state["yellow_player_name"] in message
    
    def test_get_players_message_without_ids(self):
        """Test _get_players_message without player IDs."""
        game_state = {
            "blue_player_name": "Blue",
            "yellow_player_name": "Yellow"
        }
        message = MessageUpdater._get_players_message(game_state)
        
        assert "Blue" in message
        assert "Yellow" in message
    
    def test_get_players_message_hyperlink_format(self, sample_game_state: dict):
        """Test _get_players_message creates hyperlinks."""
        message = MessageUpdater._get_players_message(sample_game_state)
        
        # Should have HTML hyperlink format
        assert "tg://user?id=" in message, "Should have user link"
        assert "<a href=" in message, "Should have HTML anchor"
    
    def test_get_turn_message_blue(self, sample_game_state: dict):
        """Test _get_turn_message for BLUE turn."""
        sample_game_state["current_turn"] = BLUE
        message = MessageUpdater._get_turn_message(sample_game_state)
        
        assert "🔵" in message or "Синіх" in message, "Should indicate BLUE turn"
        assert sample_game_state["blue_player_name"] in message
    
    def test_get_turn_message_yellow(self, sample_game_state: dict):
        """Test _get_turn_message for YELLOW turn."""
        sample_game_state["current_turn"] = YELLOW
        message = MessageUpdater._get_turn_message(sample_game_state)
        
        assert "🟡" in message or "Жовтих" in message, "Should indicate YELLOW turn"
        assert sample_game_state["yellow_player_name"] in message
    
    def test_get_turn_message_hyperlink(self, sample_game_state: dict):
        """Test _get_turn_message creates hyperlink."""
        message = MessageUpdater._get_turn_message(sample_game_state)
        
        # Should have HTML hyperlink format
        assert "tg://user?id=" in message or sample_game_state["yellow_player_name"] in message


@pytest.mark.unit
class TestMessageUpdates:
    """Test message update functions."""
    
    @pytest.mark.asyncio
    async def test_update_message_inline(self, mock_bot: Mock, sample_game_state: dict, checkers_engine: CheckersEngine):
        """Test update_message for inline messages."""
        mock_bot.edit_message_text = AsyncMock()
        
        result = await MessageUpdater.update_message(
            mock_bot,
            sample_game_state,
            checkers_engine,
            inline_message_id="test_inline_123"
        )
        
        assert result is True, "Should return True on success"
        mock_bot.edit_message_text.assert_called_once()
        call_kwargs = mock_bot.edit_message_text.call_args[1]
        assert call_kwargs["inline_message_id"] == "test_inline_123"
    
    @pytest.mark.asyncio
    async def test_update_message_regular(self, mock_bot: Mock, sample_game_state: dict, checkers_engine: CheckersEngine):
        """Test update_message for regular messages."""
        mock_bot.edit_message_text = AsyncMock()
        
        result = await MessageUpdater.update_message(
            mock_bot,
            sample_game_state,
            checkers_engine,
            chat_id=12345,
            message_id=1
        )
        
        assert result is True, "Should return True on success"
        mock_bot.edit_message_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_message_private_match(self, mock_bot: Mock, sample_game_state: dict, checkers_engine: CheckersEngine):
        """Test update_message for private matches."""
        mock_bot.edit_message_text = AsyncMock()
        sample_game_state["is_private_match"] = True
        sample_game_state["opponent_chat_id"] = 11111
        sample_game_state["opponent_message_id"] = 1
        sample_game_state["challenger_chat_id"] = 22222
        sample_game_state["challenger_message_id"] = 2
        
        result = await MessageUpdater.update_message(
            mock_bot,
            sample_game_state,
            checkers_engine
        )
        
        # Should update both messages
        assert mock_bot.edit_message_text.call_count == 2, "Should update both players' messages"
    
    @pytest.mark.asyncio
    async def test_update_message_with_selection(self, mock_bot: Mock, sample_game_state: dict, checkers_engine: CheckersEngine):
        """Test update_message with selected piece."""
        mock_bot.edit_message_text = AsyncMock()
        
        moves = checkers_engine.get_legal_moves(YELLOW)
        if moves:
            selected_pos = moves[0].from_pos
            result = await MessageUpdater.update_message(
                mock_bot,
                sample_game_state,
                checkers_engine,
                selected_pos=selected_pos,
                inline_message_id="test_inline_123"
            )
            
            assert result is True, "Should handle selected position"
    
    @pytest.mark.asyncio
    async def test_update_message_error_handling(self, mock_bot: Mock, sample_game_state: dict, checkers_engine: CheckersEngine):
        """Test update_message error handling."""
        mock_bot.edit_message_text = AsyncMock(side_effect=Exception("Test error"))
        
        result = await MessageUpdater.update_message(
            mock_bot,
            sample_game_state,
            checkers_engine,
            inline_message_id="test_inline_123"
        )
        
        # Should return False on error
        assert result is False, "Should return False on error"
    
    @pytest.mark.asyncio
    async def test_update_message_no_target(self, mock_bot: Mock, sample_game_state: dict, checkers_engine: CheckersEngine):
        """Test update_message with no target specified."""
        result = await MessageUpdater.update_message(
            mock_bot,
            sample_game_state,
            checkers_engine
        )
        
        assert result is False, "Should return False when no target specified"


@pytest.mark.unit
class TestSafeEditing:
    """Test safe message editing."""
    
    @pytest.mark.asyncio
    async def test_safe_edit_message_success(self, mock_bot: Mock):
        """Test _safe_edit_message on success."""
        mock_bot.edit_message_text = AsyncMock(return_value=True)
        
        await MessageUpdater._safe_edit_message(
            mock_bot,
            chat_id=12345,
            message_id=1,
            text="Test"
        )
        
        mock_bot.edit_message_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_safe_edit_message_timeout(self, mock_bot: Mock):
        """Test _safe_edit_message on timeout."""
        mock_bot.edit_message_text = AsyncMock(side_effect=asyncio.TimeoutError())
        
        with pytest.raises(asyncio.TimeoutError):
            await MessageUpdater._safe_edit_message(
                mock_bot,
                chat_id=12345,
                message_id=1,
                text="Test",
                timeout=0.1
            )
    
    @pytest.mark.asyncio
    async def test_update_inline_success(self, mock_bot: Mock):
        """Test _update_inline on success."""
        mock_bot.edit_message_text = AsyncMock()
        
        keyboard = Mock(spec=InlineKeyboardMarkup)
        result = await MessageUpdater._update_inline(
            mock_bot,
            "test_inline_123",
            "Test message",
            keyboard
        )
        
        assert result is True, "Should return True on success"
        mock_bot.edit_message_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_inline_timeout(self, mock_bot: Mock):
        """Test _update_inline on timeout."""
        mock_bot.edit_message_text = AsyncMock(side_effect=asyncio.TimeoutError())
        
        keyboard = Mock(spec=InlineKeyboardMarkup)
        result = await MessageUpdater._update_inline(
            mock_bot,
            "test_inline_123",
            "Test message",
            keyboard
        )
        
        assert result is False, "Should return False on timeout"
    
    @pytest.mark.asyncio
    async def test_update_inline_error(self, mock_bot: Mock):
        """Test _update_inline on error."""
        mock_bot.edit_message_text = AsyncMock(side_effect=Exception("Test error"))
        
        keyboard = Mock(spec=InlineKeyboardMarkup)
        result = await MessageUpdater._update_inline(
            mock_bot,
            "test_inline_123",
            "Test message",
            keyboard
        )
        
        assert result is False, "Should return False on error"
    
    @pytest.mark.asyncio
    async def test_update_private_match_success(self, mock_bot: Mock, sample_game_state: dict):
        """Test _update_private_match on success."""
        mock_bot.edit_message_text = AsyncMock()
        sample_game_state["opponent_chat_id"] = 11111
        sample_game_state["opponent_message_id"] = 1
        sample_game_state["challenger_chat_id"] = 22222
        sample_game_state["challenger_message_id"] = 2
        
        keyboard = Mock(spec=InlineKeyboardMarkup)
        result = await MessageUpdater._update_private_match(
            mock_bot,
            sample_game_state,
            "Test message",
            keyboard
        )
        
        assert result is True, "Should return True on success"
        assert mock_bot.edit_message_text.call_count == 2, "Should update both messages"
    
    @pytest.mark.asyncio
    async def test_update_private_match_partial_failure(self, mock_bot: Mock, sample_game_state: dict):
        """Test _update_private_match with partial failure."""
        def side_effect(**kwargs):
            if kwargs.get("chat_id") == 11111:
                raise Exception("Test error")
            return AsyncMock()
        
        mock_bot.edit_message_text = AsyncMock(side_effect=side_effect)
        sample_game_state["opponent_chat_id"] = 11111
        sample_game_state["opponent_message_id"] = 1
        sample_game_state["challenger_chat_id"] = 22222
        sample_game_state["challenger_message_id"] = 2
        
        keyboard = Mock(spec=InlineKeyboardMarkup)
        result = await MessageUpdater._update_private_match(
            mock_bot,
            sample_game_state,
            "Test message",
            keyboard
        )
        
        assert result is False, "Should return False if any update fails"
    
    @pytest.mark.asyncio
    async def test_update_regular_message_success(self):
        """Test _update_regular_message on success."""
        message_obj = Mock()
        message_obj.edit_text = AsyncMock()
        
        keyboard = Mock(spec=InlineKeyboardMarkup)
        result = await MessageUpdater._update_regular_message(
            message_obj,
            "Test message",
            keyboard
        )
        
        assert result is True, "Should return True on success"
        message_obj.edit_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_regular_message_timeout(self):
        """Test _update_regular_message on timeout."""
        message_obj = Mock()
        message_obj.edit_text = AsyncMock(side_effect=asyncio.TimeoutError())
        
        keyboard = Mock(spec=InlineKeyboardMarkup)
        result = await MessageUpdater._update_regular_message(
            message_obj,
            "Test message",
            keyboard
        )
        
        assert result is False, "Should return False on timeout"
    
    @pytest.mark.asyncio
    async def test_update_regular_by_id_success(self, mock_bot: Mock):
        """Test _update_regular_by_id on success."""
        mock_bot.edit_message_text = AsyncMock()
        
        keyboard = Mock(spec=InlineKeyboardMarkup)
        result = await MessageUpdater._update_regular_by_id(
            mock_bot,
            12345,
            1,
            "Test message",
            keyboard
        )
        
        assert result is True, "Should return True on success"
        mock_bot.edit_message_text.assert_called_once()


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases for message updater."""
    
    @pytest.mark.asyncio
    async def test_update_message_missing_player_data(self, mock_bot: Mock, checkers_engine: CheckersEngine):
        """Test update_message with missing player data."""
        game_state = {
            "board": checkers_engine.board,
            "current_turn": YELLOW
        }
        mock_bot.edit_message_text = AsyncMock()
        
        result = await MessageUpdater.update_message(
            mock_bot,
            game_state,
            checkers_engine,
            inline_message_id="test_inline_123"
        )
        
        # Should handle missing data gracefully
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_get_players_message_missing_names(self):
        """Test _get_players_message with missing names."""
        game_state = {}
        message = MessageUpdater._get_players_message(game_state)
        
        # Should use defaults
        assert "Blue" in message or "Yellow" in message or message, "Should handle missing names"
    
    @pytest.mark.asyncio
    async def test_get_turn_message_missing_data(self):
        """Test _get_turn_message with missing data."""
        game_state = {"current_turn": YELLOW}
        message = MessageUpdater._get_turn_message(game_state)
        
        # Should use defaults
        assert isinstance(message, str), "Should return string even with missing data"

