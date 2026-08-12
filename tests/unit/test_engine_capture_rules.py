"""
Regression tests for the core capture and win-detection rules.

These pin behaviours that previously had no collected coverage: the 30
hand-built scenarios that were meant to cover check_winner lived in a
root-level script that `testpaths = tests` excluded, so nothing enforced them.

Each board below is stated explicitly and the expectation is derived from the
draughts rule, not from what the engine happens to return.
"""

import pytest

from engine import (
    CheckersEngine,
    EMPTY,
    YELLOW,
    YELLOW_KING,
    BLUE,
    BLUE_KING,
)


def _blank_engine(current_turn: int) -> CheckersEngine:
    engine = CheckersEngine()
    engine.board = [EMPTY] * 64
    engine.current_turn = current_turn
    return engine


@pytest.mark.unit
class TestCheckWinnerRespectsTurn:
    """A player loses only when blocked ON THEIR OWN TURN."""

    def test_blocked_opponent_does_not_end_the_game(self):
        # BLUE man on 1, YELLOW man on 17, YELLOW to move.
        # After YELLOW 17->8 it is BLUE's turn; YELLOW then has no move, but it
        # is not YELLOW's turn, and BLUE's only legal move (1->10) frees them.
        engine = _blank_engine(YELLOW)
        engine.board[1] = BLUE
        engine.board[17] = YELLOW

        move = next(m for m in engine.get_legal_moves(YELLOW) if m.to_pos == 8)
        engine.apply_move(move)

        assert engine.current_turn == BLUE
        assert engine.get_legal_moves(YELLOW) == []
        assert len(engine.get_legal_moves(BLUE)) == 1
        assert engine.check_winner() is None, (
            "YELLOW is blocked but it is BLUE's turn; BLUE's forced move unblocks them"
        )

    def test_player_to_move_with_no_moves_loses(self):
        # Mirror of the above: the side to move is the one that is blocked.
        engine = _blank_engine(YELLOW)
        engine.board[0] = YELLOW
        engine.board[1] = BLUE
        engine.board[8] = BLUE

        assert engine.get_legal_moves(YELLOW) == []
        assert engine.check_winner() == BLUE

    def test_wipeout_still_wins_regardless_of_turn(self):
        engine = _blank_engine(YELLOW)
        engine.board[20] = BLUE
        assert engine.check_winner() == BLUE

        engine2 = _blank_engine(BLUE)
        engine2.board[20] = YELLOW
        assert engine2.check_winner() == YELLOW


@pytest.mark.unit
class TestTurkishStrikeRule:
    """Captured pieces stay on the board as blockers until the move ends."""

    def test_king_may_not_fly_through_a_square_it_just_captured(self):
        # BLUE king on 19, BLUE man on 61; YELLOW men on 28, 10, 54.
        # Flying through square 28 after capturing on it would fabricate a
        # 2-capture line and, captures being mandatory, hide the legal
        # 1-capture 61->47.
        engine = _blank_engine(BLUE)
        engine.board[19] = BLUE_KING
        engine.board[61] = BLUE
        for pos in (28, 10, 54):
            engine.board[pos] = YELLOW

        moves = engine.get_legal_moves(BLUE)
        assert moves, "BLUE has captures available"
        assert max(len(m.captures) for m in moves) == 1, (
            "no 2-capture line exists once captured pieces block"
        )

    def test_mandatory_capture_does_not_hide_a_legal_move(self):
        engine = _blank_engine(BLUE)
        engine.board[19] = BLUE_KING
        engine.board[61] = BLUE
        for pos in (28, 10, 54):
            engine.board[pos] = YELLOW

        hops = engine.get_legal_single_hop_moves()
        assert any(m.from_pos == 61 and m.to_pos == 47 for m in hops), (
            "the man on 61 has an equally-scoring capture and must be offered"
        )

    def test_captured_sentinel_never_reaches_a_real_board(self):
        engine = _blank_engine(BLUE)
        engine.board[19] = BLUE_KING
        engine.board[61] = BLUE
        for pos in (28, 10, 54):
            engine.board[pos] = YELLOW

        engine.apply_move(engine.get_legal_moves(BLUE)[0])
        assert all(square >= EMPTY for square in engine.board)


@pytest.mark.unit
class TestInteractiveWalkMatchesEnumerator:
    """
    apply_move clears captured squares to EMPTY, so the hop-by-hop path the UI walks
    has to be handed the already-captured squares explicitly or it plays under the
    pre-sentinel rules and diverges from get_legal_moves.
    """

    @staticmethod
    def _walk(board_spec: dict, turn: int) -> tuple:
        """Return (captures the enumerator declares, captures the UI path actually walks)."""
        engine = _blank_engine(turn)
        for pos, value in board_spec.items():
            engine.board[pos] = value

        declared = max(
            (len(m.captures) for m in engine.get_legal_moves(turn)), default=0
        )

        captured_so_far: list = []
        walked = 0
        hops = engine.get_legal_single_hop_moves()
        while hops and hops[0].captures:
            hop = hops[0]
            engine.apply_move(hop)
            engine.current_turn = turn  # move_callback restores the turn to continue
            captured_so_far += list(hop.captures)
            walked += len(hop.captures)
            if not engine.must_continue_capturing(
                hop.to_pos, captured_so_far=captured_so_far
            ):
                break
            hops = engine.get_legal_single_hop_moves(
                pending_pos=hop.to_pos, captured_so_far=captured_so_far
            )
        return declared, walked

    @pytest.mark.parametrize(
        "board_spec",
        [
            # King on 35 may take 17 but must not fly back through it to reach 53.
            {7: BLUE_KING, 17: BLUE_KING, 35: YELLOW_KING, 53: BLUE},
            {14: BLUE_KING, 40: BLUE_KING, 44: BLUE_KING, 49: BLUE, 53: YELLOW_KING},
            {36: YELLOW_KING, 27: BLUE, 45: BLUE},
        ],
    )
    def test_walked_sequence_never_exceeds_the_declared_maximum(self, board_spec):
        declared, walked = self._walk(board_spec, YELLOW)
        assert walked == declared, (
            f"UI walked {walked} captures but get_legal_moves declared {declared}"
        )


@pytest.mark.unit
class TestApplyMovePreservesMovingPiece:
    def test_multi_capture_keeps_the_capturing_king(self):
        engine = _blank_engine(YELLOW)
        engine.board[26] = YELLOW_KING
        engine.board[24] = YELLOW_KING
        engine.board[8] = YELLOW
        engine.board[56] = YELLOW
        for pos in (3, 35, 30, 51, 49, 33):
            engine.board[pos] = BLUE

        before = sum(1 for p in engine.board if p in (YELLOW, YELLOW_KING))
        move = max(engine.get_legal_moves(YELLOW), key=lambda m: len(m.captures))
        assert engine.apply_move(move) is True

        after = sum(1 for p in engine.board if p in (YELLOW, YELLOW_KING))
        assert engine.board[move.to_pos] != EMPTY, "the capturing piece vanished"
        assert after == before, "capturing must not cost the mover a piece"

    def test_sequence_ending_on_its_own_origin_keeps_the_piece(self):
        # Applying a Move whose to_pos == from_pos must not clear the square.
        engine = _blank_engine(YELLOW)
        engine.board[26] = YELLOW_KING
        engine.board[35] = BLUE

        from engine import Move

        engine.apply_move(Move(from_pos=26, to_pos=26, captures=[35]))
        assert engine.board[26] == YELLOW_KING
        assert engine.board[35] == EMPTY
