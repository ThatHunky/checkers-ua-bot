"""
Telegram bot handlers for Ukrainian Checkers game.
"""

import os
import uuid
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
    def create_move_keyboard(engine: CheckersEngine, selected_pos: Optional[int] = None, move_count: int = 1) -> InlineKeyboardMarkup:
        """
        Create inline keyboard showing the actual board as clickable buttons.
        
        If selected_pos is None: highlight pieces that can move (green)
        If selected_pos is set: highlight selected piece and show possible destinations
        """
        buttons = []
        
        # Get legal moves for highlighting
        legal_moves = engine.get_legal_moves(engine.current_turn)
        movable_positions = set(move.from_pos for move in legal_moves)
        
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
                    label = f"✅{BoardRenderer._get_piece_emoji(piece)}"
                elif pos in selected_destinations:
                    # Possible destination - show target
                    label = "🎯"
                elif piece != 0:
                    # Regular piece (clickable or not)
                    # Remove padding spaces to prevent horizontal cutoff in 8x8 grid
                    label = BoardRenderer._get_piece_emoji(piece)
                else:
                    # Empty square - use Braille pattern blank for consistent height
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
        if selected_pos is not None:
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
        if piece == 1:  # White man
            return "⚪"
        elif piece == 2:  # White king
            return "🤍"  # White heart
        elif piece == 3:  # Red man
            return "🔴"
        elif piece == 4:  # Red king
            return "❤️"  # Red heart
        return ""


class GameHandlers:
    """Telegram bot command and callback handlers."""
    
    def __init__(self, repository: GameRepository, rating_system=None):
        self.repo = repository
        self.rating_system = rating_system
    
    async def start_bot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - register user and show welcome message."""
        user = update.effective_user
        
        # Register user in the registry (enables receiving private game invites)
        self.repo.register_user(user.id, user.username, user.first_name)
        
        await update.message.reply_text(
            f"👋 Привіт, <b>{user.first_name}</b>!\n\n"
            "🎮 Я — бот для гри в <b>Українські Шашки</b>.\n\n"
            "<b>Як грати:</b>\n"
            "• У групі: /checkersplay — будь-хто може приєднатись\n"
            "• В особистому чаті: <code>/checkersplay @username</code>\n\n"
            "<b>Команди:</b>\n"
            "• /myrating — ваш рейтинг\n"
            "• /ratings — таблиця лідерів\n\n"
            "Удачі! 🏆",
            parse_mode="HTML"
        )
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /checkersplay command - create a new game challenge."""
        user = update.effective_user
        chat = update.effective_chat
        
        # Register user in the registry (for future invites)
        self.repo.register_user(user.id, user.username, user.first_name)
        
        # Private chat requires opponent specification
        if chat.type == "private":
            # Check if opponent is specified
            if not context.args:
                await update.message.reply_text(
                    "🎮 Щоб запросити гравця в особистому чаті:\n\n"
                    "<code>/checkersplay @username</code>\n\n"
                    "Або використовуйте команду в груповому чаті.",
                    parse_mode="HTML"
                )
                return
            
            # Try to get opponent info from args
            opponent_username = context.args[0]
            
            # Remove @ if present
            if opponent_username.startswith("@"):
                opponent_username = opponent_username[1:]
            
            # Don't allow challenging yourself
            if user.username and opponent_username.lower() == user.username.lower():
                await update.message.reply_text(
                    "❌ Ви не можете грати проти себе!"
                )
                return
            
            # Look up opponent in user registry
            opponent_info = self.repo.get_user_by_username(opponent_username)
            
            if not opponent_info:
                await update.message.reply_text(
                    f"❌ Користувача @{opponent_username} не знайдено.\n\n"
                    "Можливі причини:\n"
                    "• Користувач ще не взаємодіяв з ботом\n"
                    "• Неправильний нікнейм\n\n"
                    "Попросіть суперника написати /start цьому боту, "
                    "щоб зареєструватися."
                )
                return
            
            # Create unique invite ID
            invite_id = str(uuid.uuid4())[:8]
            
            # Create pending invite in Redis
            self.repo.create_invite(
                invite_id=invite_id,
                challenger_id=user.id,
                challenger_name=user.first_name,
                challenger_username=user.username,
                challenger_chat_id=chat.id,
                opponent_id=opponent_info["user_id"],
                opponent_username=opponent_username
            )
            
            # Send invitation to opponent
            invite_keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Прийняти", callback_data=f"accept_invite_{invite_id}"),
                InlineKeyboardButton("❌ Відхилити", callback_data=f"decline_invite_{invite_id}")
            ]])
            
            try:
                await context.bot.send_message(
                    chat_id=opponent_info["user_id"],
                    text=f"🎮 <b>{user.first_name}</b> запрошує вас на гру в шашки!\n\n"
                         f"⏰ Запрошення дійсне 5 хвилин.",
                    parse_mode="HTML",
                    reply_markup=invite_keyboard
                )
                
                await update.message.reply_text(
                    f"✅ Запрошення надіслано @{opponent_username}!\n\n"
                    f"⏰ Очікуємо відповідь протягом 5 хвилин..."
                )
            except Exception as e:
                # Failed to send - opponent may have blocked the bot
                self.repo.delete_invite(invite_id)
                await update.message.reply_text(
                    f"❌ Не вдалося надіслати запрошення @{opponent_username}.\n\n"
                    "Можливо, користувач заблокував бота."
                )
            return
        
        # Group chat flow - normal challenge
        # Create challenge message
        challenge_text = locales.CHALLENGE.format(opponent=user.mention_html())
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(locales.JOIN_BTN, callback_data="join"),
            InlineKeyboardButton("🚫 Скасувати", callback_data="cancel_invite")
        ]])
        
        message = await update.message.reply_html(challenge_text, reply_markup=keyboard)
        
        # Store challenger info temporarily
        context.chat_data[f"challenge_{message.message_id}"] = {
            "red_player_id": user.id,
            "red_player_name": user.first_name,
            "red_player_username": user.username
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
        now = datetime.utcnow().isoformat()
        game_state = {
            "board": engine.board,
            "current_turn": engine.current_turn,
            "red_player_id": challenge_info["red_player_id"],
            "red_player_name": challenge_info["red_player_name"],
            "red_player_username": challenge_info.get("red_player_username"),
            "white_player_id": user.id,
            "white_player_name": user.first_name,
            "white_player_username": user.username,
            "created_at": now,
            "last_activity": now
        }
        
        # Save to Redis
        self.repo.save_game(chat.id, message_id, game_state)
        
        # Clean up challenge data
        del context.chat_data[challenge_key]
        
        # Show game board
        await self._update_game_message(query.message, engine, game_state)
    
    async def cancel_invite_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle cancel invitation button - only challenger can cancel."""
        query = update.callback_query
        
        user = query.from_user
        message_id = query.message.message_id
        
        # Get challenge info
        challenge_key = f"challenge_{message_id}"
        challenge_info = context.chat_data.get(challenge_key)
        
        if not challenge_info:
            await query.answer("❌ Запрошення вже недійсне.", show_alert=True)
            return
        
        # Only the challenger can cancel
        if user.id != challenge_info["red_player_id"]:
            await query.answer("❌ Тільки автор запрошення може його скасувати!", show_alert=True)
            return
        
        # Delete challenge data
        del context.chat_data[challenge_key]
        
        # Update message
        await query.answer("Запрошення скасовано")
        await query.edit_message_text("🚫 Запрошення на гру скасовано.")
    
    async def accept_private_invite_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle accepting a private game invitation."""
        query = update.callback_query
        user = query.from_user
        
        # Register user in registry
        self.repo.register_user(user.id, user.username, user.first_name)
        
        # Parse invite ID from callback data: accept_invite_{invite_id}
        parts = query.data.split("_")
        if len(parts) != 3:
            await query.answer("❌ Неправильний формат запрошення.", show_alert=True)
            return
        
        invite_id = parts[2]
        
        # Get invite info
        invite_info = self.repo.get_invite(invite_id)
        
        if not invite_info:
            await query.answer("❌ Запрошення закінчилось або вже використане.", show_alert=True)
            await query.edit_message_text("⏰ Це запрошення вже недійсне.")
            return
        
        # Verify this user is the intended opponent
        if user.id != invite_info["opponent_id"]:
            await query.answer("❌ Це запрошення не для вас!", show_alert=True)
            return
        
        # Delete the invite
        self.repo.delete_invite(invite_id)
        
        # Initialize game
        engine = CheckersEngine()
        now = datetime.utcnow().isoformat()
        
        # Challenger is red (initiator), opponent is white
        game_state = {
            "board": engine.board,
            "current_turn": engine.current_turn,
            "red_player_id": invite_info["challenger_id"],
            "red_player_name": invite_info["challenger_name"],
            "red_player_username": invite_info.get("challenger_username"),
            "white_player_id": user.id,
            "white_player_name": user.first_name,
            "white_player_username": user.username,
            "created_at": now,
            "last_activity": now,
            "is_private_match": True,
            "challenger_chat_id": invite_info["challenger_chat_id"]
        }
        
        # Game will be played in the OPPONENT's chat (where they accepted)
        # This provides better UX - they're already looking at the message
        opponent_chat_id = query.message.chat.id
        
        try:
            # Create board display
            board_text = BoardRenderer.render(engine.board)
            players_msg = self._get_players_message(game_state)
            turn_msg = self._get_turn_message(game_state)
            keyboard = BoardRenderer.create_move_keyboard(engine, move_count=engine.move_count)
            
            # Send game board as a NEW message in opponent's chat
            game_message = await context.bot.send_message(
                chat_id=opponent_chat_id,
                text=f"{players_msg}\n\n{board_text}\n\n{turn_msg}",
                reply_markup=keyboard
            )
            
            # Save game state (keyed by opponent's chat)
            self.repo.save_game(opponent_chat_id, game_message.message_id, game_state)
            
            # Update the original invite message
            await query.answer("Гра розпочалась!")
            await query.edit_message_text(
                f"✅ Ви прийняли виклик від <b>{invite_info['challenger_name']}</b>!\n"
                f"⬇️ Дивіться дошку нижче.",
                parse_mode="HTML"
            )
            
            # Notify challenger that game started - they need to open chat with bot
            try:
                await context.bot.send_message(
                    chat_id=invite_info["challenger_chat_id"],
                    text=f"🎮 <b>{user.first_name}</b> прийняв виклик!\n\n"
                         f"{players_msg}\n\n{board_text}\n\n{turn_msg}\n\n"
                         f"⚠️ Грайте у чаті з <b>{user.first_name}</b> або тут — "
                         f"хід відобразиться в обох чатах.",
                    parse_mode="HTML"
                )
            except Exception:
                pass  # Ignore if can't notify challenger
            
        except Exception as e:
            await query.answer("❌ Помилка при створенні гри.", show_alert=True)
            await query.edit_message_text(
                f"❌ Не вдалося створити гру: {str(e)}"
            )
    
    async def decline_private_invite_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle declining a private game invitation."""
        query = update.callback_query
        user = query.from_user
        
        # Parse invite ID from callback data: decline_invite_{invite_id}
        parts = query.data.split("_")
        if len(parts) != 3:
            await query.answer("❌ Неправильний формат запрошення.", show_alert=True)
            return
        
        invite_id = parts[2]
        
        # Get invite info
        invite_info = self.repo.get_invite(invite_id)
        
        if not invite_info:
            await query.answer("❌ Запрошення вже недійсне.", show_alert=True)
            await query.edit_message_text("⏰ Це запрошення вже недійсне.")
            return
        
        # Verify this user is the intended opponent
        if user.id != invite_info["opponent_id"]:
            await query.answer("❌ Це запрошення не для вас!", show_alert=True)
            return
        
        # Delete the invite
        self.repo.delete_invite(invite_id)
        
        # Notify challenger about decline
        try:
            await context.bot.send_message(
                chat_id=invite_info["challenger_chat_id"],
                text=f"❌ <b>{user.first_name}</b> відхилив запрошення на гру.",
                parse_mode="HTML"
            )
        except Exception:
            pass  # Ignore if can't notify
        
        # Update message for opponent
        await query.answer("Запрошення відхилено")
        await query.edit_message_text("❌ Ви відхилили запрошення на гру.")
    
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
            "current_turn": game_state["current_turn"],
            "move_count": game_state.get("move_count", 0)
        })
        
        # Show available moves
        board_text = BoardRenderer.render(engine.board)
        turn_msg = self._get_turn_message(game_state)
        
        keyboard = BoardRenderer.create_move_keyboard(engine, selected_pos, engine.move_count)
        
        try:
            await query.edit_message_text(
                f"{board_text}\n\n{turn_msg}\n\n✅ Обрано: позиція {selected_pos}",
                reply_markup=keyboard
            )
        except Exception:
            pass  # Ignore "Message is not modified" errors
    
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
            "current_turn": game_state["current_turn"],
            "move_count": game_state.get("move_count", 0)
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
            
            # keyboard = InlineKeyboardMarkup([[
            #     InlineKeyboardButton(locales.BTN_NEW_GAME, callback_data="new_game")
            # ]])
            
            await query.edit_message_text(
                f"{board_text}\n\n{win_msg}",
                reply_markup=None
            )
            
            # Delete game from Redis
            self.repo.delete_game(chat_id, message_id)
        else:
            # Update game state
            game_state["board"] = engine.board
            game_state["current_turn"] = engine.current_turn
            game_state["move_count"] = engine.move_count
            game_state["last_activity"] = datetime.utcnow().isoformat()
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
            "current_turn": game_state["current_turn"],
            "move_count": game_state.get("move_count", 0)
        })
        
        # Show board with piece selection
        await self._update_game_message(query.message, engine, game_state)
    
    async def forfeit_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle forfeit/cancel button."""
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
        
        # Verify user is actually a player in this game
        if user_id != game_state["red_player_id"] and user_id != game_state["white_player_id"]:
            await query.answer("❌ Ви не є гравцем у цій грі!", show_alert=True)
            return
        
        move_count = game_state.get("move_count", 0)
        
        # Check if cancelling (no moves yet) or forfeiting
        if move_count == 0:
            # Game Cancelled - NO RATING CHANGE
            win_msg = "🚫 Гра скасована. Рейтинг не змінено."
            
            # Restore engine for display
            engine = CheckersEngine()
            engine.set_board_state({
                "board": game_state["board"],
                "current_turn": game_state["current_turn"],
                "move_count": move_count
            })
            board_text = BoardRenderer.render(engine.board)
            
            # keyboard = InlineKeyboardMarkup([[
            #     InlineKeyboardButton(locales.BTN_NEW_GAME, callback_data="new_game")
            # ]])
            
            await query.edit_message_text(
                f"{board_text}\n\n{win_msg}",
                reply_markup=None
            )
            
            # Delete game
            self.repo.delete_game(chat_id, message_id)
            return

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
            "current_turn": game_state["current_turn"],
            "move_count": move_count
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
        
        # keyboard = InlineKeyboardMarkup([[
        #     InlineKeyboardButton(locales.BTN_NEW_GAME, callback_data="new_game")
        # ]])
        
        await query.edit_message_text(
            f"{board_text}\n\n{win_msg}",
            reply_markup=None
        )
        
        # Delete game
        self.repo.delete_game(chat_id, message_id)
    
    async def new_game_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new game button - just show welcome message."""
        query = update.callback_query
        await query.answer("Використайте /checkersplay для нової гри")
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /cancel command - cancel current game (only before moves)."""
        user = update.effective_user
        chat = update.effective_chat
        
        # Only works in private chat
        if chat.type != "private":
            await update.message.reply_text(
                "❌ Ця команда працює тільки в особистому чаті з ботом."
            )
            return
        
        # Find user's active game
        game_info = self.repo.get_user_game(user.id)
        
        if not game_info:
            await update.message.reply_text(
                "❌ У вас немає активної гри."
            )
            return
        
        chat_id, message_id, game_state = game_info
        move_count = game_state.get("move_count", 0)
        
        if move_count > 0:
            await update.message.reply_text(
                "❌ Неможливо скасувати гру після першого ходу.\n\n"
                "Використовуйте /forfeit щоб здатися."
            )
            return
        
        # Get opponent name
        if user.id == game_state["red_player_id"]:
            opponent_name = game_state["white_player_name"]
        else:
            opponent_name = game_state["red_player_name"]
        
        # Show confirmation
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Так, скасувати", callback_data=f"confirm_cancel_{chat_id}_{message_id}"),
            InlineKeyboardButton("❌ Ні", callback_data="cancel_abort")
        ]])
        
        await update.message.reply_text(
            f"⚠️ Ви впевнені, що хочете скасувати гру з <b>{opponent_name}</b>?\n\n"
            "Рейтинг не буде змінено.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    
    async def forfeit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /forfeit command - forfeit current game."""
        user = update.effective_user
        chat = update.effective_chat
        
        # Only works in private chat
        if chat.type != "private":
            await update.message.reply_text(
                "❌ Ця команда працює тільки в особистому чаті з ботом."
            )
            return
        
        # Find user's active game
        game_info = self.repo.get_user_game(user.id)
        
        if not game_info:
            await update.message.reply_text(
                "❌ У вас немає активної гри."
            )
            return
        
        chat_id, message_id, game_state = game_info
        move_count = game_state.get("move_count", 0)
        
        if move_count == 0:
            await update.message.reply_text(
                "ℹ️ Гра ще не почалась. Використовуйте /cancel щоб скасувати."
            )
            return
        
        # Get opponent name
        if user.id == game_state["red_player_id"]:
            opponent_name = game_state["white_player_name"]
        else:
            opponent_name = game_state["red_player_name"]
        
        # Show confirmation
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Так, здатися", callback_data=f"confirm_forfeit_{chat_id}_{message_id}"),
            InlineKeyboardButton("❌ Ні", callback_data="cancel_abort")
        ]])
        
        await update.message.reply_text(
            f"⚠️ Ви впевнені, що хочете здатися у грі з <b>{opponent_name}</b>?\n\n"
            "⚠️ Ваш рейтинг зменшиться!",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    
    async def confirm_cancel_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle confirmation of game cancellation."""
        query = update.callback_query
        user = query.from_user
        
        # Parse callback data: confirm_cancel_{chat_id}_{message_id}
        parts = query.data.split("_")
        if len(parts) != 4:
            await query.answer("❌ Помилка.", show_alert=True)
            return
        
        game_chat_id = int(parts[2])
        game_message_id = int(parts[3])
        
        # Get game state
        game_state = self.repo.get_game(game_chat_id, game_message_id)
        
        if not game_state:
            await query.answer("❌ Гра вже закінчилась.", show_alert=True)
            await query.edit_message_text("❌ Гра вже закінчилась.")
            return
        
        # Verify user is a player
        if user.id != game_state["red_player_id"] and user.id != game_state["white_player_id"]:
            await query.answer("❌ Ви не є гравцем у цій грі!", show_alert=True)
            return
        
        # Cancel the game
        self.repo.delete_game(game_chat_id, game_message_id)
        
        # Update game message
        try:
            await context.bot.edit_message_text(
                chat_id=game_chat_id,
                message_id=game_message_id,
                text="🚫 Гра скасована. Рейтинг не змінено."
            )
        except Exception:
            pass
        
        # Update confirmation message
        await query.answer("Гру скасовано")
        await query.edit_message_text("🚫 Гру скасовано. Рейтинг не змінено.")
        
        # Notify opponent
        opponent_id = game_state["white_player_id"] if user.id == game_state["red_player_id"] else game_state["red_player_id"]
        try:
            await context.bot.send_message(
                chat_id=opponent_id,
                text=f"🚫 <b>{user.first_name}</b> скасував гру.",
                parse_mode="HTML"
            )
        except Exception:
            pass
    
    async def confirm_forfeit_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle confirmation of forfeit."""
        query = update.callback_query
        user = query.from_user
        
        # Parse callback data: confirm_forfeit_{chat_id}_{message_id}
        parts = query.data.split("_")
        if len(parts) != 4:
            await query.answer("❌ Помилка.", show_alert=True)
            return
        
        game_chat_id = int(parts[2])
        game_message_id = int(parts[3])
        
        # Get game state
        game_state = self.repo.get_game(game_chat_id, game_message_id)
        
        if not game_state:
            await query.answer("❌ Гра вже закінчилась.", show_alert=True)
            await query.edit_message_text("❌ Гра вже закінчилась.")
            return
        
        # Verify user is a player
        if user.id != game_state["red_player_id"] and user.id != game_state["white_player_id"]:
            await query.answer("❌ Ви не є гравцем у цій грі!", show_alert=True)
            return
        
        # Determine winner (opponent)
        if user.id == game_state["red_player_id"]:
            winner_id = game_state["white_player_id"]
            winner_name = game_state["white_player_name"]
            loser_id = game_state["red_player_id"]
            loser_name = game_state["red_player_name"]
        else:
            winner_id = game_state["red_player_id"]
            winner_name = game_state["red_player_name"]
            loser_id = game_state["white_player_id"]
            loser_name = game_state["white_player_name"]
        
        # Record rating changes
        rating_msg = ""
        if self.rating_system:
            try:
                winner_data, loser_data = await self.rating_system.record_game(
                    winner_id, winner_name, loser_id, loser_name
                )
                rating_msg = (
                    f"\n\n📊 Рейтинг:\n"
                    f"🏆 {winner_name}: {winner_data['rating']} ({winner_data['rating_change']:+d})\n"
                    f"💀 {loser_name}: {loser_data['rating']} ({loser_data['rating_change']:+d})"
                )
            except Exception:
                pass
        
        # Delete game
        self.repo.delete_game(game_chat_id, game_message_id)
        
        # Update game message
        try:
            await context.bot.edit_message_text(
                chat_id=game_chat_id,
                message_id=game_message_id,
                text=f"🏳️ <b>{user.first_name}</b> здався!\n\n"
                     f"🏆 Переможець: <b>{winner_name}</b>{rating_msg}",
                parse_mode="HTML"
            )
        except Exception:
            pass
        
        # Update confirmation message
        await query.answer("Ви здались")
        await query.edit_message_text(
            f"🏳️ Ви здались. {winner_name} переміг!{rating_msg}",
            parse_mode="HTML" if rating_msg else None
        )
        
        # Notify winner
        try:
            await context.bot.send_message(
                chat_id=winner_id,
                text=f"🏆 <b>{loser_name}</b> здався! Ви перемогли!{rating_msg}",
                parse_mode="HTML"
            )
        except Exception:
            pass
    
    async def cancel_abort_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle aborting cancel/forfeit confirmation."""
        query = update.callback_query
        await query.answer("Дію скасовано")
        await query.edit_message_text("✅ Гра продовжується.")
    
    async def reset_rankings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Hidden admin command to reset all rankings. Only works in private chat for admin."""
        user = update.effective_user
        chat = update.effective_chat
        
        # Check if private chat
        if chat.type != "private":
            return  # Silently ignore in group chats
        
        # Check if admin
        admin_id_str = os.getenv("ADMIN_ID", "")
        if not admin_id_str:
            return  # No admin configured
        
        try:
            admin_id = int(admin_id_str)
        except ValueError:
            return  # Invalid admin ID
        
        if user.id != admin_id:
            return  # Not admin, silently ignore
        
        # Admin confirmed - reset rankings
        if not self.rating_system:
            await update.message.reply_text("❌ Система рейтингу не налаштована.")
            return
        
        count = await self.rating_system.reset_all_rankings()
        await update.message.reply_text(
            f"✅ Рейтинги скинуто!\n\n"
            f"🗑️ Видалено записів: {count}\n"
            f"📊 Всі гравці почнуть з {1200} ELO."
        )
    
    async def add_legend_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Hidden admin command to add arcade-style leaderboard entries.
        Usage: /addlegend NAME RATING [WINS] [LOSSES]
        Example: /addlegend AAA 2500 50 10
        """
        user = update.effective_user
        chat = update.effective_chat
        
        # Check if private chat
        if chat.type != "private":
            return  # Silently ignore in group chats
        
        # Check if admin
        admin_id_str = os.getenv("ADMIN_ID", "")
        if not admin_id_str:
            return
        
        try:
            admin_id = int(admin_id_str)
        except ValueError:
            return
        
        if user.id != admin_id:
            return  # Not admin, silently ignore
        
        # Parse arguments
        if not self.rating_system:
            await update.message.reply_text("❌ Система рейтингу не налаштована.")
            return
        
        if not context.args or len(context.args) < 2:
            await update.message.reply_text(
                "🕹️ <b>Додати легенду до таблиці лідерів</b>\n\n"
                "Використання:\n"
                "<code>/addlegend ІМ'Я РЕЙТИНГ [ПЕРЕМОГИ] [ПОРАЗКИ]</code>\n\n"
                "Приклади:\n"
                "• <code>/addlegend AAA 2500</code>\n"
                "• <code>/addlegend PRO 1800 42 13</code>\n"
                "• <code>/addlegend ACE 2200 100 20</code>",
                parse_mode="HTML"
            )
            return
        
        name = context.args[0]
        
        try:
            rating = int(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Рейтинг повинен бути числом.")
            return
        
        # Optional wins/losses
        wins = 0
        losses = 0
        if len(context.args) >= 3:
            try:
                wins = int(context.args[2])
            except ValueError:
                pass
        if len(context.args) >= 4:
            try:
                losses = int(context.args[3])
            except ValueError:
                pass
        
        # Add the arcade entry
        fake_id = await self.rating_system.add_arcade_entry(name, rating, wins, losses)
        
        await update.message.reply_text(
            f"🕹️ <b>Легенду додано!</b>\n\n"
            f"👤 Ім'я: <b>{name}</b>\n"
            f"📊 Рейтинг: <b>{rating}</b> ELO\n"
            f"🏆 Перемоги: {wins}\n"
            f"💀 Поразки: {losses}\n\n"
            f"<i>(ID: {fake_id})</i>",
            parse_mode="HTML"
        )
    
    async def _update_game_message(self, message, engine: CheckersEngine, game_state: dict):
        """Update game message with current board and turn info."""
        board_text = BoardRenderer.render(engine.board)
        players_msg = self._get_players_message(game_state)
        turn_msg = self._get_turn_message(game_state)
        keyboard = BoardRenderer.create_move_keyboard(engine, move_count=engine.move_count)
        
        await message.edit_text(
            f"{players_msg}\n\n{board_text}\n\n{turn_msg}",
            reply_markup=keyboard
        )
    
    @staticmethod
    def _get_player_tag(game_state: dict, color: str) -> str:
        """Get @mention or name for a player. Color is 'red' or 'white'."""
        username = game_state.get(f"{color}_player_username")
        name = game_state[f"{color}_player_name"]
        
        if username:
            return f"@{username}"
        return name
    
    @staticmethod
    def _get_players_message(game_state: dict) -> str:
        """Get message showing both players with @mentions."""
        red_username = game_state.get("red_player_username")
        white_username = game_state.get("white_player_username")
        
        red_tag = f"@{red_username}" if red_username else game_state["red_player_name"]
        white_tag = f"@{white_username}" if white_username else game_state["white_player_name"]
        
        return f"🔴 {red_tag}  vs  ⚪ {white_tag}"
    
    @staticmethod
    def _get_turn_message(game_state: dict) -> str:
        """Get turn message for current player with @mention."""
        current_turn = game_state["current_turn"]
        
        if current_turn == RED:
            username = game_state.get("red_player_username")
            name = game_state["red_player_name"]
            player_tag = f"@{username}" if username else name
            return locales.TURN_RED.format(player_tag=player_tag)
        else:
            username = game_state.get("white_player_username")
            name = game_state["white_player_name"]
            player_tag = f"@{username}" if username else name
            return locales.TURN_WHITE.format(player_tag=player_tag)
    
    async def noop_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle noop (no-operation) callbacks from non-interactive squares."""
        query = update.callback_query
        # Just answer the callback without doing anything
        await query.answer()
    
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
        """Handle /ratings command - show leaderboard with pagination."""
        if not self.rating_system:
            await update.message.reply_text("Система рейтингу недоступна.")
            return
        
        await self._send_leaderboard(update.message, page=0)
    
    async def ratings_page_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle leaderboard page navigation."""
        query = update.callback_query
        await query.answer()
        
        if not self.rating_system:
            return
        
        # Parse page number from callback data: ratings_page_N
        _, _, page_str = query.data.split("_")
        page = int(page_str)
        
        await self._send_leaderboard(query.message, page=page, edit=True)
    
    async def _send_leaderboard(self, message, page: int = 0, edit: bool = False):
        """Send or edit leaderboard message with pagination."""
        PLAYERS_PER_PAGE = 15
        offset = page * PLAYERS_PER_PAGE
        
        leaderboard, total_count = await self.rating_system.get_leaderboard(
            limit=PLAYERS_PER_PAGE, offset=offset
        )
        
        if not leaderboard and page == 0:
            text = "Ще немає рейтингу. Зіграйте першу гру!"
            if edit:
                await message.edit_text(text)
            else:
                await message.reply_text(text)
            return
        
        total_pages = (total_count + PLAYERS_PER_PAGE - 1) // PLAYERS_PER_PAGE
        
        # Build message
        text = f"🏆 <b>Таблиця лідерів</b> (стор. {page + 1}/{total_pages})\n\n"
        
        for idx, player in enumerate(leaderboard, start=offset + 1):
            # Medal for top 3
            if idx == 1:
                medal = "🥇"
            elif idx == 2:
                medal = "🥈"
            elif idx == 3:
                medal = "🥉"
            else:
                medal = f"{idx}."
            
            text += f"{medal} {player['username']} — {player['rating']} ELO ({player['wins']}W/{player['losses']}L)\n"
        
        # Navigation buttons
        buttons = []
        if page > 0:
            buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"ratings_page_{page - 1}"))
        if page < total_pages - 1:
            buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"ratings_page_{page + 1}"))
        
        keyboard = InlineKeyboardMarkup([buttons]) if buttons else None
        
        if edit:
            await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")

