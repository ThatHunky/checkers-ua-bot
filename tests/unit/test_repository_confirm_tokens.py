import pytest

from repository import GameRepository


@pytest.mark.unit
def test_confirm_token_roundtrip(game_repository: GameRepository) -> None:
    token = "tok123"
    payload = {"k": "v", "n": 1}

    assert game_repository.save_confirm_token(token, payload, ttl_seconds=60) is True
    assert game_repository.get_confirm_token(token) == payload
    assert game_repository.delete_confirm_token(token) is True
    assert game_repository.get_confirm_token(token) is None


@pytest.mark.unit
def test_get_user_inline_game_finds_player(game_repository: GameRepository, inline_game_state: dict) -> None:
    inline_message_id = inline_game_state["inline_message_id"]
    assert game_repository.save_inline_game(inline_message_id, inline_game_state) is True

    found = game_repository.get_user_inline_game(inline_game_state["blue_player_id"])
    assert found is not None
    found_inline_id, found_state = found
    assert found_inline_id == inline_message_id
    assert found_state["blue_player_id"] == inline_game_state["blue_player_id"]

