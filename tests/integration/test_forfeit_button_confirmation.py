import pytest
from unittest.mock import Mock, AsyncMock

from handlers.game_handlers import GameHandlers
from engine import CheckersEngine, YELLOW


@pytest.mark.integration
class TestForfeitButtonConfirmation:
    @pytest.mark.asyncio
    async def test_in_board_forfeit_shows_confirmation_for_move_count_gt_zero(
        self, game_repository, mock_context
    ):
        handlers = GameHandlers(game_repository)

        engine = CheckersEngine()
        game_state = {
            "board": engine.board.copy(),
            "initial_board": engine.board.copy(),
            "current_turn": YELLOW,
            "blue_player_id": 111,
            "blue_player_name": "Blue",
            "yellow_player_id": 222,
            "yellow_player_name": "Yellow",
            "move_count": 3,
            "mode": "rated",
        }
        assert game_repository.save_game(12345, 1, game_state) is True

        query = Mock()
        query.id = "cb_forfeit_1"
        query.data = "forfeit"
        query.inline_message_id = None
        query.from_user = Mock()
        query.from_user.id = 111
        query.from_user.first_name = "Alice"
        query.from_user.username = "alice"
        query.answer = AsyncMock()
        query.message = Mock()
        query.message.chat = Mock()
        query.message.chat.id = 12345
        query.message.message_id = 1

        update = Mock()
        update.callback_query = query

        await handlers.forfeit_callback(update, mock_context)

        assert mock_context.bot.edit_message_text.await_count == 1
        _, kwargs = mock_context.bot.edit_message_text.await_args
        markup = kwargs.get("reply_markup")
        assert markup is not None
        callbacks = [
            btn.callback_data for row in markup.inline_keyboard for btn in row if btn.callback_data
        ]
        assert f"confirm_forfeit_12345_1_111" in callbacks
        assert f"abort_forfeit_12345_1_111" in callbacks

