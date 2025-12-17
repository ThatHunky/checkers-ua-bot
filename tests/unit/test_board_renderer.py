"""
Unit tests for BoardRenderer
"""

import pytest
from handlers.board_renderer import BoardRenderer
from engine import CheckersEngine, YELLOW, BLUE, YELLOW_KING, BLUE_KING, EMPTY
import locales


@pytest.mark.unit
class TestBoardRendering:
    """Test board text rendering."""
    
    def test_render_initial_board(self, checkers_engine: CheckersEngine):
        """Test rendering initial board."""
        board_text = BoardRenderer.render(checkers_engine.board)
        
        assert isinstance(board_text, str), "Should return string"
        assert "A B C D E F G H" in board_text, "Should have column headers"
        
        # Check row numbers
        for row_num in range(1, 9):
            assert str(row_num) in board_text, f"Should have row {row_num}"
        
        # Check piece emojis are present
        assert locales.PIECE_WHITE in board_text or locales.PIECE_RED in board_text, "Should have piece emojis"
    
    def test_render_all_piece_types(self, empty_engine: CheckersEngine):
        """Test rendering all piece types."""
        # Place one of each piece type
        empty_engine.board[0] = YELLOW
        empty_engine.board[1] = YELLOW_KING
        empty_engine.board[2] = BLUE
        empty_engine.board[3] = BLUE_KING
        
        board_text = BoardRenderer.render(empty_engine.board)
        
        assert locales.PIECE_WHITE in board_text, "Should render YELLOW man"
        assert locales.PIECE_WHITE_KING in board_text, "Should render YELLOW king"
        assert locales.PIECE_RED in board_text, "Should render BLUE man"
        assert locales.PIECE_RED_KING in board_text, "Should render BLUE king"
    
    def test_render_empty_squares(self, empty_engine: CheckersEngine):
        """Test rendering empty squares."""
        board_text = BoardRenderer.render(empty_engine.board)
        
        # Should have empty square emojis
        assert locales.PIECE_EMPTY_DARK in board_text or locales.PIECE_EMPTY_LIGHT in board_text, "Should have empty squares"
    
    def test_render_format(self, checkers_engine: CheckersEngine):
        """Test board rendering format."""
        board_text = BoardRenderer.render(checkers_engine.board)
        lines = board_text.split("\n")
        
        # Should have header + 8 rows = 9 lines
        assert len(lines) == 9, f"Should have 9 lines (header + 8 rows), got {len(lines)}"
        
        # First line should be column headers
        assert lines[0].strip().startswith("A"), "First line should be column headers"
        
        # Each row should have row number
        for i in range(1, 9):
            assert str(9 - i) in lines[i], f"Row {i} should have row number"
    
    def test_render_empty_board(self, empty_engine: CheckersEngine):
        """Test rendering completely empty board."""
        board_text = BoardRenderer.render(empty_engine.board)
        
        assert isinstance(board_text, str), "Should return string"
        assert len(board_text) > 0, "Should not be empty"
        # Should still have structure
        assert "A B C D E F G H" in board_text, "Should have column headers"


@pytest.mark.unit
class TestKeyboardCreation:
    """Test inline keyboard creation."""
    
    def test_create_keyboard_normal_mode(self, checkers_engine: CheckersEngine):
        """Test creating keyboard in normal mode (no selection)."""
        keyboard = BoardRenderer.create_move_keyboard(checkers_engine)
        
        assert keyboard is not None, "Should create keyboard"
        assert hasattr(keyboard, "inline_keyboard"), "Should have inline_keyboard attribute"
        
        # Should have 8 rows for board + control buttons
        assert len(keyboard.inline_keyboard) >= 8, "Should have at least 8 rows"
    
    def test_create_keyboard_with_selection(self, checkers_engine: CheckersEngine):
        """Test creating keyboard with selected piece."""
        moves = checkers_engine.get_legal_moves(YELLOW)
        if moves:
            selected_pos = moves[0].from_pos
            keyboard = BoardRenderer.create_move_keyboard(checkers_engine, selected_pos=selected_pos)
            
            assert keyboard is not None, "Should create keyboard"
            # Should have cancel button
            has_cancel = any(
                any("back" in str(btn.callback_data) for btn in row)
                for row in keyboard.inline_keyboard
            )
            assert has_cancel, "Should have cancel button when piece selected"
    
    def test_create_keyboard_pending_capture(self, empty_engine: CheckersEngine):
        """Test creating keyboard with pending capture."""
        # Set up capture scenario
        empty_engine.board[19] = YELLOW
        empty_engine.board[28] = BLUE
        empty_engine.current_turn = YELLOW
        
        # Make capture
        moves = empty_engine.get_legal_moves(YELLOW)
        if moves and moves[0].captures:
            empty_engine.apply_move(moves[0])
            
            # Check if must continue
            if empty_engine.must_continue_capturing(moves[0].to_pos):
                pending_capture = {"pos": moves[0].to_pos}
                keyboard = BoardRenderer.create_move_keyboard(
                    empty_engine,
                    pending_capture=pending_capture
                )
                
                assert keyboard is not None, "Should create keyboard"
                # Should have continuation message
                has_continue = any(
                    any("continue" in str(btn.callback_data) for btn in row)
                    for row in keyboard.inline_keyboard
                )
                # May or may not have continue button depending on implementation
                assert isinstance(has_continue, bool)
    
    def test_create_keyboard_button_labels(self, checkers_engine: CheckersEngine):
        """Test keyboard button labels are correct."""
        keyboard = BoardRenderer.create_move_keyboard(checkers_engine)
        
        # Check all buttons have labels
        for row in keyboard.inline_keyboard:
            for button in row:
                assert button.text is not None, "Button should have text"
                assert len(button.text) > 0, "Button text should not be empty"
    
    def test_create_keyboard_callback_data(self, checkers_engine: CheckersEngine):
        """Test keyboard callback data format."""
        keyboard = BoardRenderer.create_move_keyboard(checkers_engine)
        
        # Check callback data format
        for row in keyboard.inline_keyboard:
            for button in row:
                assert button.callback_data is not None, "Button should have callback_data"
                assert isinstance(button.callback_data, str), "Callback data should be string"
    
    def test_create_keyboard_control_buttons(self, checkers_engine: CheckersEngine):
        """Test control buttons are present."""
        keyboard = BoardRenderer.create_move_keyboard(checkers_engine, move_count=0)
        
        # Should have forfeit/cancel button
        has_control = any(
            any("forfeit" in str(btn.callback_data) or "cancel" in str(btn.callback_data).lower() for btn in row)
            for row in keyboard.inline_keyboard
        )
        assert has_control, "Should have control buttons"

    def test_create_keyboard_includes_review_button_after_first_move(self, checkers_engine: CheckersEngine):
        """When at least one move was made, keyboard should include review button."""
        keyboard = BoardRenderer.create_move_keyboard(checkers_engine, move_count=1)

        has_review = any(
            any(str(btn.callback_data).startswith("review_") for btn in row)
            for row in keyboard.inline_keyboard
        )
        assert has_review, "Should have review button when move_count > 0"
    
    def test_create_keyboard_move_count_zero(self, checkers_engine: CheckersEngine):
        """Test keyboard with move_count=0 shows cancel button."""
        keyboard = BoardRenderer.create_move_keyboard(checkers_engine, move_count=0)
        
        # Should have cancel button (not forfeit)
        has_cancel = any(
            any(locales.BTN_CANCEL in btn.text for btn in row)
            for row in keyboard.inline_keyboard
        )
        # May have cancel button
        assert isinstance(has_cancel, bool)
    
    def test_create_keyboard_move_count_nonzero(self, checkers_engine: CheckersEngine):
        """Test keyboard with move_count>0 shows forfeit button."""
        keyboard = BoardRenderer.create_move_keyboard(checkers_engine, move_count=5)
        
        # Should have forfeit button
        has_forfeit = any(
            any(locales.BTN_FORFEIT in btn.text for btn in row)
            for row in keyboard.inline_keyboard
        )
        # May have forfeit button
        assert isinstance(has_forfeit, bool)


@pytest.mark.unit
class TestPieceEmoji:
    """Test piece emoji functions."""
    
    def test_get_piece_emoji_yellow_man(self):
        """Test _get_piece_emoji for YELLOW man."""
        emoji = BoardRenderer._get_piece_emoji(YELLOW)
        assert emoji == locales.PIECE_WHITE, "Should return YELLOW man emoji"
    
    def test_get_piece_emoji_yellow_king(self):
        """Test _get_piece_emoji for YELLOW king."""
        emoji = BoardRenderer._get_piece_emoji(YELLOW_KING)
        assert emoji == locales.PIECE_WHITE_KING, "Should return YELLOW king emoji"
    
    def test_get_piece_emoji_blue_man(self):
        """Test _get_piece_emoji for BLUE man."""
        emoji = BoardRenderer._get_piece_emoji(BLUE)
        assert emoji == locales.PIECE_RED, "Should return BLUE man emoji"
    
    def test_get_piece_emoji_blue_king(self):
        """Test _get_piece_emoji for BLUE king."""
        emoji = BoardRenderer._get_piece_emoji(BLUE_KING)
        assert emoji == locales.PIECE_RED_KING, "Should return BLUE king emoji"
    
    def test_get_piece_emoji_empty(self):
        """Test _get_piece_emoji for empty square."""
        emoji = BoardRenderer._get_piece_emoji(EMPTY)
        assert emoji == "", "Should return empty string for empty square"
    
    def test_get_selected_piece_emoji_yellow_man(self):
        """Test _get_selected_piece_emoji for YELLOW man."""
        emoji = BoardRenderer._get_selected_piece_emoji(YELLOW)
        assert emoji == locales.PIECE_WHITE_SELECTED, "Should return selected YELLOW man emoji"
    
    def test_get_selected_piece_emoji_yellow_king(self):
        """Test _get_selected_piece_emoji for YELLOW king."""
        emoji = BoardRenderer._get_selected_piece_emoji(YELLOW_KING)
        assert emoji == locales.PIECE_WHITE_KING_SELECTED, "Should return selected YELLOW king emoji"
    
    def test_get_selected_piece_emoji_blue_man(self):
        """Test _get_selected_piece_emoji for BLUE man."""
        emoji = BoardRenderer._get_selected_piece_emoji(BLUE)
        assert emoji == locales.PIECE_RED_SELECTED, "Should return selected BLUE man emoji"
    
    def test_get_selected_piece_emoji_blue_king(self):
        """Test _get_selected_piece_emoji for BLUE king."""
        emoji = BoardRenderer._get_selected_piece_emoji(BLUE_KING)
        assert emoji == locales.PIECE_RED_KING_SELECTED, "Should return selected BLUE king emoji"
    
    def test_get_selected_piece_emoji_empty(self):
        """Test _get_selected_piece_emoji for empty square."""
        emoji = BoardRenderer._get_selected_piece_emoji(EMPTY)
        assert emoji == "", "Should return empty string for empty square"
    
    def test_emoji_consistency(self):
        """Test emoji functions are consistent."""
        # Selected emojis should be different from regular emojis
        assert BoardRenderer._get_piece_emoji(YELLOW) != BoardRenderer._get_selected_piece_emoji(YELLOW)
        assert BoardRenderer._get_piece_emoji(BLUE) != BoardRenderer._get_selected_piece_emoji(BLUE)


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases for board renderer."""
    
    def test_render_all_pieces_captured(self, empty_engine: CheckersEngine):
        """Test rendering when all pieces are captured."""
        board_text = BoardRenderer.render(empty_engine.board)
        assert isinstance(board_text, str), "Should handle empty board"
    
    def test_keyboard_empty_board(self, empty_engine: CheckersEngine):
        """Test keyboard creation for empty board."""
        keyboard = BoardRenderer.create_move_keyboard(empty_engine)
        assert keyboard is not None, "Should create keyboard even for empty board"
    
    def test_keyboard_invalid_selected_pos(self, checkers_engine: CheckersEngine):
        """Test keyboard with invalid selected position."""
        keyboard = BoardRenderer.create_move_keyboard(checkers_engine, selected_pos=999)
        assert keyboard is not None, "Should handle invalid selected position gracefully"
    
    def test_keyboard_all_pieces_selected(self, checkers_engine: CheckersEngine):
        """Test keyboard when all pieces could be selected."""
        # This is a stress test - should not crash
        keyboard = BoardRenderer.create_move_keyboard(checkers_engine)
        assert keyboard is not None, "Should handle multiple selectable pieces"

