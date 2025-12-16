"""
Integration tests for GameRepository
"""

import pytest
import json
from datetime import datetime, timezone
from repository import GameRepository
from engine import CheckersEngine, YELLOW


@pytest.mark.integration
class TestGameStateManagement:
    """Test game state save/retrieve/delete operations."""
    
    def test_save_game(self, game_repository: GameRepository, sample_game_state: dict):
        """Test saving game state."""
        result = game_repository.save_game(12345, 1, sample_game_state)
        assert result is True, "Should save game successfully"
    
    def test_get_game(self, game_repository: GameRepository, sample_game_state: dict):
        """Test retrieving game state."""
        game_repository.save_game(12345, 1, sample_game_state)
        retrieved = game_repository.get_game(12345, 1)
        
        assert retrieved is not None, "Should retrieve game"
        assert retrieved["blue_player_id"] == sample_game_state["blue_player_id"]
        assert retrieved["yellow_player_id"] == sample_game_state["yellow_player_id"]
    
    def test_delete_game(self, game_repository: GameRepository, sample_game_state: dict):
        """Test deleting game state."""
        game_repository.save_game(12345, 1, sample_game_state)
        result = game_repository.delete_game(12345, 1)
        
        assert result is True, "Should delete game"
        retrieved = game_repository.get_game(12345, 1)
        assert retrieved is None, "Game should be deleted"
    
    def test_get_game_nonexistent(self, game_repository: GameRepository):
        """Test retrieving nonexistent game."""
        retrieved = game_repository.get_game(99999, 999)
        assert retrieved is None, "Should return None for nonexistent game"


@pytest.mark.integration
class TestMatchmakingQueue:
    """Test matchmaking queue operations."""
    
    def test_mm_enqueue(self, game_repository: GameRepository):
        """Test enqueueing player in matchmaking."""
        ticket = game_repository.mm_enqueue(10001, 100, "rated", 1200)
        
        assert ticket is not None, "Should return ticket"
        assert ticket["status"] == "queued", "Status should be queued"
        assert ticket["user_id"] == 10001
    
    def test_mm_cancel(self, game_repository: GameRepository):
        """Test canceling matchmaking."""
        game_repository.mm_enqueue(10002, 100, "rated", 1200)
        result = game_repository.mm_cancel(10002)
        
        assert result is True, "Should cancel successfully"
        status = game_repository.mm_status(10002)
        assert status["status"] == "cancelled", "Status should be cancelled"
    
    def test_mm_status(self, game_repository: GameRepository):
        """Test getting matchmaking status."""
        game_repository.mm_enqueue(10003, 100, "rated", 1200)
        status = game_repository.mm_status(10003)
        
        assert status is not None, "Should return status"
        assert status["status"] == "queued"
    
    def test_mm_try_match(self, game_repository: GameRepository):
        """Test matchmaking logic."""
        game_repository.mm_enqueue(10004, 100, "rated", 1200)
        game_repository.mm_enqueue(10005, 101, "rated", 1210)
        
        result = game_repository.mm_try_match("rated", base_delta=50, step=50, step_seconds=1, max_delta=400)
        
        assert result is not None, "Should find match"
        assert "users" in result
        user_ids = {u["user_id"] for u in result["users"]}
        assert 10004 in user_ids and 10005 in user_ids, "Should match both players"
    
    def test_mm_try_match_rating_difference(self, game_repository: GameRepository):
        """Test matchmaking prefers close ratings."""
        game_repository.mm_enqueue(10006, 100, "rated", 1200)
        game_repository.mm_enqueue(10007, 101, "rated", 1210)
        game_repository.mm_enqueue(10008, 102, "rated", 1500)
        
        result = game_repository.mm_try_match("rated", base_delta=50, step=50, step_seconds=1, max_delta=400)
        
        assert result is not None
        user_ids = {u["user_id"] for u in result["users"]}
        # Should match closer ratings (10006 and 10007)
        assert {10006, 10007} == user_ids, "Should match players with closer ratings"


@pytest.mark.integration
class TestInviteSystem:
    """Test invite system operations."""
    
    def test_mm_create_invite(self, game_repository: GameRepository):
        """Test creating invite."""
        result = game_repository.mm_create_invite(20001, 100, "rated", "ABC123")
        
        assert result is not None, "Should create invite"
        assert "code" in result
        assert result["code"] == "ABC123"
    
    def test_mm_accept_invite(self, game_repository: GameRepository):
        """Test accepting invite."""
        game_repository.mm_create_invite(20002, 100, "rated", "XYZ789")
        invite = game_repository.mm_accept_invite(20003, 200, "XYZ789")
        
        assert invite is not None, "Should accept invite"
        assert invite.get("status") == "used", "Status should be used"
    
    def test_mm_accept_invite_duplicate(self, game_repository: GameRepository):
        """Test duplicate invite acceptance."""
        game_repository.mm_create_invite(20004, 100, "rated", "DUP123")
        game_repository.mm_accept_invite(20005, 200, "DUP123")
        
        # Second acceptance should fail
        again = game_repository.mm_accept_invite(20006, 300, "DUP123")
        assert again is None, "Should not accept duplicate"


@pytest.mark.integration
class TestInlineChallenges:
    """Test inline challenge operations."""
    
    def test_save_inline_challenge(self, game_repository: GameRepository):
        """Test saving inline challenge."""
        challenge_data = {
            "creator_id": 30001,
            "creator_name": "Creator",
            "creator_username": "creator",
            "inline_message_id": "inline_123",
            "mode": "casual"
        }
        
        result = game_repository.save_inline_challenge("inline_123", challenge_data)
        assert result is True, "Should save challenge"
    
    def test_get_inline_challenge(self, game_repository: GameRepository):
        """Test retrieving inline challenge."""
        challenge_data = {
            "creator_id": 30002,
            "creator_name": "Creator",
            "creator_username": "creator",
            "inline_message_id": "inline_456",
            "mode": "casual"
        }
        
        game_repository.save_inline_challenge("inline_456", challenge_data)
        retrieved = game_repository.get_inline_challenge("inline_456")
        
        assert retrieved is not None, "Should retrieve challenge"
        assert retrieved["creator_id"] == 30002
    
    def test_delete_inline_challenge(self, game_repository: GameRepository):
        """Test deleting inline challenge."""
        challenge_data = {
            "creator_id": 30003,
            "creator_name": "Creator",
            "inline_message_id": "inline_789",
            "mode": "casual"
        }
        
        game_repository.save_inline_challenge("inline_789", challenge_data)
        game_repository.delete_inline_challenge("inline_789")
        
        retrieved = game_repository.get_inline_challenge("inline_789")
        assert retrieved is None, "Challenge should be deleted"


@pytest.mark.integration
class TestInlineGames:
    """Test inline game operations."""
    
    def test_save_inline_game(self, game_repository: GameRepository, inline_game_state: dict):
        """Test saving inline game."""
        game_repository.save_inline_game("inline_game_123", inline_game_state)
        
        retrieved = game_repository.get_inline_game("inline_game_123")
        assert retrieved is not None, "Should retrieve inline game"
        assert retrieved["is_inline"] is True
    
    def test_get_inline_game(self, game_repository: GameRepository, inline_game_state: dict):
        """Test retrieving inline game."""
        game_repository.save_inline_game("inline_game_456", inline_game_state)
        retrieved = game_repository.get_inline_game("inline_game_456")
        
        assert retrieved["blue_player_id"] == inline_game_state["blue_player_id"]
        assert retrieved["yellow_player_id"] == inline_game_state["yellow_player_id"]


@pytest.mark.integration
class TestConnectionManagement:
    """Test connection and health checks."""
    
    def test_ping(self, game_repository: GameRepository):
        """Test Redis ping."""
        result = game_repository.ping()
        assert result is True, "Should ping successfully"

