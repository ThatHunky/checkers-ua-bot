"""
Ukrainian Checkers (Шашки) Game Engine
Implements Russian/Ukrainian drafts rules on an 8x8 board.
"""

from typing import List, Tuple, Optional, Set
from dataclasses import dataclass

# Piece constants
EMPTY = 0
WHITE = 1
WHITE_KING = 2
RED = 3
RED_KING = 4

# Board is 8x8 = 64 squares, indexed 0-63
# Index mapping: row * 8 + col
# Row 0 is top (RED side), Row 7 is bottom (WHITE side)

@dataclass
class Move:
    """Represents a move/capture sequence."""
    from_pos: int
    to_pos: int
    captures: List[int]  # Positions of captured pieces
    promotes: bool = False  # Does this move result in promotion?


class CheckersEngine:
    """Core game logic for Ukrainian Checkers."""
    
    def __init__(self):
        self.board: List[int] = self.init_board()
        self.current_turn = RED  # RED starts (top of board)
        self.move_count = 0  # Track total moves made
    
    @staticmethod
    def init_board() -> List[int]:
        """Initialize standard 8x8 checkers starting position."""
        board = [EMPTY] * 64
        
        # RED pieces (top 3 rows, dark squares only)
        for row in range(3):
            for col in range(8):
                if (row + col) % 2 == 1:  # Dark squares
                    board[row * 8 + col] = RED
        
        # WHITE pieces (bottom 3 rows, dark squares only)
        for row in range(5, 8):
            for col in range(8):
                if (row + col) % 2 == 1:  # Dark squares
                    board[row * 8 + col] = WHITE
        
        return board
    
    @staticmethod
    def pos_to_coords(pos: int) -> Tuple[int, int]:
        """Convert linear position to (row, col)."""
        return (pos // 8, pos % 8)
    
    @staticmethod
    def coords_to_pos(row: int, col: int) -> int:
        """Convert (row, col) to linear position."""
        return row * 8 + col
    
    @staticmethod
    def is_valid_pos(row: int, col: int) -> bool:
        """Check if position is on the board."""
        return 0 <= row < 8 and 0 <= col < 8
    
    def get_piece_color(self, piece: int) -> Optional[int]:
        """Get the color of a piece (WHITE or RED)."""
        if piece in (WHITE, WHITE_KING):
            return WHITE
        elif piece in (RED, RED_KING):
            return RED
        return None
    
    def is_king(self, piece: int) -> bool:
        """Check if piece is a king."""
        return piece in (WHITE_KING, RED_KING)
    
    def get_legal_moves(self, color: int) -> List[Move]:
        """
        Get all legal moves for the given color.
        Enforces mandatory capture rule.
        """
        all_captures = []
        all_normal_moves = []
        
        for pos in range(64):
            piece = self.board[pos]
            if self.get_piece_color(piece) == color:
                # Check for captures first
                piece_captures = self._get_captures_from_pos(pos)
                all_captures.extend(piece_captures)
                
                # Also get normal moves (we'll only use them if no captures exist)
                piece_moves = self._get_normal_moves_from_pos(pos)
                all_normal_moves.extend(piece_moves)
        
        # Mandatory capture: return captures if any exist
        return all_captures if all_captures else all_normal_moves
    
    def _get_normal_moves_from_pos(self, pos: int) -> List[Move]:
        """Get non-capturing moves from a position."""
        piece = self.board[pos]
        if piece == EMPTY:
            return []
        
        row, col = self.pos_to_coords(pos)
        moves = []
        
        if self.is_king(piece):
            # Kings can move any distance diagonally
            moves.extend(self._get_king_moves(pos, row, col))
        else:
            # Men move forward one square diagonally
            moves.extend(self._get_man_moves(pos, row, col, piece))
        
        return moves
    
    def _get_man_moves(self, pos: int, row: int, col: int, piece: int) -> List[Move]:
        """Get normal moves for a man (non-king piece)."""
        moves = []
        # Men move forward only (WHITE moves up, RED moves down)
        direction = -1 if piece == WHITE else 1
        
        for dc in [-1, 1]:  # Left and right diagonals
            new_row = row + direction
            new_col = col + dc
            
            if self.is_valid_pos(new_row, new_col):
                new_pos = self.coords_to_pos(new_row, new_col)
                if self.board[new_pos] == EMPTY:
                    # Check if this move promotes
                    promotes = (piece == WHITE and new_row == 0) or (piece == RED and new_row == 7)
                    moves.append(Move(pos, new_pos, [], promotes))
        
        return moves
    
    def _get_king_moves(self, pos: int, row: int, col: int) -> List[Move]:
        """Get normal moves for a king (flying movement)."""
        moves = []
        
        # Four diagonal directions
        for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            # Try each distance along this diagonal
            for dist in range(1, 8):
                new_row = row + dr * dist
                new_col = col + dc * dist
                
                if not self.is_valid_pos(new_row, new_col):
                    break
                
                new_pos = self.coords_to_pos(new_row, new_col)
                if self.board[new_pos] != EMPTY:
                    break  # Blocked by a piece
                
                moves.append(Move(pos, new_pos, [], False))
        
        return moves
    
    def _get_captures_from_pos(self, pos: int) -> List[Move]:
        """Get all possible capture sequences starting from this position."""
        piece = self.board[pos]
        if piece == EMPTY:
            return []
        
        # Find all capture sequences
        captures = []
        self._find_captures_recursive(
            start_pos=pos,
            current_pos=pos,
            piece=piece,
            captured_so_far=[],
            all_captures=captures
        )
        return captures
    
    def _find_captures_recursive(
        self,
        start_pos: int,
        current_pos: int,
        piece: int,
        captured_so_far: List[int],
        all_captures: List[Move]
    ):
        """
        Recursively find all possible capture sequences.
        Handles multi-captures and instant promotion during jumps.
        """
        row, col = self.pos_to_coords(current_pos)
        found_capture = False
        current_color = self.get_piece_color(piece)
        
        if self.is_king(piece):
            # Kings can jump any distance
            found_capture = self._find_king_captures(
                start_pos, current_pos, row, col, piece, current_color, captured_so_far, all_captures
            )
        else:
            # Men capture in all 4 diagonal directions (forward AND backward)
            found_capture = self._find_man_captures(
                start_pos, current_pos, row, col, piece, current_color, captured_so_far, all_captures
            )
        
        # If no further captures, record this capture sequence
        if not found_capture and captured_so_far:
            all_captures.append(Move(
                from_pos=start_pos,
                to_pos=current_pos,
                captures=captured_so_far.copy(),
                promotes=False
            ))
    
    def _find_man_captures(
        self,
        start_pos: int,
        current_pos: int,
        row: int,
        col: int,
        piece: int,
        current_color: int,
        captured_so_far: List[int],
        all_captures: List[Move]
    ) -> bool:
        """Find captures for a man (can capture forward AND backward)."""
        found_capture = False
        
        # All 4 diagonal directions (Ukrainian rules: men can capture backward!)
        for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            enemy_row = row + dr
            enemy_col = col + dc
            land_row = row + 2 * dr
            land_col = col + 2 * dc
            
            if not self.is_valid_pos(enemy_row, enemy_col) or not self.is_valid_pos(land_row, land_col):
                continue
            
            enemy_pos = self.coords_to_pos(enemy_row, enemy_col)
            land_pos = self.coords_to_pos(land_row, land_col)
            
            # Check if we can capture this piece
            enemy_piece = self.board[enemy_pos]
            enemy_color = self.get_piece_color(enemy_piece)
            
            if (enemy_color and enemy_color != current_color and 
                enemy_pos not in captured_so_far and
                self.board[land_pos] == EMPTY):
                
                found_capture = True
                
                # Make temporary move
                new_captured = captured_so_far + [enemy_pos]
                
                # Check for instant promotion
                new_piece = piece
                if (piece == WHITE and land_row == 0) or (piece == RED and land_row == 7):
                    new_piece = WHITE_KING if piece == WHITE else RED_KING
                
                # Continue searching from landing position
                self._find_captures_recursive(
                    start_pos, land_pos, new_piece, new_captured, all_captures
                )
        
        return found_capture
    
    def _find_king_captures(
        self,
        start_pos: int,
        current_pos: int,
        row: int,
        col: int,
        piece: int,
        current_color: int,
        captured_so_far: List[int],
        all_captures: List[Move]
    ) -> bool:
        """Find captures for a king (flying captures)."""
        found_capture = False
        
        # Four diagonal directions
        for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
            # Look for enemy pieces along this diagonal
            for dist in range(1, 8):
                enemy_row = row + dr * dist
                enemy_col = col + dc * dist
                
                if not self.is_valid_pos(enemy_row, enemy_col):
                    break
                
                enemy_pos = self.coords_to_pos(enemy_row, enemy_col)
                enemy_piece = self.board[enemy_pos]
                
                if enemy_piece == EMPTY:
                    continue  # Keep looking
                
                enemy_color = self.get_piece_color(enemy_piece)
                
                # Found a piece - check if it's capturable
                if enemy_color == current_color:
                    break  # Own piece blocks
                
                if enemy_pos in captured_so_far:
                    break  # Already captured
                
                # Try to land beyond the enemy
                for land_dist in range(dist + 1, 8):
                    land_row = row + dr * land_dist
                    land_col = col + dc * land_dist
                    
                    if not self.is_valid_pos(land_row, land_col):
                        break
                    
                    land_pos = self.coords_to_pos(land_row, land_col)
                    if self.board[land_pos] != EMPTY:
                        break  # Blocked
                    
                    found_capture = True
                    new_captured = captured_so_far + [enemy_pos]
                    
                    # Continue searching from landing position
                    self._find_captures_recursive(
                        start_pos, land_pos, piece, new_captured, all_captures
                    )
                
                break  # Stop after first piece in this direction
        
        return found_capture
    
    def apply_move(self, move: Move) -> bool:
        """
        Apply a move to the board.
        Returns True if successful, False otherwise.
        """
        # Validate move
        if not (0 <= move.from_pos < 64 and 0 <= move.to_pos < 64):
            return False
        
        piece = self.board[move.from_pos]
        if piece == EMPTY:
            return False
        
        # Move the piece
        self.board[move.to_pos] = piece
        self.board[move.from_pos] = EMPTY
        
        # Remove captured pieces
        for cap_pos in move.captures:
            self.board[cap_pos] = EMPTY
        
        # Handle promotion
        to_row, _ = self.pos_to_coords(move.to_pos)
        if piece == WHITE and to_row == 0:
            self.board[move.to_pos] = WHITE_KING
        elif piece == RED and to_row == 7:
            self.board[move.to_pos] = RED_KING
        
        # Switch turn
        self.current_turn = RED if self.current_turn == WHITE else WHITE
        self.move_count += 1
        
        return True
    
    def check_winner(self) -> Optional[int]:
        """
        Check if there's a winner.
        Returns WHITE, RED, or None if game continues.
        """
        # Count pieces and check for legal moves
        white_count = 0
        red_count = 0
        
        for piece in self.board:
            if piece in (WHITE, WHITE_KING):
                white_count += 1
            elif piece in (RED, RED_KING):
                red_count += 1
        
        # No pieces left = loss
        if white_count == 0:
            return RED
        if red_count == 0:
            return WHITE
        
        # No legal moves = loss
        legal_moves = self.get_legal_moves(self.current_turn)
        if not legal_moves:
            return RED if self.current_turn == WHITE else WHITE
        
        return None
    
    def get_board_state(self) -> dict:
        """Get serializable game state."""
        return {
            "board": self.board.copy(),
            "current_turn": self.current_turn,
            "move_count": self.move_count
        }
    
    def set_board_state(self, state: dict):
        """Restore game state from serialized data."""
        self.board = state["board"].copy()
        self.current_turn = state["current_turn"]
        self.move_count = state.get("move_count", 0)
