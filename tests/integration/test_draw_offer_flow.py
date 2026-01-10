import pytest
from unittest.mock import Mock, AsyncMock

from handlers.game_handlers import GameHandlers
from engine import CheckersEngine, YELLOW


@pytest.mark.integration
class TestDrawOfferFlow:
    @pytest.mark.asyncio
    async def test_draw_button_not_available_before_threshold(self, game_repository, mock_context):
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
            "move_count": 19,
            "mode": "casual",
        }
        assert game_repository.save_game(12345, 1, game_state) is True

        query = Mock()
        query.id = "cb_draw_offer_1"
        query.data = "draw_offer"
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

        await handlers.draw_callback(update, mock_context)

        # No message edit should happen (offer rejected), and state unchanged
        assert mock_context.bot.edit_message_text.await_count == 0
        stored = game_repository.get_game(12345, 1)
        assert stored is not None
        assert stored.get("draw_offer") in (None, {})

    @pytest.mark.asyncio
    async def test_offer_draw_sets_state_and_renders_accept_decline(self, game_repository, mock_context):
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
            "move_count": 20,
            "mode": "casual",
        }
        assert game_repository.save_game(12345, 1, game_state) is True

        query = Mock()
        query.id = "cb_draw_offer_2"
        query.data = "draw_offer"
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
        query.message.edit_text = AsyncMock()

        update = Mock()
        update.callback_query = query

        await handlers.draw_callback(update, mock_context)

        stored = game_repository.get_game(12345, 1)
        assert stored is not None
        assert isinstance(stored.get("draw_offer"), dict)
        assert stored["draw_offer"]["by_user_id"] == 111

        assert query.message.edit_text.await_count == 1
        _, kwargs = query.message.edit_text.await_args
        markup = kwargs.get("reply_markup")
        assert markup is not None
        callbacks = [
            btn.callback_data for row in markup.inline_keyboard for btn in row if btn.callback_data
        ]
        assert "draw_accept" in callbacks
        assert "draw_decline" in callbacks

    @pytest.mark.asyncio
    async def test_accept_draw_ends_game_and_deletes_active_state(self, game_repository, mock_context):
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
            "move_count": 20,
            "mode": "casual",
            "draw_offer": {"by_user_id": 111, "created_at": "2025-01-01T00:00:00"},
        }
        assert game_repository.save_game(12345, 1, game_state) is True

        query = Mock()
        query.id = "cb_draw_accept_1"
        query.data = "draw_accept"
        query.inline_message_id = None
        query.from_user = Mock()
        query.from_user.id = 222  # opponent accepts
        query.from_user.first_name = "Bob"
        query.from_user.username = "bob"
        query.answer = AsyncMock()
        query.message = Mock()
        query.message.chat = Mock()
        query.message.chat.id = 12345
        query.message.message_id = 1
        # query.edit_message_text is used by _handle_game_draw for regular games
        query.edit_message_text = AsyncMock()

        update = Mock()
        update.callback_query = query

        await handlers.draw_callback(update, mock_context)

        # Active game should be deleted after accepting draw
        assert game_repository.get_game(12345, 1) is None

        # Final message should be edited to a draw result
        assert query.edit_message_text.await_count == 1
        call = query.edit_message_text.await_args
        args = call.args or ()
        kwargs = call.kwargs or {}
        text = (kwargs.get("text") or (args[0] if args else "")) or ""
        assert "Нічия" in text


