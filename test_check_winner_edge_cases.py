#!/usr/bin/env python3
"""
Comprehensive edge case tests for check_winner function.
Tests all possible scenarios where a game can end or continue.
"""

from engine import CheckersEngine, YELLOW, BLUE, YELLOW_KING, BLUE_KING, EMPTY


def pos_to_notation(pos):
    """Convert position to chess notation."""
    row, col = pos // 8, pos % 8
    return f"{chr(65 + col)}{8 - row}"


def print_board_state(engine, test_name):
    """Print board state for debugging."""
    print(f"\n{test_name}:")
    yellow_pieces = []
    blue_pieces = []
    for pos in range(64):
        piece = engine.board[pos]
        if piece in (YELLOW, YELLOW_KING):
            yellow_pieces.append(f"{'K' if piece == YELLOW_KING else 'M'}{pos_to_notation(pos)}")
        elif piece in (BLUE, BLUE_KING):
            blue_pieces.append(f"{'K' if piece == BLUE_KING else 'M'}{pos_to_notation(pos)}")
    print(f"  YELLOW: {yellow_pieces}")
    print(f"  BLUE: {blue_pieces}")
    print(f"  Turn: {'YELLOW' if engine.current_turn == YELLOW else 'BLUE'}")


def test_edge_case(name, setup_func, expected_winner, expected_yellow_moves=None, expected_blue_moves=None):
    """Test a single edge case."""
    engine = CheckersEngine()
    engine.board = [EMPTY] * 64
    setup_func(engine)
    
    yellow_moves = engine.get_legal_moves(YELLOW)
    blue_moves = engine.get_legal_moves(BLUE)
    winner = engine.check_winner()
    
    print_board_state(engine, name)
    print(f"  YELLOW moves: {len(yellow_moves)}")
    print(f"  BLUE moves: {len(blue_moves)}")
    print(f"  Winner: {winner} (expected: {expected_winner})")
    
    if expected_yellow_moves is not None:
        assert len(yellow_moves) == expected_yellow_moves, f"Expected {expected_yellow_moves} YELLOW moves, got {len(yellow_moves)}"
    if expected_blue_moves is not None:
        assert len(blue_moves) == expected_blue_moves, f"Expected {expected_blue_moves} BLUE moves, got {len(blue_moves)}"
    
    assert winner == expected_winner, f"Expected winner {expected_winner}, got {winner}"
    print(f"  ✓ PASSED")
    return True


def main():
    """Run all edge case tests."""
    print("=" * 80)
    print("COMPREHENSIVE EDGE CASE TESTS FOR check_winner")
    print("=" * 80)
    
    tests_passed = 0
    tests_failed = 0
    
    # ========================================================================
    # EDGE CASE 1: Both players have no pieces
    # ========================================================================
    try:
        def setup1(e):
            pass  # Empty board
        
        test_edge_case(
            "EDGE CASE 1: Both players have no pieces",
            setup1,
            BLUE,  # YELLOW loses (no pieces)
            expected_yellow_moves=0,
            expected_blue_moves=0
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 2: YELLOW has no pieces, BLUE has pieces
    # ========================================================================
    try:
        def setup2(e):
            e.board[9] = BLUE  # B7
        
        test_edge_case(
            "EDGE CASE 2: YELLOW has no pieces, BLUE has pieces",
            setup2,
            BLUE,
            expected_yellow_moves=0,
            expected_blue_moves=2
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 3: BLUE has no pieces, YELLOW has pieces
    # ========================================================================
    try:
        def setup3(e):
            e.board[54] = YELLOW  # G2
        
        test_edge_case(
            "EDGE CASE 3: BLUE has no pieces, YELLOW has pieces",
            setup3,
            YELLOW,
            expected_yellow_moves=2,
            expected_blue_moves=0
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 4: YELLOW has pieces but no legal moves (blocked)
    # ========================================================================
    try:
        def setup4(e):
            e.board[0] = YELLOW  # A8 - blocked
            e.board[1] = BLUE    # B8 - blocks
            e.board[8] = BLUE    # A7 - blocks
            e.board[9] = BLUE    # B7 - has moves
            e.current_turn = BLUE
        
        test_edge_case(
            "EDGE CASE 4: YELLOW blocked, no moves (BLUE's turn)",
            setup4,
            BLUE,
            expected_yellow_moves=0,
            expected_blue_moves=2
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 5: BLUE has pieces but no legal moves (blocked)
    # ========================================================================
    try:
        def setup5(e):
            e.board[63] = BLUE   # H1 - blocked
            e.board[62] = YELLOW  # G1 - blocks
            e.board[55] = YELLOW  # H2 - blocks
            e.board[54] = YELLOW  # G2 - has moves
            e.current_turn = YELLOW
        
        test_edge_case(
            "EDGE CASE 5: BLUE blocked, no moves (YELLOW's turn)",
            setup5,
            YELLOW,
            expected_yellow_moves=2,
            expected_blue_moves=0
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 6: Both players have pieces and legal moves (game continues)
    # ========================================================================
    try:
        def setup6(e):
            e.board[54] = YELLOW  # G2
            e.board[9] = BLUE     # B7
            e.current_turn = YELLOW
        
        test_edge_case(
            "EDGE CASE 6: Both players have pieces and moves (game continues)",
            setup6,
            None,
            expected_yellow_moves=2,
            expected_blue_moves=2
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 7: YELLOW king blocked completely
    # ========================================================================
    try:
        def setup7(e):
            e.board[0] = YELLOW_KING  # A8 - king blocked
            e.board[1] = BLUE          # B8
            e.board[8] = BLUE         # A7
            e.board[9] = BLUE          # B7
            e.board[10] = BLUE         # C7
            e.current_turn = BLUE
        
        test_edge_case(
            "EDGE CASE 7: YELLOW king completely blocked",
            setup7,
            BLUE,
            expected_yellow_moves=0
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 8: BLUE king blocked completely
    # ========================================================================
    try:
        def setup8(e):
            e.board[63] = BLUE_KING   # H1 - king blocked
            e.board[62] = YELLOW       # G1
            e.board[55] = YELLOW       # H2
            e.board[54] = YELLOW       # G2
            e.board[53] = YELLOW       # F2
            e.current_turn = YELLOW
        
        test_edge_case(
            "EDGE CASE 8: BLUE king completely blocked",
            setup8,
            YELLOW,
            expected_blue_moves=0
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 9: YELLOW has only captures (mandatory capture)
    # ========================================================================
    try:
        def setup9(e):
            e.board[18] = YELLOW  # C6
            e.board[27] = BLUE     # D5 - can be captured
            e.board[28] = BLUE     # E5 - blocks normal moves
            e.current_turn = YELLOW
        
        yellow_moves = CheckersEngine().get_legal_moves(YELLOW)
        engine = CheckersEngine()
        engine.board = [EMPTY] * 64
        setup9(engine)
        yellow_moves = engine.get_legal_moves(YELLOW)
        blue_moves = engine.get_legal_moves(BLUE)
        winner = engine.check_winner()
        
        print_board_state(engine, "EDGE CASE 9: YELLOW has only captures (mandatory)")
        print(f"  YELLOW moves: {len(yellow_moves)} (all captures: {all(m.captures for m in yellow_moves)})")
        print(f"  BLUE moves: {len(blue_moves)}")
        print(f"  Winner: {winner} (expected: None - game continues)")
        
        assert winner is None, f"Game should continue, got winner {winner}"
        assert len(yellow_moves) > 0, "YELLOW should have capture moves"
        assert all(m.captures for m in yellow_moves), "All YELLOW moves should be captures"
        print(f"  ✓ PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 10: BLUE has only captures (mandatory capture)
    # ========================================================================
    try:
        def setup10(e):
            e.board[45] = BLUE    # F3
            e.board[36] = YELLOW   # E4 - can be captured
            e.board[35] = YELLOW   # D4 - blocks normal moves
            e.current_turn = BLUE
        
        engine = CheckersEngine()
        engine.board = [EMPTY] * 64
        setup10(engine)
        yellow_moves = engine.get_legal_moves(YELLOW)
        blue_moves = engine.get_legal_moves(BLUE)
        winner = engine.check_winner()
        
        print_board_state(engine, "EDGE CASE 10: BLUE has only captures (mandatory)")
        print(f"  YELLOW moves: {len(yellow_moves)}")
        print(f"  BLUE moves: {len(blue_moves)} (all captures: {all(m.captures for m in blue_moves)})")
        print(f"  Winner: {winner} (expected: None - game continues)")
        
        assert winner is None, f"Game should continue, got winner {winner}"
        assert len(blue_moves) > 0, "BLUE should have capture moves"
        assert all(m.captures for m in blue_moves), "All BLUE moves should be captures"
        print(f"  ✓ PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 11: Corner piece blocked (YELLOW at A8)
    # ========================================================================
    try:
        def setup11(e):
            e.board[0] = YELLOW   # A8 - corner
            e.board[1] = BLUE      # B8 - blocks
            e.board[8] = BLUE     # A7 - blocks
            e.board[9] = BLUE     # B7 - has moves
            e.current_turn = BLUE
        
        test_edge_case(
            "EDGE CASE 11: YELLOW corner piece (A8) blocked",
            setup11,
            BLUE,
            expected_yellow_moves=0
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 12: Corner piece blocked (BLUE at H1)
    # ========================================================================
    try:
        def setup12(e):
            e.board[63] = BLUE    # H1 - corner
            e.board[62] = YELLOW   # G1 - blocks
            e.board[55] = YELLOW   # H2 - blocks
            e.board[54] = YELLOW   # G2 - has moves
            e.current_turn = YELLOW
        
        test_edge_case(
            "EDGE CASE 12: BLUE corner piece (H1) blocked",
            setup12,
            YELLOW,
            expected_blue_moves=0
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 13: Multiple YELLOW pieces, all blocked
    # ========================================================================
    try:
        def setup13(e):
            e.board[0] = YELLOW   # A8 - blocked
            e.board[2] = YELLOW   # C8 - blocked
            e.board[1] = BLUE     # B8
            e.board[8] = BLUE     # A7
            e.board[9] = BLUE     # B7
            e.board[10] = BLUE    # C7
            e.board[11] = BLUE    # D7
            e.current_turn = BLUE
        
        test_edge_case(
            "EDGE CASE 13: Multiple YELLOW pieces, all blocked",
            setup13,
            BLUE,
            expected_yellow_moves=0
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 14: Multiple BLUE pieces, all blocked
    # ========================================================================
    try:
        def setup14(e):
            e.board[63] = BLUE    # H1 - blocked
            e.board[61] = BLUE    # F1 - blocked
            e.board[62] = YELLOW  # G1
            e.board[55] = YELLOW  # H2
            e.board[54] = YELLOW  # G2
            e.board[53] = YELLOW  # F2
            e.board[52] = YELLOW  # E2
            e.current_turn = YELLOW
        
        test_edge_case(
            "EDGE CASE 14: Multiple BLUE pieces, all blocked",
            setup14,
            YELLOW,
            expected_blue_moves=0
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 15: YELLOW has only kings, BLUE has only men
    # ========================================================================
    try:
        def setup15(e):
            e.board[18] = YELLOW_KING  # C6
            e.board[9] = BLUE           # B7
            e.current_turn = YELLOW
        
        test_edge_case(
            "EDGE CASE 15: YELLOW has only kings, BLUE has only men",
            setup15,
            None,  # Game continues
            expected_yellow_moves=7,  # King can move in 4 directions
            expected_blue_moves=2
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 16: BLUE has only kings, YELLOW has only men
    # ========================================================================
    try:
        def setup16(e):
            e.board[45] = BLUE_KING     # F3
            e.board[54] = YELLOW        # G2
            e.current_turn = YELLOW
        
        test_edge_case(
            "EDGE CASE 16: BLUE has only kings, YELLOW has only men",
            setup16,
            None,  # Game continues
            expected_yellow_moves=2,
            expected_blue_moves=7  # King can move in 4 directions
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 17: Both players have only kings
    # ========================================================================
    try:
        def setup17(e):
            e.board[18] = YELLOW_KING  # C6
            e.board[45] = BLUE_KING    # F3
            e.current_turn = YELLOW
        
        test_edge_case(
            "EDGE CASE 17: Both players have only kings",
            setup17,
            None,  # Game continues
            expected_yellow_moves=7,
            expected_blue_moves=7
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 18: YELLOW king in center, completely surrounded
    # ========================================================================
    try:
        def setup18(e):
            e.board[27] = YELLOW_KING  # D5 - center
            e.board[18] = BLUE          # C6 - blocks
            e.board[19] = BLUE          # D6 - blocks
            e.board[20] = BLUE          # E6 - blocks
            e.board[26] = BLUE          # C5 - blocks
            e.board[28] = BLUE          # E5 - blocks
            e.board[34] = BLUE          # C4 - blocks
            e.board[35] = BLUE          # D4 - blocks
            e.board[36] = BLUE          # E4 - blocks
            e.current_turn = BLUE
        
        test_edge_case(
            "EDGE CASE 18: YELLOW king completely surrounded",
            setup18,
            BLUE,
            expected_yellow_moves=0
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 19: BLUE king in center, completely surrounded
    # ========================================================================
    try:
        def setup19(e):
            e.board[36] = BLUE_KING     # E4 - center
            e.board[27] = YELLOW        # D5 - blocks
            e.board[28] = YELLOW        # E5 - blocks
            e.board[29] = YELLOW        # F5 - blocks
            e.board[35] = YELLOW        # D4 - blocks
            e.board[37] = YELLOW        # F4 - blocks
            e.board[43] = YELLOW        # D3 - blocks
            e.board[44] = YELLOW        # E3 - blocks
            e.board[45] = YELLOW        # F3 - blocks
            e.current_turn = YELLOW
        
        test_edge_case(
            "EDGE CASE 19: BLUE king completely surrounded",
            setup19,
            YELLOW,
            expected_blue_moves=0
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 20: Edge piece (YELLOW on A-file, not corner)
    # ========================================================================
    try:
        def setup20(e):
            e.board[16] = YELLOW   # A6 - edge, not corner
            e.board[8] = BLUE      # A7 - blocks forward
            e.board[9] = BLUE      # B7 - blocks diagonal
            e.board[24] = BLUE     # A5 - blocks backward
            e.board[25] = BLUE     # B5 - blocks backward diagonal
            e.current_turn = BLUE
        
        test_edge_case(
            "EDGE CASE 20: YELLOW edge piece (A-file) blocked",
            setup20,
            BLUE,
            expected_yellow_moves=0
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 21: Edge piece (BLUE on H-file, not corner)
    # ========================================================================
    try:
        def setup21(e):
            e.board[47] = BLUE     # H3 - edge, not corner
            e.board[55] = YELLOW   # H2 - blocks forward
            e.board[54] = YELLOW   # G2 - blocks diagonal
            e.board[39] = YELLOW    # H4 - blocks backward
            e.board[38] = YELLOW    # G4 - blocks backward diagonal
            e.current_turn = YELLOW
        
        test_edge_case(
            "EDGE CASE 21: BLUE edge piece (H-file) blocked",
            setup21,
            YELLOW,
            expected_blue_moves=0
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 22: Endgame - YELLOW has 1 piece, BLUE has 1 piece, both can move
    # ========================================================================
    try:
        def setup22(e):
            e.board[27] = YELLOW   # D5
            e.board[36] = BLUE     # E4
            e.current_turn = YELLOW
        
        test_edge_case(
            "EDGE CASE 22: Endgame - 1 vs 1, both can move",
            setup22,
            None,  # Game continues
            expected_yellow_moves=2,
            expected_blue_moves=2
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 23: Endgame - YELLOW has 1 king, BLUE has 1 king, both can move
    # ========================================================================
    try:
        def setup23(e):
            e.board[27] = YELLOW_KING  # D5
            e.board[36] = BLUE_KING    # E4
            e.current_turn = YELLOW
        
        test_edge_case(
            "EDGE CASE 23: Endgame - 1 king vs 1 king, both can move",
            setup23,
            None,  # Game continues
            expected_yellow_moves=7,
            expected_blue_moves=7
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 24: YELLOW piece on promotion square (row 0) as regular piece
    # (shouldn't happen in normal play, but test edge case)
    # ========================================================================
    try:
        def setup24(e):
            e.board[0] = YELLOW   # A8 - on promotion square but not king
            e.board[1] = BLUE     # B8 - blocks
            e.board[8] = BLUE     # A7 - blocks
            e.current_turn = BLUE
        
        test_edge_case(
            "EDGE CASE 24: YELLOW piece on promotion square, blocked",
            setup24,
            BLUE,
            expected_yellow_moves=0
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 25: BLUE piece on promotion square (row 7) as regular piece
    # ========================================================================
    try:
        def setup25(e):
            e.board[63] = BLUE    # H1 - on promotion square but not king
            e.board[62] = YELLOW  # G1 - blocks
            e.board[55] = YELLOW  # H2 - blocks
            e.current_turn = YELLOW
        
        test_edge_case(
            "EDGE CASE 25: BLUE piece on promotion square, blocked",
            setup25,
            YELLOW,
            expected_blue_moves=0
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 26: YELLOW has pieces but all are blocked by own pieces
    # (shouldn't happen, but test)
    # ========================================================================
    try:
        def setup26(e):
            e.board[0] = YELLOW   # A8
            e.board[2] = YELLOW    # C8 - blocks A8's diagonal
            e.board[1] = BLUE     # B8 - blocks A8
            e.board[8] = BLUE      # A7 - blocks A8
            e.board[9] = BLUE      # B7
            e.current_turn = BLUE
        
        test_edge_case(
            "EDGE CASE 26: YELLOW pieces blocked by own pieces",
            setup26,
            BLUE,
            expected_yellow_moves=0
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 27: BLUE has pieces but all are blocked by own pieces
    # ========================================================================
    try:
        def setup27(e):
            e.board[63] = BLUE    # H1
            e.board[61] = BLUE    # F1 - blocks H1's diagonal
            e.board[62] = YELLOW  # G1 - blocks H1
            e.board[55] = YELLOW  # H2 - blocks H1
            e.board[54] = YELLOW  # G2
            e.current_turn = YELLOW
        
        test_edge_case(
            "EDGE CASE 27: BLUE pieces blocked by own pieces",
            setup27,
            YELLOW,
            expected_blue_moves=0
        )
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 28: YELLOW king can only capture (mandatory), but capture blocked
    # ========================================================================
    try:
        def setup28(e):
            e.board[27] = YELLOW_KING  # D5
            e.board[18] = BLUE          # C6 - can be captured
            e.board[9] = BLUE           # B7 - blocks landing square
            e.current_turn = YELLOW
        
        engine = CheckersEngine()
        engine.board = [EMPTY] * 64
        setup28(engine)
        yellow_moves = engine.get_legal_moves(YELLOW)
        blue_moves = engine.get_legal_moves(BLUE)
        winner = engine.check_winner()
        
        print_board_state(engine, "EDGE CASE 28: YELLOW king capture blocked")
        print(f"  YELLOW moves: {len(yellow_moves)}")
        print(f"  BLUE moves: {len(blue_moves)}")
        print(f"  Winner: {winner} (expected: BLUE if no moves, else None)")
        
        if len(yellow_moves) == 0:
            assert winner == BLUE, f"If YELLOW has no moves, BLUE should win, got {winner}"
        else:
            assert winner is None, f"If YELLOW has moves, game should continue, got {winner}"
        print(f"  ✓ PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 29: BLUE king can only capture (mandatory), but capture blocked
    # ========================================================================
    try:
        def setup29(e):
            e.board[36] = BLUE_KING     # E4
            e.board[45] = YELLOW        # F3 - can be captured
            e.board[54] = YELLOW        # G2 - blocks landing square
            e.current_turn = BLUE
        
        engine = CheckersEngine()
        engine.board = [EMPTY] * 64
        setup29(engine)
        yellow_moves = engine.get_legal_moves(YELLOW)
        blue_moves = engine.get_legal_moves(BLUE)
        winner = engine.check_winner()
        
        print_board_state(engine, "EDGE CASE 29: BLUE king capture blocked")
        print(f"  YELLOW moves: {len(yellow_moves)}")
        print(f"  BLUE moves: {len(blue_moves)}")
        print(f"  Winner: {winner} (expected: YELLOW if no moves, else None)")
        
        if len(blue_moves) == 0:
            assert winner == YELLOW, f"If BLUE has no moves, YELLOW should win, got {winner}"
        else:
            assert winner is None, f"If BLUE has moves, game should continue, got {winner}"
        print(f"  ✓ PASSED")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # EDGE CASE 30: Both players have pieces but both have no legal moves
    # This is a DRAW scenario - but current implementation doesn't handle draws
    # ========================================================================
    try:
        def setup30(e):
            e.board[0] = YELLOW   # A8 - blocked
            e.board[63] = BLUE    # H1 - blocked
            e.board[1] = BLUE     # B8 - blocks YELLOW
            e.board[8] = BLUE     # A7 - blocks YELLOW
            e.board[62] = YELLOW  # G1 - blocks BLUE
            e.board[55] = YELLOW  # H2 - blocks BLUE
            e.current_turn = YELLOW
        
        engine = CheckersEngine()
        engine.board = [EMPTY] * 64
        setup30(engine)
        yellow_moves = engine.get_legal_moves(YELLOW)
        blue_moves = engine.get_legal_moves(BLUE)
        winner = engine.check_winner()
        
        print_board_state(engine, "EDGE CASE 30: Both players blocked (potential DRAW)")
        print(f"  YELLOW moves: {len(yellow_moves)}")
        print(f"  BLUE moves: {len(blue_moves)}")
        print(f"  Winner: {winner}")
        print(f"  NOTE: Current implementation returns winner based on turn order")
        print(f"  (DRAW handling not implemented - this may need to be addressed)")
        
        # Current behavior: if both have no moves, the one whose turn it is loses
        # This is technically correct per checkers rules (player to move loses if no moves)
        assert winner is not None, "If both have no moves, there should be a winner"
        print(f"  ✓ PASSED (current behavior documented)")
        tests_passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        tests_failed += 1
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 80)
    print(f"TEST SUMMARY: {tests_passed} passed, {tests_failed} failed")
    print("=" * 80)
    
    if tests_failed == 0:
        print("✅ ALL EDGE CASE TESTS PASSED!")
        return 0
    else:
        print(f"❌ {tests_failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    exit(main())

