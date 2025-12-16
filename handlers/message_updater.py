"""
Message update utilities for inline and regular game messages.
"""

import asyncio
import logging
from typing import Optional
from telegram import InlineKeyboardMarkup
from telegram.constants import ParseMode
from engine import CheckersEngine
from .board_renderer import BoardRenderer
from .constants import MESSAGE_EDIT_TIMEOUT

logger = logging.getLogger(__name__)


class MessageUpdater:
    """Helper class for updating game messages (inline and regular)."""
    
    @staticmethod
    async def _safe_edit_message(bot, timeout: float = MESSAGE_EDIT_TIMEOUT, **kwargs) -> None:
        """
        Safely edit a message with timeout handling.
        Raises asyncio.TimeoutError if timeout occurs.
        """
        try:
            return await asyncio.wait_for(
                bot.edit_message_text(**kwargs),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Timeout editing message: chat_id={kwargs.get('chat_id')}, message_id={kwargs.get('message_id')}, inline_message_id={kwargs.get('inline_message_id')}")
            raise
    
    @staticmethod
    def _get_players_message(game_state: dict) -> str:
        """Get message showing both players with hyperlinked first names."""
        blue_player_id = game_state.get("blue_player_id")
        blue_player_name = game_state.get("blue_player_name", "Blue")
        yellow_player_id = game_state.get("yellow_player_id")
        yellow_player_name = game_state.get("yellow_player_name", "Yellow")
        
        # Create hyperlinked first names
        blue_tag = f'<a href="tg://user?id={blue_player_id}">{blue_player_name}</a>' if blue_player_id else blue_player_name
        yellow_tag = f'<a href="tg://user?id={yellow_player_id}">{yellow_player_name}</a>' if yellow_player_id else yellow_player_name
        
        return f"🔵 {blue_tag}  vs  🟡 {yellow_tag}"
    
    @staticmethod
    def _get_turn_message(game_state: dict) -> str:
        """Get turn message for current player with hyperlinked first name."""
        import locales
        from engine import BLUE, YELLOW
        
        current_turn = game_state["current_turn"]
        
        if current_turn == BLUE:
            player_id = game_state.get("blue_player_id")
            name = game_state.get("blue_player_name", "Blue")
            # Create hyperlinked first name
            player_tag = f'<a href="tg://user?id={player_id}">{name}</a>' if player_id else name
            return locales.TURN_RED.format(player_tag=player_tag)
        else:
            player_id = game_state.get("yellow_player_id")
            name = game_state.get("yellow_player_name", "Yellow")
            # Create hyperlinked first name
            player_tag = f'<a href="tg://user?id={player_id}">{name}</a>' if player_id else name
            return locales.TURN_WHITE.format(player_tag=player_tag)
    
    @staticmethod
    async def update_message(
        bot,
        game_state: dict,
        engine: CheckersEngine,
        selected_pos: Optional[int] = None,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        inline_message_id: Optional[str] = None,
        message_obj=None
    ) -> bool:
        """
        Unified method to update game messages (inline or regular).
        
        Args:
            bot: Bot instance
            game_state: Current game state
            engine: CheckersEngine instance
            selected_pos: Optional selected piece position
            chat_id: Chat ID (for regular messages)
            message_id: Message ID (for regular messages)
            inline_message_id: Inline message ID (for inline messages)
            message_obj: Message object (for regular messages, alternative to chat_id/message_id)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            board_text = BoardRenderer.render(engine.board)
            players_msg = MessageUpdater._get_players_message(game_state)
            turn_msg = MessageUpdater._get_turn_message(game_state)
            keyboard = BoardRenderer.create_move_keyboard(
                engine,
                selected_pos=selected_pos,
                move_count=engine.move_count,
                pending_capture=game_state.get("pending_capture")
            )
            
            message_text = f"{players_msg}\n\n{board_text}\n\n{turn_msg}"
            
            # Handle inline messages
            if inline_message_id:
                return await MessageUpdater._update_inline(bot, inline_message_id, message_text, keyboard)
            
            # Handle private matches (update both players' messages)
            if game_state.get("is_private_match"):
                return await MessageUpdater._update_private_match(bot, game_state, message_text, keyboard)
            
            # Handle regular group chat messages
            if message_obj:
                return await MessageUpdater._update_regular_message(message_obj, message_text, keyboard)
            elif chat_id is not None and message_id is not None:
                return await MessageUpdater._update_regular_by_id(bot, chat_id, message_id, message_text, keyboard)
            
            return False
        except Exception as e:
            logger.exception(f"[MessageUpdater] Unexpected error: {e}")
            return False
    
    @staticmethod
    async def _update_inline(bot, inline_message_id: str, message_text: str, keyboard: InlineKeyboardMarkup) -> bool:
        """Update an inline message."""
        try:
            await MessageUpdater._safe_edit_message(
                bot,
                inline_message_id=inline_message_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
            return True
        except asyncio.TimeoutError:
            logger.error(f"[MessageUpdater] Timeout updating inline message: {inline_message_id}")
            return False
        except Exception as e:
            logger.warning(f"[MessageUpdater] Failed to update inline message: {inline_message_id}, error={e}")
            return False
    
    @staticmethod
    async def _update_private_match(bot, game_state: dict, message_text: str, keyboard: InlineKeyboardMarkup) -> bool:
        """Update both players' messages in a private match."""
        success = True
        try:
            await MessageUpdater._safe_edit_message(
                bot,
                chat_id=game_state["opponent_chat_id"],
                message_id=game_state["opponent_message_id"],
                text=message_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        except asyncio.TimeoutError:
            logger.error(f"[MessageUpdater] Timeout updating opponent message: chat_id={game_state.get('opponent_chat_id')}")
            success = False
        except Exception as e:
            logger.warning(f"[MessageUpdater] Failed to update opponent message: chat_id={game_state.get('opponent_chat_id')}, error={e}")
            success = False
        
        try:
            await MessageUpdater._safe_edit_message(
                bot,
                chat_id=game_state["challenger_chat_id"],
                message_id=game_state["challenger_message_id"],
                text=message_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
        except asyncio.TimeoutError:
            logger.error(f"[MessageUpdater] Timeout updating challenger message: chat_id={game_state.get('challenger_chat_id')}")
            success = False
        except Exception as e:
            logger.warning(f"[MessageUpdater] Failed to update challenger message: chat_id={game_state.get('challenger_chat_id')}, error={e}")
            success = False
        
        return success
    
    @staticmethod
    async def _update_regular_message(message_obj, message_text: str, keyboard: InlineKeyboardMarkup) -> bool:
        """Update a regular message using message object."""
        try:
            await asyncio.wait_for(
                message_obj.edit_text(
                    message_text,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML
                ),
                timeout=MESSAGE_EDIT_TIMEOUT
            )
            return True
        except asyncio.TimeoutError:
            logger.error("[MessageUpdater] Timeout updating regular message")
            return False
        except Exception as e:
            logger.warning(f"[MessageUpdater] Failed to update regular message: error={e}")
            return False
    
    @staticmethod
    async def _update_regular_by_id(bot, chat_id: int, message_id: int, message_text: str, keyboard: InlineKeyboardMarkup) -> bool:
        """Update a regular message using chat_id and message_id."""
        try:
            await MessageUpdater._safe_edit_message(
                bot,
                chat_id=chat_id,
                message_id=message_id,
                text=message_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML
            )
            return True
        except asyncio.TimeoutError:
            logger.error(f"[MessageUpdater] Timeout updating regular message: chat_id={chat_id}, message_id={message_id}")
            return False
        except Exception as e:
            logger.warning(f"[MessageUpdater] Failed to update regular message: chat_id={chat_id}, message_id={message_id}, error={e}")
            return False

