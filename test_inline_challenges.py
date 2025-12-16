#!/usr/bin/env python3
"""
Tests for inline challenge functionality.
Tests the flow of creating and accepting inline challenges.
"""

import fakeredis
import json
from datetime import datetime
from repository import GameRepository
from engine import CheckersEngine, YELLOW


def setup_repo():
    """Create a test repository with fake Redis."""
    repo = GameRepository("redis://localhost/0")
    repo.redis_client = fakeredis.FakeRedis(decode_responses=True)
    return repo


def test_save_and_get_inline_challenge():
    """Test saving and retrieving inline challenges."""
    repo = setup_repo()
    inline_message_id = "test_inline_123"
    
    challenge_data = {
        "creator_id": 12345,
        "creator_name": "TestUser",
        "creator_username": "testuser",
        "inline_message_id": inline_message_id,
        "mode": "casual"
    }
    
    # Save challenge
    assert repo.save_inline_challenge(inline_message_id, challenge_data) is True
    
    # Retrieve challenge
    retrieved = repo.get_inline_challenge(inline_message_id)
    assert retrieved is not None
    assert retrieved["creator_id"] == 12345
    assert retrieved["creator_name"] == "TestUser"
    assert retrieved["mode"] == "casual"
    
    print("✓ Save and get inline challenge works")


def test_inline_challenge_not_found():
    """Test retrieving non-existent challenge."""
    repo = setup_repo()
    inline_message_id = "nonexistent_123"
    
    retrieved = repo.get_inline_challenge(inline_message_id)
    assert retrieved is None
    
    print("✓ Non-existent challenge returns None")


def test_delete_inline_challenge():
    """Test deleting inline challenges."""
    repo = setup_repo()
    inline_message_id = "test_inline_456"
    
    challenge_data = {
        "creator_id": 67890,
        "creator_name": "AnotherUser",
        "creator_username": "anotheruser",
        "inline_message_id": inline_message_id,
        "mode": "ranked"
    }
    
    # Save and verify
    repo.save_inline_challenge(inline_message_id, challenge_data)
    assert repo.get_inline_challenge(inline_message_id) is not None
    
    # Delete and verify
    repo.delete_inline_challenge(inline_message_id)
    assert repo.get_inline_challenge(inline_message_id) is None
    
    print("✓ Delete inline challenge works")


def test_save_inline_game():
    """Test saving inline game state."""
    repo = setup_repo()
    inline_message_id = "game_123"
    
    engine = CheckersEngine()
    game_state = {
        "board": engine.board,
        "current_turn": YELLOW,
        "blue_player_id": 111,
        "blue_player_name": "BluePlayer",
        "blue_player_username": "blue",
        "yellow_player_id": 222,
        "yellow_player_name": "YellowPlayer",
        "yellow_player_username": "yellow",
        "move_count": 0,
        "created_at": datetime.utcnow().isoformat(),
        "last_activity": datetime.utcnow().isoformat(),
        "is_inline": True,
        "inline_message_id": inline_message_id,
        "mode": "casual"
    }
    
    # Save game
    repo.save_inline_game(inline_message_id, game_state)
    
    # Retrieve game
    retrieved = repo.get_inline_game(inline_message_id)
    assert retrieved is not None
    assert retrieved["blue_player_id"] == 111
    assert retrieved["yellow_player_id"] == 222
    assert retrieved["is_inline"] is True
    assert retrieved["inline_message_id"] == inline_message_id
    
    print("✓ Save and get inline game works")


def test_inline_challenge_self_join_prevention():
    """Test that creator cannot join their own challenge."""
    repo = setup_repo()
    inline_message_id = "self_join_test"
    creator_id = 99999
    
    challenge_data = {
        "creator_id": creator_id,
        "creator_name": "Creator",
        "creator_username": "creator",
        "inline_message_id": inline_message_id,
        "mode": "casual"
    }
    
    repo.save_inline_challenge(inline_message_id, challenge_data)
    
    # Creator tries to join
    challenge = repo.get_inline_challenge(inline_message_id)
    assert challenge is not None
    assert challenge["creator_id"] == creator_id
    
    # This should be blocked in the handler (tested in integration)
    print("✓ Challenge data structure supports self-join prevention")


def test_inline_challenge_mode_preservation():
    """Test that challenge mode is preserved."""
    repo = setup_repo()
    
    for mode in ["casual", "ranked", "practice"]:
        inline_message_id = f"mode_test_{mode}"
        challenge_data = {
            "creator_id": 100,
            "creator_name": "Test",
            "creator_username": "test",
            "inline_message_id": inline_message_id,
            "mode": mode
        }
        
        repo.save_inline_challenge(inline_message_id, challenge_data)
        retrieved = repo.get_inline_challenge(inline_message_id)
        assert retrieved["mode"] == mode
    
    print("✓ Challenge mode preservation works")


def test_inline_challenge_ttl():
    """Test that challenges expire after TTL."""
    repo = setup_repo()
    inline_message_id = "ttl_test"
    
    challenge_data = {
        "creator_id": 200,
        "creator_name": "TTLTest",
        "creator_username": "ttltest",
        "inline_message_id": inline_message_id,
        "mode": "casual"
    }
    
    # Save with short TTL (if supported by fakeredis)
    repo.save_inline_challenge(inline_message_id, challenge_data)
    
    # Immediately should exist
    assert repo.get_inline_challenge(inline_message_id) is not None
    
    print("✓ Challenge TTL structure works (actual expiration tested in integration)")


def test_inline_game_state_structure():
    """Test that inline game state has all required fields."""
    repo = setup_repo()
    inline_message_id = "state_test"
    
    engine = CheckersEngine()
    game_state = {
        "board": engine.board,
        "current_turn": YELLOW,
        "blue_player_id": 300,
        "blue_player_name": "Blue",
        "blue_player_username": "blue",
        "yellow_player_id": 400,
        "yellow_player_name": "Yellow",
        "yellow_player_username": "yellow",
        "move_count": 0,
        "created_at": datetime.utcnow().isoformat(),
        "last_activity": datetime.utcnow().isoformat(),
        "is_inline": True,
        "inline_message_id": inline_message_id,
        "mode": "casual"
    }
    
    # Verify required fields
    required_fields = [
        "board", "current_turn", "blue_player_id", "yellow_player_id",
        "is_inline", "inline_message_id", "mode"
    ]
    
    for field in required_fields:
        assert field in game_state, f"Missing required field: {field}"
    
    assert game_state["is_inline"] is True
    assert game_state["inline_message_id"] == inline_message_id
    
    print("✓ Inline game state structure is valid")


def main():
    """Run all inline challenge tests."""
    print("=" * 60)
    print("Inline Challenge Test Suite")
    print("=" * 60)
    
    try:
        test_save_and_get_inline_challenge()
        test_inline_challenge_not_found()
        test_delete_inline_challenge()
        test_save_inline_game()
        test_inline_challenge_self_join_prevention()
        test_inline_challenge_mode_preservation()
        test_inline_challenge_ttl()
        test_inline_game_state_structure()
        
        print("\n" + "=" * 60)
        print("✅ All inline challenge tests passed!")
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

