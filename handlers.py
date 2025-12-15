"""
Telegram bot handlers for Ukrainian Checkers game.
"""

import os
import uuid
import json
import logging
from datetime import datetime
from typing import Optional
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

MENU_MAIN = "menu_main"
MENU_PLAY = "menu_play"
MENU_PROFILE = "menu_profile"
MENU_RATING = "menu_rating"
MENU_SETTINGS = "menu_settings"
MENU_HELP = "menu_help"
MENU_ABOUT = "menu_about"

PLAY_RATED = "play_rated"
PLAY_CASUAL = "play_casual"
INVITE_RATED = "invite_rated"
INVITE_CASUAL = "invite_casual"
JOIN_CODE = "join_code"
MM_CANCEL = "mm_cancel"
BACK_TO_PLAY = "back_to_play"

from engine import CheckersEngine, WHITE, RED, Move
from repository import GameRepository
from matchmaking import MatchmakingService
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
            # Only show single-hop captures from the pending position
            legal_moves = engine.find_single_hop_captures(pending_capture["pos"])
            movable_positions = {pending_capture["pos"]}
            selected_pos = pending_capture["pos"]  # Auto-select the piece
        else:
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
                    label = f"✅{BoardRenderer._get_piece_emoji(piece)}"
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
    
    def __init__(self, repository: GameRepository, rating_system=None, game_data_repo=None):
        self.repo = repository
        self.rating_system = rating_system
        self.game_data_repo = game_data_repo
        self.matchmaking = MatchmakingService(repository, rating_system)

    # ======== Menus ========
    def _main_menu_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(locales.MENU_PLAY, callback_data=MENU_PLAY)],
                [InlineKeyboardButton(locales.MENU_PROFILE, callback_data=MENU_PROFILE)],
                [InlineKeyboardButton(locales.MENU_RATING, callback_data=MENU_RATING)],
                [InlineKeyboardButton(locales.MENU_SETTINGS, callback_data=MENU_SETTINGS)],
                [InlineKeyboardButton(locales.MENU_HELP, callback_data=MENU_HELP)],
                [InlineKeyboardButton(locales.MENU_ABOUT, callback_data=MENU_ABOUT)],
            ]
        )

    def _play_menu_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(locales.PLAY_QUICK_RATED, callback_data=PLAY_RATED)],
                [InlineKeyboardButton(locales.PLAY_QUICK_CASUAL, callback_data=PLAY_CASUAL)],
                [InlineKeyboardButton(locales.PLAY_INVITE_RATED, callback_data=INVITE_RATED)],
                [InlineKeyboardButton(locales.PLAY_INVITE_CASUAL, callback_data=INVITE_CASUAL)],
                [InlineKeyboardButton(locales.PLAY_JOIN_CODE, callback_data=JOIN_CODE)],
                [InlineKeyboardButton(locales.BTN_BACK, callback_data=MENU_MAIN)],
            ]
        )

    def _menu_reply_keyboard(self) -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            [[KeyboardButton(locales.MENU_BUTTON)]],
            resize_keyboard=True,
            is_persistent=True,
        )

    async def _send_menu_reply_keyboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ensure the persistent Menu reply keyboard is available."""
        message = update.effective_message
        if not message:
            return

        if context.chat_data.get("has_menu_keyboard"):
            return

        context.chat_data["has_menu_keyboard"] = True
        await message.reply_text(
            locales.MENU_SHORTCUT_HINT,
            reply_markup=self._menu_reply_keyboard(),
        )

    def _searching_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(locales.SEARCHING_CANCEL, callback_data=MM_CANCEL)],
                [InlineKeyboardButton(locales.SEARCHING_BACK, callback_data=BACK_TO_PLAY)],
            ]
        )
    
    def _get_game_state(self, chat_id: int = None, message_id: int = None, inline_message_id: str = None) -> Optional[dict]:
        """
        Get game state, supporting both regular messages and inline messages.
        For private matches, if game not found in current chat, try the other player's chat.
        """
        # Handle inline messages
        if inline_message_id:
            return self.repo.get_inline_game(inline_message_id)
        
        # Handle regular messages
        if chat_id and message_id:
            game_state = self.repo.get_game(chat_id, message_id)
            
            if game_state:
                return game_state
            
            # If not found, check if there's a private match we can find
            # by checking all games and finding one where this chat_id matches
            all_games = self.repo.get_all_games()
            for game_chat_id, game_message_id, state in all_games:
                if state.get("is_private_match"):
                    # Check if this chat_id matches either player's chat
                    if (state.get("challenger_chat_id") == chat_id or 
                        state.get("opponent_chat_id") == chat_id):
                        # Found a private match for this chat, return it
                        return state
        
        return None
    
    async def start_bot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - register user and show welcome message."""
        user = update.effective_user

        # Register user in the registry (enables receiving private game invites)
        self.repo.register_user(user.id, user.username, user.first_name)

        await self.show_main_menu(update, context)
        await self._send_menu_reply_keyboard(update, context)

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Explicit /menu command."""
        await self.show_main_menu(update, context)
        await self._send_menu_reply_keyboard(update, context)

    async def menu_text_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text button presses that request the menu."""
        await self.show_main_menu(update, context)
        await self._send_menu_reply_keyboard(update, context)

    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Display the main menu via message or edit."""
        text = locales.MENU_TITLE
        keyboard = self._main_menu_keyboard()
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=keyboard)
        else:
            await update.effective_message.reply_text(text, reply_markup=keyboard)
            await self._send_menu_reply_keyboard(update, context)

    async def show_play_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = locales.PLAY_TITLE
        keyboard = self._play_menu_keyboard()
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=keyboard)
        else:
            await update.effective_message.reply_text(text, reply_markup=keyboard)

    async def menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        data = query.data
        if data == MENU_PLAY:
            await self.show_play_menu(update, context)
        elif data == MENU_MAIN or data == BACK_TO_PLAY:
            await self.show_main_menu(update, context)
        elif data == MENU_PROFILE:
            await self.profile_menu(update, context)
        elif data == MENU_RATING:
            await self.ratings_command(update, context)
        elif data == MENU_SETTINGS:
            await self.settings_menu(update, context)
        elif data == MENU_HELP:
            await query.edit_message_text(locales.HELP_TEXT, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(locales.BTN_BACK, callback_data=MENU_MAIN)]]))
        elif data == MENU_ABOUT:
            await query.edit_message_text(locales.ABOUT_TEXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(locales.BTN_BACK, callback_data=MENU_MAIN)]]))
        elif data == PLAY_RATED:
            await self.quick_match(update, context, "rated")
        elif data == PLAY_CASUAL:
            await self.quick_match(update, context, "casual")
        elif data == INVITE_RATED:
            await self.create_invite(update, context, "rated")
        elif data == INVITE_CASUAL:
            await self.create_invite(update, context, "casual")
        elif data == JOIN_CODE:
            await query.edit_message_text(
                "Введіть код запрошення командою /join <код>",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(locales.BTN_BACK, callback_data=MENU_PLAY)]]),
            )
        elif data == MM_CANCEL:
            await self.cancel_matchmaking(update, context)

    async def cancel_matchmaking(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        self.matchmaking.cancel(user.id)
        await update.callback_query.edit_message_text("Пошук скасовано", reply_markup=self._play_menu_keyboard())

    async def quick_match(self, update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
        user = update.effective_user
        chat = update.effective_chat
        # Check active game
        if self.repo.get_user_game(user.id):
            await update.callback_query.answer("Завершіть поточну гру спочатку", show_alert=True)
            return

        ticket = await self.matchmaking.enqueue(user.id, chat.id, mode, user.username)
        text = f"{locales.SEARCHING_TITLE}\nРежим: {mode.upper()}\nРейтинг: {ticket.rating}"
        keyboard = self._searching_keyboard()
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
        await self.matchmaking_tick(context)

    async def create_invite(self, update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str):
        user = update.effective_user
        chat = update.effective_chat
        invite = self.matchmaking.create_invite(user.id, chat.id, mode)
        code = invite["code"]
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(locales.INVITE_SHARE, switch_inline_query=code)],
                [InlineKeyboardButton(locales.INVITE_CANCEL, callback_data=MM_CANCEL)],
                [InlineKeyboardButton(locales.BTN_BACK, callback_data=MENU_PLAY)],
            ]
        )
        await update.callback_query.edit_message_text(
            locales.INVITE_CREATED.format(code=code), parse_mode="HTML", reply_markup=keyboard
        )

    async def join_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Формат: /join ABC123")
            return
        code = context.args[0].strip().upper()
        user = update.effective_user
        chat = update.effective_chat
        invite = self.matchmaking.accept_invite(user.id, chat.id, code)
        if not invite:
            await update.message.reply_text("Запрошення не знайдено або вже використане.")
            return
        await update.message.reply_text("Готуємо гру...")
        await self._start_invite_match(invite, context)

    async def profile_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        rating = 1200
        games = wins = losses = 0
        if self.rating_system:
            data = await self.rating_system.get_player(user.id, user.username)
            rating = data.get("rating", rating)
            games = data.get("games_played", games)
            wins = data.get("wins", wins)
            losses = data.get("losses", losses)
        text = locales.PROFILE_TEMPLATE.format(
            name=user.full_name, rating=rating, games=games, wins=wins, losses=losses
        )
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(locales.BTN_BACK, callback_data=MENU_MAIN)]])
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=keyboard)
        else:
            await update.effective_message.reply_text(text, reply_markup=keyboard)

    async def settings_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(locales.SETTINGS_NOTIFICATIONS, callback_data=MENU_MAIN)],
                [InlineKeyboardButton(locales.SETTINGS_PREFER_RATED, callback_data=MENU_MAIN)],
                [InlineKeyboardButton(locales.BTN_BACK, callback_data=MENU_MAIN)],
            ]
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(locales.SETTINGS_TITLE, reply_markup=keyboard)
        else:
            await update.effective_message.reply_text(locales.SETTINGS_TITLE, reply_markup=keyboard)

    async def matchmaking_tick(self, context: ContextTypes.DEFAULT_TYPE):
        for mode in ("rated", "casual"):
            pairing = self.matchmaking.try_match(mode)
            if pairing:
                await self._start_paired_game(pairing, context)

    async def _start_invite_match(self, invite_data: dict, context: ContextTypes.DEFAULT_TYPE):
        try:
            opponent_id = int(invite_data.get("creator_user_id"))
            opponent_chat = int(invite_data.get("creator_chat_id"))
        except (TypeError, ValueError):
            return
        pairing = {
            "mode": invite_data.get("mode", "rated"),
            "users": [
                {"user_id": opponent_id, "chat_id": invite_data.get("creator_chat_id"), "rating": 1200},
                {"user_id": int(invite_data.get("opponent_user_id")), "chat_id": invite_data.get("opponent_chat_id"), "rating": 1200},
            ],
        }
        await self._start_paired_game(pairing, context)

    async def _start_paired_game(self, pairing: dict, context: ContextTypes.DEFAULT_TYPE):
        users = pairing.get("users", [])
        if len(users) < 2:
            return
        user_a, user_b = users[0], users[1]
        bot = context.bot

        # Fetch user info
        chat_a = await bot.get_chat(user_a["user_id"])
        chat_b = await bot.get_chat(user_b["user_id"])

        engine = CheckersEngine()
        now = datetime.utcnow().isoformat()

        # Assign colors based on ratings (higher rated gets red)
        red_player = chat_a if user_a.get("rating", 0) >= user_b.get("rating", 0) else chat_b
        white_player = chat_b if red_player == chat_a else chat_a
        red_id = red_player.id
        white_id = white_player.id

        game_state = {
            "board": engine.board,
            "current_turn": engine.current_turn,
            "red_player_id": red_id,
            "red_player_name": red_player.first_name,
            "white_player_id": white_id,
            "white_player_name": white_player.first_name,
            "created_at": now,
            "last_activity": now,
            "move_history": [],
            "initial_board": engine.board.copy(),
            "pending_capture": None,
            "is_private_match": True,
        }

        board_text = BoardRenderer.render(engine.board)
        players_msg = self._get_players_message(game_state)
        turn_msg = self._get_turn_message(game_state)
        keyboard = BoardRenderer.create_move_keyboard(engine, move_count=engine.move_count, pending_capture=None)
        message_text = f"{players_msg}\n\n{board_text}\n\n{turn_msg}"

        try:
            msg_a = await bot.send_message(chat_id=int(user_a["chat_id"]), text=message_text, reply_markup=keyboard, parse_mode="HTML")
            msg_b = await bot.send_message(chat_id=int(user_b["chat_id"]), text=message_text, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error("Failed to deliver match start: %s", e)
            self.repo.mm_cleanup_user(user_a["user_id"])
            self.repo.mm_cleanup_user(user_b["user_id"])
            return

        game_state["challenger_chat_id"] = msg_a.chat_id
        game_state["challenger_message_id"] = msg_a.message_id
        game_state["opponent_chat_id"] = msg_b.chat_id
        game_state["opponent_message_id"] = msg_b.message_id

        self.repo.save_game(msg_a.chat_id, msg_a.message_id, game_state)
        self.repo.save_game(msg_b.chat_id, msg_b.message_id, game_state)
        self.repo.mm_cleanup_user(user_a["user_id"])
        self.repo.mm_cleanup_user(user_b["user_id"])
    
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
            
            # Check rate limit for invitations (max 3 invites per minute)
            is_allowed, remaining = self.repo.check_rate_limit(
                user.id, "invite", max_actions=3, window_seconds=60
            )
            
            if not is_allowed:
                await update.message.reply_text(
                    "⏸️ Занадто багато запрошень! Будь ласка, зачекайте хвилину перед наступним запрошенням."
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
        # Check rate limit for group challenges (max 5 challenges per 2 minutes)
        is_allowed, remaining = self.repo.check_rate_limit(
            user.id, "challenge", max_actions=5, window_seconds=120
        )
        
        if not is_allowed:
            await update.message.reply_text(
                "⏸️ Занадто багато викликів! Будь ласка, зачекайте перед наступним викликом."
            )
            return
        
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
        
        user = query.from_user
        message = query.message
        
        # Check if this is an inline message (inline_message_id is present when callback is from inline mode)
        # For inline messages, query.inline_message_id is a string, and query.message is None
        inline_message_id = query.inline_message_id
        
        if inline_message_id:
            # Handle inline message join
            logger.info(f"Join callback for inline message: {inline_message_id}, user: {user.id}")
            
            # Get challenge from inline message first
            challenge_info = self.repo.get_inline_challenge(inline_message_id)
            
            # Fallback logic: if challenge not found but we have user_id in callback
            if not challenge_info:
                # Check if this is the new format join_{user_id}
                parts = query.data.split("_")
                if len(parts) >= 2 and parts[0] == "join":
                    try:
                        challenger_id = int(parts[1])
                        logger.info(f"Challenge not found, reconstructing from callback for challenger {challenger_id}")
                        
                        # Get challenger info
                        try:
                            challenger = await context.bot.get_chat(challenger_id)
                            challenge_info = {
                                "red_player_id": challenger.id,
                                "red_player_name": challenger.first_name,
                                "red_player_username": challenger.username,
                                "inline_message_id": inline_message_id
                            }
                        except Exception as e:
                            logger.error(f"Failed to get challenger info: {e}")
                    except ValueError:
                        pass
            
            if not challenge_info:
                logger.warning(f"No challenge found for inline_message_id: {inline_message_id}")
                await query.answer("Виклик закінчився або вже використаний", show_alert=True)
                return
            
            logger.info(f"Found challenge for inline message: {challenge_info}")
            
            # Don't allow challenger to play against themselves
            if user.id == challenge_info["red_player_id"]:
                await query.answer(locales.ERROR_SELF_PLAY, show_alert=True)
                return
            
            # Answer the callback (only once, before starting the game)
            await query.answer()
            
            try:
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
                    "last_activity": now,
                    "is_inline": True,
                    "inline_message_id": inline_message_id,
                    "move_history": [],
                    "initial_board": engine.board.copy(),
                    "pending_capture": None
                }
                
                # Save inline game
                success = self.repo.save_inline_game(inline_message_id, game_state)
                if not success:
                    logger.error(f"Failed to save inline game for {inline_message_id}")
                    await query.answer("Помилка при збереженні гри", show_alert=True)
                    return
                
                # Delete challenge
                self.repo.delete_inline_challenge(inline_message_id)
                
                # Update inline message
                await self._update_inline_game_message(context.bot, inline_message_id, engine, game_state)
                logger.info(f"Successfully started inline game for {inline_message_id}")
            except Exception as e:
                logger.error(f"Error starting inline game: {e}", exc_info=True)
                try:
                    await query.answer("Помилка при створенні гри", show_alert=True)
                except Exception:
                    pass
            return
        
        # Regular group chat flow
        # Answer the callback for regular messages
        await query.answer()
        
        if not message or not message.chat:
            try:
                await context.bot.answer_callback_query(
                    query.id,
                    text="Помилка: не вдалося визначити чат",
                    show_alert=True
                )
            except Exception:
                pass
            return
            
        chat = message.chat
        message_id = message.message_id
            
        # Get challenge info
        challenge_key = f"challenge_{message_id}"
        challenge_info = context.chat_data.get(challenge_key)
        
        if not challenge_info:
            await query.edit_message_text(locales.ERROR_NO_GAME)
            return
        
        # Don't allow challenger to play against themselves
        if user.id == challenge_info["red_player_id"]:
            await query.answer(locales.ERROR_SELF_PLAY, show_alert=True)
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
            "last_activity": now,
            "move_history": [],
            "initial_board": engine.board.copy(),
            "pending_capture": None
        }
        
        # Save to Redis
        self.repo.save_game(chat.id, message_id, game_state)
        
        # Clean up challenge data
        del context.chat_data[challenge_key]
        
        # Show game board
        await self._update_game_message(message, engine, game_state, context)
    
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
        
        # Check rate limit for invite actions
        is_allowed, _ = self.repo.check_rate_limit(
            user.id, "invite_action", max_actions=10, window_seconds=60
        )
        
        if not is_allowed:
            await query.answer("⏸️ Занадто багато дій! Будь ласка, зачекайте.", show_alert=True)
            return
        
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
            "challenger_chat_id": invite_info["challenger_chat_id"],
            "move_history": [],
            "initial_board": engine.board.copy(),
            "pending_capture": None
        }
        
        # For private matches, we need to send board messages to BOTH players
        opponent_chat_id = query.message.chat.id
        challenger_chat_id = invite_info["challenger_chat_id"]
        
        try:
            # Create board display
            board_text = BoardRenderer.render(engine.board)
            players_msg = self._get_players_message(game_state)
            turn_msg = self._get_turn_message(game_state)
            keyboard = BoardRenderer.create_move_keyboard(engine, move_count=engine.move_count, pending_capture=game_state.get("pending_capture"))
            
            game_message_text = f"{players_msg}\n\n{board_text}\n\n{turn_msg}"
            
            # Send game board to OPPONENT's chat (where they accepted)
            opponent_game_message = await context.bot.send_message(
                chat_id=opponent_chat_id,
                text=game_message_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            # Send game board to CHALLENGER's chat (with same buttons)
            challenger_game_message = await context.bot.send_message(
                chat_id=challenger_chat_id,
                text=game_message_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            # Store both message IDs for private matches
            game_state["opponent_chat_id"] = opponent_chat_id
            game_state["opponent_message_id"] = opponent_game_message.message_id
            game_state["challenger_chat_id"] = challenger_chat_id
            game_state["challenger_message_id"] = challenger_game_message.message_id
            
            # Save game state (keyed by opponent's chat as primary, but both are stored)
            self.repo.save_game(opponent_chat_id, opponent_game_message.message_id, game_state)
            # Also save a reference in challenger's chat for easier lookup
            self.repo.save_game(challenger_chat_id, challenger_game_message.message_id, game_state)
            
            # Update the original invite message
            await query.answer("Гра розпочалась!")
            await query.edit_message_text(
                f"✅ Ви прийняли виклик від <b>{invite_info['challenger_name']}</b>!\n"
                f"⬇️ Дивіться дошку нижче.",
                parse_mode="HTML"
            )
            
        except Exception as e:
            await query.answer("❌ Помилка при створенні гри.", show_alert=True)
            await query.edit_message_text(
                f"❌ Не вдалося створити гру: {str(e)}"
            )
    
    async def decline_private_invite_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle declining a private game invitation."""
        query = update.callback_query
        user = query.from_user
        
        # Check rate limit for invite actions
        is_allowed, _ = self.repo.check_rate_limit(
            user.id, "invite_action", max_actions=10, window_seconds=60
        )
        
        if not is_allowed:
            await query.answer("⏸️ Занадто багато дій! Будь ласка, зачекайте.", show_alert=True)
            return
        
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
        user_id = query.from_user.id
        
        # Check rate limit for callbacks (max 20 actions per 10 seconds)
        is_allowed, _ = self.repo.check_rate_limit(
            user_id, "callback", max_actions=20, window_seconds=10
        )
        
        if not is_allowed:
            await query.answer("⏸️ Занадто швидко! Будь ласка, зачекайте трохи.", show_alert=True)
            return
        
        await query.answer()
        
        # Parse callback data
        _, pos_str = query.data.split("_")
        selected_pos = int(pos_str)
        
        # Check if this is an inline message
        inline_message_id = query.inline_message_id
        
        if inline_message_id:
            # Get inline game state
            game_state = self._get_game_state(inline_message_id=inline_message_id)
            if not game_state:
                await query.answer(locales.ERROR_NO_GAME, show_alert=True)
                return
        else:
            # Regular message
            if not query.message or not query.message.chat:
                await query.answer("Помилка: не вдалося визначити чат", show_alert=True)
                return
            chat_id = query.message.chat.id
            message_id = query.message.message_id
            game_state = self._get_game_state(chat_id, message_id)
            
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
        
        keyboard = BoardRenderer.create_move_keyboard(engine, selected_pos, engine.move_count, pending_capture=game_state.get("pending_capture"))
        message_text = f"{board_text}\n\n{turn_msg}\n\n✅ Обрано: позиція {selected_pos}"
        
        # Check if this is an inline message
        if inline_message_id:
            try:
                await context.bot.edit_message_text(
                    inline_message_id=inline_message_id,
                    text=message_text,
                    reply_markup=keyboard
                )
            except Exception:
                pass  # Ignore errors
        # For private matches, update both players' messages
        elif game_state.get("is_private_match"):
            try:
                # Update opponent's message
                await context.bot.edit_message_text(
                    chat_id=game_state["opponent_chat_id"],
                    message_id=game_state["opponent_message_id"],
                    text=message_text,
                    reply_markup=keyboard
                )
            except Exception:
                pass  # Ignore errors
            
            try:
                # Update challenger's message
                await context.bot.edit_message_text(
                    chat_id=game_state["challenger_chat_id"],
                    message_id=game_state["challenger_message_id"],
                    text=message_text,
                    reply_markup=keyboard
                )
            except Exception:
                pass  # Ignore errors
        else:
            # Regular group chat - just update the one message
            try:
                await query.edit_message_text(
                    message_text,
                    reply_markup=keyboard
                )
            except Exception:
                pass  # Ignore "Message is not modified" errors
    
    async def move_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle move execution."""
        query = update.callback_query
        user_id = query.from_user.id
        
        # Check rate limit for callbacks (max 20 actions per 10 seconds)
        is_allowed, _ = self.repo.check_rate_limit(
            user_id, "callback", max_actions=20, window_seconds=10
        )
        
        if not is_allowed:
            await query.answer("⏸️ Занадто швидко! Будь ласка, зачекайте трохи.", show_alert=True)
            return
        
        await query.answer()
        
        # Parse callback data: move_from_to
        _, from_str, to_str = query.data.split("_")
        from_pos = int(from_str)
        to_pos = int(to_str)
        
        # Check if this is an inline message
        inline_message_id = query.inline_message_id
        
        if inline_message_id:
            game_state = self._get_game_state(inline_message_id=inline_message_id)
            if not game_state:
                await query.answer(locales.ERROR_NO_GAME, show_alert=True)
                return
        else:
            if not query.message or not query.message.chat:
                await query.answer("Помилка: не вдалося визначити чат", show_alert=True)
                return
            chat_id = query.message.chat.id
            message_id = query.message.message_id
            game_state = self._get_game_state(chat_id, message_id)
            
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
        
        # Verify the selected piece belongs to the current player
        piece_at_from = engine.board[from_pos]
        piece_color = engine.get_piece_color(piece_at_from)
        
        if piece_color != engine.current_turn:
            await query.answer("❌ Ви не можете рухати фігуру суперника!", show_alert=True)
            return
        
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
        
        # Record move in history before applying
        move_record = {
            "from": move_to_apply.from_pos,
            "to": move_to_apply.to_pos,
            "captures": move_to_apply.captures.copy() if move_to_apply.captures else [],
            "board_before": engine.board.copy(),
            "player": "red" if engine.current_turn == RED else "white"
        }
        game_state.setdefault("move_history", []).append(move_record)
        
        # Apply move
        engine.apply_move(move_to_apply)
        
        # Check if this was a capture and if player must continue
        must_continue = False
        if move_to_apply.captures:
            # Check if more captures are mandatory from landing position
            must_continue = engine.must_continue_capturing(move_to_apply.to_pos)
        
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
            
            # Save completed game for replay
            game_id = str(uuid.uuid4())[:8]
            completed_game_data = {
                "game_id": game_id,
                "red_player_id": game_state["red_player_id"],
                "red_player_name": game_state["red_player_name"],
                "white_player_id": game_state["white_player_id"],
                "white_player_name": game_state["white_player_name"],
                "winner_id": winner_id,
                "winner_name": winner_name,
                "winner_color": "red" if winner == RED else "white",
                "initial_board": game_state.get("initial_board", CheckersEngine.init_board()),
                "move_history": game_state.get("move_history", []),
                "final_board": engine.board.copy(),
                "completed_at": datetime.utcnow().isoformat()
            }
            completed_at = completed_game_data["completed_at"]
            self.game_data_repo.save_completed_game(completed_game_data)
            # Add reference for both players
            self.game_data_repo.add_user_game_reference(game_state["red_player_id"], game_id, completed_at)
            self.game_data_repo.add_user_game_reference(game_state["white_player_id"], game_id, completed_at)
            
            # keyboard = InlineKeyboardMarkup([[
            #     InlineKeyboardButton(locales.BTN_NEW_GAME, callback_data="new_game")
            # ]])
            
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("📺 Переглянути гру", callback_data=f"replay_{game_id}_0")
            ]])
            
            final_message = f"{board_text}\n\n{win_msg}"

            
            # Check if this is an inline message
            if inline_message_id:
                try:
                    await context.bot.edit_message_text(
                        inline_message_id=inline_message_id,
                        text=final_message,
                        reply_markup=keyboard
                    )
                except Exception:
                    pass  # Ignore errors
                # Delete inline game
                self.repo.delete_inline_game(inline_message_id)
            # For private matches, update both players' messages
            elif game_state.get("is_private_match"):
                try:
                    # Update opponent's message
                    await context.bot.edit_message_text(
                        chat_id=game_state["opponent_chat_id"],
                        message_id=game_state["opponent_message_id"],
                        text=final_message,
                        reply_markup=keyboard
                    )
                except Exception:
                    pass  # Ignore errors
                
                try:
                    # Update challenger's message
                    await context.bot.edit_message_text(
                        chat_id=game_state["challenger_chat_id"],
                        message_id=game_state["challenger_message_id"],
                        text=final_message,
                        reply_markup=keyboard
                    )
                except Exception:
                    pass  # Ignore errors
                
                # Delete game from both chats
                self.repo.delete_game(game_state["opponent_chat_id"], game_state["opponent_message_id"])
                self.repo.delete_game(game_state["challenger_chat_id"], game_state["challenger_message_id"])
            else:
                # Regular group chat
                await query.edit_message_text(
                    final_message,
                    reply_markup=keyboard
                )
                
                # Delete game from Redis
                self.repo.delete_game(chat_id, message_id)
        else:
            # Game continues - update state
            game_state["board"] = engine.board
            game_state["move_count"] = engine.move_count
            game_state["last_activity"] = datetime.utcnow().isoformat()
            
            # Handle pending capture (mandatory continuation)
            if must_continue:
                # Set pending capture - turn does NOT switch
                game_state["pending_capture"] = {
                    "pos": move_to_apply.to_pos,
                    "must_continue": True
                }
                # Keep current_turn the same
                game_state["current_turn"] = engine.current_turn
            else:
                # Clear pending capture and switch turns normally
                game_state["pending_capture"] = None
                game_state["current_turn"] = engine.current_turn
            
            # Check if this is an inline message
            if inline_message_id:
                self.repo.save_inline_game(inline_message_id, game_state)
                # Show updated board using inline message update
                await self._update_inline_game_message(context.bot, inline_message_id, engine, game_state)
            else:
                self.repo.save_game(chat_id, message_id, game_state)
                
                # For private matches, also save to the other player's chat
                if game_state.get("is_private_match"):
                    # Save to challenger's chat
                    self.repo.save_game(
                        game_state["challenger_chat_id"],
                        game_state["challenger_message_id"],
                        game_state
                    )
                    # Save to opponent's chat
                    self.repo.save_game(
                        game_state["opponent_chat_id"],
                        game_state["opponent_message_id"],
                        game_state
                    )
                
                # Show updated board
                await self._update_game_message(query.message, engine, game_state, context)
    
    async def back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle back button - return to piece selection."""
        query = update.callback_query
        await query.answer()
        
        # Check if this is an inline message
        inline_message_id = query.inline_message_id
        
        if inline_message_id:
            game_state = self._get_game_state(inline_message_id=inline_message_id)
            if not game_state:
                await query.answer(locales.ERROR_NO_GAME, show_alert=True)
                return
        else:
            if not query.message or not query.message.chat:
                await query.answer("Помилка: не вдалося визначити чат", show_alert=True)
                return
            chat_id = query.message.chat.id
            message_id = query.message.message_id
            game_state = self._get_game_state(chat_id, message_id)
            
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
        if inline_message_id:
            await self._update_inline_game_message(context.bot, inline_message_id, engine, game_state)
        else:
            await self._update_game_message(query.message, engine, game_state, context)
    
    async def forfeit_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle forfeit/cancel button."""
        query = update.callback_query
        await query.answer()
        
        # Check if this is an inline message
        inline_message_id = query.inline_message_id
        
        if inline_message_id:
            game_state = self._get_game_state(inline_message_id=inline_message_id)
            if not game_state:
                await query.answer(locales.ERROR_NO_GAME, show_alert=True)
                return
        else:
            if not query.message or not query.message.chat:
                await query.answer("Помилка: не вдалося визначити чат", show_alert=True)
                return
            chat_id = query.message.chat.id
            message_id = query.message.message_id
            game_state = self._get_game_state(chat_id, message_id)
            
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
            
            cancel_message = f"{board_text}\n\n{win_msg}"
            
            # Check if this is an inline message
            if inline_message_id:
                try:
                    await context.bot.edit_message_text(
                        inline_message_id=inline_message_id,
                        text=cancel_message,
                        reply_markup=None
                    )
                except Exception:
                    pass
                self.repo.delete_inline_game(inline_message_id)
            # For private matches, update both players' messages
            elif game_state.get("is_private_match"):
                try:
                    await context.bot.edit_message_text(
                        chat_id=game_state["opponent_chat_id"],
                        message_id=game_state["opponent_message_id"],
                        text=cancel_message,
                        reply_markup=None
                    )
                except Exception:
                    pass
                
                try:
                    await context.bot.edit_message_text(
                        chat_id=game_state["challenger_chat_id"],
                        message_id=game_state["challenger_message_id"],
                        text=cancel_message,
                        reply_markup=None
                    )
                except Exception:
                    pass
                
                # Delete game from both chats
                self.repo.delete_game(game_state["opponent_chat_id"], game_state["opponent_message_id"])
                self.repo.delete_game(game_state["challenger_chat_id"], game_state["challenger_message_id"])
            else:
                if not inline_message_id:  # Only edit if not inline (already handled above)
                    await query.edit_message_text(
                        cancel_message,
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
        
        forfeit_message = f"{board_text}\n\n{win_msg}"
        
        # Check if this is an inline message
        if inline_message_id:
            try:
                await context.bot.edit_message_text(
                    inline_message_id=inline_message_id,
                    text=forfeit_message,
                    reply_markup=None
                )
            except Exception:
                pass
            self.repo.delete_inline_game(inline_message_id)
        # For private matches, update both players' messages
        elif game_state.get("is_private_match"):
            try:
                await context.bot.edit_message_text(
                    chat_id=game_state["opponent_chat_id"],
                    message_id=game_state["opponent_message_id"],
                    text=forfeit_message,
                    reply_markup=None
                )
            except Exception:
                pass
            
            try:
                await context.bot.edit_message_text(
                    chat_id=game_state["challenger_chat_id"],
                    message_id=game_state["challenger_message_id"],
                    text=forfeit_message,
                    reply_markup=None
                )
            except Exception:
                pass
            
            # Delete game from both chats
            self.repo.delete_game(game_state["opponent_chat_id"], game_state["opponent_message_id"])
            self.repo.delete_game(game_state["challenger_chat_id"], game_state["challenger_message_id"])
        else:
            if not inline_message_id:  # Only edit if not inline (already handled above)
                await query.edit_message_text(
                    forfeit_message,
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
        game_state = self._get_game_state(game_chat_id, game_message_id)
        
        if not game_state:
            await query.answer("❌ Гра вже закінчилась.", show_alert=True)
            await query.edit_message_text("❌ Гра вже закінчилась.")
            return
        
        # Verify user is a player
        if user.id != game_state["red_player_id"] and user.id != game_state["white_player_id"]:
            await query.answer("❌ Ви не є гравцем у цій грі!", show_alert=True)
            return
        
        # Cancel the game
        cancel_message = "🚫 Гра скасована. Рейтинг не змінено."
        
        # For private matches, update both players' messages
        if game_state.get("is_private_match"):
            try:
                await context.bot.edit_message_text(
                    chat_id=game_state["opponent_chat_id"],
                    message_id=game_state["opponent_message_id"],
                    text=cancel_message
                )
            except Exception:
                pass
            
            try:
                await context.bot.edit_message_text(
                    chat_id=game_state["challenger_chat_id"],
                    message_id=game_state["challenger_message_id"],
                    text=cancel_message
                )
            except Exception:
                pass
            
            # Delete game from both chats
            self.repo.delete_game(game_state["opponent_chat_id"], game_state["opponent_message_id"])
            self.repo.delete_game(game_state["challenger_chat_id"], game_state["challenger_message_id"])
        else:
            # Update game message
            try:
                await context.bot.edit_message_text(
                    chat_id=game_chat_id,
                    message_id=game_message_id,
                    text=cancel_message
                )
            except Exception:
                pass
            
            # Delete game
            self.repo.delete_game(game_chat_id, game_message_id)
        
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
        game_state = self._get_game_state(game_chat_id, game_message_id)
        
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
        forfeit_message = f"🏳️ <b>{user.first_name}</b> здався!\n\n🏆 Переможець: <b>{winner_name}</b>{rating_msg}"
        
        # For private matches, update both players' messages
        if game_state.get("is_private_match"):
            try:
                await context.bot.edit_message_text(
                    chat_id=game_state["opponent_chat_id"],
                    message_id=game_state["opponent_message_id"],
                    text=forfeit_message,
                    parse_mode="HTML"
                )
            except Exception:
                pass
            
            try:
                await context.bot.edit_message_text(
                    chat_id=game_state["challenger_chat_id"],
                    message_id=game_state["challenger_message_id"],
                    text=forfeit_message,
                    parse_mode="HTML"
                )
            except Exception:
                pass
            
            # Delete game from both chats
            self.repo.delete_game(game_state["opponent_chat_id"], game_state["opponent_message_id"])
            self.repo.delete_game(game_state["challenger_chat_id"], game_state["challenger_message_id"])
        else:
            # Update game message
            try:
                await context.bot.edit_message_text(
                    chat_id=game_chat_id,
                    message_id=game_message_id,
                    text=forfeit_message,
                    parse_mode="HTML"
                )
            except Exception:
                pass
            
            # Delete game
            self.repo.delete_game(game_chat_id, game_message_id)
        
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
    
    async def _update_game_message(self, message, engine: CheckersEngine, game_state: dict, context: ContextTypes.DEFAULT_TYPE = None):
        """Update game message with current board and turn info."""
        board_text = BoardRenderer.render(engine.board)
        players_msg = self._get_players_message(game_state)
        turn_msg = self._get_turn_message(game_state)
        keyboard = BoardRenderer.create_move_keyboard(engine, move_count=engine.move_count, pending_capture=game_state.get("pending_capture"))
        
        message_text = f"{players_msg}\n\n{board_text}\n\n{turn_msg}"
        
        # Check if this is an inline message
        if game_state.get("is_inline") and context:
            inline_message_id = game_state.get("inline_message_id")
            if inline_message_id:
                await self._update_inline_game_message(context.bot, inline_message_id, engine, game_state)
                return
        
        # For private matches, update both players' messages
        if game_state.get("is_private_match") and context:
            try:
                # Update opponent's message
                await context.bot.edit_message_text(
                    chat_id=game_state["opponent_chat_id"],
                    message_id=game_state["opponent_message_id"],
                    text=message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception:
                pass  # Ignore errors (message might be deleted or unchanged)
            
            try:
                # Update challenger's message
                await context.bot.edit_message_text(
                    chat_id=game_state["challenger_chat_id"],
                    message_id=game_state["challenger_message_id"],
                    text=message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception:
                pass  # Ignore errors (message might be deleted or unchanged)
        else:
            # Regular group chat - just update the one message
            await message.edit_text(
                message_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    
    async def _update_inline_game_message(
        self,
        bot,
        inline_message_id: str,
        engine: CheckersEngine,
        game_state: dict
    ):
        """Update inline message with current game state."""
        board_text = BoardRenderer.render(engine.board)
        players_msg = self._get_players_message(game_state)
        turn_msg = self._get_turn_message(game_state)
        keyboard = BoardRenderer.create_move_keyboard(engine, move_count=engine.move_count, pending_capture=game_state.get("pending_capture"))
        
        message_text = f"{players_msg}\n\n{board_text}\n\n{turn_msg}"
        
        try:
            await bot.edit_message_text(
                inline_message_id=inline_message_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error updating inline message: {e}")
    
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
        """Get message showing both players with hyperlinked first names."""
        red_player_id = game_state.get("red_player_id")
        red_player_name = game_state["red_player_name"]
        white_player_id = game_state.get("white_player_id")
        white_player_name = game_state["white_player_name"]
        
        # Create hyperlinked first names
        red_tag = f'<a href="tg://user?id={red_player_id}">{red_player_name}</a>' if red_player_id else red_player_name
        white_tag = f'<a href="tg://user?id={white_player_id}">{white_player_name}</a>' if white_player_id else white_player_name
        
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
        message = update.message or update.effective_message

        if not self.rating_system:
            await message.reply_text("Система рейтингу недоступна.")
            return

        edit = bool(update.callback_query)
        if update.callback_query:
            await update.callback_query.answer()

        await self._send_leaderboard(message, page=0, edit=edit)
    
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

    # ============ Game Replay Handlers ============
    
    async def replay_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /checkersreplay command - show list of recent games for replay."""
        user = update.effective_user
        
        # Get user's completed games
        game_ids = self.game_data_repo.get_user_completed_games(user.id, limit=10)
        
        if not game_ids:
            await update.message.reply_text(
                "📺 <b>Історія ігор</b>\n\n"
                "У вас ще немає завершених ігор для перегляду.",
                parse_mode="HTML"
            )
            return
        
        # Build list of games
        buttons = []
        text = "📺 <b>Історія ваших ігор</b>\n\n"
        text += "Оберіть гру для перегляду:\n\n"
        
        for i, game_id in enumerate(game_ids, 1):
            game_data = self.game_data_repo.get_completed_game(game_id)
            if game_data:
                opponent_name = (game_data["white_player_name"] 
                               if game_data["red_player_id"] == user.id 
                               else game_data["red_player_name"])
                result = "🏆" if game_data["winner_id"] == user.id else "❌"
                move_count = len(game_data.get("move_history", []))
                
                text += f"{i}. {result} vs {opponent_name} ({move_count} ходів)\n"
                buttons.append([
                    InlineKeyboardButton(
                        f"{result} vs {opponent_name}", 
                        callback_data=f"replay_{game_id}_0"
                    )
                ])
        
        keyboard = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    async def replay_game_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle replay navigation - show board at specific move."""
        query = update.callback_query
        await query.answer()
        
        # Parse callback: replay_{game_id}_{move_number}
        parts = query.data.split("_")
        if len(parts) != 3:
            await query.answer("❌ Неправильний формат", show_alert=True)
            return
        
        game_id = parts[1]
        move_num = int(parts[2])
        
        # Get game data
        game_data = self.game_data_repo.get_completed_game(game_id)
        if not game_data:
            await query.answer("❌ Гру не знайдено", show_alert=True)
            return
        
        move_history = game_data.get("move_history", [])
        total_moves = len(move_history)
        
        # Get board state at this move
        if move_num == 0:
            # Initial board
            board = game_data.get("initial_board", CheckersEngine.init_board())
            move_info = "🎬 Початкова позиція"
        elif move_num <= total_moves:
            # Board AFTER move (move_num - 1)
            move_record = move_history[move_num - 1]
            board = move_record.get("board_before", CheckersEngine.init_board())
            
            # Actually we need to show the board AFTER the move
            # So we need to get the next move's board_before, or final_board if last move
            if move_num < total_moves:
                board = move_history[move_num].get("board_before", board)
            else:
                board = game_data.get("final_board", board)
            
            player_color = "🔴" if move_record["player"] == "red" else "⚪"
            from_pos = move_record["from"]
            to_pos = move_record["to"]
            captures = move_record.get("captures", [])
            capture_text = f" (x{len(captures)})" if captures else ""
            move_info = f"Хід {move_num}: {player_color} {from_pos}→{to_pos}{capture_text}"
        else:
            board = game_data.get("final_board", CheckersEngine.init_board())
            move_info = "🏁 Фінальна позиція"
        
        # Render board
        board_text = BoardRenderer.render(board)
        
        # Game info
        info_text = (
            f"📺 <b>Перегляд гри</b>\n"
            f"🔴 {game_data['red_player_name']} vs ⚪ {game_data['white_player_name']}\n"
            f"🏆 Переможець: {game_data['winner_name']}\n\n"
            f"{board_text}\n\n"
            f"{move_info}\n"
            f"[{move_num}/{total_moves}]"
        )
        
        # Navigation buttons
        nav_buttons = []
        if move_num > 0:
            nav_buttons.append(InlineKeyboardButton("⏮️", callback_data=f"replay_{game_id}_0"))
            nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"replay_{game_id}_{move_num - 1}"))
        if move_num < total_moves:
            nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"replay_{game_id}_{move_num + 1}"))
            nav_buttons.append(InlineKeyboardButton("⏭️", callback_data=f"replay_{game_id}_{total_moves}"))
        
        keyboard = InlineKeyboardMarkup([nav_buttons]) if nav_buttons else None
        
        try:
            await query.edit_message_text(
                info_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception:
            pass  # Ignore "Message is not modified" errors

    # ============ Inline Mode Handlers ============

    
    async def inline_query_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline queries when user types @botname."""
        query = update.inline_query
        user = query.from_user
        
        # Register user
        self.repo.register_user(user.id, user.username, user.first_name)
        
        # Parse query
        query_text = query.query.strip().lower() if query.query else ""
        
        results = []
        
        # Default: Show "Start Challenge" option
        if not query_text or query_text in ["play", "start", "game"]:
            results.append(
                InlineQueryResultArticle(
                    id="challenge",
                    title="🎮 Надіслати запрошення в шашки",
                    description="Створити виклик, до якого може приєднатися будь-хто",
                    input_message_content=InputTextMessageContent(
                        message_text=f"🎮 <b>Виклик до гри в Шашки!</b>\n\n"
                                    f"{user.first_name} викликає на партію в Українські Шашки!\n"
                                    "Хто зіграє за Білих (⚪)?",
                        parse_mode=ParseMode.HTML
                    ),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⚔️ До бою!", callback_data=f"join_{user.id}")
                    ]])
                )
            )
        
        # If query contains @username or "challenge", show challenge option
        elif "@" in query_text or "challenge" in query_text:
            # Extract username if present
            username = None
            query_parts = query_text.split()
            
            for part in query_parts:
                if part.startswith("@"):
                    username = part[1:]
                    break
                elif part == "challenge" and query_parts.index(part) + 1 < len(query_parts):
                    next_part = query_parts[query_parts.index(part) + 1]
                    if next_part.startswith("@"):
                        username = next_part[1:]
                    else:
                        username = next_part
                    break
            
            if username:
                # Check if user exists
                opponent_info = self.repo.get_user_by_username(username)
                if opponent_info:
                    results.append(
                        InlineQueryResultArticle(
                            id=f"challenge_{username}",
                            title=f"🎮 Викликати @{username}",
                            description=f"Викликати {opponent_info['first_name']} на гру",
                            input_message_content=InputTextMessageContent(
                                message_text=f"🎮 <b>{user.first_name}</b> викликає <b>@{username}</b> на гру в Українські Шашки!",
                                parse_mode=ParseMode.HTML
                            ),
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("✅ Прийняти виклик", callback_data=f"accept_inline_{username}")
                            ]])
                        )
                    )
                else:
                    results.append(
                        InlineQueryResultArticle(
                            id="user_not_found",
                            title="❌ Користувача не знайдено",
                            description=f"@{username} ще не використовував цього бота",
                            input_message_content=InputTextMessageContent(
                                message_text=f"❌ Користувача @{username} не знайдено.\n\n"
                                            "Користувач повинен спочатку використати /start з цим ботом."
                            )
                        )
                    )
            else:
                # Show challenge option
                results.append(
                    InlineQueryResultArticle(
                        id="challenge",
                        title="🎮 Створити виклик",
                        description="Введіть: @botname challenge @username",
                        input_message_content=InputTextMessageContent(
                            message_text="🎮 Виклик до гри в Шашки! Натисніть, щоб приєднатися.",
                            parse_mode=ParseMode.HTML
                        )
                    )
                )
        
        # If no results yet, show default
        if not results:
            results.append(
                InlineQueryResultArticle(
                    id="challenge",
                    title="🎮 Надіслати запрошення в шашки",
                    description="Створити виклик, до якого може приєднатися будь-хто",
                    input_message_content=InputTextMessageContent(
                        message_text=f"🎮 <b>Виклик до гри в Шашки!</b>\n\n"
                                    f"{user.first_name} викликає на партію в Українські Шашки!\n"
                                    "Хто зіграє за Білих (⚪)?",
                        parse_mode=ParseMode.HTML
                    ),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⚔️ До бою!", callback_data=f"join_{user.id}")
                    ]])
                )
            )
        
        # Answer the inline query (cache for 1 second)
        await query.answer(results, cache_time=1)

    async def chosen_inline_result_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle when user selects an inline result."""
        chosen_result = update.chosen_inline_result
        user = chosen_result.from_user
        result_id = chosen_result.result_id
        inline_message_id = chosen_result.inline_message_id
        
        if not inline_message_id:
            logger.warning(f"Chosen inline result without inline_message_id: {result_id}")
            return  # Should not happen, but safety check
        
        # Register user
        self.repo.register_user(user.id, user.username, user.first_name)
        
        logger.info(f"Chosen inline result: {result_id}, inline_message_id: {inline_message_id}, user: {user.id}")
        
        if result_id == "challenge":
            # Create a challenge game
            challenge_data = {
                "red_player_id": user.id,
                "red_player_name": user.first_name,
                "red_player_username": user.username,
                "inline_message_id": inline_message_id,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Store challenge in Redis
            success = self.repo.save_inline_challenge(inline_message_id, challenge_data)
            if success:
                logger.info(f"Saved inline challenge for {inline_message_id}")
            else:
                logger.error(f"Failed to save inline challenge for {inline_message_id}")
        
        elif result_id.startswith("challenge_"):
            # Direct challenge to specific user
            username = result_id.replace("challenge_", "")
            opponent_info = self.repo.get_user_by_username(username)
            
            if opponent_info:
                # Create invite similar to private invites but for inline
                invite_id = str(uuid.uuid4())[:8]
                
                # Store challenge data
                challenge_data = {
                    "red_player_id": user.id,
                    "red_player_name": user.first_name,
                    "red_player_username": user.username,
                    "opponent_id": opponent_info["user_id"],
                    "opponent_username": username,
                    "inline_message_id": inline_message_id,
                    "invite_id": invite_id,
                    "created_at": datetime.utcnow().isoformat()
                }
                
                self.repo.save_inline_challenge(inline_message_id, challenge_data)
                
                # Try to notify opponent (they must have started the bot)
                try:
                    # We'll handle this in the accept callback
                    pass
                except Exception:
                    pass  # Can't notify, but challenge is still valid

