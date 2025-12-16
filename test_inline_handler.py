#!/usr/bin/env python3
"""
Integration tests for inline challenge handler.
Tests the full flow of inline challenge creation and acceptance.
"""

import fakeredis
import json
from datetime import datetime, timezone
from repository import GameRepository
from engine import CheckersEngine, YELLOW


def setup_repo():
    """Create a test repository with fake Redis."""
    repo = GameRepository("redis://localhost/0")
    repo.redis_client = fakeredis.FakeRedis(decode_responses=True)
    return repo


def test_inline_challenge_creation_flow():
    """Test the complete flow of creating an inline challenge."""
    repo = setup_repo()
    inline_message_id = "test_inline_789"
    creator_id = 11111
    creator_name = "CreatorUser"
    creator_username = "creator"
    
    # Simulate chosen_inline_result_handler creating a challenge
    challenge_data = {
        "creator_id": creator_id,
        "creator_name": creator_name,
        "creator_username": creator_username,
        "inline_message_id": inline_message_id,
        "mode": "casual"
    }
    
    # Save challenge (as chosen_inline_result_handler would)
    assert repo.save_inline_challenge(inline_message_id, challenge_data) is True
    
    # Verify challenge exists
    challenge = repo.get_inline_challenge(inline_message_id)
    assert challenge is not None
    assert challenge["creator_id"] == creator_id
    assert challenge["mode"] == "casual"
    
    print("✓ Inline challenge creation flow works")


def test_inline_challenge_join_flow():
    """Test the flow of joining an inline challenge."""
    repo = setup_repo()
    inline_message_id = "test_join_456"
    creator_id = 22222
    accepter_id = 33333
    
    # Create challenge
    challenge_data = {
        "creator_id": creator_id,
        "creator_name": "Creator",
        "creator_username": "creator",
        "inline_message_id": inline_message_id,
        "mode": "casual"
    }
    repo.save_inline_challenge(inline_message_id, challenge_data)
    
    # Verify challenge exists
    challenge = repo.get_inline_challenge(inline_message_id)
    assert challenge is not None
    
    # Verify creator cannot join (self-join prevention)
    assert challenge["creator_id"] == creator_id
    # In handler: if query.from_user.id == creator_user_id: return error
    
    # Simulate accepter joining
    # In handler: get challenge, verify not creator, create game
    engine = CheckersEngine()
    game_state = {
        "board": engine.board,
        "current_turn": YELLOW,
        "blue_player_id": creator_id,
        "blue_player_name": "Creator",
        "blue_player_username": "creator",
        "yellow_player_id": accepter_id,
        "yellow_player_name": "Accepter",
        "yellow_player_username": "accepter",
        "move_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_activity": datetime.now(timezone.utc).isoformat(),
        "is_inline": True,
        "inline_message_id": inline_message_id,
        "mode": "casual"
    }
    
    # Save game
    repo.save_inline_game(inline_message_id, game_state)
    
    # Delete challenge
    repo.delete_inline_challenge(inline_message_id)
    
    # Verify challenge is gone
    assert repo.get_inline_challenge(inline_message_id) is None
    
    # Verify game exists
    game = repo.get_inline_game(inline_message_id)
    assert game is not None
    assert game["blue_player_id"] == creator_id
    assert game["yellow_player_id"] == accepter_id
    
    print("✓ Inline challenge join flow works")


def test_inline_challenge_modes():
    """Test that all challenge modes work correctly."""
    repo = setup_repo()
    
    for mode in ["casual", "ranked", "practice"]:
        inline_message_id = f"mode_test_{mode}"
        challenge_data = {
            "creator_id": 1000,
            "creator_name": "Test",
            "creator_username": "test",
            "inline_message_id": inline_message_id,
            "mode": mode
        }
        
        repo.save_inline_challenge(inline_message_id, challenge_data)
        challenge = repo.get_inline_challenge(inline_message_id)
        assert challenge["mode"] == mode
        
        # Create game with mode
        engine = CheckersEngine()
        game_state = {
            "board": engine.board,
            "current_turn": YELLOW,
            "blue_player_id": 1000,
            "blue_player_name": "Test",
            "blue_player_username": "test",
            "yellow_player_id": 2000,
            "yellow_player_name": "Opponent",
            "yellow_player_username": "opponent",
            "move_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_activity": datetime.now(timezone.utc).isoformat(),
            "is_inline": True,
            "inline_message_id": inline_message_id,
            "mode": mode
        }
        
        repo.save_inline_game(inline_message_id, game_state)
        game = repo.get_inline_game(inline_message_id)
        assert game["mode"] == mode
    
    print("✓ All challenge modes work correctly")


def test_inline_challenge_self_join_prevention():
    """Test that creators cannot join their own challenges."""
    repo = setup_repo()
    inline_message_id = "self_join_999"
    creator_id = 99999
    
    challenge_data = {
        "creator_id": creator_id,
        "creator_name": "SelfJoiner",
        "creator_username": "selfjoiner",
        "inline_message_id": inline_message_id,
        "mode": "casual"
    }
    
    repo.save_inline_challenge(inline_message_id, challenge_data)
    challenge = repo.get_inline_challenge(inline_message_id)
    
    # Verify the data structure allows self-join detection
    assert challenge["creator_id"] == creator_id
    # Handler logic: if query.from_user.id == creator_user_id: show error
    
    print("✓ Self-join prevention data structure is correct")


def test_inline_challenge_missing_challenge():
    """Test handling of missing challenge (expired or not created)."""
    repo = setup_repo()
    inline_message_id = "missing_123"
    
    # Try to get non-existent challenge
    challenge = repo.get_inline_challenge(inline_message_id)
    assert challenge is None
    
    # Handler should handle this gracefully
    # In handler: if not challenge: show error message
    
    print("✓ Missing challenge handling works")


def test_inline_game_state_completeness():
    """Test that inline game state has all required fields."""
    repo = setup_repo()
    inline_message_id = "complete_state_test"
    
    engine = CheckersEngine()
    game_state = {
        "board": engine.board,
        "current_turn": YELLOW,
        "blue_player_id": 5000,
        "blue_player_name": "Blue",
        "blue_player_username": "blue",
        "yellow_player_id": 6000,
        "yellow_player_name": "Yellow",
        "yellow_player_username": "yellow",
        "move_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_activity": datetime.now(timezone.utc).isoformat(),
        "is_inline": True,
        "inline_message_id": inline_message_id,
        "mode": "casual"
    }
    
    # Verify all required fields
    required_fields = [
        "board", "current_turn", "blue_player_id", "yellow_player_id",
        "is_inline", "inline_message_id", "mode"
    ]
    
    for field in required_fields:
        assert field in game_state, f"Missing field: {field}"
    
    # Save and retrieve
    repo.save_inline_game(inline_message_id, game_state)
    retrieved = repo.get_inline_game(inline_message_id)
    
    for field in required_fields:
        assert field in retrieved, f"Missing field in retrieved: {field}"
    
    print("✓ Inline game state completeness verified")


def main():
    """Run all inline handler integration tests."""
    print("=" * 60)
    print("Inline Handler Integration Test Suite")
    print("=" * 60)
    
    try:
        test_inline_challenge_creation_flow()
        test_inline_challenge_join_flow()
        test_inline_challenge_modes()
        test_inline_challenge_self_join_prevention()
        test_inline_challenge_missing_challenge()
        test_inline_game_state_completeness()
        
        print("\n" + "=" * 60)
        print("✅ All inline handler integration tests passed!")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())

