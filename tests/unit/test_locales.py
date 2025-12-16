"""
Unit tests for locales (localization strings)
"""

import pytest
import locales


@pytest.mark.unit
class TestStringConstants:
    """Test that all string constants are defined."""
    
    def test_welcome_constant(self):
        """Test WELCOME constant exists."""
        assert hasattr(locales, "WELCOME"), "WELCOME constant should exist"
        assert isinstance(locales.WELCOME, str), "WELCOME should be string"
        assert len(locales.WELCOME) > 0, "WELCOME should not be empty"
    
    def test_challenge_constant(self):
        """Test CHALLENGE constant exists."""
        assert hasattr(locales, "CHALLENGE"), "CHALLENGE constant should exist"
        assert isinstance(locales.CHALLENGE, str), "CHALLENGE should be string"
    
    def test_game_status_constants(self):
        """Test game status constants exist."""
        assert hasattr(locales, "TURN_RED"), "TURN_RED constant should exist"
        assert hasattr(locales, "TURN_WHITE"), "TURN_WHITE constant should exist"
        assert hasattr(locales, "GAME_STARTED"), "GAME_STARTED constant should exist"
    
    def test_win_loss_constants(self):
        """Test win/loss constants exist."""
        assert hasattr(locales, "WINNER"), "WINNER constant should exist"
        assert hasattr(locales, "WINNER_WITH_RATING"), "WINNER_WITH_RATING constant should exist"
        assert hasattr(locales, "DRAW"), "DRAW constant should exist"
    
    def test_rating_constants(self):
        """Test rating constants exist."""
        assert hasattr(locales, "RATING_INFO"), "RATING_INFO constant should exist"
        assert hasattr(locales, "LEADERBOARD_TITLE"), "LEADERBOARD_TITLE constant should exist"
        assert hasattr(locales, "LEADERBOARD_ENTRY"), "LEADERBOARD_ENTRY constant should exist"
    
    def test_error_constants(self):
        """Test error constants exist."""
        error_constants = [
            "ERROR_FORCE_JUMP",
            "ERROR_INVALID_MOVE",
            "ERROR_NOT_YOUR_TURN",
            "ERROR_NO_GAME",
            "ERROR_ALREADY_STARTED",
            "ERROR_SELF_PLAY"
        ]
        
        for const_name in error_constants:
            assert hasattr(locales, const_name), f"{const_name} constant should exist"
            const_value = getattr(locales, const_name)
            assert isinstance(const_value, str), f"{const_name} should be string"
    
    def test_button_constants(self):
        """Test button constants exist."""
        assert hasattr(locales, "BTN_FORFEIT"), "BTN_FORFEIT constant should exist"
        assert hasattr(locales, "BTN_CANCEL"), "BTN_CANCEL constant should exist"
        assert hasattr(locales, "BTN_NEW_GAME"), "BTN_NEW_GAME constant should exist"
    
    def test_piece_emoji_constants(self):
        """Test piece emoji constants exist."""
        emoji_constants = [
            "PIECE_EMPTY_DARK",
            "PIECE_EMPTY_LIGHT",
            "PIECE_WHITE",
            "PIECE_WHITE_KING",
            "PIECE_RED",
            "PIECE_RED_KING"
        ]
        
        for const_name in emoji_constants:
            assert hasattr(locales, const_name), f"{const_name} constant should exist"
            const_value = getattr(locales, const_name)
            assert isinstance(const_value, str), f"{const_name} should be string"
    
    def test_selected_piece_constants(self):
        """Test selected piece emoji constants exist."""
        selected_constants = [
            "PIECE_WHITE_SELECTED",
            "PIECE_WHITE_KING_SELECTED",
            "PIECE_RED_SELECTED",
            "PIECE_RED_KING_SELECTED"
        ]
        
        for const_name in selected_constants:
            assert hasattr(locales, const_name), f"{const_name} constant should exist"
    
    def test_menu_constants(self):
        """Test menu constants exist."""
        menu_constants = [
            "MENU_TITLE",
            "MENU_PLAY",
            "MENU_PROFILE",
            "MENU_RATING",
            "MENU_SETTINGS",
            "MENU_HELP",
            "MENU_ABOUT"
        ]
        
        for const_name in menu_constants:
            assert hasattr(locales, const_name), f"{const_name} constant should exist"


@pytest.mark.unit
class TestTemplateFormatting:
    """Test format string templates work correctly."""
    
    def test_challenge_formatting(self):
        """Test CHALLENGE template formatting."""
        opponent = "TestPlayer"
        formatted = locales.CHALLENGE.format(opponent=opponent)
        assert opponent in formatted, "Should include opponent name"
        assert isinstance(formatted, str), "Should return string"
    
    def test_turn_red_formatting(self):
        """Test TURN_RED template formatting."""
        player_tag = "TestPlayer"
        formatted = locales.TURN_RED.format(player_tag=player_tag)
        assert player_tag in formatted, "Should include player tag"
        assert isinstance(formatted, str), "Should return string"
    
    def test_turn_white_formatting(self):
        """Test TURN_WHITE template formatting."""
        player_tag = "TestPlayer"
        formatted = locales.TURN_WHITE.format(player_tag=player_tag)
        assert player_tag in formatted, "Should include player tag"
        assert isinstance(formatted, str), "Should return string"
    
    def test_game_started_formatting(self):
        """Test GAME_STARTED template formatting."""
        board = "Test Board"
        turn_msg = "Test Turn"
        formatted = locales.GAME_STARTED.format(board=board, turn_msg=turn_msg)
        assert board in formatted, "Should include board"
        assert turn_msg in formatted, "Should include turn message"
    
    def test_winner_formatting(self):
        """Test WINNER template formatting."""
        name = "Winner"
        formatted = locales.WINNER.format(name=name)
        assert name in formatted, "Should include winner name"
    
    def test_winner_with_rating_formatting(self):
        """Test WINNER_WITH_RATING template formatting."""
        name = "Winner"
        winner_name = "Winner"
        winner_rating = 1200
        winner_change = 20
        loser_name = "Loser"
        loser_rating = 1180
        loser_change = -20
        
        formatted = locales.WINNER_WITH_RATING.format(
            name=name,
            winner_name=winner_name,
            winner_rating=winner_rating,
            winner_change=winner_change,
            loser_name=loser_name,
            loser_rating=loser_rating,
            loser_change=loser_change
        )
        
        assert winner_name in formatted, "Should include winner name"
        assert str(winner_rating) in formatted, "Should include winner rating"
        assert str(winner_change) in formatted, "Should include rating change"
    
    def test_rating_info_formatting(self):
        """Test RATING_INFO template formatting."""
        name = "Player"
        rating = 1200
        rank = 1
        games_played = 10
        wins = 6
        losses = 4
        
        formatted = locales.RATING_INFO.format(
            name=name,
            rating=rating,
            rank=rank,
            games_played=games_played,
            wins=wins,
            losses=losses
        )
        
        assert name in formatted, "Should include player name"
        assert str(rating) in formatted, "Should include rating"
        assert str(games_played) in formatted, "Should include games played"
    
    def test_leaderboard_entry_formatting(self):
        """Test LEADERBOARD_ENTRY template formatting."""
        rank = 1
        name = "Player"
        rating = 1200
        wins = 6
        losses = 4
        
        formatted = locales.LEADERBOARD_ENTRY.format(
            rank=rank,
            name=name,
            rating=rating,
            wins=wins,
            losses=losses
        )
        
        assert str(rank) in formatted, "Should include rank"
        assert name in formatted, "Should include name"
        assert str(rating) in formatted, "Should include rating"
    
    def test_invite_created_formatting(self):
        """Test INVITE_CREATED template formatting."""
        code = "ABC123"
        formatted = locales.INVITE_CREATED.format(code=code)
        assert code in formatted, "Should include invite code"
    
    def test_inline_challenge_msg_formatting(self):
        """Test INLINE_CHALLENGE_MSG template formatting."""
        name = "Creator"
        formatted = locales.INLINE_CHALLENGE_MSG.format(name=name)
        assert name in formatted, "Should include creator name"
    
    def test_profile_template_formatting(self):
        """Test PROFILE_TEMPLATE formatting."""
        # PROFILE_TEMPLATE is a multi-line template
        if hasattr(locales, "PROFILE_TEMPLATE"):
            name = "Player"
            rating = 1200
            rank = "Гравець"
            games = 10
            wins = 6
            losses = 4
            
            formatted = locales.PROFILE_TEMPLATE.format(
                name=name,
                rating=rating,
                rank=rank,
                games=games,
                wins=wins,
                losses=losses
            )
            
            assert name in formatted, "Should include name"
            assert str(rating) in formatted, "Should include rating"


@pytest.mark.unit
class TestEmojiPresence:
    """Test that emoji constants contain emojis."""
    
    def test_piece_emojis_present(self):
        """Test piece emoji constants have emojis."""
        emoji_constants = [
            "PIECE_WHITE",
            "PIECE_WHITE_KING",
            "PIECE_RED",
            "PIECE_RED_KING"
        ]
        
        for const_name in emoji_constants:
            if hasattr(locales, const_name):
                emoji = getattr(locales, const_name)
                # Emojis are Unicode characters, so just check it's not empty
                assert len(emoji) > 0, f"{const_name} should have emoji"
    
    def test_empty_square_emojis_present(self):
        """Test empty square emoji constants have emojis."""
        if hasattr(locales, "PIECE_EMPTY_DARK"):
            assert len(locales.PIECE_EMPTY_DARK) > 0, "PIECE_EMPTY_DARK should have emoji"
        if hasattr(locales, "PIECE_EMPTY_LIGHT"):
            assert len(locales.PIECE_EMPTY_LIGHT) > 0, "PIECE_EMPTY_LIGHT should have emoji"


@pytest.mark.unit
class TestSpecialCharacterHandling:
    """Test handling of special characters in templates."""
    
    def test_html_special_chars(self):
        """Test templates handle HTML special characters."""
        # Test with HTML-like content
        name = "<Test>Player</Test>"
        formatted = locales.CHALLENGE.format(opponent=name)
        # Should not crash, may or may not escape
        assert isinstance(formatted, str)
    
    def test_unicode_characters(self):
        """Test templates handle Unicode characters."""
        name = "ТестГравець"  # Ukrainian characters
        formatted = locales.CHALLENGE.format(opponent=name)
        assert name in formatted or isinstance(formatted, str), "Should handle Unicode"
    
    def test_empty_strings(self):
        """Test templates handle empty strings."""
        formatted = locales.CHALLENGE.format(opponent="")
        assert isinstance(formatted, str), "Should handle empty strings"

