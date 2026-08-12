"""
Integration tests for inline challenge callback payload handling.
"""

import pytest
from unittest.mock import AsyncMock, Mock

import locales
from handlers.game_handlers import GameHandlers
from repository import GameRepository


def _callback_answer_text(call) -> str:
    if call.args:
        return call.args[0]
    return call.kwargs.get("text", "")


@pytest.mark.integration
class TestInlineChallengeCallbackPayloads:
    @pytest.mark.asyncio
    async def test_inline_join_uses_payload_creator_when_challenge_missing(
        self,
        game_repository: GameRepository,
        mock_context: Mock,
    ):
        handlers = GameHandlers(game_repository)
        handlers._update_inline_game_message = AsyncMock(return_value=True)

        game_repository.register_user(5001, "creator", "Creator")
        game_repository.register_user(5002, "joiner", "Joiner")

        query = Mock()
        query.from_user = Mock()
        query.from_user.id = 5002
        query.from_user.first_name = "Joiner"
        query.from_user.username = "joiner"
        query.inline_message_id = "inline_payload_join"
        query.data = "inline_challenge_join:5001:rated"
        query.answer = AsyncMock()

        update = Mock()
        update.callback_query = query

        await handlers.inline_challenge_join_callback(update, mock_context)

        game_state = game_repository.get_inline_game("inline_payload_join")
        assert game_state is not None
        assert game_state["blue_player_id"] == 5001
        assert game_state["yellow_player_id"] == 5002
        # The payload says "rated", but the stored challenge is gone and the payload
        # carries no timestamp, so this could equally be a button from a months-old
        # message. Rebuilding it rated would let a stranger put the absent creator's
        # ELO on the line; the rebuild is deliberately downgraded to casual.
        assert game_state["mode"] == "casual"

        answer_texts = [_callback_answer_text(c) for c in query.answer.await_args_list]
        assert locales.INLINE_CHALLENGE_SELF_JOIN not in answer_texts

    @pytest.mark.asyncio
    async def test_live_challenge_record_keeps_its_rated_mode(
        self,
        game_repository: GameRepository,
        mock_context: Mock,
    ):
        """The downgrade applies only to the payload-rebuild path, not to live records."""
        handlers = GameHandlers(game_repository)
        handlers._update_inline_game_message = AsyncMock(return_value=True)

        game_repository.register_user(5011, "creator2", "Creator2")
        game_repository.register_user(5012, "joiner2", "Joiner2")
        game_repository.save_inline_challenge(
            "inline_live_rated",
            {
                "creator_id": 5011,
                "creator_name": "Creator2",
                "creator_username": "creator2",
                "inline_message_id": "inline_live_rated",
                "mode": "rated",
            },
        )

        query = Mock()
        query.from_user = Mock()
        query.from_user.id = 5012
        query.from_user.first_name = "Joiner2"
        query.from_user.username = "joiner2"
        query.inline_message_id = "inline_live_rated"
        query.data = "inline_challenge_join:5011:rated"
        query.answer = AsyncMock()

        update = Mock()
        update.callback_query = query

        await handlers.inline_challenge_join_callback(update, mock_context)

        game_state = game_repository.get_inline_game("inline_live_rated")
        assert game_state is not None
        assert game_state["mode"] == "rated"

    @pytest.mark.asyncio
    async def test_accept_inline_rejects_non_target_user(
        self,
        game_repository: GameRepository,
        mock_context: Mock,
    ):
        handlers = GameHandlers(game_repository)
        handlers._update_inline_game_message = AsyncMock(return_value=True)

        query = Mock()
        query.from_user = Mock()
        query.from_user.id = 6003
        query.from_user.first_name = "Intruder"
        query.from_user.username = "intruder"
        query.inline_message_id = "inline_targeted"
        query.data = "accept_inline:6001:casual:6002"
        query.answer = AsyncMock()

        update = Mock()
        update.callback_query = query

        await handlers.accept_inline_callback(update, mock_context)

        assert game_repository.get_inline_game("inline_targeted") is None
        query.answer.assert_awaited_with(
            locales.INLINE_CHALLENGE_WRONG_OPPONENT, show_alert=True
        )

    @pytest.mark.asyncio
    async def test_inline_query_challenge_buttons_include_creator_and_mode_payload(
        self,
        game_repository: GameRepository,
        mock_context: Mock,
    ):
        handlers = GameHandlers(game_repository)

        query = Mock()
        query.from_user = Mock()
        query.from_user.id = 7001
        query.from_user.first_name = "Creator"
        query.from_user.username = "creator"
        query.query = ""
        query.answer = AsyncMock()

        update = Mock()
        update.inline_query = query

        await handlers.inline_query_handler(update, mock_context)

        query.answer.assert_awaited()
        results = query.answer.await_args.args[0]
        callbacks = [
            item.reply_markup.inline_keyboard[0][0].callback_data for item in results
        ]
        assert callbacks == [
            "inline_challenge_join:7001:casual",
            "inline_challenge_join:7001:rated",
            "inline_challenge_join:7001:practice",
        ]

    @pytest.mark.asyncio
    async def test_inline_query_targeted_challenge_includes_target_user_in_payload(
        self,
        game_repository: GameRepository,
        mock_context: Mock,
    ):
        handlers = GameHandlers(game_repository)
        game_repository.register_user(8002, "targetuser", "Target")

        query = Mock()
        query.from_user = Mock()
        query.from_user.id = 8001
        query.from_user.first_name = "Creator"
        query.from_user.username = "creator"
        query.query = "@targetuser"
        query.answer = AsyncMock()

        update = Mock()
        update.inline_query = query

        await handlers.inline_query_handler(update, mock_context)

        query.answer.assert_awaited()
        results = query.answer.await_args.args[0]
        callback_data = results[0].reply_markup.inline_keyboard[0][0].callback_data
        assert callback_data == "accept_inline:8001:casual:8002"
