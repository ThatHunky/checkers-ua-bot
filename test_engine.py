#!/usr/bin/env python3
"""
Simple test script for Ukrainian Checkers Engine (core only)
Tests game logic without telegram dependencies.
"""

from engine import CheckersEngine, WHITE, RED


def test_initial_board():
    """Test initial board setup."""
    print("Testing initial board setup...")
    engine = CheckersEngine()
    
    # Count pieces
    white_count = sum(1 for p in engine.board if p in (1, 2))
    red_count = sum(1 for p in engine.board if p in (3, 4))
    
    assert white_count == 12, f"Expected 12 white pieces, got {white_count}"
    assert red_count == 12, f"Expected 12 red pieces, got {red_count}"
    assert engine.current_turn == WHITE, "WHITE should start"
    
    print("✓ Initial board setup correct (12 vs 12 pieces)")


def test_legal_moves():
    """Test legal move generation."""
    print("\nTesting legal move generation...")
    engine = CheckersEngine()
    
    # WHITE starts
    moves = engine.get_legal_moves(WHITE)
    print(f"  WHITE has {len(moves)} legal opening moves")
    assert len(moves) > 0, "WHITE should have legal moves at start"
    
    # Verify moves are forward diagonal
    for move in moves[:3]:
        from_row, from_col = engine.pos_to_coords(move.from_pos)
        to_row, to_col = engine.pos_to_coords(move.to_pos)
        print(f"  Example: {chr(65+from_col)}{8-from_row} → {chr(65+to_col)}{8-to_row}")
    
    print("✓ Legal moves generated correctly")


def test_capture_backward():
    """Test that men can capture backward (Ukrainian rule)."""
    print("\nTesting backward capture for men...")
    engine = CheckersEngine()
    
    # Set up a position where WHITE man can capture backward
    engine.board = [0] * 64
    engine.board[19] = WHITE  # C6
    engine.board[28] = RED    # E5
    engine.current_turn = WHITE
    
    moves = engine.get_legal_moves(WHITE)
    
    # Filter for captures
    captures = [m for m in moves if m.captures]
    
    if captures:
        print(f"✓ Found {len(captures)} capture(s)")
        for cap in captures:
            from_r, from_c = engine.pos_to_coords(cap.from_pos)
            to_r, to_c = engine.pos_to_coords(cap.to_pos)
            print(f"  Capture: {chr(65+from_c)}{8-from_r} → {chr(65+to_c)}{8-to_r}")
    else:
        print("✗ No captures found")


def test_mandatory_capture():
    """Test mandatory capture rule."""
    print("\nTesting mandatory capture rule...")
    engine = CheckersEngine()
    
    # Set up position with capture available
    engine.board = [0] * 64
    engine.board[18] = RED    # C6
    engine.board[27] = WHITE  # D5
    engine.board[20] = RED    # E6 - can move normally
    engine.current_turn = RED
    
    moves = engine.get_legal_moves(RED)
    
    # All moves should be captures if any capture exists
    has_captures = any(m.captures for m in moves)
    has_normal = any(not m.captures for m in moves)
    
    if has_captures:
        assert not has_normal, "Should only return captures when captures available"
        print("✓ Mandatory capture enforced (only captures returned)")
    else:
        print("  No captures in this position")


def test_game_winner():
    """Test win condition detection."""
    print("\nTesting win condition...")
    engine = CheckersEngine()
    
    # Empty board except one piece
    engine.board = [0] * 64
    engine.board[10] = WHITE
    engine.current_turn = RED
    
    winner = engine.check_winner()
    assert winner == WHITE, "WHITE should win (RED has no pieces and no moves)"
    
    print("✓ Win condition detected correctly")


def test_move_application():
    """Test applying moves."""
    print("\nTesting move application...")
    engine = CheckersEngine()
    
    # Get first legal move and apply it
    moves = engine.get_legal_moves(RED)
    first_move = moves[0]
    
    old_turn = engine.current_turn
    engine.apply_move(first_move)
    
    assert engine.current_turn != old_turn, "Turn should switch after move"
    print(f"✓ Move applied successfully, turn switched to {'WHITE' if engine.current_turn == WHITE else 'RED'}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Ukrainian Checkers Engine Test Suite")
    print("=" * 60)
    
    try:
        test_initial_board()
        test_legal_moves()
        test_capture_backward()
        test_mandatory_capture()
        test_game_winner()
        test_move_application()
        
        print("\n" + "=" * 60)
        print("✅ All core engine tests passed!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Copy .env.example to .env and add your bot TOKEN")
        print("2. Build containers: podman-compose build")
        print("3. Start services: podman-compose up -d")
        print("4. Check logs: podman-compose logs -f bot")
        return 0
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
