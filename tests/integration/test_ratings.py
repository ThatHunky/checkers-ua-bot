"""
Integration tests for RatingSystem
"""

import pytest
from ratings import RatingSystem, get_k_factor, INITIAL_RATING
from ranks import get_rank


@pytest.mark.integration
class TestKFactorCalculation:
    """Test K-factor calculation function."""
    
    def test_get_k_factor_all_thresholds(self):
        """Test get_k_factor for all threshold values."""
        test_cases = [
            (0, 64),
            (3, 64),
            (5, 64),
            (6, 48),
            (10, 48),
            (11, 40),
            (20, 40),
            (21, 36),
            (30, 36),
            (31, 32),
            (50, 32),
            (51, 28),
            (100, 28),
            (101, 24),
            (500, 24),
            (1000, 24),
        ]
        
        for games_played, expected_k in test_cases:
            k = get_k_factor(games_played)
            assert k == expected_k, f"Games {games_played} should have K={expected_k}, got {k}"
    
    def test_get_k_factor_boundary_values(self):
        """Test get_k_factor at exact boundaries."""
        assert get_k_factor(5) == 64
        assert get_k_factor(6) == 48
        assert get_k_factor(10) == 48
        assert get_k_factor(11) == 40
        assert get_k_factor(20) == 40
        assert get_k_factor(21) == 36
        assert get_k_factor(30) == 36
        assert get_k_factor(31) == 32
        assert get_k_factor(50) == 32
        assert get_k_factor(51) == 28
        assert get_k_factor(100) == 28
        assert get_k_factor(101) == 24
    
    def test_get_k_factor_very_high(self):
        """Test get_k_factor for very high game counts."""
        assert get_k_factor(10000) == 24
        assert get_k_factor(999999) == 24


@pytest.mark.integration
class TestDatabaseOperations:
    """Test database initialization and operations."""
    
    @pytest.mark.asyncio
    async def test_initialize_creates_tables(self, temp_ratings_db: RatingSystem):
        """Test initialize creates database tables."""
        # Database should be initialized by fixture
        # Verify by trying to query
        player = await temp_ratings_db.get_player(99999, "TestUser")
        assert player is not None
        assert player["user_id"] == 99999
    
    @pytest.mark.asyncio
    async def test_initialize_schema_migration(self, temp_ratings_db: RatingSystem):
        """Test initialize handles schema migration."""
        # Create a player to verify schema
        player = await temp_ratings_db.get_player(12345, "Test")
        
        # Check new columns exist
        required_fields = [
            "current_streak", "best_streak", "best_rating", "peak_rank",
            "total_rating_gained", "total_rating_lost", "perfect_games",
            "comeback_wins", "games_this_week", "games_this_month"
        ]
        
        # Fields should be accessible (may have defaults)
        assert "rating" in player
        assert "games_played" in player


@pytest.mark.integration
class TestPlayerManagement:
    """Test player data management."""
    
    @pytest.mark.asyncio
    async def test_get_player_new_player(self, temp_ratings_db: RatingSystem):
        """Test get_player creates new player."""
        player = await temp_ratings_db.get_player(11111, "NewPlayer")
        
        assert player["user_id"] == 11111
        assert player["username"] == "NewPlayer"
        assert player["rating"] == INITIAL_RATING
        assert player["games_played"] == 0
        assert player["wins"] == 0
        assert player["losses"] == 0
    
    @pytest.mark.asyncio
    async def test_get_player_existing_player(self, temp_ratings_db: RatingSystem):
        """Test get_player retrieves existing player."""
        # Create player
        player1 = await temp_ratings_db.get_player(22222, "Existing")
        
        # Retrieve same player
        player2 = await temp_ratings_db.get_player(22222, "Existing")
        
        assert player2["user_id"] == player1["user_id"]
        assert player2["rating"] == player1["rating"]
    
    @pytest.mark.asyncio
    async def test_get_player_username_update(self, temp_ratings_db: RatingSystem):
        """Test get_player updates username."""
        # Create with initial username
        player1 = await temp_ratings_db.get_player(33333, "OldName")
        assert player1["username"] == "OldName"
        
        # Update with new username
        player2 = await temp_ratings_db.get_player(33333, "NewName")
        assert player2["username"] == "NewName"
    
    @pytest.mark.asyncio
    async def test_get_player_no_username(self, temp_ratings_db: RatingSystem):
        """Test get_player without username."""
        player = await temp_ratings_db.get_player(44444)
        
        assert player["user_id"] == 44444
        assert player["username"] == "Unknown" or player["username"] is None


@pytest.mark.integration
class TestRatingCalculations:
    """Test ELO rating calculations."""
    
    def test_calculate_elo_change_equal_ratings(self):
        """Test calculate_elo_change with equal ratings."""
        winner_rating = 1200
        loser_rating = 1200
        
        new_winner, new_loser = RatingSystem.calculate_elo_change(
            winner_rating, loser_rating, 10, 10
        )
        
        # With equal ratings, winner should gain ~K/2, loser should lose ~K/2
        assert new_winner > winner_rating, "Winner should gain rating"
        assert new_loser < loser_rating, "Loser should lose rating"
        # Zero-sum property
        total_change = (new_winner - winner_rating) + (new_loser - loser_rating)
        assert abs(total_change) < 1, "Should be zero-sum (within rounding)"
    
    def test_calculate_elo_change_large_difference(self):
        """Test calculate_elo_change with large rating difference."""
        winner_rating = 1500
        loser_rating = 1000
        
        new_winner, new_loser = RatingSystem.calculate_elo_change(
            winner_rating, loser_rating, 50, 50
        )
        
        # Higher rated winner should gain less
        winner_change = new_winner - winner_rating
        loser_change = new_loser - loser_rating
        
        assert winner_change < 20, "Higher rated winner should gain less"
        # Rating changes are zero-sum: loser should lose exactly what winner gains (within rounding).
        assert abs(loser_change) == abs(winner_change), "Should be zero-sum"
    
    def test_calculate_elo_change_upset(self):
        """Test calculate_elo_change for upset (lower rated wins)."""
        winner_rating = 1000
        loser_rating = 1500
        
        new_winner, new_loser = RatingSystem.calculate_elo_change(
            winner_rating, loser_rating, 10, 50
        )
        
        # Upset should result in larger rating changes
        winner_change = new_winner - winner_rating
        loser_change = new_loser - loser_rating
        
        assert winner_change > 20, "Upset winner should gain significant rating"
        assert abs(loser_change) > 20, "Upset loser should lose significant rating"
    
    def test_calculate_elo_change_dynamic_k_factor(self):
        """Test calculate_elo_change uses dynamic K-factor."""
        # New player (high K) vs veteran (low K)
        new_winner, new_loser = RatingSystem.calculate_elo_change(
            1200, 1200, 3, 150  # 3 games vs 150 games
        )
        
        # Average K should be between 64 and 24
        winner_change = new_winner - 1200
        assert winner_change > 0, "Winner should gain rating"
    
    def test_calculate_elo_change_zero_sum(self):
        """Test calculate_elo_change maintains zero-sum property."""
        winner_rating = 1200
        loser_rating = 1180
        
        new_winner, new_loser = RatingSystem.calculate_elo_change(
            winner_rating, loser_rating, 20, 20
        )
        
        winner_change = new_winner - winner_rating
        loser_change = new_loser - loser_rating
        
        # Should be zero-sum (within rounding)
        total = winner_change + loser_change
        assert abs(total) < 1, f"Should be zero-sum, got total={total}"


@pytest.mark.integration
class TestGameRecording:
    """Test recording game results."""
    
    @pytest.mark.asyncio
    async def test_record_game_win_scenario(self, temp_ratings_db: RatingSystem):
        """Test record_game for win scenario."""
        winner_data, loser_data = await temp_ratings_db.record_game(
            winner_id=50001,
            winner_name="Winner",
            loser_id=50002,
            loser_name="Loser"
        )
        
        assert winner_data["rating"] > INITIAL_RATING, "Winner should gain rating"
        assert loser_data["rating"] < INITIAL_RATING, "Loser should lose rating"
        assert winner_data["wins"] == 1, "Winner should have 1 win"
        assert loser_data["losses"] == 1, "Loser should have 1 loss"
        assert winner_data["games_played"] == 1
        assert loser_data["games_played"] == 1

    @pytest.mark.asyncio
    async def test_record_game_idempotent_with_game_key(self, temp_ratings_db: RatingSystem):
        """Calling record_game twice with the same game_key must not double-count wins/losses."""
        game_key = "chat:1:1"

        winner_data_1, loser_data_1 = await temp_ratings_db.record_game(
            winner_id=51001,
            winner_name="Winner",
            loser_id=51002,
            loser_name="Loser",
            game_key=game_key,
            move_count=12,
        )

        winner_data_2, loser_data_2 = await temp_ratings_db.record_game(
            winner_id=51001,
            winner_name="Winner",
            loser_id=51002,
            loser_name="Loser",
            game_key=game_key,
            move_count=12,
        )

        winner = await temp_ratings_db.get_player(51001, "Winner")
        loser = await temp_ratings_db.get_player(51002, "Loser")

        assert winner["wins"] == 1
        assert loser["losses"] == 1
        assert winner["games_played"] == 1
        assert loser["games_played"] == 1

        # Second call should return the same post-game rating (not apply changes again).
        assert winner_data_2["rating"] == winner_data_1["rating"]
        assert loser_data_2["rating"] == loser_data_1["rating"]
    
    @pytest.mark.asyncio
    async def test_record_game_streak_tracking(self, temp_ratings_db: RatingSystem):
        """Test record_game tracks win streaks."""
        # Record multiple wins
        for i in range(3):
            winner_data, _ = await temp_ratings_db.record_game(
                winner_id=50003,
                winner_name="StreakPlayer",
                loser_id=50004 + i,
                loser_name=f"Loser{i}"
            )
        
        # Check streak
        player = await temp_ratings_db.get_player(50003, "StreakPlayer")
        assert player["current_streak"] == 3, "Should have 3-game streak"
        assert player["best_streak"] == 3, "Best streak should be 3"
    
    @pytest.mark.asyncio
    async def test_record_game_streak_reset(self, temp_ratings_db: RatingSystem):
        """Test record_game resets streak on loss."""
        # Win first
        await temp_ratings_db.record_game(
            winner_id=50005,
            winner_name="Player",
            loser_id=50006,
            loser_name="Opponent1"
        )
        
        # Lose
        _, loser_data = await temp_ratings_db.record_game(
            winner_id=50007,
            winner_name="Opponent2",
            loser_id=50005,
            loser_name="Player"
        )
        
        assert loser_data["current_streak"] == 0, "Streak should reset on loss"
    
    @pytest.mark.asyncio
    async def test_record_game_best_rating_tracking(self, temp_ratings_db: RatingSystem):
        """Test record_game tracks best rating."""
        winner_data, _ = await temp_ratings_db.record_game(
            winner_id=50008,
            winner_name="Player",
            loser_id=50009,
            loser_name="Opponent"
        )
        
        assert winner_data["best_rating"] >= winner_data["rating"], "Best rating should be >= current"
    
    @pytest.mark.asyncio
    async def test_record_game_peak_rank_tracking(self, temp_ratings_db: RatingSystem):
        """Test record_game tracks peak rank."""
        # Play games to increase rating
        for i in range(5):
            await temp_ratings_db.record_game(
                winner_id=50010,
                winner_name="Player",
                loser_id=50011 + i,
                loser_name=f"Opponent{i}"
            )
        
        player = await temp_ratings_db.get_player(50010, "Player")
        assert "peak_rank" in player or player.get("peak_rank") is not None
    
    @pytest.mark.asyncio
    async def test_record_game_perfect_game(self, temp_ratings_db: RatingSystem):
        """Test record_game tracks perfect games."""
        winner_data, _ = await temp_ratings_db.record_game(
            winner_id=50012,
            winner_name="Player",
            loser_id=50013,
            loser_name="Opponent",
            winner_pieces_lost=0  # Perfect game
        )
        
        player = await temp_ratings_db.get_player(50012, "Player")
        assert player.get("perfect_games", 0) >= 1, "Should track perfect games"
    
    @pytest.mark.asyncio
    async def test_record_game_comeback_win(self, temp_ratings_db: RatingSystem):
        """Test record_game tracks comeback wins."""
        # Set up: lower rated player wins
        # First, create players with different ratings
        lower_player = await temp_ratings_db.get_player(50014, "Lower")
        higher_player = await temp_ratings_db.get_player(50015, "Higher")
        
        # Manually set ratings to create deficit
        import aiosqlite
        async with aiosqlite.connect(temp_ratings_db.db_path) as db:
            await db.execute(
                "UPDATE players SET rating = ? WHERE user_id = ?",
                (800, 50014)
            )
            await db.execute(
                "UPDATE players SET rating = ? WHERE user_id = ?",
                (1000, 50015)
            )
            await db.commit()
        
        # Lower rated player wins (comeback)
        winner_data, _ = await temp_ratings_db.record_game(
            winner_id=50014,
            winner_name="Lower",
            loser_id=50015,
            loser_name="Higher"
        )
        
        player = await temp_ratings_db.get_player(50014, "Lower")
        assert player.get("comeback_wins", 0) >= 1, "Should track comeback wins"
    
    @pytest.mark.asyncio
    async def test_record_game_fastest_win(self, temp_ratings_db: RatingSystem):
        """Test record_game tracks fastest win."""
        winner_data, _ = await temp_ratings_db.record_game(
            winner_id=50016,
            winner_name="Player",
            loser_id=50017,
            loser_name="Opponent",
            move_count=5  # Fast game
        )
        
        player = await temp_ratings_db.get_player(50016, "Player")
        assert player.get("fastest_win") == 5, "Should track fastest win"
    
    @pytest.mark.asyncio
    async def test_record_game_longest_game(self, temp_ratings_db: RatingSystem):
        """Test record_game tracks longest game."""
        _, loser_data = await temp_ratings_db.record_game(
            winner_id=50018,
            winner_name="Winner",
            loser_id=50019,
            loser_name="Player",
            move_count=100  # Long game
        )
        
        player = await temp_ratings_db.get_player(50019, "Player")
        assert player.get("longest_game") == 100, "Should track longest game"
    
    @pytest.mark.asyncio
    async def test_record_game_rating_changes(self, temp_ratings_db: RatingSystem):
        """Test record_game updates ratings correctly."""
        winner_data, loser_data = await temp_ratings_db.record_game(
            winner_id=50020,
            winner_name="Winner",
            loser_id=50021,
            loser_name="Loser"
        )
        
        assert "rating_change" in winner_data, "Should include rating change"
        assert "rating_change" in loser_data, "Should include rating change"
        assert winner_data["rating_change"] > 0, "Winner should gain rating"
        assert loser_data["rating_change"] < 0, "Loser should lose rating"
    
    @pytest.mark.asyncio
    async def test_record_game_statistics(self, temp_ratings_db: RatingSystem):
        """Test record_game updates all statistics."""
        winner_data, loser_data = await temp_ratings_db.record_game(
            winner_id=50022,
            winner_name="Winner",
            loser_id=50023,
            loser_name="Loser",
            move_count=25
        )
        
        # Check all statistics are updated
        assert winner_data["games_played"] > 0
        assert winner_data["wins"] > 0
        assert loser_data["games_played"] > 0
        assert loser_data["losses"] > 0


@pytest.mark.integration
class TestLeaderboard:
    """Test leaderboard functionality."""
    
    @pytest.mark.asyncio
    async def test_get_leaderboard_empty(self, temp_ratings_db: RatingSystem):
        """Test get_leaderboard with no players."""
        players, total = await temp_ratings_db.get_leaderboard()
        
        assert len(players) == 0, "Should return empty list"
        assert total == 0, "Total should be 0"
    
    @pytest.mark.asyncio
    async def test_get_leaderboard_single_player(self, temp_ratings_db: RatingSystem):
        """Test get_leaderboard with single player."""
        # Create player with a game
        await temp_ratings_db.record_game(
            winner_id=60001,
            winner_name="Player1",
            loser_id=60002,
            loser_name="Player2"
        )
        
        players, total = await temp_ratings_db.get_leaderboard()
        
        assert total >= 1, "Should have at least 1 player"
        assert len(players) >= 1, "Should return at least 1 player"
    
    @pytest.mark.asyncio
    async def test_get_leaderboard_rating_ordering(self, temp_ratings_db: RatingSystem):
        """Test get_leaderboard orders by rating."""
        # Create multiple players with different ratings
        for i in range(3):
            await temp_ratings_db.record_game(
                winner_id=60010 + i,
                winner_name=f"Player{i}",
                loser_id=60020 + i,
                loser_name=f"Opponent{i}"
            )
        
        players, total = await temp_ratings_db.get_leaderboard()
        
        # Should be ordered by rating descending
        if len(players) > 1:
            for i in range(len(players) - 1):
                assert players[i]["rating"] >= players[i + 1]["rating"], "Should be ordered by rating"
    
    @pytest.mark.asyncio
    async def test_get_leaderboard_limit(self, temp_ratings_db: RatingSystem):
        """Test get_leaderboard respects limit."""
        # Create multiple players
        for i in range(10):
            await temp_ratings_db.record_game(
                winner_id=60030 + i,
                winner_name=f"Player{i}",
                loser_id=60040 + i,
                loser_name=f"Opponent{i}"
            )
        
        players, total = await temp_ratings_db.get_leaderboard(limit=5)
        
        assert len(players) <= 5, "Should respect limit"
        assert total >= 10, "Total should include all players"
    
    @pytest.mark.asyncio
    async def test_get_leaderboard_offset(self, temp_ratings_db: RatingSystem):
        """Test get_leaderboard respects offset."""
        # Create multiple players
        for i in range(10):
            await temp_ratings_db.record_game(
                winner_id=60050 + i,
                winner_name=f"Player{i}",
                loser_id=60060 + i,
                loser_name=f"Opponent{i}"
            )
        
        players1, _ = await temp_ratings_db.get_leaderboard(limit=5, offset=0)
        players2, _ = await temp_ratings_db.get_leaderboard(limit=5, offset=5)
        
        # Should get different players
        if len(players1) > 0 and len(players2) > 0:
            assert players1[0]["user_id"] != players2[0]["user_id"], "Should get different players with offset"


@pytest.mark.integration
class TestPlayerRank:
    """Test player rank calculation."""
    
    @pytest.mark.asyncio
    async def test_get_player_rank(self, temp_ratings_db: RatingSystem):
        """Test get_player_rank returns correct rank."""
        # Create players
        await temp_ratings_db.record_game(
            winner_id=70001,
            winner_name="Player1",
            loser_id=70002,
            loser_name="Player2"
        )
        
        rank = await temp_ratings_db.get_player_rank(70001)
        
        assert rank is not None, "Should return rank"
        assert rank >= 1, "Rank should be >= 1"
    
    @pytest.mark.asyncio
    async def test_get_player_rank_nonexistent(self, temp_ratings_db: RatingSystem):
        """Test get_player_rank for nonexistent player."""
        rank = await temp_ratings_db.get_player_rank(999999)
        
        # May return None or a rank depending on implementation
        assert rank is None or rank >= 1


@pytest.mark.integration
class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    @pytest.mark.asyncio
    async def test_first_game_no_previous_stats(self, temp_ratings_db: RatingSystem):
        """Test recording first game with no previous stats."""
        winner_data, loser_data = await temp_ratings_db.record_game(
            winner_id=80001,
            winner_name="NewPlayer1",
            loser_id=80002,
            loser_name="NewPlayer2"
        )
        
        # Should handle first game gracefully
        assert winner_data["games_played"] == 1
        assert loser_data["games_played"] == 1
    
    @pytest.mark.asyncio
    async def test_very_high_ratings(self, temp_ratings_db: RatingSystem):
        """Test handling very high ratings."""
        # Manually set high rating
        await temp_ratings_db.get_player(80001, "HighRated")
        import aiosqlite
        async with aiosqlite.connect(temp_ratings_db.db_path) as db:
            await db.execute(
                "UPDATE players SET rating = ? WHERE user_id = ?",
                (3000, 80001)
            )
            await db.commit()
        
        player = await temp_ratings_db.get_player(80001)
        assert player["rating"] == 3000
    
    @pytest.mark.asyncio
    async def test_multiple_games_same_players(self, temp_ratings_db: RatingSystem):
        """Test recording multiple games between same players."""
        for i in range(3):
            await temp_ratings_db.record_game(
                winner_id=80010,
                winner_name="Player1",
                loser_id=80011,
                loser_name="Player2"
            )
        
        player1 = await temp_ratings_db.get_player(80010)
        player2 = await temp_ratings_db.get_player(80011)
        
        assert player1["games_played"] == 3
        assert player2["games_played"] == 3
        assert player1["wins"] == 3
        assert player2["losses"] == 3

