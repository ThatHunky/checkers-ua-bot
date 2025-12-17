"""
Integration tests for in-game review pager (review_ callbacks).
"""

import pytest
from unittest.mock import Mock, AsyncMock

from handlers.game_handlers import GameHandlers
from engine import CheckersEngine, YELLOW


@pytest.mark.integration
class TestInGameReviewPager:
    @pytest.mark.asyncio
    async def test_review_callback_renders_review_and_includes_return_to_live(
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
            "move_count": 1,
            "move_history": [
                {
                    "from": 10,
                    "to": 14,
                    "captures": [],
                    "board_before": engine.board.copy(),
                    "player": "yellow",
                }
            ],
        }
        assert game_repository.save_game(12345, 1, game_state) is True

        query = Mock()
        query.data = "review_0"
        query.inline_message_id = None
        query.from_user = Mock()
        query.from_user.id = 111  # player
        query.answer = AsyncMock()
        query.message = Mock()
        query.message.chat = Mock()
        query.message.chat.id = 12345
        query.message.message_id = 1

        update = Mock()
        update.callback_query = query

        await handlers.review_callback(update, mock_context)

        # Should edit the message and include review_live in reply_markup.
        assert mock_context.bot.edit_message_text.await_count == 1
        _, kwargs = mock_context.bot.edit_message_text.await_args
        markup = kwargs.get("reply_markup")
        assert markup is not None
        flat_callbacks = [
            btn.callback_data for row in markup.inline_keyboard for btn in row if btn.callback_data
        ]
        assert "review_live" in flat_callbacks

    @pytest.mark.asyncio
    async def test_review_callback_rejects_non_player(self, game_repository, mock_context):
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
            "move_count": 1,
            "move_history": [
                {
                    "from": 10,
                    "to": 14,
                    "captures": [],
                    "board_before": engine.board.copy(),
                    "player": "yellow",
                }
            ],
        }
        assert game_repository.save_game(12345, 1, game_state) is True

        query = Mock()
        query.data = "review_0"
        query.inline_message_id = None
        query.from_user = Mock()
        query.from_user.id = 999  # not a player
        query.answer = AsyncMock()
        query.message = Mock()
        query.message.chat = Mock()
        query.message.chat.id = 12345
        query.message.message_id = 1

        update = Mock()
        update.callback_query = query

        await handlers.review_callback(update, mock_context)

        # Should not attempt to edit message.
        assert mock_context.bot.edit_message_text.await_count == 0


