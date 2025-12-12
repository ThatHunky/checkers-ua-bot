"""
Telegram bot handlers for Ukrainian Checkers game.
"""

from datetime import datetime
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from engine import CheckersEngine, WHITE, RED, Move
from repository import GameRepository
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
                elif piece == 1:  # White man
                    row_str += locales.PIECE_WHITE
                elif piece == 2:  # White king
                    row_str += locales.PIECE_WHITE_KING
                elif piece == 3:  # Red man
                    row_str += locales.PIECE_RED
                elif piece == 4:  # Red king
                    row_str += locales.PIECE_RED_KING
                
                row_str += " "
            
            lines.append(row_str)
        
        return "\n".join(lines)
    
    @staticmethod
    def create_move_keyboard(engine: CheckersEngine, selected_pos: Optional[int] = None) -> InlineKeyboardMarkup:
        """
        Create inline keyboard for piece selection and moves.
        
        If selected_pos is None: show all pieces of current player
        If selected_pos is set: show legal moves from that position
        """
        buttons = []
        
        if selected_pos is None:
            # Show all pieces that can move
            legal_moves = engine.get_legal_moves(engine.current_turn)
            movable_positions = set(move.from_pos for move in legal_moves)
            
            row_buttons = []
            for pos in sorted(movable_positions):
                row, col = engine.pos_to_coords(pos)
                label = f"{chr(65+col)}{8-row}"  # e.g., "A3"
                row_buttons.append(InlineKeyboardButton(label, callback_data=f"select_{pos}"))
                
                if len(row_buttons) == 4:  # 4 buttons per row
                    buttons.append(row_buttons)
                    row_buttons = []
            
            if row_buttons:
                buttons.append(row_buttons)
        else:
            # Show legal moves from selected position
            legal_moves = [m for m in engine.get_legal_moves(engine.current_turn) if m.from_pos == selected_pos]
            
            row_buttons = []
            for move in legal_moves:
                to_row, to_col = engine.pos_to_coords(move.to_pos)
                label = f"→ {chr(65+to_col)}{8-to_row}"
                row_buttons.append(InlineKeyboardButton(label, callback_data=f"move_{selected_pos}_{move.to_pos}"))
                
                if len(row_buttons) == 4:
                    buttons.append(row_buttons)
                    row_buttons = []
            
            if row_buttons:
                buttons.append(row_buttons)
            
            # Add back button
            buttons.append([InlineKeyboardButton("« Назад", callback_data="back")])
        
        # Add forfeit button
        buttons.append([InlineKeyboardButton(locales.BTN_FORFEIT, callback_data="forfeit")])
        
        return InlineKeyboardMarkup(buttons)


class GameHandlers:
    """Telegram bot command and callback handlers."""
    
    def __init__(self, repository: GameRepository, rating_system=None):
        self.repo = repository
        self.rating_system = rating_system
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /checkersplay command - create a new game challenge."""
        user = update.effective_user
        chat = update.effective_chat
        
        # Send welcome message
        await update.message.reply_text(locales.WELCOME)
        
        # Create challenge message
        challenge_text = locales.CHALLENGE.format(opponent=user.mention_html())
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(locales.JOIN_BTN, callback_data="join")
        ]])
        
        message = await update.message.reply_html(challenge_text, reply_markup=keyboard)
        
        # Store challenger info temporarily
        context.chat_data[f"challenge_{message.message_id}"] = {
            "red_player_id": user.id,
            "red_player_name": user.first_name
        }
    
    async def join_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle join button - start the game."""
        query = update.callback_query
        await query.answer()
        
        user = query.from_user
        chat = query.message.chat
        message_id = query.message.message_id
        
        # Get challenge info
        challenge_key = f"challenge_{message_id}"
        challenge_info = context.chat_data.get(challenge_key)
        
        if not challenge_info:
            await query.edit_message_text(locales.ERROR_NO_GAME)
            return
        
        # Don't allow challenger to play against themselves
        if user.id == challenge_info["red_player_id"]:
            await query.answer(locales.ERROR_ALREADY_STARTED, show_alert=True)
            return
        
        # Initialize game
        engine = CheckersEngine()
        game_state = {
            "board": engine.board,
            "current_turn": engine.current_turn,
            "red_player_id": challenge_info["red_player_id"],
            "red_player_name": challenge_info["red_player_name"],
            "white_player_id": user.id,
            "white_player_name": user.first_name,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Save to Redis
        self.repo.save_game(chat.id, message_id, game_state)
        
        # Clean up challenge data
        del context.chat_data[challenge_key]
        
        # Show game board
        await self._update_game_message(query.message, engine, game_state)
    
    async def select_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle piece selection."""
        query = update.callback_query
        await query.answer()
        
        # Parse callback data
        _, pos_str = query.data.split("_")
        selected_pos = int(pos_str)
        
        # Get game state
        chat_id = query.message.chat.id
        message_id = query.message.message_id
        game_state = self.repo.get_game(chat_id, message_id)
        
        if not game_state:
            await query.edit_message_text(locales.ERROR_NO_GAME)
            return
        
        # Verify it's the player's turn
        user_id = query.from_user.id
        current_turn = game_state["current_turn"]
        
        if current_turn == RED and user_id != game_state["red_player_id"]:
            await query.answer(locales.ERROR_NOT_YOUR_TURN, show_alert=True)
            return
        
        if current_turn == WHITE and user_id != game_state["white_player_id"]:
            await query.answer(locales.ERROR_NOT_YOUR_TURN, show_alert=True)
            return
        
        # Load engine state
        engine = CheckersEngine()
        engine.set_board_state({
            "board": game_state["board"],
            "current_turn": game_state["current_turn"]
        })
        
        # Show available moves
        board_text = BoardRenderer.render(engine.board)
        turn_msg = self._get_turn_message(game_state)
        
        keyboard = BoardRenderer.create_move_keyboard(engine, selected_pos)
        
        await query.edit_message_text(
            f"{board_text}\n\n{turn_msg}\n\n✅ Обрано: позиція {selected_pos}",
            reply_markup=keyboard
        )
    
    async def move_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle move execution."""
        query = update.callback_query
        await query.answer()
        
        # Parse callback data: move_from_to
        _, from_str, to_str = query.data.split("_")
        from_pos = int(from_str)
        to_pos = int(to_str)
        
        # Get game state
        chat_id = query.message.chat.id
        message_id = query.message.message_id
        game_state = self.repo.get_game(chat_id, message_id)
        
        if not game_state:
            await query.edit_message_text(locales.ERROR_NO_GAME)
            return
        
        # Load engine state
        engine = CheckersEngine()
        engine.set_board_state({
            "board": game_state["board"],
            "current_turn": game_state["current_turn"]
        })
        
        # Find and apply the move
        legal_moves = engine.get_legal_moves(engine.current_turn)
        move_to_apply = None
        
        for move in legal_moves:
            if move.from_pos == from_pos and move.to_pos == to_pos:
                move_to_apply = move
                break
        
        if not move_to_apply:
            await query.answer(locales.ERROR_INVALID_MOVE, show_alert=True)
            return
        
        # Apply move
        engine.apply_move(move_to_apply)
        
        # Check for winner
        winner = engine.check_winner()
        
        if winner:
            # Game over
            winner_id = game_state["red_player_id"] if winner == RED else game_state["white_player_id"]
            winner_name = game_state["red_player_name"] if winner == RED else game_state["white_player_name"]
            loser_id = game_state["white_player_id"] if winner == RED else game_state["red_player_id"]
            loser_name = game_state["white_player_name"] if winner == RED else game_state["red_player_name"]
            
            board_text = BoardRenderer.render(engine.board)
            
            # Record rating changes if rating system available
            if self.rating_system:
                winner_data, loser_data = await self.rating_system.record_game(
                    winner_id, winner_name, loser_id, loser_name
                )
                
                win_msg = locales.WINNER_WITH_RATING.format(
                    name=winner_name,
                    winner_name=winner_name,
                    winner_rating=winner_data["rating"],
                    winner_change=winner_data["rating_change"],
                    loser_name=loser_name,
                    loser_rating=loser_data["rating"],
                    loser_change=loser_data["rating_change"]
                )
            else:
                win_msg = locales.WINNER.format(name=winner_name)
            
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(locales.BTN_NEW_GAME, callback_data="new_game")
            ]])
            
            await query.edit_message_text(
                f"{board_text}\n\n{win_msg}",
                reply_markup=keyboard
            )
            
            # Delete game from Redis
            self.repo.delete_game(chat_id, message_id)
        else:
            # Update game state
            game_state["board"] = engine.board
            game_state["current_turn"] = engine.current_turn
            self.repo.save_game(chat_id, message_id, game_state)
            
            # Show updated board
            await self._update_game_message(query.message, engine, game_state)
    
    async def back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle back button - return to piece selection."""
        query = update.callback_query
        await query.answer()
        
        # Get game state
        chat_id = query.message.chat.id
        message_id = query.message.message_id
        game_state = self.repo.get_game(chat_id, message_id)
        
        if not game_state:
            await query.edit_message_text(locales.ERROR_NO_GAME)
            return
        
        # Load engine state
        engine = CheckersEngine()
        engine.set_board_state({
            "board": game_state["board"],
            "current_turn": game_state["current_turn"]
        })
        
        # Show board with piece selection
        await self._update_game_message(query.message, engine, game_state)
    
    async def forfeit_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle forfeit button."""
        query = update.callback_query
        await query.answer()
        
        # Get game state
        chat_id = query.message.chat.id
        message_id = query.message.message_id
        game_state = self.repo.get_game(chat_id, message_id)
        
        if not game_state:
            await query.edit_message_text(locales.ERROR_NO_GAME)
            return
        
        user_id = query.from_user.id
        
        # Determine winner (opponent of forfeiting player)
        if user_id == game_state["red_player_id"]:
            winner_id = game_state["white_player_id"]
            winner_name = game_state["white_player_name"]
            loser_id = game_state["red_player_id"]
            loser_name = game_state["red_player_name"]
        else:
            winner_id = game_state["red_player_id"]
            winner_name = game_state["red_player_name"]
            loser_id = game_state["white_player_id"]
            loser_name = game_state["white_player_name"]
        
        # Load engine for final board display
        engine = CheckersEngine()
        engine.set_board_state({
            "board": game_state["board"],
            "current_turn": game_state["current_turn"]
        })
        
        board_text = BoardRenderer.render(engine.board)
        
        # Record rating changes if rating system available
        if self.rating_system:
            winner_data, loser_data = await self.rating_system.record_game(
                winner_id, winner_name, loser_id, loser_name
            )
            
            win_msg = f"{locales.WINNER_WITH_RATING.format(name=winner_name, winner_name=winner_name, winner_rating=winner_data['rating'], winner_change=winner_data['rating_change'], loser_name=loser_name, loser_rating=loser_data['rating'], loser_change=loser_data['rating_change'])}\n(Суперник здався)"
        else:
            win_msg = f"{locales.WINNER.format(name=winner_name)}\n(Суперник здався)"
        
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(locales.BTN_NEW_GAME, callback_data="new_game")
        ]])
        
        await query.edit_message_text(
            f"{board_text}\n\n{win_msg}",
            reply_markup=keyboard
        )
        
        # Delete game
        self.repo.delete_game(chat_id, message_id)
    
    async def new_game_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new game button - just show welcome message."""
        query = update.callback_query
        await query.answer("Використайте /checkersplay для нової гри")
    
    async def _update_game_message(self, message, engine: CheckersEngine, game_state: dict):
        """Update game message with current board and turn info."""
        board_text = BoardRenderer.render(engine.board)
        turn_msg = self._get_turn_message(game_state)
        keyboard = BoardRenderer.create_move_keyboard(engine)
        
        await message.edit_text(
            f"{board_text}\n\n{turn_msg}",
            reply_markup=keyboard
        )
    
    @staticmethod
    def _get_turn_message(game_state: dict) -> str:
        """Get turn message for current player."""
        current_turn = game_state["current_turn"]
        
        if current_turn == RED:
            name = game_state["red_player_name"]
            return locales.TURN_RED.format(name=name)
        else:
            name = game_state["white_player_name"]
            return locales.TURN_WHITE.format(name=name)
    
    async def myrating_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /myrating command - show user's rating."""
        if not self.rating_system:
            await update.message.reply_text("Система рейтингу недоступна.")
            return
        
        user = update.effective_user
        player_data = await self.rating_system.get_player(user.id, user.first_name)
        
        if player_data["games_played"] == 0:
            await update.message.reply_text(locales.NO_GAMES_PLAYED)
            return
        
        rank = await self.rating_system.get_player_rank(user.id)
        
        message = locales.RATING_INFO.format(
            name=user.first_name,
            rating=player_data["rating"],
            rank=rank or "?",
            games_played=player_data["games_played"],
            wins=player_data["wins"],
            losses=player_data["losses"]
        )
        
        await update.message.reply_text(message)
    
    async def ratings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /ratings command - show leaderboard."""
        if not self.rating_system:
            await update.message.reply_text("Система рейтингу недоступна.")
            return
        
        leaderboard = await self.rating_system.get_leaderboard(limit=10)
        
        if not leaderboard:
            await update.message.reply_text("Ще немає рейтингу. Зіграйте першу гру!")
            return
        
        message = locales.LEADERBOARD_TITLE.format(count=len(leaderboard))
        
        for idx, player in enumerate(leaderboard, 1):
            entry = locales.LEADERBOARD_ENTRY.format(
                rank=idx,
                name=player["username"],
                rating=player["rating"],
                wins=player["wins"],
                losses=player["losses"]
            )
            message += entry + "\n"
        
        await update.message.reply_text(message)

