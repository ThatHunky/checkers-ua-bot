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
                            move_count: int = 1,
                            pending_capture: dict = None,
                            draw_offer: Optional[dict] = None,
                            draw_button_min_moves: int = 20) -> InlineKeyboardMarkup:
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
            # If no follow-up captures remain, fall back to normal selection.
            # captured_so_far keeps the already-captured squares as blockers, so the
            # squares drawn here are exactly the ones move_callback will accept.
            legal_moves = engine.get_legal_single_hop_moves(
                pending_pos=pending_pos,
                captured_so_far=pending_capture.get("captured"),
            )
            if not legal_moves:
                pending_capture = None
            else:
                movable_positions = {pending_pos}
                selected_pos = pending_pos  # Auto-select the piece

        if not pending_capture:
            # Normal mode: use engine-filtered single-hop moves (captures are mandatory and best-line enforced)
            legal_moves = engine.get_legal_single_hop_moves()
            movable_positions = {m.from_pos for m in legal_moves}
        
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
            
        # Review previous moves (only after at least one move exists)
        # This switches the message into a non-destructive "review" mode via GameHandlers.review_callback.
        if int(move_count or 0) > 0:
            # Most recent move index is move_count - 1 (move_history is appended once per applied move).
            control_buttons.append(
                InlineKeyboardButton("⏪ Попередній хід", callback_data=f"review_{int(move_count) - 1}")
            )

        # Specific button based on game stage
        if move_count == 0:
            control_buttons.append(InlineKeyboardButton(locales.BTN_CANCEL, callback_data="forfeit"))
        else:
            # Draw controls: manual offer/accept/decline flow (only after threshold)
            if int(move_count or 0) >= int(draw_button_min_moves or 0):
                if isinstance(draw_offer, dict) and draw_offer.get("by_user_id"):
                    control_buttons.append(
                        InlineKeyboardButton(locales.BTN_DRAW_ACCEPT, callback_data="draw_accept")
                    )
                    control_buttons.append(
                        InlineKeyboardButton(locales.BTN_DRAW_DECLINE, callback_data="draw_decline")
                    )
                else:
                    control_buttons.append(
                        InlineKeyboardButton(locales.BTN_DRAW_OFFER, callback_data="draw_offer")
                    )
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

