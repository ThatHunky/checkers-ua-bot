# Inline Mode Implementation Guide

## Overview

This document explains how to implement **inline mode** for the Ukrainian Checkers Telegram Bot. Inline mode allows users to use the bot in any group or private chat **without adding the bot** to that chat.

## What is Inline Mode?

Inline mode is a Telegram Bot API feature that enables bots to provide results that users can send directly to chats. Users trigger inline mode by typing `@botname query` in any chat (group, supergroup, or private).

### Key Benefits

1. **No Bot Addition Required**: Users can play checkers in any group without adding the bot as a member
2. **Universal Access**: Works in groups, supergroups, and private chats
3. **Seamless Integration**: Results appear as interactive messages that can be sent to any chat
4. **Better User Experience**: No need to add/remove bots from groups

## How Inline Mode Works

### User Flow

1. User types `@botname` or `@botname play` in any chat
2. Telegram sends an `InlineQuery` update to the bot
3. Bot responds with `InlineQueryResult` objects (up to 50 results)
4. User sees a list of results and selects one
5. Telegram sends a `ChosenInlineResult` update to the bot
6. The selected result is sent to the chat as a message

### Telegram API Flow

```
User types: @checkers_bot play
    ↓
Telegram → Bot: InlineQuery (query="play", from_user, chat_type)
    ↓
Bot → Telegram: answerInlineQuery([InlineQueryResultArticle, ...])
    ↓
User selects result
    ↓
Telegram → Bot: ChosenInlineResult (result_id, from_user, inline_message_id)
    ↓
Result appears in chat as message
```

## Implementation Strategy

### Approach 1: Challenge Creation (Recommended)

When a user types `@botname play` or `@botname challenge @username`:

1. **InlineQuery Handler**: 
   - Parse the query to determine intent
   - Show results like "Start Challenge", "Challenge @username", etc.
   - Each result contains a unique `result_id` with game metadata

2. **ChosenInlineResult Handler**:
   - Create a game challenge
   - Send an interactive message to the chat with inline keyboard
   - Store game state in Redis keyed by `inline_message_id`

3. **Game Interaction**:
   - Use `inline_message_id` instead of `chat_id` + `message_id` for game state
   - Update the inline message using `edit_message_text` with `inline_message_id`
   - Handle callback queries normally (they work with inline messages)

### Approach 2: Direct Game Board

When a user types `@botname play`:

1. **InlineQuery Handler**:
   - Show a single result: "Start Checkers Game"
   - Result contains initial game state

2. **ChosenInlineResult Handler**:
   - Create a new game
   - Send game board as inline message
   - Store game state keyed by `inline_message_id`

3. **Game Interaction**:
   - Players interact via callback buttons
   - Bot updates the inline message after each move

## Technical Implementation

### 1. Enable Inline Mode in BotFather

First, enable inline mode for your bot:

```
/start
/setinline
@your_bot_name
[Enable inline mode]
```

Optionally set inline placeholder text:
```
/setinlinefeedback
@your_bot_name
[Enable inline feedback]
```

### 2. Add InlineQuery Handler

In `main.py`, add the handler:

```python
from telegram.ext import InlineQueryHandler, ChosenInlineResultHandler

# Register inline query handler
application.add_handler(InlineQueryHandler(handlers.inline_query_handler))

# Register chosen inline result handler
application.add_handler(ChosenInlineResultHandler(handlers.chosen_inline_result_handler))
```

### 3. Implement Inline Query Handler

In `handlers.py`, add the handler method:

```python
from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram.constants import ParseMode

async def inline_query_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline queries when user types @botname."""
    query = update.inline_query
    user = query.from_user
    
    # Register user
    self.repo.register_user(user.id, user.username, user.first_name)
    
    # Parse query
    query_text = query.query.strip().lower()
    
    results = []
    
    # Default: Show "Start Challenge" option
    if not query_text or query_text == "play" or query_text == "start":
        results.append(
            InlineQueryResultArticle(
                id="challenge",
                title="🎮 Start Checkers Challenge",
                description="Create a challenge that anyone can join",
                input_message_content=InputTextMessageContent(
                    message_text="🎮 <b>Checkers Challenge</b>\n\n"
                                f"{user.first_name} wants to play Ukrainian Checkers!\n"
                                "Click the button below to join.",
                    parse_mode=ParseMode.HTML
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⚔️ Join Game", callback_data="join")
                ]])
            )
        )
    
    # If query contains @username, show challenge option
    elif query_text.startswith("@") or "challenge" in query_text:
        # Extract username if present
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
                results.append(
                    InlineQueryResultArticle(
                        id=f"challenge_{username}",
                        title=f"🎮 Challenge @{username}",
                        description=f"Challenge {opponent_info['first_name']} to a game",
                        input_message_content=InputTextMessageContent(
                            message_text=f"🎮 <b>{user.first_name}</b> challenges <b>@{username}</b> to Ukrainian Checkers!",
                            parse_mode=ParseMode.HTML
                        ),
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("✅ Accept", callback_data=f"accept_inline_{username}")
                        ]])
                    )
                )
            else:
                results.append(
                    InlineQueryResultArticle(
                        id="user_not_found",
                        title="❌ User Not Found",
                        description=f"@{username} hasn't used this bot yet",
                        input_message_content=InputTextMessageContent(
                            message_text=f"❌ User @{username} not found. They need to use /start with the bot first."
                        )
                    )
                )
        else:
            # Show challenge option
            results.append(
                InlineQueryResultArticle(
                    id="challenge",
                    title="🎮 Start Challenge",
                    description="Type: @botname challenge @username",
                    input_message_content=InputTextMessageContent(
                        message_text="🎮 Checkers Challenge! Click to join.",
                        parse_mode=ParseMode.HTML
                    )
                )
            )
    
    # Answer the inline query
    await query.answer(results, cache_time=1)
```

### 4. Implement Chosen Inline Result Handler

```python
async def chosen_inline_result_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle when user selects an inline result."""
    chosen_result = update.chosen_inline_result
    user = chosen_result.from_user
    result_id = chosen_result.result_id
    inline_message_id = chosen_result.inline_message_id
    
    # Register user
    self.repo.register_user(user.id, user.username, user.first_name)
    
    if result_id == "challenge":
        # Create a challenge game
        # Store challenge info temporarily (similar to group challenge)
        # The actual game starts when someone clicks "Join Game"
        challenge_data = {
            "red_player_id": user.id,
            "red_player_name": user.first_name,
            "red_player_username": user.username,
            "inline_message_id": inline_message_id,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Store in Redis with inline_message_id as key
        challenge_key = f"checkers:inline_challenge:{inline_message_id}"
        self.repo.redis_client.setex(
            challenge_key,
            300,  # 5 minutes TTL
            json.dumps(challenge_data)
        )
    
    elif result_id.startswith("challenge_"):
        # Direct challenge to specific user
        username = result_id.replace("challenge_", "")
        # Handle direct challenge logic
        # ...
```

### 5. Update Repository for Inline Messages

Add methods to `repository.py`:

```python
@staticmethod
def _make_inline_key(inline_message_id: str) -> str:
    """Generate Redis key for an inline message game."""
    return f"checkers:inline_game:{inline_message_id}"

def save_inline_game(self, inline_message_id: str, game_state: dict) -> bool:
    """Save game state for inline message."""
    try:
        key = self._make_inline_key(inline_message_id)
        value = json.dumps(game_state)
        self.redis_client.setex(key, self.ttl, value)
        return True
    except Exception as e:
        print(f"Error saving inline game: {e}")
        return False

def get_inline_game(self, inline_message_id: str) -> Optional[dict]:
    """Get game state for inline message."""
    try:
        key = self._make_inline_key(inline_message_id)
        value = self.redis_client.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        print(f"Error getting inline game: {e}")
        return None

def delete_inline_game(self, inline_message_id: str) -> bool:
    """Delete inline game state."""
    try:
        key = self._make_inline_key(inline_message_id)
        self.redis_client.delete(key)
        return True
    except Exception as e:
        print(f"Error deleting inline game: {e}")
        return False
```

### 6. Update Game Handlers for Inline Messages

Modify existing handlers to support inline messages:

```python
async def join_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle join button - works for both regular and inline messages."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    message = query.message
    
    # Check if this is an inline message
    if message and hasattr(message, 'inline_message_id') and message.inline_message_id:
        inline_message_id = message.inline_message_id
        
        # Get challenge from inline message
        challenge_key = f"checkers:inline_challenge:{inline_message_id}"
        challenge_data_json = self.repo.redis_client.get(challenge_key)
        
        if not challenge_data_json:
            await query.answer("Challenge expired", show_alert=True)
            return
        
        challenge_info = json.loads(challenge_data_json)
        
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
            "inline_message_id": inline_message_id
        }
        
        # Save inline game
        self.repo.save_inline_game(inline_message_id, game_state)
        
        # Delete challenge
        self.repo.redis_client.delete(challenge_key)
        
        # Update inline message
        await self._update_inline_game_message(
            context.bot,
            inline_message_id,
            engine,
            game_state
        )
    else:
        # Regular group chat flow (existing code)
        # ...
```

### 7. Helper Method for Updating Inline Messages

```python
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
    keyboard = BoardRenderer.create_move_keyboard(engine, move_count=engine.move_count)
    
    message_text = f"{players_msg}\n\n{board_text}\n\n{turn_msg}"
    
    try:
        await bot.edit_message_text(
            inline_message_id=inline_message_id,
            text=message_text,
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error updating inline message: {e}")
```

## Key Differences: Inline vs Regular Messages

### Message Identification

- **Regular**: `chat_id` + `message_id`
- **Inline**: `inline_message_id` (string, not int)

### Updating Messages

- **Regular**: `bot.edit_message_text(chat_id=..., message_id=..., ...)`
- **Inline**: `bot.edit_message_text(inline_message_id=..., ...)`

### Callback Queries

- Both work the same way
- `query.message.inline_message_id` is set for inline messages
- `query.message.chat_id` and `query.message.message_id` are `None` for inline messages

### Limitations

1. **No Direct Messaging**: Bot cannot send messages directly to users from inline mode
2. **No Notifications**: Bot cannot notify players when it's their turn (must rely on callback queries)
3. **Message Limits**: Inline messages have same size limits as regular messages
4. **TTL**: Inline messages can be edited indefinitely (no expiration)

## Implementation Checklist

- [ ] Enable inline mode in BotFather
- [ ] Add `InlineQueryHandler` to `main.py`
- [ ] Add `ChosenInlineResultHandler` to `main.py`
- [ ] Implement `inline_query_handler` in `handlers.py`
- [ ] Implement `chosen_inline_result_handler` in `handlers.py`
- [ ] Add inline game storage methods to `repository.py`
- [ ] Update `join_callback` to handle inline messages
- [ ] Update `select_callback` to handle inline messages
- [ ] Update `move_callback` to handle inline messages
- [ ] Update `forfeit_callback` to handle inline messages
- [ ] Add `_update_inline_game_message` helper method
- [ ] Test inline mode in groups (without adding bot)
- [ ] Test inline mode in private chats
- [ ] Test callback queries with inline messages
- [ ] Update documentation

## Testing Strategy

### Test Cases

1. **Basic Inline Query**
   - Type `@botname` in a group
   - Verify results appear
   - Select a result
   - Verify message appears in chat

2. **Challenge Creation**
   - Type `@botname play` in a group
   - Select "Start Challenge"
   - Verify challenge message appears
   - Have another user click "Join Game"
   - Verify game starts

3. **Direct Challenge**
   - Type `@botname challenge @username` in a group
   - Verify challenge result appears
   - Select result
   - Verify challenge message appears

4. **Game Interaction**
   - Start game via inline mode
   - Make moves via callback buttons
   - Verify inline message updates correctly
   - Complete game
   - Verify game end message

5. **Multiple Games**
   - Start multiple games in different chats via inline mode
   - Verify each game state is independent
   - Verify no conflicts between games

## Security Considerations

1. **User Validation**: Always verify users are players before allowing moves
2. **Rate Limiting**: Consider rate limiting inline queries to prevent abuse
3. **TTL Management**: Set appropriate TTLs for challenge and game states
4. **Input Sanitization**: Validate and sanitize all user inputs from inline queries

## Performance Considerations

1. **Caching**: Use `cache_time` parameter in `answerInlineQuery` to cache results
2. **Result Limits**: Telegram allows up to 50 results per inline query
3. **Response Time**: Inline queries should respond quickly (< 1 second ideally)
4. **Redis Keys**: Use efficient key naming for inline games

## Future Enhancements

1. **Inline Game Search**: Allow users to search for active games
2. **Quick Start**: Pre-create game board in inline result
3. **Game History**: Show recent games in inline results
4. **Player Stats**: Show player ratings in inline results

## References

- [Telegram Bot API - Inline Mode](https://core.telegram.org/bots/api#inline-mode)
- [python-telegram-bot - Inline Queries](https://docs.python-telegram-bot.org/en/stable/telegram.ext.inlinequeryhandler.html)
- [Telegram Bot API - InlineQueryResult](https://core.telegram.org/bots/api#inlinequeryresult)
- [Telegram Bot API - ChosenInlineResult](https://core.telegram.org/bots/api#choseninlineresult)

