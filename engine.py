"""
Ukrainian Checkers (Шашки) Game Engine
Implements Russian/Ukrainian drafts rules on an 8x8 board.
"""

from typing import List, Tuple, Optional, Set, Sequence
from dataclasses import dataclass
from functools import lru_cache

# Piece constants
EMPTY = 0
YELLOW = 1
YELLOW_KING = 2
BLUE = 3
BLUE_KING = 4

# Sentinel used only inside the multi-capture search. Under Russian/Ukrainian
# rules ("Turkish strike") a captured piece stays on the board as a blocker
# until the whole capture sequence ends: it may not be jumped over again, and
# it may not be landed on. It is never written to a real board.
CAPTURED = -1

# Backward compatibility aliases (deprecated, use YELLOW/BLUE)
WHITE = YELLOW
WHITE_KING = YELLOW_KING
RED = BLUE
RED_KING = BLUE_KING

# Board is 8x8 = 64 squares, indexed 0-63
# Index mapping: row * 8 + col
# Row 0 is top (BLUE side), Row 7 is bottom (YELLOW side)

@dataclass
class Move:
    """Represents a move/capture sequence."""
    from_pos: int
    to_pos: int
    captures: List[int]  # Positions of captured pieces
    promotes: bool = False  # Does this move result in promotion?
    promoted_during_capture: bool = False  # Did piece promote mid-capture?


class CheckersEngine:
    """Core game logic for Ukrainian Checkers."""
    
    def __init__(self):
        self.board: List[int] = self.init_board()
        self.current_turn = YELLOW  # YELLOW starts (opponent moves first)
        self.move_count = 0  # Track total moves made

    # Score = (total_captures, total_kings_captured)
    _Score = Tuple[int, int]

    @staticmethod
    def piece_color(piece: int) -> Optional[int]:
        """Pure helper: color of a piece, or None if EMPTY/unknown."""
        if piece in (YELLOW, YELLOW_KING):
            return YELLOW
        if piece in (BLUE, BLUE_KING):
            return BLUE
        return None

    @staticmethod
    def is_king_piece(piece: int) -> bool:
        """Pure helper: whether a piece value represents a king."""
        return piece in (YELLOW_KING, BLUE_KING)

    @staticmethod
    def is_king_row_for_piece(piece: int, row: int) -> bool:
        """Pure helper: whether row is the promotion row for this man piece."""
        return (piece == YELLOW and row == 0) or (piece == BLUE and row == 7)

    @staticmethod
    def is_king_value(piece: int) -> bool:
        """Pure helper: piece is a king constant."""
        return piece in (YELLOW_KING, BLUE_KING)

    @staticmethod
    def _apply_single_hop_capture(
        board: Tuple[int, ...],
        from_pos: int,
        to_pos: int,
        new_piece: int,
        captured_pos: int,
    ) -> Tuple[int, ...]:
        """Return a new board after applying a single-hop capture.

        The captured square is marked CAPTURED rather than EMPTY: it remains a
        blocker for the rest of the sequence (Turkish strike rule). to_pos is
        written last so a sequence returning to its own origin keeps the piece.
        """
        b = list(board)
        b[from_pos] = EMPTY
        b[captured_pos] = CAPTURED
        b[to_pos] = new_piece
        return tuple(b)

    @staticmethod
    def _generate_single_hop_captures_from_state(
        board: Tuple[int, ...],
        from_pos: int,
        piece: int,
    ) -> List[Tuple[int, int, int, bool]]:
        """
        Generate all single-hop capture options from a position for a given board state.

        Returns tuples: (to_pos, captured_pos, new_piece_value, promoted_during_capture)
        """
        if piece == EMPTY:
            return []

        color = CheckersEngine.piece_color(piece)
        if color is None:
            return []

        row, col = CheckersEngine.pos_to_coords(from_pos)
        results: List[Tuple[int, int, int, bool]] = []

        if CheckersEngine.is_king_piece(piece):
            # Flying king captures: first enemy in direction, land on any empty square beyond.
            for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                # Scan to first piece.
                enemy_pos: Optional[int] = None
                for dist in range(1, 8):
                    r = row + dr * dist
                    c = col + dc * dist
                    if not CheckersEngine.is_valid_pos(r, c):
                        break
                    p = board[CheckersEngine.coords_to_pos(r, c)]
                    if p == EMPTY:
                        continue
                    if p == CAPTURED:
                        break  # already captured this move: blocks, cannot be taken again
                    p_color = CheckersEngine.piece_color(p)
                    if p_color == color:
                        break  # blocked by own piece
                    enemy_pos = CheckersEngine.coords_to_pos(r, c)
                    break

                if enemy_pos is None:
                    continue

                # Landing squares beyond enemy until blocked/offboard.
                enemy_row, enemy_col = CheckersEngine.pos_to_coords(enemy_pos)
                for land_dist in range(1, 8):
                    r = enemy_row + dr * land_dist
                    c = enemy_col + dc * land_dist
                    if not CheckersEngine.is_valid_pos(r, c):
                        break
                    land_pos = CheckersEngine.coords_to_pos(r, c)
                    if board[land_pos] != EMPTY:
                        break
                    results.append((land_pos, enemy_pos, piece, False))
        else:
            # Men capture in all 4 diagonal directions (forward + backward).
            for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                enemy_row = row + dr
                enemy_col = col + dc
                land_row = row + 2 * dr
                land_col = col + 2 * dc
                if not CheckersEngine.is_valid_pos(enemy_row, enemy_col) or not CheckersEngine.is_valid_pos(land_row, land_col):
                    continue

                enemy_pos = CheckersEngine.coords_to_pos(enemy_row, enemy_col)
                land_pos = CheckersEngine.coords_to_pos(land_row, land_col)
                enemy_piece = board[enemy_pos]
                enemy_color = CheckersEngine.piece_color(enemy_piece)
                if enemy_color is None or enemy_color == color:
                    continue
                if board[land_pos] != EMPTY:
                    continue

                promoted = CheckersEngine.is_king_row_for_piece(piece, land_row)
                new_piece = (YELLOW_KING if piece == YELLOW else BLUE_KING) if promoted else piece
                results.append((land_pos, enemy_pos, new_piece, promoted))

        return results

    @staticmethod
    @lru_cache(maxsize=200_000)
    def _best_capture_score_from_state(
        board: Tuple[int, ...],
        from_pos: int,
        piece: int,
    ) -> _Score:
        """
        Compute best achievable capture score from a given state.
        Score is lexicographically compared as (captures_count, kings_captured_count).
        """
        hops = CheckersEngine._generate_single_hop_captures_from_state(board, from_pos, piece)
        if not hops:
            return (0, 0)

        best: CheckersEngine._Score = (0, 0)
        for to_pos, captured_pos, new_piece, _promoted in hops:
            captured_piece = board[captured_pos]
            captured_kings = 1 if CheckersEngine.is_king_piece(captured_piece) else 0
            next_board = CheckersEngine._apply_single_hop_capture(
                board=board,
                from_pos=from_pos,
                to_pos=to_pos,
                new_piece=new_piece,
                captured_pos=captured_pos,
            )
            child = CheckersEngine._best_capture_score_from_state(next_board, to_pos, new_piece)
            score = (1 + child[0], captured_kings + child[1])
            if score > best:
                best = score

        return best

    @staticmethod
    def _best_hops_from_state(
        board: Tuple[int, ...],
        from_pos: int,
        piece: int,
    ) -> List[Tuple[int, int, int, bool]]:
        """
        Filter single-hop captures to only those that can lead to the best score from this state.
        """
        hops = CheckersEngine._generate_single_hop_captures_from_state(board, from_pos, piece)
        if not hops:
            return []

        best_score: CheckersEngine._Score = (0, 0)
        scored: List[Tuple[CheckersEngine._Score, Tuple[int, int, int, bool]]] = []
        for hop in hops:
            to_pos, captured_pos, new_piece, promoted = hop
            captured_piece = board[captured_pos]
            captured_kings = 1 if CheckersEngine.is_king_piece(captured_piece) else 0
            next_board = CheckersEngine._apply_single_hop_capture(
                board=board,
                from_pos=from_pos,
                to_pos=to_pos,
                new_piece=new_piece,
                captured_pos=captured_pos,
            )
            child = CheckersEngine._best_capture_score_from_state(next_board, to_pos, new_piece)
            total = (1 + child[0], captured_kings + child[1])
            if total > best_score:
                best_score = total
            scored.append((total, (to_pos, captured_pos, new_piece, promoted)))

        return [hop for score, hop in scored if score == best_score]

    # Capture sequence element:
    # (final_landing_pos, captured_positions_in_order, promoted_during_capture_any_step)
    _CaptureSeq = Tuple[int, Tuple[int, ...], bool]
    _SeqResult = Tuple[_Score, Tuple[_CaptureSeq, ...]]

    @staticmethod
    @lru_cache(maxsize=200_000)
    def _best_capture_sequences_from_state(
        board: Tuple[int, ...],
        from_pos: int,
        piece: int,
    ) -> _SeqResult:
        """
        Return (best_score, sequences) for the given state.

        sequences are only those that achieve the best_score (max captures, then max king captures).
        """
        hops = CheckersEngine._generate_single_hop_captures_from_state(board, from_pos, piece)
        if not hops:
            return (0, 0), tuple()

        best_score: CheckersEngine._Score = (0, 0)
        best_sequences: List[CheckersEngine._CaptureSeq] = []

        for to_pos, captured_pos, new_piece, promoted in hops:
            captured_piece = board[captured_pos]
            captured_kings = 1 if CheckersEngine.is_king_piece(captured_piece) else 0
            next_board = CheckersEngine._apply_single_hop_capture(
                board=board,
                from_pos=from_pos,
                to_pos=to_pos,
                new_piece=new_piece,
                captured_pos=captured_pos,
            )

            child_score, child_seqs = CheckersEngine._best_capture_sequences_from_state(next_board, to_pos, new_piece)
            total_score = (1 + child_score[0], captured_kings + child_score[1])

            # Build full sequences by prepending this captured_pos.
            if child_seqs:
                built = [
                    (end_pos, (captured_pos,) + caps, promoted or child_promoted)
                    for (end_pos, caps, child_promoted) in child_seqs
                ]
            else:
                built = [(to_pos, (captured_pos,), promoted)]

            if total_score > best_score:
                best_score = total_score
                best_sequences = built
                continue

            if total_score == best_score:
                best_sequences.extend(built)

        # Deduplicate sequences defensively (can happen when multiple paths lead to same end/capture list).
        seen: Set[Tuple[int, Tuple[int, ...], bool]] = set()
        unique: List[CheckersEngine._CaptureSeq] = []
        for seq in best_sequences:
            if seq in seen:
                continue
            seen.add(seq)
            unique.append(seq)

        return best_score, tuple(unique)

    @staticmethod
    def position_key(board: Sequence[int], current_turn: int) -> str:
        """
        Compute a stable signature for repetition detection.

        The key is defined by:
        - board piece placement (64 integers 0-4)
        - side to move (current_turn)

        This is intentionally deterministic and cheap to compute.
        """
        # Pieces are single-digit (0-4), so concatenation is unambiguous.
        return f"{int(current_turn)}|{''.join(str(int(p)) for p in board)}"
    
    @staticmethod
    def init_board() -> List[int]:
        """Initialize standard 8x8 checkers starting position."""
        board = [EMPTY] * 64
        
        # BLUE pieces (top 3 rows, dark squares only)
        for row in range(3):
            for col in range(8):
                if (row + col) % 2 == 1:  # Dark squares
                    board[row * 8 + col] = BLUE
        
        # YELLOW pieces (bottom 3 rows, dark squares only)
        for row in range(5, 8):
            for col in range(8):
                if (row + col) % 2 == 1:  # Dark squares
                    board[row * 8 + col] = YELLOW
        
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
        """Get the color of a piece (YELLOW or BLUE)."""
        if piece in (YELLOW, YELLOW_KING):
            return YELLOW
        elif piece in (BLUE, BLUE_KING):
            return BLUE
        return None
    
    def is_king(self, piece: int) -> bool:
        """Check if piece is a king."""
        return piece in (YELLOW_KING, BLUE_KING)

    def board_with_sequence_blockers(
        self, captured_so_far: Optional[Sequence[int]] = None
    ) -> Tuple[int, ...]:
        """
        Board tuple with squares captured earlier in the *current, unfinished* capture
        sequence restored as CAPTURED blockers.

        apply_move clears captured squares to EMPTY on the real board, so interactive
        hop-by-hop play would otherwise let a king fly back through a square it just
        captured -- the exact line the search (which keeps the sentinel) already ruled
        out. Every entry point that continues a sequence must rebuild the blockers here
        so the walked line matches the enumerated one.
        """
        if not captured_so_far:
            return tuple(self.board)
        b = list(self.board)
        for pos in captured_so_far:
            if isinstance(pos, int) and 0 <= pos < 64 and b[pos] == EMPTY:
                b[pos] = CAPTURED
        return tuple(b)

    def get_legal_single_hop_moves(
        self,
        pending_pos: Optional[int] = None,
        captured_so_far: Optional[Sequence[int]] = None,
    ) -> List[Move]:
        """
        Get legal *single-step* moves for the current player, applying best-capture rules.

        If pending_pos is provided, this returns only legal continuation captures from that position
        (and filters them to only the best remaining line).

        If pending_pos is None:
        - If any capture exists: return only capture hops that lead to the globally best line
          (max total captures, then max kings captured).
        - Otherwise: return normal non-capturing moves.

        captured_so_far lists the squares already captured in an in-progress sequence; they
        stay on the board as blockers (Turkish strike) for the rest of the move.
        """
        board_state = self.board_with_sequence_blockers(captured_so_far)
        color = self.current_turn

        if pending_pos is not None:
            if not (0 <= pending_pos < 64):
                return []
            piece = self.board[pending_pos]
            if self.get_piece_color(piece) != color:
                return []

            best_hops = self._best_hops_from_state(board_state, pending_pos, piece)
            return [
                Move(
                    from_pos=pending_pos,
                    to_pos=to_pos,
                    captures=[captured_pos],
                    promotes=promoted,
                    promoted_during_capture=promoted,
                )
                for (to_pos, captured_pos, _new_piece, promoted) in best_hops
            ]

        # Not in a forced continuation: compute all captures and enforce global best.
        capture_candidates: List[Tuple[int, int, int, bool]] = []
        best_global: CheckersEngine._Score = (0, 0)
        scored_moves: List[Tuple[CheckersEngine._Score, Move]] = []

        for from_pos in range(64):
            piece = self.board[from_pos]
            if self.get_piece_color(piece) != color:
                continue
            hops = self._generate_single_hop_captures_from_state(board_state, from_pos, piece)
            for to_pos, captured_pos, new_piece, promoted in hops:
                captured_piece = board_state[captured_pos]
                captured_kings = 1 if self.is_king(captured_piece) else 0
                next_board = self._apply_single_hop_capture(
                    board=board_state,
                    from_pos=from_pos,
                    to_pos=to_pos,
                    new_piece=new_piece,
                    captured_pos=captured_pos,
                )
                child = self._best_capture_score_from_state(next_board, to_pos, new_piece)
                total = (1 + child[0], captured_kings + child[1])
                if total > best_global:
                    best_global = total
                scored_moves.append(
                    (
                        total,
                        Move(
                            from_pos=from_pos,
                            to_pos=to_pos,
                            captures=[captured_pos],
                            promotes=promoted,
                            promoted_during_capture=promoted,
                        ),
                    )
                )

        if scored_moves and best_global > (0, 0):
            return [m for score, m in scored_moves if score == best_global]

        # No captures exist anywhere: allow normal moves.
        normal_moves: List[Move] = []
        for pos in range(64):
            piece = self.board[pos]
            if self.get_piece_color(piece) != color:
                continue
            normal_moves.extend(self._get_normal_moves_from_pos(pos))
        return normal_moves
    
    def get_legal_moves(self, color: int) -> List[Move]:
        """
        Get all legal moves for the given color.
        Enforces mandatory capture rule.
        """
        board_state = tuple(self.board)

        # Find global best capture score among all pieces of this color.
        global_best: CheckersEngine._Score = (0, 0)
        per_piece: List[Tuple[int, CheckersEngine._Score, Tuple[CheckersEngine._CaptureSeq, ...]]] = []

        for pos in range(64):
            piece = self.board[pos]
            if self.get_piece_color(piece) != color:
                continue
            score, seqs = self._best_capture_sequences_from_state(board_state, pos, piece)
            if score > global_best:
                global_best = score
            if score > (0, 0):
                per_piece.append((pos, score, seqs))

        # If any capture exists, enforce best-capture rule (max captures, then max kings captured).
        if global_best > (0, 0):
            moves: List[Move] = []
            for from_pos, score, seqs in per_piece:
                if score != global_best:
                    continue
                for end_pos, captures, promoted_during_capture in seqs:
                    moves.append(
                        Move(
                            from_pos=from_pos,
                            to_pos=end_pos,
                            captures=list(captures),
                            promotes=False,
                            promoted_during_capture=promoted_during_capture,
                        )
                    )
            return moves

        # Otherwise, allow normal non-capturing moves.
        all_normal_moves: List[Move] = []
        for pos in range(64):
            piece = self.board[pos]
            if self.get_piece_color(piece) != color:
                continue
            all_normal_moves.extend(self._get_normal_moves_from_pos(pos))
        return all_normal_moves
    
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
        # Men move forward only (YELLOW moves up, BLUE moves down)
        direction = -1 if piece == YELLOW else 1
        
        for dc in [-1, 1]:  # Left and right diagonals
            new_row = row + direction
            new_col = col + dc
            
            if self.is_valid_pos(new_row, new_col):
                new_pos = self.coords_to_pos(new_row, new_col)
                if self.board[new_pos] == EMPTY:
                    # Check if this move promotes
                    promotes = (piece == YELLOW and new_row == 0) or (piece == BLUE and new_row == 7)
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
            all_captures=captures,
            visited_positions=set(),
            depth=0
        )
        
        # Deduplicate capture sequences to avoid processing duplicate moves
        # Two moves are duplicates if they have same from_pos, to_pos, and captures
        seen = set()
        unique_captures = []
        for move in captures:
            # Create a unique key based on from_pos, to_pos, and sorted captures
            key = (move.from_pos, move.to_pos, tuple(sorted(move.captures)))
            if key not in seen:
                seen.add(key)
                unique_captures.append(move)
        
        return unique_captures
    
    def _find_captures_recursive(
        self,
        start_pos: int,
        current_pos: int,
        piece: int,
        captured_so_far: List[int],
        all_captures: List[Move],
        visited_positions: Set[int],
        depth: int = 0
    ):
        """
        Recursively find all possible capture sequences.
        Handles multi-captures and instant promotion during jumps.
        
        Args:
            start_pos: Original starting position of the piece
            current_pos: Current position during capture sequence
            piece: Current piece (may have been promoted)
            captured_so_far: List of positions captured so far
            all_captures: List to accumulate all capture sequences
            visited_positions: Set of positions already visited in this capture sequence (prevents cycles)
            depth: Recursion depth (safety limit to prevent infinite loops)
        """
        # Safety limit: prevent infinite recursion (max 12 captures = all enemy pieces)
        MAX_RECURSION_DEPTH = 12
        if depth > MAX_RECURSION_DEPTH:
            # If we've exceeded depth, record what we have so far
            if captured_so_far:
                original_piece = self.board[start_pos]
                was_promoted = self.is_king(piece) and not self.is_king(original_piece)
                all_captures.append(Move(
                    from_pos=start_pos,
                    to_pos=current_pos,
                    captures=captured_so_far.copy(),
                    promotes=False,
                    promoted_during_capture=was_promoted
                ))
            return
        
        # Prevent exploring the same position multiple times in the same capture sequence
        # This avoids cycles and redundant exploration when multiple landing positions exist
        if current_pos in visited_positions:
            # Already visited this position in this sequence, record what we have
            if captured_so_far:
                original_piece = self.board[start_pos]
                was_promoted = self.is_king(piece) and not self.is_king(original_piece)
                all_captures.append(Move(
                    from_pos=start_pos,
                    to_pos=current_pos,
                    captures=captured_so_far.copy(),
                    promotes=False,
                    promoted_during_capture=was_promoted
                ))
            return
        
        # Mark current position as visited
        visited_positions.add(current_pos)
        
        row, col = self.pos_to_coords(current_pos)
        found_capture = False
        current_color = self.get_piece_color(piece)
        
        if self.is_king(piece):
            # Kings can jump any distance
            found_capture = self._find_king_captures(
                start_pos, current_pos, row, col, piece, current_color, 
                captured_so_far, all_captures, visited_positions, depth
            )
        else:
            # Men capture in all 4 diagonal directions (forward AND backward)
            found_capture = self._find_man_captures(
                start_pos, current_pos, row, col, piece, current_color, 
                captured_so_far, all_captures, visited_positions, depth
            )
        
        # If no further captures, record this capture sequence
        if not found_capture and captured_so_far:
            # Get original piece to check if it was promoted during capture
            original_piece = self.board[start_pos]
            was_promoted = self.is_king(piece) and not self.is_king(original_piece)
            
            all_captures.append(Move(
                from_pos=start_pos,
                to_pos=current_pos,
                captures=captured_so_far.copy(),
                promotes=False,
                promoted_during_capture=was_promoted
            ))
        
        # Remove current position from visited set when backtracking
        # This allows exploring different paths that might revisit positions
        visited_positions.remove(current_pos)
    
    def _find_man_captures(
        self,
        start_pos: int,
        current_pos: int,
        row: int,
        col: int,
        piece: int,
        current_color: int,
        captured_so_far: List[int],
        all_captures: List[Move],
        visited_positions: Set[int],
        depth: int
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
                if (piece == YELLOW and land_row == 0) or (piece == BLUE and land_row == 7):
                    new_piece = YELLOW_KING if piece == YELLOW else BLUE_KING
                
                # Continue searching from landing position
                self._find_captures_recursive(
                    start_pos, land_pos, new_piece, new_captured, all_captures,
                    visited_positions, depth + 1
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
        all_captures: List[Move],
        visited_positions: Set[int],
        depth: int
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
                # Optimize: only explore unique landing positions to avoid redundant recursion
                landing_positions = []
                for land_dist in range(dist + 1, 8):
                    land_row = row + dr * land_dist
                    land_col = col + dc * land_dist
                    
                    if not self.is_valid_pos(land_row, land_col):
                        break
                    
                    land_pos = self.coords_to_pos(land_row, land_col)
                    if self.board[land_pos] != EMPTY:
                        break  # Blocked
                    
                    # Only add if not already visited (prevents redundant exploration)
                    if land_pos not in visited_positions:
                        landing_positions.append(land_pos)
                
                # Process each unique landing position
                for land_pos in landing_positions:
                    found_capture = True
                    new_captured = captured_so_far + [enemy_pos]
                    
                    # Continue searching from landing position
                    self._find_captures_recursive(
                        start_pos, land_pos, piece, new_captured, all_captures,
                        visited_positions, depth + 1
                    )
                
                break  # Stop after first piece in this direction
        
        return found_capture
    
    def find_single_hop_captures(self, from_pos: int) -> List[Move]:
        """
        Find all single-hop captures from a position (not full sequences).
        Used for manual multi-jump gameplay.
        
        Args:
            from_pos: Starting position
            
        Returns:
            List of single-hop capture moves
        """
        piece = self.board[from_pos]
        if piece == EMPTY:
            return []
        
        color = self.get_piece_color(piece)
        if color != self.current_turn:
            return []
        
        single_hops = []
        row, col = self.pos_to_coords(from_pos)
        
        if self.is_king(piece):
            # King can jump in all 4 diagonal directions, any distance
            for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                for dist in range(1, 8):
                    enemy_row = row + dr * dist
                    enemy_col = col + dc * dist
                    
                    if not self.is_valid_pos(enemy_row, enemy_col):
                        break
                    
                    enemy_pos = self.coords_to_pos(enemy_row, enemy_col)
                    enemy_piece = self.board[enemy_pos]
                    enemy_color = self.get_piece_color(enemy_piece)
                    
                    if enemy_piece == EMPTY:
                        continue  # Empty square, keep looking
                    
                    # Found a piece
                    if enemy_color != color:
                        # Enemy piece - check landing squares beyond it
                        for land_dist in range(dist + 1, 9):
                            land_row = row + dr * land_dist
                            land_col = col + dc * land_dist
                            
                            if not self.is_valid_pos(land_row, land_col):
                                break
                            
                            land_pos = self.coords_to_pos(land_row, land_col)
                            if self.board[land_pos] != EMPTY:
                                break  # Blocked
                            
                            # Valid single-hop capture
                            single_hops.append(Move(
                                from_pos=from_pos,
                                to_pos=land_pos,
                                captures=[enemy_pos],
                                promotes=False,
                                promoted_during_capture=False
                            ))
                    
                    break  # Stop after first piece in this direction
        else:
            # Man captures in all 4 diagonal directions
            for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                enemy_row = row + dr
                enemy_col = col + dc
                land_row = row + 2 * dr
                land_col = col + 2 * dc
                
                if not self.is_valid_pos(enemy_row, enemy_col) or not self.is_valid_pos(land_row, land_col):
                    continue
                
                enemy_pos = self.coords_to_pos(enemy_row, enemy_col)
                land_pos = self.coords_to_pos(land_row, land_col)
                
                enemy_piece = self.board[enemy_pos]
                enemy_color = self.get_piece_color(enemy_piece)
                
                if (enemy_color and enemy_color != color and 
                    self.board[land_pos] == EMPTY):
                    
                    # Check if piece will promote on landing
                    will_promote = (piece == YELLOW and land_row == 0) or (piece == BLUE and land_row == 7)
                    
                    single_hops.append(Move(
                        from_pos=from_pos,
                        to_pos=land_pos,
                        captures=[enemy_pos],
                        promotes=will_promote,
                        promoted_during_capture=will_promote
                    ))
        
        return single_hops
    
    def must_continue_capturing(
        self, pos: int, captured_so_far: Optional[Sequence[int]] = None
    ) -> bool:
        """
        Check if piece at position has mandatory continuation captures.
        Used after a capture to determine if player must continue.

        Args:
            pos: Position to check
            captured_so_far: squares already captured in this sequence; they remain
                blockers under the Turkish strike rule and must be passed, or the
                continuation search will offer lines the move enumerator forbids.

        Returns:
            True if piece must continue capturing
        """
        continuation = self.get_legal_single_hop_moves(
            pending_pos=pos, captured_so_far=captured_so_far
        )
        return len(continuation) > 0
    
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
        
        # Clear the origin and every captured square *before* placing the piece.
        # A capture sequence may end on its own starting square (circular king
        # capture); writing to_pos last keeps the moving piece in that case.
        self.board[move.from_pos] = EMPTY
        for cap_pos in move.captures:
            self.board[cap_pos] = EMPTY
        self.board[move.to_pos] = piece

        # Handle promotion
        # Promote if: reached king row at end, OR promoted during multi-capture
        to_row, _ = self.pos_to_coords(move.to_pos)
        reached_king_row = (piece == YELLOW and to_row == 0) or (piece == BLUE and to_row == 7)
        
        if move.promoted_during_capture or reached_king_row:
            if piece in (YELLOW, YELLOW_KING):
                self.board[move.to_pos] = YELLOW_KING
            else:
                self.board[move.to_pos] = BLUE_KING
        
        # Switch turn
        self.current_turn = BLUE if self.current_turn == YELLOW else YELLOW
        self.move_count += 1
        
        return True
    
    def check_winner(self) -> Optional[int]:
        """
        Check if there's a winner.
        Returns YELLOW, BLUE, or None if game continues.
        """
        # Count pieces and check for legal moves
        yellow_count = 0
        blue_count = 0
        
        for piece in self.board:
            if piece in (YELLOW, YELLOW_KING):
                yellow_count += 1
            elif piece in (BLUE, BLUE_KING):
                blue_count += 1
        
        # No pieces left = loss
        if yellow_count == 0:
            return BLUE
        if blue_count == 0:
            return YELLOW
        
        # A player loses only when they have no legal move ON THEIR OWN TURN.
        # Checking the side that is not to move ends the game a ply early: the
        # player to move may well unblock them (and with captures mandatory,
        # may be forced to).
        if not self.get_legal_moves(self.current_turn):
            return BLUE if self.current_turn == YELLOW else YELLOW

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
