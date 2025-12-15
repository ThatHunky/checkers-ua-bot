"""
Board rendering utilities for displaying the checkers board.
"""

from typing import Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from engine import CheckersEngine
import locales


class BoardRenderer:
    """Renders the checkers board as text with emoji."""
    
    @staticmethod
    def render(board: list) -> str:
        """Render board as 8x8 grid with emoji pieces."""
        lines = []
        
        # Column headers
        lines.append("  A B C D E F G H")
        
        for row in range(8):
            row_str = f"{8-row} "  # Row numbers (8 to 1)
            for col in range(8):
                pos = row * 8 + col
                piece = board[pos]
                
                # Determine square color (dark squares are playable)
                is_dark = (row + col) % 2 == 1
                
                if piece == 0:  # Empty
                    row_str += locales.PIECE_EMPTY_DARK if is_dark else locales.PIECE_EMPTY_LIGHT
                elif piece == 1:  # Yellow man
                    row_str += locales.PIECE_WHITE
                elif piece == 2:  # Yellow king
                    row_str += locales.PIECE_WHITE_KING
                elif piece == 3:  # Blue man
                    row_str += locales.PIECE_RED
                elif piece == 4:  # Blue king
                    row_str += locales.PIECE_RED_KING
                
                row_str += " "
            
            lines.append(row_str)
        
        return "\n".join(lines)
    
    @staticmethod
    def create_move_keyboard(engine: CheckersEngine, selected_pos: Optional[int] = None, 
                            move_count: int = 1, pending_capture: dict = None) -> InlineKeyboardMarkup:
        """
        Create inline keyboard showing the actual board as clickable buttons.
        
        If pending_capture is set: only show continuation captures from that position
        If selected_pos is None: highlight pieces that can move (green)
        If selected_pos is set: highlight selected piece and show possible destinations
        """
        buttons = []
        
        # Handle pending capture (must continue capturing)
        if pending_capture:
            pending_pos = pending_capture.get("pos")
            # If no follow-up captures remain, fall back to normal selection
            if not engine.must_continue_capturing(pending_pos):
                pending_capture = None
            else:
                # Only show single-hop captures from the pending position
                legal_moves = engine.find_single_hop_captures(pending_pos)
                movable_positions = {pending_pos}
                selected_pos = pending_pos  # Auto-select the piece

        if not pending_capture:
            # Normal mode: get all legal moves but use single-hop for captures
            all_legal_moves = engine.get_legal_moves(engine.current_turn)
            
            # Separate captures from regular moves
            capture_positions = set()
            regular_move_positions = set()
            
            for move in all_legal_moves:
                if move.captures:
                    capture_positions.add(move.from_pos)
                else:
                    regular_move_positions.add(move.from_pos)
            
            # If any captures available, ONLY show captures (mandatory)
            if capture_positions:
                movable_positions = capture_positions
                # Get single-hop captures for these positions
                legal_moves = []
                for pos in capture_positions:
                    legal_moves.extend(engine.find_single_hop_captures(pos))
            else:
                movable_positions = regular_move_positions
                legal_moves = [m for m in all_legal_moves if not m.captures]
        
        # If a piece is selected, get its possible moves
        selected_destinations = set()
        if selected_pos is not None:
            for move in legal_moves:
                if move.from_pos == selected_pos:
                    selected_destinations.add(move.to_pos)
        
        # Create 8x8 board keyboard
        for row in range(8):
            row_buttons = []
            for col in range(8):
                pos = row * 8 + col
                piece = engine.board[pos]
                is_dark = (row + col) % 2 == 1
                
                # Determine button label
                if pos == selected_pos:
                    # Selected piece - show with highlight
                    label = BoardRenderer._get_selected_piece_emoji(piece)
                elif pos in selected_destinations:
                    # Possible destination - show target
                    label = "🎯"
                elif piece != 0:
                    # Regular piece (clickable or not)
                    label = BoardRenderer._get_piece_emoji(piece)
                else:
                    # Empty square - use Braille pattern blank
                    label = "⠀"
                
                # Determine callback data
                if selected_pos is None and pos in movable_positions:
                    # Clickable piece to select
                    callback = f"select_{pos}"
                elif selected_pos is not None and pos in selected_destinations:
                    # Clickable destination
                    callback = f"move_{selected_pos}_{pos}"
                else:
                    # Non-clickable square
                    callback = f"noop_{pos}"
                
                row_buttons.append(InlineKeyboardButton(label, callback_data=callback))
            
            buttons.append(row_buttons)
        
        # Add control buttons
        control_buttons = []
        
        # Continuation indicator
        if pending_capture:
            # Show mandatory continuation message
            buttons.insert(0, [InlineKeyboardButton("⚡ Продовжуйте бити!", callback_data="noop_continue")])
        
        if selected_pos is not None and not pending_capture:
            control_buttons.append(InlineKeyboardButton("« Скасувати", callback_data="back"))
            
        # Specific button based on game stage
        if move_count == 0:
            control_buttons.append(InlineKeyboardButton(locales.BTN_CANCEL, callback_data="forfeit"))
        else:
            control_buttons.append(InlineKeyboardButton(locales.BTN_FORFEIT, callback_data="forfeit"))
            
        buttons.append(control_buttons)
        
        return InlineKeyboardMarkup(buttons)
    
    @staticmethod
    def _get_piece_emoji(piece: int) -> str:
        """Get emoji for a piece."""
        if piece == 1:  # Yellow man
            return locales.PIECE_WHITE
        elif piece == 2:  # Yellow king
            return locales.PIECE_WHITE_KING
        elif piece == 3:  # Blue man
            return locales.PIECE_RED
        elif piece == 4:  # Blue king
            return locales.PIECE_RED_KING
        return ""
    
    @staticmethod
    def _get_selected_piece_emoji(piece: int) -> str:
        """Get emoji for a selected piece."""
        if piece == 1:  # Yellow man
            return locales.PIECE_WHITE_SELECTED
        elif piece == 2:  # Yellow king
            return locales.PIECE_WHITE_KING_SELECTED
        elif piece == 3:  # Blue man
            return locales.PIECE_RED_SELECTED
        elif piece == 4:  # Blue king
            return locales.PIECE_RED_KING_SELECTED
        return ""

