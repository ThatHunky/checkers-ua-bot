"""
Ukrainian localization strings for the Checkers bot.
"""

# Welcome and Challenge
WELCOME = "👋 Вітаю! Хочете зіграти в Шашки?"
CHALLENGE = "🔴 <b>Виклик!</b>\n\n{opponent} викликає на партію в Шашки!\nХто зіграє за Білих (⚪)?"
JOIN_BTN = "⚔️ До бою!"

# Game Status
TURN_RED = "🔴 Хід Червоних\nГравець: {player_tag}"
TURN_WHITE = "⚪ Хід Білих\nГравець: {player_tag}"
GAME_STARTED = "🎮 Гра почалася!\n\n{board}\n\n{turn_msg}"

# Win/Loss
WINNER = "🏆 Перемога!\n\n{name} виграв партію!"
WINNER_WITH_RATING = "🏆 Перемога!\n\n{name} виграв партію!\n\n📊 Рейтинг:\n{winner_name}: {winner_rating} ({winner_change:+d})\n{loser_name}: {loser_rating} ({loser_change:+d})"
DRAW = "🤝 Нічия!"

# Rating/Stats
RATING_INFO = "📊 Рейтинг гравця {name}:\n\n⭐ Рейтинг: {rating}\n🏅 Місце: #{rank}\n🎮 Ігор: {games_played}\n✅ Перемог: {wins}\n❌ Програшів: {losses}"
LEADERBOARD_TITLE = "🏆 Топ-{count} гравців\n\n"
LEADERBOARD_ENTRY = "{rank}. {name} — {rating} ELO ({wins}W/{losses}L)"
NO_GAMES_PLAYED = "Ви ще не зіграли жодної гри!\nВикористайте /checkersplay щоб почати."

# Errors
ERROR_FORCE_JUMP = "⚠️ Ви повинні бити! Виберіть хід з битям."
ERROR_INVALID_MOVE = "❌ Неправильний хід! Виберіть іншу фігуру."
ERROR_NOT_YOUR_TURN = "⏸️ Зараз не ваш хід!"
ERROR_NO_GAME = "❌ Гра не знайдена або закінчилася."
ERROR_ALREADY_STARTED = "⚠️ Гра вже почалася!"
ERROR_SELF_PLAY = "❌ Ви не можете грати проти себе!"

# Buttons
BTN_FORFEIT = "🏳️ Здатися"
BTN_CANCEL = "🚫 Скасувати гру"
BTN_NEW_GAME = "🆕 Нова гра"

# Board Pieces (for text rendering)
PIECE_EMPTY_DARK = "⬛"
PIECE_EMPTY_LIGHT = "⬜"
PIECE_WHITE = "⚪"
PIECE_WHITE_KING = "👑"
PIECE_RED = "🔴"
PIECE_RED_KING = "💎"
