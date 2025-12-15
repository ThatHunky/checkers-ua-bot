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
            pending_pos = pending_capture.get("pos")
            # If no follow-up captures remain, fall back to normal selection
            if not engine.must_continue_capturing(pending_pos):
                pending_capture = None
            else:
                # Only show single-hop captures from the pending position
                legal_moves = engine.find_single_hop_captures(pending_pos)
                movable_positions = {pending_pos}
                selected_pos = pending_pos  # Auto-select the piece

        if not pending_capture:
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

    # ------------------------------------------------------------------
    # High-level menu + matchmaking helpers (lightweight implementations)
    # ------------------------------------------------------------------

    async def start_bot_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start - show the main menu in private chat."""
        await self.menu_command(update, context)

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show the main menu (private chats only)."""
        chat = update.effective_chat
        message = update.effective_message

        if not self._is_private_chat(chat):
            await message.reply_text(locales.MENU_PRIVATE_ONLY)
            return

        await self._send_main_menu(message)

    async def menu_text_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text-based menu triggers in the same way as the /menu command."""
        message = update.effective_message
        text = (message.text or "").strip().lower() if message else ""

        triggers = {"/menu", "menu", "меню"}

        # Recognize bot-mention variants like /menu@YourBotName
        if text.startswith("/menu@"):
            return await self.menu_command(update, context)

        if text in triggers:
            return await self.menu_command(update, context)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Entry point for /checkersplay - show play modes."""
        chat = update.effective_chat
        message = update.effective_message

        if not self._is_private_chat(chat):
            await message.reply_text(locales.MENU_PRIVATE_ONLY)
            return

        await self._send_play_menu(message)

    async def replay_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Placeholder for game history until full UI is implemented."""
        await update.effective_message.reply_text(
            "📺 Перегляд історії ігор тимчасово недоступний. Спробуйте пізніше."
        )

    async def inline_query_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle inline queries (currently used for sharing invite codes)."""

        query = update.inline_query
        query_text = (query.query or "").strip()

        # If the inline query is empty, gently discourage inline usage for now
        if not query_text:
            results = [
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title="Надішліть код запрошення",
                    description=(
                        "Створіть запрошення у приваті з ботом та вкажіть код тут, "
                        "щоб поділитися ним у чаті."
                    ),
                    input_message_content=InputTextMessageContent(
                        "Щоб поділитися запрошенням, спочатку створіть код у меню бота."
                    ),
                )
            ]
            await query.answer(results, cache_time=0, is_personal=True)
            return

        # Provide a simple inline share message with the supplied code
        share_text = (
            "🎲 Гра в шашки!\n"
            f"Код запрошення: {query_text}\n"
            "Приєднуйтесь через /join <код>."
        )

        results = [
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=f"Поділитися кодом {query_text}",
                description="Надіслати запрошення на гру",
                input_message_content=InputTextMessageContent(share_text),
            )
        ]

        await query.answer(results, cache_time=0, is_personal=True)

    async def chosen_inline_result_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle selection of inline results (currently a no-op)."""

        result = update.chosen_inline_result
        logger.info("Inline result chosen: %s", result)

    async def join_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Join an invite by code (if created via the menu)."""
        message = update.effective_message
        args = context.args or []
        if not args:
            await message.reply_text("Використання: /join <код запрошення>")
            return

        code = args[0].strip().upper()
        result = self.matchmaking.accept_invite(
            update.effective_user.id, message.chat_id, code
        )
        if not result:
            await message.reply_text("❌ Запрошення не знайдено або вже використано.")
            return

        creator = result.get("creator_user_id")
        await message.reply_text(
            f"✅ Ви приєдналися до запрошення {code}. "
            f"Створіть нову гру разом із користувачем {creator}."
        )

    async def menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle menu navigation callbacks."""
        query = update.callback_query
        await query.answer()

        data = query.data

        if data == MENU_MAIN:
            await self._send_main_menu(query.message, edit=True)
        elif data == MENU_PLAY:
            await self._send_play_menu(query.message, edit=True)
        elif data == MENU_PROFILE:
            await self.myrating_command(update, context)
        elif data == MENU_RATING:
            await self.ratings_command(update, context)
        elif data == MENU_HELP:
            await query.message.edit_text(locales.HELP_TEXT, parse_mode="HTML")
        elif data == MENU_ABOUT:
            await query.message.edit_text(locales.ABOUT_TEXT)
        elif data in {PLAY_RATED, PLAY_CASUAL}:
            mode = "rated" if data == PLAY_RATED else "casual"
            await self._start_matchmaking(query, mode)
        elif data in {PLAY_INVITE_RATED, PLAY_INVITE_CASUAL}:
            mode = "rated" if data == PLAY_INVITE_RATED else "casual"
            code = self.matchmaking.create_invite(
                query.from_user.id, query.message.chat_id, mode
            )["code"]
            keyboard = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton(locales.INVITE_SHARE, switch_inline_query=code)],
                    [
                        InlineKeyboardButton(
                            locales.INVITE_CANCEL, callback_data=MM_CANCEL
                        )
                    ],
                    [InlineKeyboardButton(locales.BTN_BACK, callback_data=BACK_TO_PLAY)],
                ]
            )
            await query.message.edit_text(
                locales.INVITE_CREATED.format(code=code),
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        elif data == JOIN_CODE:
            await query.message.edit_text(
                "Використайте /join <код> щоб приєднатися до запрошення",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(locales.BTN_BACK, callback_data=BACK_TO_PLAY)]]
                ),
            )
        elif data in {MM_CANCEL, BACK_TO_PLAY}:
            # Cancel any queued ticket and return to play menu
            self.matchmaking.cancel(query.from_user.id)
            await self._send_play_menu(query.message, edit=True)

    async def join_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle legacy join callbacks (fallback)."""
        query = update.callback_query
        await query.answer("Приєднання через кнопки більше не використовується. Спробуйте /join")

    async def cancel_invite_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel an invite from inline button."""
        query = update.callback_query
        await query.answer()
        self.matchmaking.cancel(query.from_user.id)
        await query.message.edit_text("Запрошення скасовано.")

    async def accept_private_invite_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Placeholder handler for accepting invites from inline keyboard."""
        query = update.callback_query
        await query.answer("Використайте /join з кодом, щоб приєднатися.")

    async def matchmaking_tick(self, context: ContextTypes.DEFAULT_TYPE):
        """Background job that attempts to pair queued players."""
        for mode in ("rated", "casual"):
            while True:
                result = self.matchmaking.try_match(mode)
                if not result:
                    break

                users = result.get("users", [])
                for user in users:
                    chat_id = int(user.get("chat_id", 0))
                    if not chat_id:
                        continue
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=(
                            "✅ Знайдено суперника! "
                            "Наразі автоматичний старт гри ще в розробці."
                        ),
                    )
                    self.matchmaking.cancel(int(user.get("user_id", 0)))

    # ------------------------------------------------------------------
    # Menu helper utilities
    # ------------------------------------------------------------------

    async def _send_main_menu(self, message, edit: bool = False):
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(locales.MENU_PLAY, callback_data=MENU_PLAY)],
                [
                    InlineKeyboardButton(locales.MENU_PROFILE, callback_data=MENU_PROFILE),
                    InlineKeyboardButton(locales.MENU_RATING, callback_data=MENU_RATING),
                ],
                [
                    InlineKeyboardButton(locales.MENU_HELP, callback_data=MENU_HELP),
                    InlineKeyboardButton(locales.MENU_ABOUT, callback_data=MENU_ABOUT),
                ],
            ]
        )

        if edit:
            await message.edit_text(locales.MENU_TITLE, reply_markup=keyboard)
        else:
            await message.reply_text(locales.MENU_TITLE, reply_markup=keyboard)

    async def _send_play_menu(self, message, edit: bool = False):
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(locales.PLAY_QUICK_RATED, callback_data=PLAY_RATED)],
                [InlineKeyboardButton(locales.PLAY_QUICK_CASUAL, callback_data=PLAY_CASUAL)],
                [
                    InlineKeyboardButton(locales.PLAY_INVITE_RATED, callback_data=INVITE_RATED),
                    InlineKeyboardButton(locales.PLAY_INVITE_CASUAL, callback_data=INVITE_CASUAL),
                ],
                [InlineKeyboardButton(locales.PLAY_JOIN_CODE, callback_data=JOIN_CODE)],
                [InlineKeyboardButton(locales.BTN_BACK_TO_MENU, callback_data=MENU_MAIN)],
            ]
        )

        if edit:
            await message.edit_text(locales.PLAY_TITLE, reply_markup=keyboard)
        else:
            await message.reply_text(locales.PLAY_TITLE, reply_markup=keyboard)

    async def _start_matchmaking(self, query, mode: str):
        ticket = await self.matchmaking.enqueue(
            query.from_user.id, query.message.chat_id, mode, query.from_user.username
        )
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(locales.SEARCHING_CANCEL, callback_data=MM_CANCEL)],
                [InlineKeyboardButton(locales.SEARCHING_BACK, callback_data=BACK_TO_PLAY)],
            ]
        )
        await query.message.edit_text(
            f"{locales.SEARCHING_TITLE}\n\nРежим: {mode}\nРейтинг: {ticket.rating}",
            reply_markup=keyboard,
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _is_private_chat(chat) -> bool:
        return chat is None or getattr(chat, "type", None) == "private"

    def _get_game_state(self, chat_id: int = None, message_id: int = None, inline_message_id: str = None):
        """Retrieve game state from repository for regular or inline games."""
        if inline_message_id:
            return self.repo.get_inline_game(inline_message_id)
        if chat_id is not None and message_id is not None:
            return self.repo.get_game(chat_id, message_id)
        return None

    async def select_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle piece selection and show available moves."""
        query = update.callback_query
        await query.answer()

        inline_message_id = query.inline_message_id

        if inline_message_id:
            game_state = self._get_game_state(inline_message_id=inline_message_id)
            if not game_state:
                await query.answer(locales.ERROR_NO_GAME, show_alert=True)
                return
            chat_id = message_id = None
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

        engine = CheckersEngine()
        engine.set_board_state({
            "board": game_state["board"],
            "current_turn": game_state["current_turn"],
            "move_count": game_state.get("move_count", 0)
        })

        user_id = query.from_user.id
        if user_id != game_state["red_player_id"] and user_id != game_state["white_player_id"]:
            await query.answer("❌ Ви не є гравцем у цій грі!", show_alert=True)
            return

        current_player_id = game_state["red_player_id"] if engine.current_turn == RED else game_state["white_player_id"]
        if user_id != current_player_id:
            await query.answer(locales.ERROR_NOT_YOUR_TURN, show_alert=True)
            return

        pending_capture = game_state.get("pending_capture")
        try:
            from_pos = int(query.data.split("_")[1])
        except Exception:
            await query.answer(locales.ERROR_INVALID_MOVE, show_alert=True)
            return

        if pending_capture and pending_capture.get("must_continue") and from_pos != pending_capture.get("pos"):
            await query.answer("⚡ Ви повинні продовжити бити цією фігурою!", show_alert=True)
            return

        piece_at_from = engine.board[from_pos]
        piece_color = engine.get_piece_color(piece_at_from)

        if piece_color != engine.current_turn:
            await query.answer("❌ Ви не можете рухати фігуру суперника!", show_alert=True)
            return

        if pending_capture:
            legal_moves = engine.find_single_hop_captures(from_pos)
        else:
            legal_moves = [m for m in engine.get_legal_moves(engine.current_turn) if m.from_pos == from_pos]

        if not legal_moves:
            await query.answer(locales.ERROR_INVALID_MOVE, show_alert=True)
            return

        if inline_message_id:
            await self._update_inline_game_message(context.bot, inline_message_id, engine, game_state, selected_pos=from_pos)
        else:
            await self._update_game_message(query.message, engine, game_state, context, selected_pos=from_pos)

    async def move_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle executing a move selection."""
        query = update.callback_query
        await query.answer()

        inline_message_id = query.inline_message_id

        if inline_message_id:
            game_state = self._get_game_state(inline_message_id=inline_message_id)
            if not game_state:
                await query.answer(locales.ERROR_NO_GAME, show_alert=True)
                return
            chat_id = message_id = None
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

        engine = CheckersEngine()
        engine.set_board_state({
            "board": game_state["board"],
            "current_turn": game_state["current_turn"],
            "move_count": game_state.get("move_count", 0)
        })

        user_id = query.from_user.id
        if user_id != game_state["red_player_id"] and user_id != game_state["white_player_id"]:
            await query.answer("❌ Ви не є гравцем у цій грі!", show_alert=True)
            return

        current_player_id = game_state["red_player_id"] if engine.current_turn == RED else game_state["white_player_id"]
        if user_id != current_player_id:
            await query.answer(locales.ERROR_NOT_YOUR_TURN, show_alert=True)
            return

        pending_capture = game_state.get("pending_capture")

        try:
            _, from_pos, to_pos = query.data.split("_")
            from_pos = int(from_pos)
            to_pos = int(to_pos)
        except Exception:
            await query.answer(locales.ERROR_INVALID_MOVE, show_alert=True)
            return

        if pending_capture and pending_capture.get("must_continue") and from_pos != pending_capture.get("pos"):
            await query.answer("⚡ Ви повинні продовжити бити цією фігурою!", show_alert=True)
            return


        # Verify the selected piece belongs to the current player
        piece_at_from = engine.board[from_pos]
        piece_color = engine.get_piece_color(piece_at_from)

        if piece_color != engine.current_turn:
            await query.answer("❌ Ви не можете рухати фігуру суперника!", show_alert=True)
            return

        # Find and apply the move
        if pending_capture:
            legal_moves = engine.find_single_hop_captures(pending_capture["pos"])
        else:
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
        previous_turn = engine.current_turn
        engine.apply_move(move_to_apply)

        # Check if this was a capture and if player must continue
        must_continue = False
        if move_to_apply.captures:
            # Temporarily keep the turn with the same player to evaluate continuation
            engine.current_turn = previous_turn
            must_continue = engine.must_continue_capturing(move_to_apply.to_pos)
            if not must_continue:
                # Restore the normal turn switch performed inside apply_move
                engine.current_turn = RED if previous_turn == WHITE else WHITE

        # Check for winner (after finalizing whose turn it is)
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
    
    async def _update_game_message(self, message, engine: CheckersEngine, game_state: dict, context: ContextTypes.DEFAULT_TYPE = None, selected_pos: Optional[int] = None):
        """Update game message with current board and turn info."""
        board_text = BoardRenderer.render(engine.board)
        players_msg = self._get_players_message(game_state)
        turn_msg = self._get_turn_message(game_state)
        keyboard = BoardRenderer.create_move_keyboard(
            engine,
            selected_pos=selected_pos,
            move_count=engine.move_count,
            pending_capture=game_state.get("pending_capture")
        )
        
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
        game_state: dict,
        selected_pos: Optional[int] = None
    ):
        """Update inline message with current game state."""
        board_text = BoardRenderer.render(engine.board)
        players_msg = self._get_players_message(game_state)
        turn_msg = self._get_turn_message(game_state)
        keyboard = BoardRenderer.create_move_keyboard(
            engine,
            selected_pos=selected_pos,
            move_count=engine.move_count,
            pending_capture=game_state.get("pending_capture")
        )
        
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
        data = query.data or ""

        # If the continuation banner is tapped, remind the player to continue capturing
        if data == "noop_continue":
            await query.answer("⚡ Ви повинні продовжити бити цією фігурою!", show_alert=True)
            return

        # Only attempt detailed feedback for square-specific noop callbacks
        if not data.startswith("noop_"):
            await query.answer()
            return

        try:
            _, pos_str = data.split("_", 1)
            tapped_pos = int(pos_str)
        except (ValueError, AttributeError):
            await query.answer()
            return

        # Attempt to load game state to provide contextual guidance
        inline_message_id = query.inline_message_id
        game_state = None

        if inline_message_id:
            game_state = self._get_game_state(inline_message_id=inline_message_id)
        elif query.message and query.message.chat:
            game_state = self._get_game_state(query.message.chat.id, query.message.message_id)

        if not game_state:
            await query.answer()
            return

        engine = CheckersEngine()
        engine.set_board_state({
            "board": game_state["board"],
            "current_turn": game_state["current_turn"],
            "move_count": game_state.get("move_count", 0)
        })

        pending_capture = game_state.get("pending_capture")
        if pending_capture and pending_capture.get("pos") != tapped_pos:
            await query.answer("⚡ Ви повинні продовжити бити цією фігурою!", show_alert=True)
            return

        legal_moves = engine.get_legal_moves(engine.current_turn)
        capture_positions = {move.from_pos for move in legal_moves if move.captures}

        if capture_positions and tapped_pos not in capture_positions:
            await query.answer("🎯 Доступний удар! Оберіть фігуру, що може бити.", show_alert=True)
            return

        # Default noop response
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
            query = update.callback_query
            await query.answer()

            if query.data == MENU_MAIN:
                await self.show_main_menu(update, context)
                return

            # For callback queries coming from inline keyboards, fall back to editing the
            # callback message (or inline message) directly when chat message is absent.
            if not message:
                message = query.message or query

        await self._send_leaderboard(
            message,
            page=0,
            edit=edit,
            is_private_chat=self._is_private_chat(update.effective_chat),
        )

    async def ratings_page_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle leaderboard page navigation."""
        query = update.callback_query
        await query.answer()

        if not self.rating_system:
            return

        if query.data == MENU_MAIN:
            await self.show_main_menu(update, context)
            return

        # Parse page number from callback data: ratings_page_N
        _, _, page_str = query.data.split("_")
        page = int(page_str)

        target = query.message or query
        await self._send_leaderboard(
            target,
            page=page,
            edit=True,
            is_private_chat=self._is_private_chat(update.effective_chat),
        )

    async def _send_leaderboard(
        self,
        message,
        page: int = 0,
        edit: bool = False,
        *,
        is_private_chat: bool = True,
    ):
        """Send or edit leaderboard message with pagination."""
        PLAYERS_PER_PAGE = 15
        offset = page * PLAYERS_PER_PAGE
        
        leaderboard, total_count = await self.rating_system.get_leaderboard(
            limit=PLAYERS_PER_PAGE, offset=offset
        )
        
        if not leaderboard and page == 0:
            text = "Ще немає рейтингу. Зіграйте першу гру!"
            if edit:
                if hasattr(message, "edit_text"):
                    await message.edit_text(text)
                elif hasattr(message, "edit_message_text"):
                    await message.edit_message_text(text)
            else:
                if hasattr(message, "reply_text"):
                    await message.reply_text(text)
                elif hasattr(message, "edit_message_text"):
                    await message.edit_message_text(text)
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

        rows = [buttons] if buttons else []
        if is_private_chat:
            rows.append([InlineKeyboardButton(locales.BTN_BACK_TO_MENU, callback_data=MENU_MAIN)])
        keyboard = InlineKeyboardMarkup(rows)
        
        if edit:
            if hasattr(message, "edit_text"):
                await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            elif hasattr(message, "edit_message_text"):
                await message.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            if hasattr(message, "reply_text"):
                await message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")
            elif hasattr(message, "edit_message_text"):
                await message.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")

