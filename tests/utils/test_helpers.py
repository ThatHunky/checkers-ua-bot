"""
Test utilities and helper functions
"""

from typing import List, Dict, Any
from engine import CheckersEngine, YELLOW, BLUE, Move


def create_game_state(
    blue_player_id: int = 12345,
    yellow_player_id: int = 67890,
    blue_player_name: str = "Blue",
    yellow_player_name: str = "Yellow",
    current_turn: int = YELLOW,
    move_count: int = 0,
    mode: str = "rated",
    is_inline: bool = False,
    inline_message_id: str = None,
    board: List[int] = None
) -> Dict[str, Any]:
    """Create a game state dictionary with default or custom values."""
    from datetime import datetime, timezone
    
    if board is None:
        engine = CheckersEngine()
        board = engine.board
    
    state = {
        "board": board,
        "current_turn": current_turn,
        "blue_player_id": blue_player_id,
        "blue_player_name": blue_player_name,
        "blue_player_username": blue_player_name.lower(),
        "yellow_player_id": yellow_player_id,
        "yellow_player_name": yellow_player_name,
        "yellow_player_username": yellow_player_name.lower(),
        "move_count": move_count,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_activity": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "is_inline": is_inline,
    }
    
    if inline_message_id:
        state["inline_message_id"] = inline_message_id
    
    return state


def create_move(from_pos: int, to_pos: int, captures: List[int] = None, 
                promotes: bool = False, promoted_during_capture: bool = False) -> Move:
    """Create a Move object with specified parameters."""
    return Move(
        from_pos=from_pos,
        to_pos=to_pos,
        captures=captures or [],
        promotes=promotes,
        promoted_during_capture=promoted_during_capture
    )


def count_pieces(board: List[int], piece_type: int) -> int:
    """Count pieces of a specific type on the board."""
    return sum(1 for p in board if p == piece_type)


def count_pieces_by_color(board: List[int], color: int) -> int:
    """Count all pieces (men and kings) of a specific color."""
    if color == YELLOW:
        return sum(1 for p in board if p in (1, 2))
    elif color == BLUE:
        return sum(1 for p in board if p in (3, 4))
    return 0


def assert_valid_board(board: List[int]) -> None:
    """Assert that a board state is valid."""
    assert len(board) == 64, "Board must have 64 squares"
    assert all(0 <= p <= 4 for p in board), "All pieces must be valid (0-4)"


def assert_move_valid(move: Move, engine: CheckersEngine) -> None:
    """Assert that a move is valid for the current engine state."""
    assert 0 <= move.from_pos < 64, "from_pos must be valid"
    assert 0 <= move.to_pos < 64, "to_pos must be valid"
    assert engine.board[move.from_pos] != 0, "Source square must have a piece"
    assert engine.board[move.to_pos] == 0, "Destination square must be empty"
    if move.captures:
        for cap_pos in move.captures:
            assert 0 <= cap_pos < 64, "Capture position must be valid"

