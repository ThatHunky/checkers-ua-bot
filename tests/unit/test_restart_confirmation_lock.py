import pytest
from unittest.mock import Mock, AsyncMock

from handlers.game_handlers import GameHandlers


@pytest.mark.unit
@pytest.mark.asyncio
async def test_restart_abort_locked_to_author(game_repository, mock_context) -> None:
    handlers = GameHandlers(game_repository)

    token = "toklock"
    game_repository.save_confirm_token(
        token,
        {
            "kind": "restart_confirm",
            "authorized_user_id": 123,
            "requester_name": "Alice",
            "active_game_ref": {"type": "regular", "chat_id": 1, "message_id": 1},
            "intent": {"type": "matchmaking", "mode": "rated"},
        },
        ttl_seconds=60,
    )

    query = Mock()
    query.data = f"restart_abort_token_{token}"
    query.inline_message_id = None
    query.from_user = Mock()
    query.from_user.id = 999  # not the author
    query.answer = AsyncMock()
    query.message = Mock()
    query.message.edit_text = AsyncMock()

    update = Mock()
    update.callback_query = query

    await handlers.restart_abort_callback(update, mock_context)

    # Should reject with an alert and not edit the message.
    assert query.answer.await_count == 1
    _, kwargs = query.answer.await_args
    assert kwargs.get("show_alert") is True
    assert query.message.edit_text.await_count == 0

