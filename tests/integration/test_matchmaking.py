"""
Integration tests for MatchmakingService
"""

import pytest
from matchmaking import MatchmakingService, TicketStatus
from ratings import INITIAL_RATING


@pytest.mark.integration
class TestEnqueueDequeue:
    """Test enqueue and dequeue operations."""
    
    @pytest.mark.asyncio
    async def test_enqueue(self, matchmaking_service: MatchmakingService):
        """Test enqueueing player."""
        ticket = await matchmaking_service.enqueue(40001, 100, "rated", "player1")
        
        assert ticket is not None, "Should return ticket"
        assert ticket.status == "queued", "Status should be queued"
        assert ticket.user_id == 40001
    
    @pytest.mark.asyncio
    async def test_cancel(self, matchmaking_service: MatchmakingService):
        """Test canceling matchmaking."""
        await matchmaking_service.enqueue(40002, 100, "rated", "player2")
        result = matchmaking_service.cancel(40002)
        
        assert result is True, "Should cancel successfully"
        status = matchmaking_service.status(40002)
        assert status.status == "cancelled", "Status should be cancelled"
    
    @pytest.mark.asyncio
    async def test_status(self, matchmaking_service: MatchmakingService):
        """Test getting status."""
        await matchmaking_service.enqueue(40003, 100, "rated", "player3")
        status = matchmaking_service.status(40003)
        
        assert status is not None, "Should return status"
        assert status.status == "queued"


@pytest.mark.integration
class TestMatchingLogic:
    """Test matching logic."""
    
    @pytest.mark.asyncio
    async def test_try_match_close_ratings(self, matchmaking_service: MatchmakingService):
        """Test matching players with close ratings."""
        await matchmaking_service.enqueue(40010, 100, "rated", "player10")
        await matchmaking_service.enqueue(40011, 101, "rated", "player11")
        
        result = matchmaking_service.try_match("rated")
        
        assert result is not None, "Should find match"
        assert "users" in result
        user_ids = {u["user_id"] for u in result["users"]}
        assert 40010 in user_ids and 40011 in user_ids
    
    @pytest.mark.asyncio
    async def test_try_match_mode_filtering(self, matchmaking_service: MatchmakingService):
        """Test matching respects mode."""
        await matchmaking_service.enqueue(40020, 100, "rated", "player20")
        await matchmaking_service.enqueue(40021, 101, "casual", "player21")
        
        result = matchmaking_service.try_match("rated")
        
        # Should not match different modes
        if result:
            user_ids = {u["user_id"] for u in result["users"]}
            assert 40021 not in user_ids, "Should not match different modes"


@pytest.mark.integration
class TestInviteFlow:
    """Test invite creation and acceptance."""
    
    @pytest.mark.asyncio
    async def test_create_invite(self, matchmaking_service: MatchmakingService):
        """Test creating invite."""
        result = matchmaking_service.create_invite(
            40030, 100, "rated", "creator", "Creator"
        )
        
        assert result is not None, "Should create invite"
        assert "code" in result
    
    @pytest.mark.asyncio
    async def test_accept_invite(self, matchmaking_service: MatchmakingService):
        """Test accepting invite."""
        invite = matchmaking_service.create_invite(
            40031, 100, "rated", "creator", "Creator"
        )
        
        result = matchmaking_service.accept_invite(40032, 200, invite["code"])
        assert result is not None, "Should accept invite"

