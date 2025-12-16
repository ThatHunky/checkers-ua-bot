"""
Telegram bot command and callback handlers for Ukrainian Checkers game.
"""

import os
import uuid
import json
import logging
import html
import asyncio
import time
from datetime import datetime
from typing import Optional, List, Dict, Tuple
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

# Import from handlers module
from .board_renderer import BoardRenderer
from .message_updater import MessageUpdater
from .constants import (
    MENU_MAIN, MENU_PLAY, MENU_PROFILE, MENU_RATING, MENU_SETTINGS, MENU_HELP, MENU_ABOUT,
    PLAY_RATED, PLAY_CASUAL, GROUP_INVITE_RATED, GROUP_INVITE_CASUAL,
    INVITE_RATED, INVITE_CASUAL, JOIN_CODE, MM_CANCEL, BACK_TO_PLAY,
    MESSAGE_EDIT_TIMEOUT, CALLBACK_DEDUP_WINDOW_MS, CALLBACK_DEDUP_CLEANUP_THRESHOLD, CALLBACK_DEDUP_CLEANUP_AGE_MS
)

logger = logging.getLogger(__name__)

from engine import CheckersEngine, YELLOW, BLUE, Move
from repository import GameRepository
from achievements import AchievementSystem
from matchmaking import MatchmakingService
import locales

class GameHandlers:
    """Telegram bot command and callback handlers."""
    
    # In-memory cache for callback deduplication
    _recent_callbacks: Dict[str, float] = {}
    
    def __init__(self, repository: GameRepository, rating_system=None, game_data_repo=None) -> None:
        self.repo = repository
        self.rating_system = rating_system
        self.game_data_repo = game_data_repo
        self.achievement_system = None  # Will be set from main.py
        self.matchmaking = MatchmakingService(repository, rating_system)
    
    @staticmethod
    def _is_duplicate_callback(callback_id: str, window_ms: int = CALLBACK_DEDUP_WINDOW_MS) -> bool:
        """
        Check if a callback query is a duplicate within the time window.
        Returns True if duplicate, False otherwise.
        """
        now = time.time() * 1000  # milliseconds
        if callback_id in GameHandlers._recent_callbacks:
            if now - GameHandlers._recent_callbacks[callback_id] < window_ms:
                return True
        GameHandlers._recent_callbacks[callback_id] = now
        
        # Clean up old entries
        if len(GameHandlers._recent_callbacks) > CALLBACK_DEDUP_CLEANUP_THRESHOLD:
            # Remove entries older than cleanup age
            cutoff = now - CALLBACK_DEDUP_CLEANUP_AGE_MS
            GameHandlers._recent_callbacks = {
                k: v for k, v in GameHandlers._recent_callbacks.items()
                if v > cutoff
            }
        
        return False
    
    @staticmethod
    async def _safe_edit_message(bot, timeout: float = MESSAGE_EDIT_TIMEOUT, **kwargs) -> None:
        """
        Safely edit a message with timeout handling.
        Raises asyncio.TimeoutError if timeout occurs.
        Delegates to MessageUpdater._safe_edit_message.
        """
        return await MessageUpdater._safe_edit_message(bot, timeout=timeout, **kwargs)

    @staticmethod
    def _pos_to_human(pos: int) -> str:
        """Convert board index to human-readable coordinates (e.g., A8)."""
        col = chr(ord("A") + (pos % 8))
        row = 8 - (pos // 8)
        return f"{col}{row}"

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

        if self._is_private_chat(chat):
            await self._send_play_menu(message)
        else:
            await self._send_group_invite_menu(message, initiator_id=update.effective_user.id if update.effective_user else None)

    async def _start_game(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        red_user: dict,
        white_user: dict,
        is_private_match: bool = False,
        mode: str = "rated",
    ):
        """Start a new game between two players."""
        # Initialize engine
        engine = CheckersEngine()
        board_state = engine.board
        first_turn = YELLOW  # Yellow moves first
        
        # Get first names from repository if not in user dict
        red_user_data = self.repo.get_user_by_id(red_user["user_id"])
        white_user_data = self.repo.get_user_by_id(white_user["user_id"])
        
        red_first_name = (
            red_user.get("first_name") or 
            (red_user_data.get("first_name") if red_user_data else None) or
            red_user.get("username") or 
            "Blue"
        )
        white_first_name = (
            white_user.get("first_name") or 
            (white_user_data.get("first_name") if white_user_data else None) or
            white_user.get("username") or 
            "Yellow"
        )
        
        # Prepare game state
        game_state = {
            "board": board_state,
            "current_turn": first_turn,
            "blue_player_id": int(red_user["user_id"]),
            "blue_player_name": red_first_name,
            "blue_player_username": red_user.get("username"),
            "yellow_player_id": int(white_user["user_id"]),
            "yellow_player_name": white_first_name,
            "yellow_player_username": white_user.get("username"),
            "move_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat(),
            "is_private_match": is_private_match,
            "mode": mode or "rated",
        }

        # Render initial board
        board_text = BoardRenderer.render(board_state)
        keyboard = BoardRenderer.create_move_keyboard(engine, move_count=0)
        
        blue_name = html.escape(game_state["blue_player_name"])
        yellow_name = html.escape(game_state["yellow_player_name"])
        info_text = (
            f"🎮 <b>Гра розпочалась!</b>\n\n"
            f"🟡 {yellow_name} (ви ходите першими)\n"
            f"🔵 {blue_name}\n\n"
            f"Хід Жовтих."
        )

        if is_private_match:
            try:
                # Send to Blue player
                msg_red = await context.bot.send_message(
                    chat_id=int(red_user["chat_id"]), 
                    text=info_text, 
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
                game_state["challenger_chat_id"] = msg_red.chat_id
                game_state["challenger_message_id"] = msg_red.message_id
                
                # Send to Yellow player
                msg_white = await context.bot.send_message(
                    chat_id=int(white_user["chat_id"]),
                    text=info_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN
                )
                game_state["opponent_chat_id"] = msg_white.chat_id
                game_state["opponent_message_id"] = msg_white.message_id
                
                # Save game for both
                self.repo.save_game(msg_red.chat_id, msg_red.message_id, game_state)
                self.repo.save_game(msg_white.chat_id, msg_white.message_id, game_state)
                
            except Exception as e:
                logger.error(f"Failed to start private match: {e}")
                # Try to notify users of failure
                for user in [red_user, white_user]:
                    try:
                        await context.bot.send_message(chat_id=int(user["chat_id"]), text="❌ Не вдалося розпочати гру.")
                    except:
                        pass
        else:
            # Group chat game (or single player play testing if we support that later)
            # For now assume red_user's chat_id is the group chat id
            try:
                msg = await context.bot.send_message(
                    chat_id=int(red_user["chat_id"]),
                    text=info_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                )
                self.repo.save_game(msg.chat_id, msg.message_id, game_state)
            except Exception as e:
                logger.error(f"Failed to start group game: {e}")

    async def replay_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show a list of recent completed games for the user."""
        message = update.effective_message
        user = update.effective_user

        if not self.game_data_repo:
            await message.reply_text("📺 Історія ігор тимчасово недоступна.")
            return

        game_ids = self.game_data_repo.get_user_completed_games(user.id, limit=5)

        if not game_ids:
            await message.reply_text("У вас поки немає завершених ігор для перегляду.")
            return

        buttons = []
        lines: List[str] = ["Оберіть гру для перегляду:"]

        for game_id in game_ids:
            data = self.game_data_repo.get_completed_game(game_id)
            if not data:
                continue

            if data["blue_player_id"] == user.id:
                opponent = data["yellow_player_name"]
                color = "синіх"
            elif data["yellow_player_id"] == user.id:
                opponent = data["blue_player_name"]
                color = "жовтих"
            else:
                opponent = "суперник"
                color = "?"

            winner_mark = "🏆" if data["winner_id"] == user.id else ""
            completed = data.get("completed_at", "")[:16].replace("T", " ")
            lines.append(f"• {game_id} – проти {opponent} ({color}) {winner_mark} {completed}")
            buttons.append([
                InlineKeyboardButton(
                    f"Гра {game_id}", callback_data=f"replay_{game_id}_0_{user.id}"
                )
            ])

        await message.reply_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    async def inline_query_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle inline queries for creating game challenges."""

        query = update.inline_query
        query_text = (query.query or "").strip().lower()
        user = query.from_user

        # If the inline query is empty or "play"/"start", show challenge options for different modes
        if not query_text or query_text in ("play", "start", "гра", "почати"):
            user_name = user.first_name or user.username or "Гравець"
            
            # Casual mode (default)
            casual_msg = locales.INLINE_CHALLENGE_MSG.format(name=user_name)
            casual_result = InlineQueryResultArticle(
                id="challenge_casual",
                title=locales.INLINE_CHALLENGE_CASUAL_TITLE,
                description=locales.INLINE_CHALLENGE_CASUAL_DESC,
                input_message_content=InputTextMessageContent(
                    casual_msg,
                    parse_mode=ParseMode.HTML
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        locales.INLINE_CHALLENGE_JOIN,
                        callback_data="inline_challenge_join"
                    )
                ]])
            )
            
            # Ranked mode
            ranked_msg = locales.INLINE_CHALLENGE_MSG_RANKED.format(name=user_name)
            ranked_result = InlineQueryResultArticle(
                id="challenge_ranked",
                title=locales.INLINE_CHALLENGE_RANKED_TITLE,
                description=locales.INLINE_CHALLENGE_RANKED_DESC,
                input_message_content=InputTextMessageContent(
                    ranked_msg,
                    parse_mode=ParseMode.HTML
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        locales.INLINE_CHALLENGE_JOIN,
                        callback_data="inline_challenge_join"
                    )
                ]])
            )
            
            # Practice mode
            practice_msg = locales.INLINE_CHALLENGE_MSG_PRACTICE.format(name=user_name)
            practice_result = InlineQueryResultArticle(
                id="challenge_practice",
                title=locales.INLINE_CHALLENGE_PRACTICE_TITLE,
                description=locales.INLINE_CHALLENGE_PRACTICE_DESC,
                input_message_content=InputTextMessageContent(
                    practice_msg,
                    parse_mode=ParseMode.HTML
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        locales.INLINE_CHALLENGE_JOIN,
                        callback_data="inline_challenge_join"
                    )
                ]])
            )
            
            results = [casual_result, ranked_result, practice_result]
            await query.answer(results, cache_time=0, is_personal=True)
            return

        # If query contains @username or "challenge @username", show challenge option for that user
        username = None
        if query_text.startswith("@"):
            username = query_text[1:].split()[0]
        elif "challenge" in query_text:
            parts = query_text.split()
            for i, part in enumerate(parts):
                if part == "challenge" and i + 1 < len(parts):
                    username = parts[i + 1].lstrip("@")
                    break
        
        if username:
            # Check if user exists
            opponent_info = self.repo.get_user_by_username(username)
            if opponent_info:
                challenge_msg = (
                    f"🎮 <b>{user.first_name or user.username or 'Гравець'}</b> викликає "
                    f"<b>@{username}</b> на гру в Українські Шашки!"
                )
                results = [
                    InlineQueryResultArticle(
                        id=f"challenge_{username}",
                        title=f"🎮 Викликати @{username}",
                        description=f"Викликати {opponent_info.get('first_name', username)} на гру",
                        input_message_content=InputTextMessageContent(
                            challenge_msg,
                            parse_mode=ParseMode.HTML
                        ),
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton(
                                "✅ Прийняти виклик",
                                callback_data="accept_inline"
                            )
                        ]])
                    )
                ]
                await query.answer(results, cache_time=0, is_personal=True)
                return
            else:
                results = [
                    InlineQueryResultArticle(
                        id="user_not_found",
                        title="❌ Користувача не знайдено",
                        description=f"@{username} ще не використовував цього бота",
                        input_message_content=InputTextMessageContent(
                            f"❌ Користувача @{username} не знайдено. Він має використати /start з ботом спочатку."
                        )
                    )
                ]
                await query.answer(results, cache_time=0, is_personal=True)
                return

        # If query contains a code, provide a simple inline share message with the supplied code
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
        """Handle selection of inline results - create challenge when challenge option is selected."""

        result = update.chosen_inline_result
        result_id = result.result_id
        inline_message_id = result.inline_message_id
        user = result.from_user

        logger.info("Inline result chosen: result_id=%s, inline_message_id=%s, user=%s", 
                   result_id, inline_message_id, user.id)

        if not inline_message_id:
            logger.warning("ChosenInlineResult has no inline_message_id result_id=%s user=%s", 
                          result_id, user.id)
            # Challenge will be created lazily when button is clicked

        # If challenge option was selected, create and save challenge
        # Parse mode from result_id: challenge, challenge_casual, challenge_ranked, challenge_practice
        if result_id.startswith("challenge") and inline_message_id:
            # Extract mode from result_id
            if result_id == "challenge" or result_id == "challenge_casual":
                mode = "casual"
            elif result_id == "challenge_ranked":
                mode = "ranked"
            elif result_id == "challenge_practice":
                mode = "practice"
            else:
                # Default to casual for backward compatibility
                mode = "casual"
            
            challenge_data = {
                "creator_id": user.id,
                "creator_name": user.first_name or user.username or "Гравець",
                "creator_username": user.username,
                "inline_message_id": inline_message_id,
                "mode": mode
            }
            
            # Save challenge to repository
            if self.repo.save_inline_challenge(inline_message_id, challenge_data):
                logger.info("Inline challenge created: inline_message_id=%s, creator=%s, mode=%s", 
                           inline_message_id, user.id, mode)
            else:
                logger.error("Failed to save inline challenge: inline_message_id=%s", inline_message_id)

    async def join_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Join an invite by code (if created via the menu)."""
        message = update.effective_message
        args = context.args or []
        if not args:
            await message.reply_text("Використання: /join <код запрошення>")
            return

        code = args[0].strip().upper()
        logger.info(
            "[/join] user=%s chat=%s code=%s",
            update.effective_user.id,
            message.chat_id if message else None,
            code,
        )
        invite = self.matchmaking.get_invite(code)
        if not invite:
            logger.info("[/join] invite not found code=%s", code)
            await message.reply_text("❌ Запрошення не знайдено або вже використано.")
            return

        creator_chat_id = int(invite.get("creator_chat_id", "0") or 0)
        creator_user_id = int(invite.get("creator_user_id", "0") or 0)

        # Enforce same chat as invite creator (group/private)
        if creator_chat_id and creator_chat_id != message.chat_id:
            logger.info(
                "[/join] chat mismatch code=%s user_chat=%s creator_chat=%s",
                code,
                message.chat_id,
                creator_chat_id,
            )
            await message.reply_text("❌ Це запрошення створено в іншому чаті.")
            return

        # Prevent creator self-joining
        if update.effective_user.id == creator_user_id:
            logger.info(
                "[/join] creator self-join blocked code=%s user=%s",
                code,
                update.effective_user.id,
            )
            await message.reply_text("❌ Ви не можете приєднатися до власного запрошення.")
            return

        result = self.matchmaking.accept_invite(
            update.effective_user.id, message.chat_id, code
        )
        if not result:
            logger.info("[/join] accept failed code=%s user=%s", code, update.effective_user.id)
            await message.reply_text("❌ Запрошення не знайдено або вже використано.")
            return

        creator_name = invite.get("creator_username") or invite.get("creator_first_name") or creator_user_id
        logger.info(
            "[/join] accepted code=%s user=%s creator=%s",
            code,
            update.effective_user.id,
            creator_user_id,
        )
        await message.reply_text(
            f"✅ Ви приєдналися до запрошення {code}. "
            f"Грайте разом із {creator_name}."
        )

    async def replay_game_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Render a saved game's move-by-move replay."""

        query = update.callback_query
        if not query:
            return

        await query.answer()

        if not self.game_data_repo:
            await query.edit_message_text("Історія ігор недоступна.")
            return

        try:
            parts = query.data.split("_")
            if len(parts) < 3:
                raise ValueError("Invalid callback data format")
            
            game_id = parts[1]
            step_str = parts[2]
            step = max(int(step_str), 0)
            
            # Parse user_id if present (new format: replay_{game_id}_{step}_{user_id})
            # Old format: replay_{game_id}_{step} (for backward compatibility with game end messages)
            authorized_user_id = None
            if len(parts) >= 4:
                authorized_user_id = int(parts[3])
        except Exception:
            await query.edit_message_text("Невідомий формат запиту на повтор гри.")
            return

        game_data = self.game_data_repo.get_completed_game(game_id)
        if not game_data:
            await query.edit_message_text("Гру не знайдено або вона недоступна.")
            return

        # Validate user access
        current_user_id = query.from_user.id
        if authorized_user_id is not None:
            # New format: only the command issuer can access
            if current_user_id != authorized_user_id:
                await query.answer("❌ Тільки автор команди може переглядати цей повтор.", show_alert=True)
                return
        else:
            # Old format (backward compatibility): allow if user is one of the game players
            # This handles game end message replay buttons
            if (current_user_id != game_data.get("blue_player_id") and 
                current_user_id != game_data.get("yellow_player_id")):
                await query.answer("❌ Тільки гравці цієї гри можуть переглядати повтор.", show_alert=True)
                return
            # For old format, use current user as authorized_user_id for pagination buttons
            authorized_user_id = current_user_id

        moves = game_data.get("move_history", [])
        total_steps = len(moves)

        # Clamp step within available range (including final board view)
        step = min(step, total_steps)

        header = (
            f"📺 Повтор гри {game_id}\n"
            f"🔵 {game_data.get('blue_player_name', game_data.get('red_player_name', 'Blue'))} vs 🟡 {game_data.get('yellow_player_name', game_data.get('white_player_name', 'Yellow'))}"
        )

        if step == total_steps:
            board = game_data.get("final_board")
            if not board and moves:
                board = moves[-1].get("board_before")
            if not board:
                board = game_data.get("initial_board")
            summary = (
                f"Фінальна позиція.\n"
                f"Переможець: {game_data['winner_name']} ({game_data['winner_color']})."
            )
        else:
            move = moves[step]
            board = move.get("board_before") or game_data.get("initial_board")
            mover = "синіх" if move.get("player") == "blue" else "жовтих"
            from_pos = self._pos_to_human(move.get("from", 0))
            to_pos = self._pos_to_human(move.get("to", 0))
            captures = move.get("captures") or []
            capture_text = ""
            if captures:
                captured_squares = ", ".join(self._pos_to_human(p) for p in captures)
                capture_text = f"; б'є: {captured_squares}"

            summary = f"Хід {step + 1} ({mover}): {from_pos} → {to_pos}{capture_text}"

        board = board or game_data.get("initial_board", CheckersEngine.init_board())
        board_text = BoardRenderer.render(board)

        prev_step = max(step - 1, 0)
        next_step = min(step + 1, total_steps)

        # Include authorized_user_id in all pagination buttons to maintain access control
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⏪ Попередній", callback_data=f"replay_{game_id}_{prev_step}_{authorized_user_id}"
                    ),
                    InlineKeyboardButton(
                        "⏩ Наступний", callback_data=f"replay_{game_id}_{next_step}_{authorized_user_id}"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "🔁 На початок", callback_data=f"replay_{game_id}_0_{authorized_user_id}"
                    ),
                    InlineKeyboardButton(
                        "🏁 Фінал", callback_data=f"replay_{game_id}_{total_steps}_{authorized_user_id}"
                    ),
                ],
            ]
        )

        await query.edit_message_text(
            f"{header}\n\n{board_text}\n\n{summary}",
            reply_markup=keyboard,
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
        elif data in {INVITE_RATED, INVITE_CASUAL}:
            mode = "rated" if data == INVITE_RATED else "casual"
            code = self.matchmaking.create_invite(
                query.from_user.id,
                query.message.chat_id,
                mode,
                creator_username=query.from_user.username,
                creator_first_name=query.from_user.first_name,
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

    async def inline_challenge_join_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle joining an inline challenge and start a game."""
        query = update.callback_query
        
        try:
            logger.info(
                "[inline_challenge:join] callback received user=%s callback_data=%s",
                query.from_user.id,
                query.data,
            )
            
            inline_message_id = query.inline_message_id
            
            if not inline_message_id:
                logger.warning("[inline_challenge:join] no inline_message_id user=%s", query.from_user.id)
                await query.answer("❌ Це не inline повідомлення.", show_alert=True)
                return

            logger.info(
                "[inline_challenge:join] user=%s inline_message_id=%s",
                query.from_user.id,
                inline_message_id,
            )

            # Get challenge data
            challenge = self.repo.get_inline_challenge(inline_message_id)
            
            if not challenge:
                # Try lazy creation - if this is a challenge message, create challenge on first click
                logger.info("[inline_challenge:join] challenge not found, attempting lazy creation inline_message_id=%s user=%s", 
                           inline_message_id, query.from_user.id)
                
                # Create challenge with first clicker as creator
                challenge_data = {
                    "creator_id": query.from_user.id,
                    "creator_name": query.from_user.first_name or query.from_user.username or "Гравець",
                    "creator_username": query.from_user.username,
                    "inline_message_id": inline_message_id,
                    "mode": "casual",
                    "lazy_created": True  # Flag to indicate this was created lazily
                }
                
                # Save the challenge
                if self.repo.save_inline_challenge(inline_message_id, challenge_data):
                    logger.info("[inline_challenge:join] lazy challenge created inline_message_id=%s creator=%s", 
                               inline_message_id, query.from_user.id)
                    challenge = challenge_data
                else:
                    logger.error("[inline_challenge:join] failed to create lazy challenge inline_message_id=%s", 
                                inline_message_id)
                    await query.answer(locales.INLINE_CHALLENGE_NOT_FOUND, show_alert=True)
                    return

            creator_user_id = challenge.get("creator_id")
            
            if query.from_user.id == creator_user_id:
                logger.info("[inline_challenge:join] creator self-join blocked inline_message_id=%s user=%s", 
                           inline_message_id, query.from_user.id)
                await query.answer(locales.INLINE_CHALLENGE_SELF_JOIN, show_alert=True)
                return
            
            # Answer the callback query after validation
            await query.answer()

            mode = challenge.get("mode", "casual")
            creator_name = challenge.get("creator_name", "Гравець")
            creator_username = challenge.get("creator_username")
            
            # Get first names from repository if available
            creator_user_data = self.repo.get_user_by_id(creator_user_id)
            creator_first_name = (
                creator_name or
                (creator_user_data.get("first_name") if creator_user_data else None) or
                creator_username or
                "Гравець"
            )
            
            white_user_data = self.repo.get_user_by_id(query.from_user.id)
            white_first_name = (
                query.from_user.first_name or
                (white_user_data.get("first_name") if white_user_data else None) or
                query.from_user.username or
                "Гравець"
            )

            # Prepare user data for game start
            # For inline games, we need to use the chat where the challenge was sent
            # Since inline messages don't have a direct chat_id, we'll need to handle this differently
            # The game will be played in the inline message itself
            red_user = {
                "user_id": creator_user_id,
                "username": creator_username,
                "first_name": creator_first_name,
                "chat_id": None,  # Inline messages don't have chat_id
            }
            white_user = {
                "user_id": query.from_user.id,
                "username": query.from_user.username,
                "first_name": white_first_name,
                "chat_id": None,  # Inline messages don't have chat_id
            }

            # Initialize engine
            engine = CheckersEngine()
            board_state = engine.board
            first_turn = YELLOW  # Yellow moves first

            # Prepare game state
            game_state = {
                "board": board_state,
                "current_turn": first_turn,
                "blue_player_id": int(red_user["user_id"]),
                "blue_player_name": creator_first_name,
                "blue_player_username": creator_username,
                "yellow_player_id": int(white_user["user_id"]),
                "yellow_player_name": white_first_name,
                "yellow_player_username": query.from_user.username,
                "move_count": 0,
                "created_at": datetime.utcnow().isoformat(),
                "last_activity": datetime.utcnow().isoformat(),
                "is_private_match": False,
                "is_inline": True,
                "inline_message_id": inline_message_id,
                "mode": mode,
            }

            # Save inline game
            self.repo.save_inline_game(inline_message_id, game_state)

            # Delete challenge after game starts
            self.repo.delete_inline_challenge(inline_message_id)

            # Update inline message with game board using the standard update method
            try:
                success = await self._update_inline_game_message(
                    context.bot,
                    inline_message_id,
                    engine,
                    game_state
                )
                if success:
                    logger.info(
                        "[inline_challenge:join] game started inline_message_id=%s creator=%s opponent=%s mode=%s",
                        inline_message_id,
                        creator_user_id,
                        query.from_user.id,
                        mode,
                    )
                else:
                    logger.error(
                        "[inline_challenge:join] failed to update message inline_message_id=%s",
                        inline_message_id
                    )
            except Exception as e:
                logger.error(
                    "[inline_challenge:join] exception updating inline message inline_message_id=%s error=%s",
                    inline_message_id,
                    e,
                    exc_info=True
                )
        except Exception as e:
            logger.error(
                "[inline_challenge:join] unhandled exception user=%s error=%s",
                query.from_user.id if query else None,
                e,
                exc_info=True
            )
            # Try to answer the callback if we haven't already
            try:
                if query:
                    await query.answer("❌ Сталася помилка при обробці запиту.", show_alert=True)
            except Exception:
                pass

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

    async def accept_inline_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle accepting an inline challenge when a user clicks accept_inline button."""
        query = update.callback_query
        
        try:
            if not query:
                return
            
            callback_data = query.data
            inline_message_id = query.inline_message_id
            accepter_user_id = query.from_user.id  # The user who clicked the accept button
            
            if not inline_message_id:
                logger.warning("[accept_inline] no inline_message_id user=%s", accepter_user_id)
                await query.answer("❌ Це не inline повідомлення.", show_alert=True)
                return
            
            logger.info(
                "[accept_inline] callback received accepter=%s callback_data=%s inline_message_id=%s",
                accepter_user_id,
                callback_data,
                inline_message_id,
            )
            
            # Get challenge data
            challenge = self.repo.get_inline_challenge(inline_message_id)
            
            if not challenge:
                # Challenge not found - it may have expired or wasn't created yet
                logger.info("[accept_inline] challenge not found inline_message_id=%s accepter=%s", 
                           inline_message_id, accepter_user_id)
                await query.answer("❌ Виклик не знайдено або вже закінчився.", show_alert=True)
                return
            
            creator_user_id = challenge.get("creator_id")
            
            if accepter_user_id == creator_user_id:
                logger.info("[accept_inline] creator self-join blocked inline_message_id=%s accepter=%s", 
                           inline_message_id, accepter_user_id)
                await query.answer(locales.INLINE_CHALLENGE_SELF_JOIN, show_alert=True)
                return
            
            # Answer the callback query after validation
            await query.answer()
            
            mode = challenge.get("mode", "casual")
            creator_name = challenge.get("creator_name", "Гравець")
            creator_username = challenge.get("creator_username")
            
            # Get first names from repository if available
            creator_user_data = self.repo.get_user_by_id(creator_user_id)
            creator_first_name = (
                creator_name or
                (creator_user_data.get("first_name") if creator_user_data else None) or
                creator_username or
                "Гравець"
            )
            
            accepter_user_data = self.repo.get_user_by_id(accepter_user_id)
            accepter_first_name = (
                query.from_user.first_name or
                (accepter_user_data.get("first_name") if accepter_user_data else None) or
                query.from_user.username or
                "Гравець"
            )
            
            # Prepare user data for game start
            red_user = {
                "user_id": creator_user_id,
                "username": creator_username,
                "first_name": creator_first_name,
                "chat_id": None,  # Inline messages don't have chat_id
            }
            white_user = {
                "user_id": accepter_user_id,
                "username": query.from_user.username,
                "first_name": accepter_first_name,
                "chat_id": None,  # Inline messages don't have chat_id
            }
            
            # Initialize engine
            engine = CheckersEngine()
            board_state = engine.board
            first_turn = YELLOW  # Yellow moves first
            
            # Prepare game state
            game_state = {
                "board": board_state,
                "current_turn": first_turn,
                "blue_player_id": int(red_user["user_id"]),
                "blue_player_name": creator_first_name,
                "blue_player_username": creator_username,
                "yellow_player_id": int(white_user["user_id"]),
                "yellow_player_name": accepter_first_name,
                "yellow_player_username": query.from_user.username,
                "move_count": 0,
                "created_at": datetime.utcnow().isoformat(),
                "last_activity": datetime.utcnow().isoformat(),
                "is_private_match": False,
                "is_inline": True,
                "inline_message_id": inline_message_id,
                "mode": mode,
            }
            
            # Save inline game
            self.repo.save_inline_game(inline_message_id, game_state)
            
            # Delete challenge after game starts
            self.repo.delete_inline_challenge(inline_message_id)
            
            # Update inline message with game board
            try:
                success = await self._update_inline_game_message(
                    context.bot,
                    inline_message_id,
                    engine,
                    game_state
                )
                if success:
                    logger.info(
                        "[accept_inline] game started inline_message_id=%s creator=%s accepter=%s mode=%s",
                        inline_message_id,
                        creator_user_id,
                        accepter_user_id,
                        mode,
                    )
                else:
                    logger.error(
                        "[accept_inline] failed to update message inline_message_id=%s",
                        inline_message_id
                    )
            except Exception as e:
                logger.error(
                    "[accept_inline] exception updating inline message inline_message_id=%s error=%s",
                    inline_message_id,
                    e,
                    exc_info=True
                )
        except Exception as e:
            logger.error(
                "[accept_inline] unhandled exception accepter=%s error=%s",
                accepter_user_id if query else None,
                e,
                exc_info=True
            )
            await query.answer("❌ Помилка при прийнятті виклику.", show_alert=True)

    async def decline_private_invite_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle declining an invite from inline keyboard in private chats."""
        query = update.callback_query
        await query.answer()

        self.matchmaking.cancel(query.from_user.id)
        await query.message.edit_text("❌ Запрошення відхилено.")

    async def matchmaking_tick(self, context: ContextTypes.DEFAULT_TYPE):
        """Background job that attempts to pair queued players."""
        for mode in ("rated", "casual"):
            while True:
                result = self.matchmaking.try_match(mode)
                if not result:
                    break

                # Pair found!
                users = result.get("users", [])
                if len(users) == 2:
                    # Randomly assign colors (or based on matchmaking logic if strict)
                    # For now, just take the first as Blue, second as Yellow
                    red_user = users[0]
                    white_user = users[1]
                    
                    await self._start_game(
                        context,
                        red_user,
                        white_user,
                        is_private_match=True,
                        mode=mode,
                    )
                    
                    self.matchmaking.cancel(int(red_user.get("user_id", 0)))
                    self.matchmaking.cancel(int(white_user.get("user_id", 0)))
                else:
                    # Should be 2 users
                     logger.warning("Matchmaking returned invalid number of users")

    # ------------------------------------------------------------------
    # Menu helper utilities
    # ------------------------------------------------------------------

    async def _send_main_menu(self, message, edit: bool = False) -> None:
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

    async def _send_play_menu(self, message, edit: bool = False) -> None:
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

    async def _send_group_invite_menu(self, message, initiator_id: int, edit: bool = False) -> None:
        """Show group invite mode selector; only the initiator may choose."""
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        locales.PLAY_QUICK_RATED, callback_data=f"{GROUP_INVITE_RATED}_{initiator_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        locales.PLAY_QUICK_CASUAL, callback_data=f"{GROUP_INVITE_CASUAL}_{initiator_id}"
                    )
                ],
            ]
        )

        prompt = "Обери режим для запрошення у цій групі"
        if edit:
            await message.edit_text(prompt, reply_markup=keyboard)
        else:
            await message.reply_text(prompt, reply_markup=keyboard)

    async def group_invite_mode_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create a group invite (rated or casual) from the group selector."""
        query = update.callback_query
        await query.answer()

        parts = query.data.split("_")
        if len(parts) != 4:
            logger.info("[invite:create] bad payload data=%s", query.data)
            await query.answer("Помилка даних.", show_alert=True)
            return

        _, _, mode, initiator_str = parts
        try:
            initiator_id = int(initiator_str)
        except ValueError:
            logger.info("[invite:create] bad initiator id data=%s", query.data)
            await query.answer("Помилка даних.", show_alert=True)
            return

        if query.from_user.id != initiator_id:
            await query.answer("Лише ініціатор може обрати режим.", show_alert=True)
            return

        chat = query.message.chat if query.message else None
        if self._is_private_chat(chat):
            await query.answer("Запрошення працюють у групах.", show_alert=True)
            return

        mode = "rated" if mode == "rated" else "casual"
        logger.info(
            "[invite:create] user=%s chat=%s mode=%s",
            query.from_user.id,
            chat.id if chat else None,
            mode,
        )
        invite = self.matchmaking.create_invite(
            query.from_user.id,
            chat.id,
            mode,
            creator_username=query.from_user.username,
            creator_first_name=query.from_user.first_name,
        )
        code = invite["code"]

        text = (
            "🤝 Запрошення на гру у цій групі\n"
            f"Режим: {'Рейтинг' if mode == 'rated' else 'Без рейтингу'}\n"
            f"Створив: {query.from_user.first_name}\n"
            f"Код: {code} (можна /join {code})"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⚔️ Приєднатися", callback_data=f"group_invite_join_{code}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "❌ Скасувати", callback_data=f"group_invite_cancel_{code}"
                    )
                ],
            ]
        )

        try:
            await query.message.edit_text(text, reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(text, reply_markup=keyboard)

    async def group_invite_join_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Accept a group invite and start a group game."""
        query = update.callback_query
        await query.answer()

        data = query.data.replace("group_invite_join_", "", 1)
        code = data.strip().upper()
        logger.info(
            "[invite:join] user=%s chat=%s code=%s",
            query.from_user.id,
            query.message.chat.id if query.message and query.message.chat else None,
            code,
        )

        chat = query.message.chat if query.message else None
        if self._is_private_chat(chat):
            await query.answer("Приєднання доступне у групі.", show_alert=True)
            return

        invite = self.matchmaking.get_invite(code)
        if not invite or invite.get("status") != "open":
            logger.info("[invite:join] invite not open code=%s user=%s", code, query.from_user.id)
            await query.answer("❌ Запрошення не знайдено або вже використано.", show_alert=True)
            return

        creator_chat_id = int(invite.get("creator_chat_id", "0") or 0)
        creator_user_id = int(invite.get("creator_user_id", "0") or 0)

        if creator_chat_id != chat.id:
            logger.info(
                "[invite:join] chat mismatch code=%s invite_chat=%s user_chat=%s",
                code,
                creator_chat_id,
                chat.id,
            )
            await query.answer("❌ Це запрошення для іншої групи.", show_alert=True)
            return

        if query.from_user.id == creator_user_id:
            logger.info("[invite:join] creator self-join blocked code=%s user=%s", code, query.from_user.id)
            await query.answer("❌ Не можна приєднатись до власного запрошення.", show_alert=True)
            return

        mode = invite.get("mode", "rated")

        # Atomically mark invite as used now
        invite_used = self.matchmaking.accept_invite(query.from_user.id, chat.id, code)
        if not invite_used:
            logger.info("[invite:join] accept failed (race) code=%s user=%s", code, query.from_user.id)
            await query.answer("❌ Запрошення вже використано.", show_alert=True)
            return
        logger.info(
            "[invite:join] accepted code=%s creator=%s opponent=%s chat=%s mode=%s",
            code,
            creator_user_id,
            query.from_user.id,
            chat.id,
            mode,
        )

        # Get first names from repository if available
        creator_user_data = self.repo.get_user_by_id(creator_user_id)
        creator_first_name = (
            invite.get("creator_first_name") or
            (creator_user_data.get("first_name") if creator_user_data else None) or
            invite.get("creator_username") or
            "Blue"
        )
        
        white_user_data = self.repo.get_user_by_id(query.from_user.id)
        white_first_name = (
            query.from_user.first_name or
            (white_user_data.get("first_name") if white_user_data else None) or
            query.from_user.username or
            "Yellow"
        )
        
        red_user = {
            "user_id": creator_user_id,
            "username": invite.get("creator_username"),
            "first_name": creator_first_name,
            "chat_id": chat.id,
        }
        white_user = {
            "user_id": query.from_user.id,
            "username": query.from_user.username,
            "first_name": white_first_name,
            "chat_id": chat.id,
        }

        await self._start_game(
            context,
            red_user,
            white_user,
            is_private_match=False,
            mode=mode,
        )

        try:
            await query.message.edit_text(
                f"✅ Пара знайдена! Режим: {'Рейтинг' if mode == 'rated' else 'Без рейтингу'}",
                reply_markup=None,
            )
        except Exception:
            pass

    async def group_invite_cancel_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel an open group invite (creator only)."""
        query = update.callback_query
        await query.answer()

        data = query.data.replace("group_invite_cancel_", "", 1)
        code = data.strip().upper()
        logger.info(
            "[invite:cancel] user=%s chat=%s code=%s",
            query.from_user.id,
            query.message.chat.id if query.message and query.message.chat else None,
            code,
        )

        invite = self.matchmaking.get_invite(code)
        if not invite:
            logger.info("[invite:cancel] invite missing code=%s", code)
            await query.answer("Запрошення вже неактивне.", show_alert=True)
            return

        creator_user_id = int(invite.get("creator_user_id", "0") or 0)
        creator_chat_id = int(invite.get("creator_chat_id", "0") or 0)

        if query.from_user.id != creator_user_id:
            logger.info("[invite:cancel] not creator user=%s creator=%s code=%s", query.from_user.id, creator_user_id, code)
            await query.answer("Лише автор може скасувати запрошення.", show_alert=True)
            return

        if query.message and query.message.chat and query.message.chat.id != creator_chat_id:
            logger.info(
                "[invite:cancel] chat mismatch code=%s creator_chat=%s user_chat=%s",
                code,
                creator_chat_id,
                query.message.chat.id if query.message else None,
            )
            await query.answer("Це запрошення створене в іншій групі.", show_alert=True)
            return

        if not self.matchmaking.cancel_invite(code):
            logger.info("[invite:cancel] already finished code=%s", code)
            await query.answer("Запрошення вже завершено.", show_alert=True)
            return
        logger.info("[invite:cancel] cancelled code=%s by user=%s", code, query.from_user.id)

        try:
            await query.message.edit_text("🚫 Запрошення скасовано.", reply_markup=None)
        except Exception:
            pass

    async def _start_matchmaking(self, query, mode: str) -> None:
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

    def _get_game_state(self, chat_id: Optional[int] = None, message_id: Optional[int] = None, inline_message_id: Optional[str] = None) -> Optional[dict]:
        """Retrieve game state from repository for regular or inline games."""
        if inline_message_id:
            return self.repo.get_inline_game(inline_message_id)
        if chat_id is not None and message_id is not None:
            return self.repo.get_game(chat_id, message_id)
        return None
    
    def _get_game_state_from_query(self, query) -> Tuple[Optional[dict], Optional[int], Optional[int], Optional[str]]:
        """
        Extract game state and identifiers from a callback query.
        Handles both inline and regular messages.
        
        Returns:
            Tuple of (game_state, chat_id, message_id, inline_message_id)
            For inline messages: (game_state, None, None, inline_message_id)
            For regular messages: (game_state, chat_id, message_id, None)
            If game not found: (None, ...)
        """
        inline_message_id = query.inline_message_id
        
        if inline_message_id:
            game_state = self._get_game_state(inline_message_id=inline_message_id)
            return (game_state, None, None, inline_message_id)
        else:
            if not query.message or not query.message.chat:
                return (None, None, None, None)
            chat_id = query.message.chat.id
            message_id = query.message.message_id
            game_state = self._get_game_state(chat_id, message_id)
            return (game_state, chat_id, message_id, None)
    
    def _get_current_player_id(self, game_state: dict) -> Optional[int]:
        """Get the ID of the player whose turn it is."""
        current_turn = game_state.get("current_turn")
        if current_turn == BLUE:
            return game_state.get("blue_player_id")
        elif current_turn == YELLOW:
            return game_state.get("yellow_player_id")
        return None
    
    def _validate_player_in_game(self, user_id: int, game_state: dict) -> bool:
        """Check if user is a player in the game."""
        return (user_id == game_state.get("blue_player_id") or 
                user_id == game_state.get("yellow_player_id"))
    
    def _validate_player_turn(self, user_id: int, game_state: dict) -> bool:
        """Check if it's the user's turn."""
        current_player_id = self._get_current_player_id(game_state)
        return current_player_id == user_id

    async def select_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle piece selection and show available moves."""
        query = update.callback_query
        start_time = time.time()
        user_id = query.from_user.id
        callback_id = f"{query.id}_{user_id}"
        
        # Check for duplicate callbacks
        if self._is_duplicate_callback(callback_id):
            logger.warning(f"[select_callback] Duplicate callback ignored: user={user_id}, callback_id={query.id}")
            await query.answer("⏳ Обробка попереднього запиту...", show_alert=False)
            return
        
        try:
            game_state, chat_id, message_id, inline_message_id = self._get_game_state_from_query(query)
            
            if not game_state:
                await query.answer(locales.ERROR_NO_GAME, show_alert=True)
                if chat_id is not None and message_id is not None:
                    try:
                        await self._safe_edit_message(context.bot, chat_id=chat_id, message_id=message_id, text=locales.ERROR_NO_GAME)
                    except Exception as e:
                        logger.error(f"[select_callback] Failed to edit message: {e}")
                return

            engine = CheckersEngine()
            engine.set_board_state({
                "board": game_state["board"],
                "current_turn": game_state["current_turn"],
                "move_count": game_state.get("move_count", 0)
            })

            if not self._validate_player_in_game(user_id, game_state):
                await query.answer("❌ Ви не є гравцем у цій грі!", show_alert=True)
                return

            if not self._validate_player_turn(user_id, game_state):
                await query.answer(locales.ERROR_NOT_YOUR_TURN, show_alert=True)
                return

            pending_capture = game_state.get("pending_capture")
            try:
                from_pos = int(query.data.split("_")[1])
            except (ValueError, IndexError) as e:
                logger.error(f"[select_callback] Invalid callback data: user={user_id}, data={query.data}, error={e}")
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

            logger.info(
                "[move:select] user=%s chat=%s pending=%s from=%s legal=%s",
                user_id,
                query.message.chat.id if query.message else None,
                pending_capture,
                from_pos,
                len(legal_moves),
            )

            # Answer callback and update board
            await query.answer()
            
            if inline_message_id:
                await self._update_inline_game_message(context.bot, inline_message_id, engine, game_state, selected_pos=from_pos)
            else:
                await self._update_game_message(query.message, engine, game_state, context, selected_pos=from_pos)
            
            elapsed = (time.time() - start_time) * 1000
            logger.debug(f"[select_callback] Completed in {elapsed:.2f}ms: user={user_id}, from_pos={from_pos}")
            
        except asyncio.TimeoutError:
            logger.error(f"[select_callback] Timeout: user={user_id}, chat_id={chat_id if 'chat_id' in locals() else None}")
            await query.answer("⏱️ Операція зайняла занадто багато часу. Спробуйте ще раз.", show_alert=True)
        except Exception as e:
            logger.exception(f"[select_callback] Error: user={user_id}, error={e}")
            await query.answer("❌ Сталася помилка. Спробуйте ще раз.", show_alert=True)

    async def move_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle executing a move selection."""
        query = update.callback_query
        start_time = time.time()
        user_id = query.from_user.id
        callback_id = f"{query.id}_{user_id}"
        
        # Check for duplicate callbacks
        if self._is_duplicate_callback(callback_id):
            logger.warning(f"[move_callback] Duplicate callback ignored: user={user_id}, callback_id={query.id}")
            await query.answer("⏳ Обробка попереднього запиту...", show_alert=False)
            return
        
        try:
            game_state, chat_id, message_id, inline_message_id = self._get_game_state_from_query(query)
            
            if not game_state:
                await query.answer(locales.ERROR_NO_GAME, show_alert=True)
                if chat_id is not None and message_id is not None:
                    try:
                        await self._safe_edit_message(context.bot, chat_id=chat_id, message_id=message_id, text=locales.ERROR_NO_GAME)
                    except Exception as e:
                        logger.error(f"[move_callback] Failed to edit message: {e}")
                return

            engine = CheckersEngine()
            engine.set_board_state({
                "board": game_state["board"],
                "current_turn": game_state["current_turn"],
                "move_count": game_state.get("move_count", 0)
            })

            if not self._validate_player_in_game(user_id, game_state):
                await query.answer("❌ Ви не є гравцем у цій грі!", show_alert=True)
                return

            if not self._validate_player_turn(user_id, game_state):
                await query.answer(locales.ERROR_NOT_YOUR_TURN, show_alert=True)
                return

            pending_capture = game_state.get("pending_capture")

            try:
                _, from_pos, to_pos = query.data.split("_")
                from_pos = int(from_pos)
                to_pos = int(to_pos)
            except (ValueError, IndexError) as e:
                logger.error(f"[move_callback] Invalid callback data: user={user_id}, data={query.data}, error={e}")
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

            # Build legal move list consistent with capture UI (single-hop when captures exist)
            if pending_capture:
                legal_moves = engine.find_single_hop_captures(pending_capture["pos"])
            else:
                all_moves = engine.get_legal_moves(engine.current_turn)
                capture_positions = {m.from_pos for m in all_moves if m.captures}
                if capture_positions:
                    # Must capture; restrict to single-hop captures from this piece
                    if from_pos not in capture_positions:
                        await query.answer(locales.ERROR_INVALID_MOVE, show_alert=True)
                        return
                    legal_moves = engine.find_single_hop_captures(from_pos)
                else:
                    legal_moves = [m for m in all_moves if m.from_pos == from_pos]
            move_to_apply = None
            
            for move in legal_moves:
                if move.from_pos == from_pos and move.to_pos == to_pos:
                    move_to_apply = move
                    break
            
            if not move_to_apply:
                await query.answer(locales.ERROR_INVALID_MOVE, show_alert=True)
                return
            
            logger.info(
                "[move:apply] user=%s chat=%s from=%s to=%s captures=%s pending_before=%s",
                user_id,
                query.message.chat.id if query.message else None,
                from_pos,
                to_pos,
                move_to_apply.captures,
                pending_capture,
            )
            
            # Answer callback before processing move
            await query.answer()

            # Record move in history before applying
            move_record = {
                "from": move_to_apply.from_pos,
                "to": move_to_apply.to_pos,
                "captures": move_to_apply.captures.copy() if move_to_apply.captures else [],
                "board_before": engine.board.copy(),
                "player": "blue" if engine.current_turn == BLUE else "yellow"
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
                    engine.current_turn = BLUE if previous_turn == YELLOW else YELLOW

            # Check for winner (after finalizing whose turn it is)
            winner = engine.check_winner()
            
            if winner:
                # Game over - use unified handler
                await self._handle_game_end(
                    context=context,
                    engine=engine,
                    game_state=game_state,
                    winner=winner,
                    chat_id=chat_id,
                    message_id=message_id,
                    inline_message_id=inline_message_id,
                    query=query
                )
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
                
                elapsed = (time.time() - start_time) * 1000
                logger.debug(f"[move_callback] Completed in {elapsed:.2f}ms: user={user_id}, from={from_pos if 'from_pos' in locals() else None}, to={to_pos if 'to_pos' in locals() else None}")
            
        except asyncio.TimeoutError:
            logger.error(f"[move_callback] Timeout: user={user_id}, chat_id={chat_id if 'chat_id' in locals() else None}")
            await query.answer("⏱️ Операція зайняла занадто багато часу. Спробуйте ще раз.", show_alert=True)
        except Exception as e:
            logger.exception(f"[move_callback] Error: user={user_id}, error={e}")
            await query.answer("❌ Сталася помилка. Спробуйте ще раз.", show_alert=True)
    
    async def back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle back button - return to piece selection."""
        query = update.callback_query
        start_time = time.time()
        user_id = query.from_user.id
        callback_id = f"{query.id}_{user_id}"
        
        # Check for duplicate callbacks
        if self._is_duplicate_callback(callback_id):
            logger.warning(f"[back_callback] Duplicate callback ignored: user={user_id}, callback_id={query.id}")
            await query.answer("⏳ Обробка попереднього запиту...", show_alert=False)
            return
        
        try:
            # Check if this is an inline message
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
                    await query.answer(locales.ERROR_NO_GAME, show_alert=True)
                    try:
                        await self._safe_edit_message(context.bot, chat_id=chat_id, message_id=message_id, text=locales.ERROR_NO_GAME)
                    except Exception as e:
                        logger.error(f"[back_callback] Failed to edit message: {e}")
                    return

            # Only active player of the game may cancel selection
            if not self._validate_player_in_game(user_id, game_state):
                await query.answer("❌ Ви не є гравцем у цій грі!", show_alert=True)
                return

            if not self._validate_player_turn(user_id, game_state):
                await query.answer(locales.ERROR_NOT_YOUR_TURN, show_alert=True)
                return
            
            # Load engine state
            engine = CheckersEngine()
            engine.set_board_state({
                "board": game_state["board"],
                "current_turn": game_state["current_turn"],
                "move_count": game_state.get("move_count", 0)
            })
            
            # Answer callback and update board
            await query.answer()
            
            # Show board with piece selection
            if inline_message_id:
                await self._update_inline_game_message(context.bot, inline_message_id, engine, game_state)
            else:
                await self._update_game_message(query.message, engine, game_state, context)
            
            elapsed = (time.time() - start_time) * 1000
            logger.debug(f"[back_callback] Completed in {elapsed:.2f}ms: user={user_id}")
            
        except asyncio.TimeoutError:
            logger.error(f"[back_callback] Timeout: user={user_id}, chat_id={chat_id if 'chat_id' in locals() else None}")
            await query.answer("⏱️ Операція зайняла занадто багато часу. Спробуйте ще раз.", show_alert=True)
        except Exception as e:
            logger.exception(f"[back_callback] Error: user={user_id}, error={e}")
            await query.answer("❌ Сталася помилка. Спробуйте ще раз.", show_alert=True)
    
    async def forfeit_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle forfeit/cancel button."""
        query = update.callback_query
        start_time = time.time()
        user_id = query.from_user.id
        callback_id = f"{query.id}_{user_id}"
        
        # Check for duplicate callbacks
        if self._is_duplicate_callback(callback_id):
            logger.warning(f"[forfeit_callback] Duplicate callback ignored: user={user_id}, callback_id={query.id}")
            await query.answer("⏳ Обробка попереднього запиту...", show_alert=False)
            return
        
        try:
            game_state, chat_id, message_id, inline_message_id = self._get_game_state_from_query(query)
            
            if not game_state:
                await query.answer(locales.ERROR_NO_GAME, show_alert=True)
                if chat_id is not None and message_id is not None:
                    try:
                        await self._safe_edit_message(context.bot, chat_id=chat_id, message_id=message_id, text=locales.ERROR_NO_GAME)
                    except Exception as e:
                        logger.error(f"[forfeit_callback] Failed to edit message: {e}")
                return
            
            # Answer callback early
            await query.answer()
            
            # Verify user is actually a player in this game
            if not self._validate_player_in_game(user_id, game_state):
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
                        await self._safe_edit_message(
                            context.bot,
                            inline_message_id=inline_message_id,
                            text=cancel_message,
                            reply_markup=None
                        )
                    except (asyncio.TimeoutError, Exception) as e:
                        logger.warning(f"[forfeit_callback] Failed to update inline cancel message: {e}")
                    self.repo.delete_inline_game(inline_message_id)
                # For private matches, update both players' messages
                elif game_state.get("is_private_match"):
                    try:
                        await self._safe_edit_message(
                            context.bot,
                            chat_id=game_state["opponent_chat_id"],
                            message_id=game_state["opponent_message_id"],
                            text=cancel_message,
                            reply_markup=None
                        )
                    except (asyncio.TimeoutError, Exception) as e:
                        logger.warning(f"[forfeit_callback] Failed to update opponent cancel message: {e}")
                    
                    try:
                        await self._safe_edit_message(
                            context.bot,
                            chat_id=game_state["challenger_chat_id"],
                            message_id=game_state["challenger_message_id"],
                            text=cancel_message,
                            reply_markup=None
                        )
                    except (asyncio.TimeoutError, Exception) as e:
                        logger.warning(f"[forfeit_callback] Failed to update challenger cancel message: {e}")
                    
                    # Delete game from both chats
                    self.repo.delete_game(game_state["opponent_chat_id"], game_state["opponent_message_id"])
                    self.repo.delete_game(game_state["challenger_chat_id"], game_state["challenger_message_id"])
                else:
                    if not inline_message_id:  # Only edit if not inline (already handled above)
                        try:
                            await asyncio.wait_for(
                                query.edit_message_text(
                                    cancel_message,
                                    reply_markup=None
                                ),
                                timeout=MESSAGE_EDIT_TIMEOUT
                            )
                        except (asyncio.TimeoutError, Exception) as e:
                            logger.warning(f"[forfeit_callback] Failed to update regular cancel message: {e}")
                        # Delete game
                        self.repo.delete_game(chat_id, message_id)
                return

            # Determine winner (opponent of forfeiting player)
            if user_id == game_state["blue_player_id"]:
                winner = YELLOW  # Opponent wins
            else:
                winner = BLUE  # Opponent wins
            
            # Load engine for final board display
            engine = CheckersEngine()
            engine.set_board_state({
                "board": game_state["board"],
                "current_turn": game_state["current_turn"],
                "move_count": move_count
            })
            
            # Use unified game end handler, but modify message to indicate forfeit
            # We'll need to extend the handler to support custom messages, but for now
            # we'll use it and then update the message
            await self._handle_game_end(
                context=context,
                engine=engine,
                game_state=game_state,
                winner=winner,
                chat_id=chat_id,
                message_id=message_id,
                inline_message_id=inline_message_id,
                query=query
            )
            
            # Update message to indicate forfeit (modify the final message)
            winner_name = game_state["yellow_player_name"] if winner == YELLOW else game_state["blue_player_name"]
            forfeit_suffix = "\n(Суперник здався)"
            
            # Re-fetch and update the message with forfeit indication
            # This is a bit hacky but works for now
            board_text = BoardRenderer.render(engine.board)
            mode = game_state.get("mode", "rated")
            
            if self.rating_system and mode == "rated":
                winner_id = game_state["yellow_player_id"] if winner == YELLOW else game_state["blue_player_id"]
                loser_id = game_state["blue_player_id"] if winner == YELLOW else game_state["yellow_player_id"]
                winner_name_full = game_state["yellow_player_name"] if winner == YELLOW else game_state["blue_player_name"]
                loser_name = game_state["blue_player_name"] if winner == YELLOW else game_state["yellow_player_name"]
                
                # Get rating data (already recorded in _handle_game_end)
                winner_data = await self.rating_system.get_player(winner_id, winner_name_full)
                loser_data = await self.rating_system.get_player(loser_id, loser_name)
                
                win_msg = locales.WINNER_WITH_RATING.format(
                    name=winner_name,
                    winner_name=winner_name,
                    winner_rating=winner_data["rating"],
                    winner_change=0,  # Change already applied
                    loser_name=loser_name,
                    loser_rating=loser_data["rating"],
                    loser_change=0
                )
            else:
                win_msg = locales.WINNER.format(name=winner_name)
            
            forfeit_message = f"{board_text}\n\n{win_msg}{forfeit_suffix}"
            
            # Update the message with forfeit indication
            if inline_message_id:
                try:
                    await self._safe_edit_message(
                        context.bot,
                        inline_message_id=inline_message_id,
                        text=forfeit_message,
                        reply_markup=None
                    )
                except Exception:
                    pass  # Already updated by _handle_game_end
            elif game_state.get("is_private_match"):
                try:
                    await self._safe_edit_message(
                        context.bot,
                        chat_id=game_state["opponent_chat_id"],
                        message_id=game_state["opponent_message_id"],
                        text=forfeit_message,
                        reply_markup=None
                    )
                except Exception:
                    pass
                try:
                    await self._safe_edit_message(
                        context.bot,
                        chat_id=game_state["challenger_chat_id"],
                        message_id=game_state["challenger_message_id"],
                        text=forfeit_message,
                        reply_markup=None
                    )
                except Exception:
                    pass
            elif chat_id is not None and message_id is not None:
                try:
                    if query:
                        await query.edit_message_text(forfeit_message, reply_markup=None)
                    else:
                        await self._safe_edit_message(
                            context.bot,
                            chat_id=chat_id,
                            message_id=message_id,
                            text=forfeit_message,
                            reply_markup=None
                        )
                except Exception:
                    pass
            
            elapsed = (time.time() - start_time) * 1000
            logger.debug(f"[forfeit_callback] Completed in {elapsed:.2f}ms: user={user_id}, move_count={move_count}")
            
        except asyncio.TimeoutError:
            logger.error(f"[forfeit_callback] Timeout: user={user_id}, chat_id={chat_id if 'chat_id' in locals() else None}")
            await query.answer("⏱️ Операція зайняла занадто багато часу. Спробуйте ще раз.", show_alert=True)
        except Exception as e:
            logger.exception(f"[forfeit_callback] Error: user={user_id}, error={e}")
            await query.answer("❌ Сталася помилка. Спробуйте ще раз.", show_alert=True)
    
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
        if user.id == game_state["blue_player_id"]:
            opponent_name = game_state["yellow_player_name"]
        else:
            opponent_name = game_state["blue_player_name"]
        
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
        if user.id == game_state["blue_player_id"]:
            opponent_name = game_state["yellow_player_name"]
        else:
            opponent_name = game_state["blue_player_name"]
        
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
        if user.id != game_state["blue_player_id"] and user.id != game_state["yellow_player_id"]:
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
        opponent_id = game_state["yellow_player_id"] if user.id == game_state["blue_player_id"] else game_state["blue_player_id"]
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
        if user.id != game_state["blue_player_id"] and user.id != game_state["yellow_player_id"]:
            await query.answer("❌ Ви не є гравцем у цій грі!", show_alert=True)
            return
        
        # Determine winner (opponent)
        if user.id == game_state["blue_player_id"]:
            winner_id = game_state["yellow_player_id"]
            winner_name = game_state["yellow_player_name"]
            loser_id = game_state["blue_player_id"]
            loser_name = game_state["blue_player_name"]
        else:
            winner_id = game_state["blue_player_id"]
            winner_name = game_state["blue_player_name"]
            loser_id = game_state["yellow_player_id"]
            loser_name = game_state["yellow_player_name"]
        
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
    
    async def achievements_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show player achievements overview."""
        user = update.effective_user
        chat = update.effective_chat
        
        if not self.achievement_system:
            await update.message.reply_text("❌ Система досягнень не налаштована.")
            return
        
        # Get player achievements
        player_achievements = await self.achievement_system.get_player_achievements(user.id)
        all_achievements = await self.achievement_system.get_all_achievements()
        
        unlocked_count = len(player_achievements)
        total_count = len(all_achievements)
        percentage = int((unlocked_count / total_count * 100)) if total_count > 0 else 0
        
        # Group by category
        categories = {
            "milestone": {"name": "🎯 Віхи", "count": 0, "unlocked": 0},
            "rank": {"name": "🏅 Ранги", "count": 0, "unlocked": 0},
            "streak": {"name": "🔥 Серії", "count": 0, "unlocked": 0},
            "victory": {"name": "⚔️ Перемоги", "count": 0, "unlocked": 0},
            "statistics": {"name": "📊 Статистика", "count": 0, "unlocked": 0},
            "gameplay": {"name": "🎮 Геймплей", "count": 0, "unlocked": 0},
            "competitive": {"name": "🏆 Конкуренція", "count": 0, "unlocked": 0},
            "time": {"name": "⏰ Часові", "count": 0, "unlocked": 0},
            "special": {"name": "🎲 Особливі", "count": 0, "unlocked": 0},
            "collection": {"name": "🏅 Колекція", "count": 0, "unlocked": 0},
        }
        
        unlocked_ids = {ach["achievement_id"] for ach in player_achievements}
        
        for ach in all_achievements:
            cat = ach["category"]
            if cat in categories:
                categories[cat]["count"] += 1
                if ach["achievement_id"] in unlocked_ids:
                    categories[cat]["unlocked"] += 1
        
        # Build message
        message = f"🏆 <b>Ваші Досягнення</b>\n\n"
        message += f"📊 Загалом: {unlocked_count}/{total_count} ({percentage}%)\n\n"
        
        for cat_key, cat_info in categories.items():
            if cat_info["count"] > 0:
                status = "✅" if cat_info["unlocked"] == cat_info["count"] else "🔒"
                message += f"{cat_info['name']}: {cat_info['unlocked']}/{cat_info['count']} {status}\n"
        
        # Create keyboard with category buttons
        keyboard_buttons = []
        row = []
        for cat_key, cat_info in list(categories.items())[:5]:
            if cat_info["count"] > 0:
                row.append(InlineKeyboardButton(
                    f"{cat_info['name']} ({cat_info['unlocked']}/{cat_info['count']})",
                    callback_data=f"ach_category_{cat_key}"
                ))
                if len(row) == 2:
                    keyboard_buttons.append(row)
                    row = []
        if row:
            keyboard_buttons.append(row)
        
        # Second row
        row = []
        for cat_key, cat_info in list(categories.items())[5:]:
            if cat_info["count"] > 0:
                row.append(InlineKeyboardButton(
                    f"{cat_info['name']} ({cat_info['unlocked']}/{cat_info['count']})",
                    callback_data=f"ach_category_{cat_key}"
                ))
                if len(row) == 2:
                    keyboard_buttons.append(row)
                    row = []
        if row:
            keyboard_buttons.append(row)
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await update.message.reply_text(message, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    
    async def achievement_category_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show achievements in a specific category."""
        query = update.callback_query
        await query.answer()
        
        user = query.from_user
        category = query.data.replace("ach_category_", "")
        
        if not self.achievement_system:
            await query.edit_message_text("❌ Система досягнень не налаштована.")
            return
        
        # Get all achievements in category
        all_achievements = await self.achievement_system.get_all_achievements()
        category_achievements = [a for a in all_achievements if a["category"] == category]
        
        # Get player achievements
        player_achievements = await self.achievement_system.get_player_achievements(user.id)
        unlocked_ids = {ach["achievement_id"] for ach in player_achievements}
        
        # Get player data for progress
        if self.rating_system:
            player_data = await self.rating_system.get_player(user.id, user.first_name)
        else:
            player_data = {}
        
        # Build message
        category_names = {
            "milestone": "🎯 Віхи",
            "rank": "🏅 Ранги",
            "streak": "🔥 Серії",
            "victory": "⚔️ Перемоги",
            "statistics": "📊 Статистика",
            "gameplay": "🎮 Геймплей",
            "competitive": "🏆 Конкуренція",
            "time": "⏰ Часові",
            "special": "🎲 Особливі",
            "collection": "🏅 Колекція",
        }
        
        message = f"<b>{category_names.get(category, category)}</b>\n\n"
        
        for ach in category_achievements[:10]:  # Show first 10
            is_unlocked = ach["achievement_id"] in unlocked_ids
            status = "✅" if is_unlocked else "🔒"
            
            message += f"{status} {ach['icon']} <b>{ach['name_uk']}</b>\n"
            message += f"   {ach['description_uk']}\n"
            
            if not is_unlocked:
                # Show progress if available
                progress = await self.achievement_system.get_achievement_progress(
                    user.id, ach["achievement_id"], player_data
                )
                if progress and not progress.get("unlocked"):
                    pct = int(progress["progress"])
                    message += f"   Прогрес: {progress['current']}/{progress['max']} ({pct}%)\n"
            
            message += "\n"
        
        if len(category_achievements) > 10:
            message += f"\n... та ще {len(category_achievements) - 10} досягнень"
        
        # Back button
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад", callback_data="ach_back")
        ]])
        
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    
    async def achievement_back_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Return to achievements overview."""
        query = update.callback_query
        await query.answer()
        
        # Reuse achievements_command logic
        user = query.from_user
        
        if not self.achievement_system:
            await query.edit_message_text("❌ Система досягнень не налаштована.")
            return
        
        player_achievements = await self.achievement_system.get_player_achievements(user.id)
        all_achievements = await self.achievement_system.get_all_achievements()
        
        unlocked_count = len(player_achievements)
        total_count = len(all_achievements)
        percentage = int((unlocked_count / total_count * 100)) if total_count > 0 else 0
        
        # Group by category (same logic as achievements_command)
        categories = {
            "milestone": {"name": "🎯 Віхи", "count": 0, "unlocked": 0},
            "rank": {"name": "🏅 Ранги", "count": 0, "unlocked": 0},
            "streak": {"name": "🔥 Серії", "count": 0, "unlocked": 0},
            "victory": {"name": "⚔️ Перемоги", "count": 0, "unlocked": 0},
            "statistics": {"name": "📊 Статистика", "count": 0, "unlocked": 0},
            "gameplay": {"name": "🎮 Геймплей", "count": 0, "unlocked": 0},
            "competitive": {"name": "🏆 Конкуренція", "count": 0, "unlocked": 0},
            "time": {"name": "⏰ Часові", "count": 0, "unlocked": 0},
            "special": {"name": "🎲 Особливі", "count": 0, "unlocked": 0},
            "collection": {"name": "🏅 Колекція", "count": 0, "unlocked": 0},
        }
        
        unlocked_ids = {ach["achievement_id"] for ach in player_achievements}
        
        for ach in all_achievements:
            cat = ach["category"]
            if cat in categories:
                categories[cat]["count"] += 1
                if ach["achievement_id"] in unlocked_ids:
                    categories[cat]["unlocked"] += 1
        
        message = f"🏆 <b>Ваші Досягнення</b>\n\n"
        message += f"📊 Загалом: {unlocked_count}/{total_count} ({percentage}%)\n\n"
        
        for cat_key, cat_info in categories.items():
            if cat_info["count"] > 0:
                status = "✅" if cat_info["unlocked"] == cat_info["count"] else "🔒"
                message += f"{cat_info['name']}: {cat_info['unlocked']}/{cat_info['count']} {status}\n"
        
        # Create keyboard (same as achievements_command)
        keyboard_buttons = []
        row = []
        for cat_key, cat_info in list(categories.items())[:5]:
            if cat_info["count"] > 0:
                row.append(InlineKeyboardButton(
                    f"{cat_info['name']} ({cat_info['unlocked']}/{cat_info['count']})",
                    callback_data=f"ach_category_{cat_key}"
                ))
                if len(row) == 2:
                    keyboard_buttons.append(row)
                    row = []
        if row:
            keyboard_buttons.append(row)
        
        row = []
        for cat_key, cat_info in list(categories.items())[5:]:
            if cat_info["count"] > 0:
                row.append(InlineKeyboardButton(
                    f"{cat_info['name']} ({cat_info['unlocked']}/{cat_info['count']})",
                    callback_data=f"ach_category_{cat_key}"
                ))
                if len(row) == 2:
                    keyboard_buttons.append(row)
                    row = []
        if row:
            keyboard_buttons.append(row)
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await query.edit_message_text(message, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    
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
    
    async def _update_game_message(self, message, engine: CheckersEngine, game_state: dict, context: ContextTypes.DEFAULT_TYPE = None, selected_pos: Optional[int] = None) -> bool:
        """
        Update game message with current board and turn info.
        Returns True if successful, False otherwise.
        """
        # Check if this is an inline message
        if game_state.get("is_inline") and context:
            inline_message_id = game_state.get("inline_message_id")
            if inline_message_id:
                return await self._update_inline_game_message(context.bot, inline_message_id, engine, game_state, selected_pos)
        
        # Use MessageUpdater for regular and private match messages
        bot = context.bot if context else None
        return await MessageUpdater.update_message(
            bot=bot,
            game_state=game_state,
            engine=engine,
            selected_pos=selected_pos,
            message_obj=message
        )
    
    async def _update_inline_game_message(
        self,
        bot,
        inline_message_id: str,
        engine: CheckersEngine,
        game_state: dict,
        selected_pos: Optional[int] = None
    ) -> bool:
        """
        Update inline message with current game state.
        Returns True if successful, False otherwise.
        """
        return await MessageUpdater.update_message(
            bot=bot,
            game_state=game_state,
            engine=engine,
            selected_pos=selected_pos,
            inline_message_id=inline_message_id
        )
    
    async def _handle_game_end(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        engine: CheckersEngine,
        game_state: dict,
        winner: int,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        inline_message_id: Optional[str] = None,
        query=None
    ) -> None:
        """
        Handle game end: determine winner, update ratings, save game data, update messages, delete game.
        
        Args:
            context: Bot context
            engine: CheckersEngine instance with final board state
            game_state: Current game state
            winner: BLUE or YELLOW (winner color)
            chat_id: Chat ID (for regular messages)
            message_id: Message ID (for regular messages)
            inline_message_id: Inline message ID (for inline messages)
            query: Optional callback query (for regular messages)
        """
        # Determine winner and loser
        winner_id = game_state["blue_player_id"] if winner == BLUE else game_state["yellow_player_id"]
        winner_name = game_state["blue_player_name"] if winner == BLUE else game_state["yellow_player_name"]
        loser_id = game_state["yellow_player_id"] if winner == BLUE else game_state["blue_player_id"]
        loser_name = game_state["yellow_player_name"] if winner == BLUE else game_state["blue_player_name"]
        
        board_text = BoardRenderer.render(engine.board)
        mode = game_state.get("mode", "rated")
        
        # Record rating changes only for rated games if rating system available
        if self.rating_system and mode == "rated":
            # Get move count from game state if available
            move_count = game_state.get("move_count", engine.move_count)
            
            winner_data, loser_data = await self.rating_system.record_game(
                winner_id, winner_name, loser_id, loser_name,
                move_count=move_count
            )
            
            # Check achievements for both players
            if self.achievement_system:
                # Winner achievements
                winner_game_result = {
                    "won": True,
                    "rating_change": winner_data.get("rating_change", 0),
                    "move_count": move_count,
                    "moved_first": game_state.get("current_turn") == YELLOW,  # Simplified
                }
                winner_achievements = await self.achievement_system.check_achievements(
                    winner_id, winner_data, winner_game_result, loser_data
                )
                
                # Loser achievements
                loser_game_result = {
                    "won": False,
                    "rating_change": loser_data.get("rating_change", 0),
                    "move_count": move_count,
                }
                loser_achievements = await self.achievement_system.check_achievements(
                    loser_id, loser_data, loser_game_result, winner_data
                )
                
                # Store newly unlocked achievements for notification
                if winner_achievements:
                    game_state["winner_achievements"] = winner_achievements
                if loser_achievements:
                    game_state["loser_achievements"] = loser_achievements
            
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
            "blue_player_id": game_state["blue_player_id"],
            "blue_player_name": game_state["blue_player_name"],
            "yellow_player_id": game_state["yellow_player_id"],
            "yellow_player_name": game_state["yellow_player_name"],
            "winner_id": winner_id,
            "winner_name": winner_name,
            "winner_color": "blue" if winner == BLUE else "yellow",
            "initial_board": game_state.get("initial_board", CheckersEngine.init_board()),
            "move_history": game_state.get("move_history", []),
            "final_board": engine.board.copy(),
            "completed_at": datetime.utcnow().isoformat()
        }
        completed_at = completed_game_data["completed_at"]
        if self.game_data_repo:
            self.game_data_repo.save_completed_game(completed_game_data)
            # Add reference for both players
            self.game_data_repo.add_user_game_reference(game_state["blue_player_id"], game_id, completed_at)
            self.game_data_repo.add_user_game_reference(game_state["yellow_player_id"], game_id, completed_at)
        
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📺 Переглянути гру", callback_data=f"replay_{game_id}_0")
        ]])
        
        final_message = f"{board_text}\n\n{win_msg}"
        
        # Update messages based on game type
        if inline_message_id:
            try:
                await self._safe_edit_message(
                    context.bot,
                    inline_message_id=inline_message_id,
                    text=final_message,
                    reply_markup=keyboard
                )
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"[_handle_game_end] Failed to update inline game over message: {e}")
            # Delete inline game
            self.repo.delete_inline_game(inline_message_id)
        elif game_state.get("is_private_match"):
            try:
                # Update opponent's message
                await self._safe_edit_message(
                    context.bot,
                    chat_id=game_state["opponent_chat_id"],
                    message_id=game_state["opponent_message_id"],
                    text=final_message,
                    reply_markup=keyboard
                )
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"[_handle_game_end] Failed to update opponent game over message: {e}")
            
            try:
                # Update challenger's message
                await self._safe_edit_message(
                    context.bot,
                    chat_id=game_state["challenger_chat_id"],
                    message_id=game_state["challenger_message_id"],
                    text=final_message,
                    reply_markup=keyboard
                )
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"[_handle_game_end] Failed to update challenger game over message: {e}")
            
            # Delete game from both chats
            self.repo.delete_game(game_state["opponent_chat_id"], game_state["opponent_message_id"])
            self.repo.delete_game(game_state["challenger_chat_id"], game_state["challenger_message_id"])
        else:
            # Regular group chat
            try:
                if query:
                    await asyncio.wait_for(
                        query.edit_message_text(
                            final_message,
                            reply_markup=keyboard
                        ),
                        timeout=MESSAGE_EDIT_TIMEOUT
                    )
                elif chat_id is not None and message_id is not None:
                    await self._safe_edit_message(
                        context.bot,
                        chat_id=chat_id,
                        message_id=message_id,
                        text=final_message,
                        reply_markup=keyboard
                    )
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"[_handle_game_end] Failed to update regular game over message: {e}")
            
            # Delete game from Redis
            if chat_id is not None and message_id is not None:
                self.repo.delete_game(chat_id, message_id)
    
    @staticmethod
    def _get_player_tag(game_state: dict, color: str) -> str:
        """Get @mention or name for a player. Color is 'blue' or 'yellow'."""
        username = game_state.get(f"{color}_player_username")
        name = game_state[f"{color}_player_name"]
        
        if username:
            return f"@{username}"
        return name
    
    @staticmethod
    def _get_players_message(game_state: dict) -> str:
        """Get message showing both players with hyperlinked first names."""
        return MessageUpdater._get_players_message(game_state)
    
    @staticmethod
    def _get_turn_message(game_state: dict) -> str:
        """Get turn message for current player with hyperlinked first name."""
        return MessageUpdater._get_turn_message(game_state)
    
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
                await self._send_main_menu(query.message, edit=True)
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
            await self._send_main_menu(query.message, edit=True)
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

