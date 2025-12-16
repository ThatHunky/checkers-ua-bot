"""
Ukrainian localization strings for the Checkers bot.
"""

# Welcome and Challenge
WELCOME = "👋 Вітаю! Хочете зіграти в Шашки?"
CHALLENGE = "🔵 <b>Виклик!</b>\n\n{opponent} викликає на партію в Шашки!\nХто зіграє за Жовтих (🟡)?"
JOIN_BTN = "⚔️ До бою!"

# Game Status
TURN_RED = "🔵 Хід Синіх\nГравець: {player_tag}"
TURN_WHITE = "🟡 Хід Жовтих\nГравець: {player_tag}"
GAME_STARTED = "🎮 Гра почалася!\n\n{board}\n\n{turn_msg}"

# Win/Loss
WINNER = "🏆 Перемога!\n\n{name} виграв партію!"
WINNER_WITH_RATING = "🏆 Перемога!\n\n{name} виграв партію!\n\n📊 Рейтинг:\n{winner_name}: {winner_rating} ({winner_change:+d})\n{loser_name}: {loser_rating} ({loser_change:+d})"
DRAW = "🤝 Нічия!"

# Rating/Stats
RATING_INFO = "📊 Рейтинг гравця {name}:\n\n⭐ Рейтинг: {rating}\n🏅 Місце: #{rank}\n🎮 Ігор: {games_played}\n✅ Перемог: {wins}\n❌ Програшів: {losses}"
LEADERBOARD_TITLE = "🏆 Топ-{count} гравців\n\n"
LEADERBOARD_ENTRY = "{rank}. {name} — {rating} ELO ({wins}W/{losses}L)"
NO_GAMES_PLAYED = "Ви ще не зіграли жодної гри!\nВикористайте `/checkersplay` щоб почати."

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
PIECE_WHITE = "🟡"        # Yellow man
PIECE_WHITE_KING = "💛"   # Yellow king (heart)
PIECE_RED = "🔵"          # Blue man
PIECE_RED_KING = "💙"     # Blue king (heart)

# Selected pieces
PIECE_WHITE_SELECTED = "🍌"        # Yellow man selected
PIECE_WHITE_KING_SELECTED = "🍍"   # Yellow king selected
PIECE_RED_SELECTED = "🐳"          # Blue man selected
PIECE_RED_KING_SELECTED = "💎"     # Blue king selected

# Matchmaking / Menu
MENU_TITLE = "Головне меню"
MENU_PLAY = "▶️ Грати"
MENU_PROFILE = "👤 Профіль"
MENU_RATING = "🏆 Рейтинг та Статистика"
MENU_SETTINGS = "⚙️ Налаштування"
MENU_HELP = "❓ Допомога"
MENU_ABOUT = "ℹ️ Про бота"
MENU_BUTTON = "📋 Меню"
MENU_SHORTCUT_HINT = "Використайте кнопку \"Меню\" внизу для швидкого доступу до головного меню."
MENU_PRIVATE_ONLY = "Головне меню доступне лише в особистих повідомленнях з ботом."

PLAY_TITLE = "Режими гри"
PLAY_QUICK_RATED = "⚡ Швидка гра (Рейтинг)"
PLAY_QUICK_CASUAL = "🎲 Швидка гра (Без рейтингу)"
PLAY_INVITE_RATED = "🤝 Запросити друга (Рейтинг)"
PLAY_INVITE_CASUAL = "🧩 Запросити друга (Без рейтингу)"
PLAY_JOIN_CODE = "🔢 Приєднатися за кодом"
BTN_BACK = "⬅️ Назад"
BTN_BACK_TO_MENU = "🏠 Повернутися до меню"
SEARCHING_TITLE = "Пошук суперника..."
SEARCHING_CANCEL = "❌ Скасувати"
SEARCHING_BACK = "⬅️ Назад до режимів"
INVITE_CREATED = "📨 Запрошення створено: <code>{code}</code>"
INVITE_SHARE = "📤 Поділитися кодом"
INVITE_CANCEL = "❌ Скасувати запрошення"

# Inline Challenge
INLINE_CHALLENGE_TITLE = "🎮 Створити виклик на гру"
INLINE_CHALLENGE_DESC = "Створіть виклик, до якого зможе приєднатися будь-хто"
INLINE_CHALLENGE_MSG = "🎮 <b>Виклик на гру в Шашки!</b>\n\n{name} хоче зіграти!\nНатисніть кнопку нижче, щоб приєднатися."
INLINE_CHALLENGE_JOIN = "⚔️ Приєднатися"
INLINE_CHALLENGE_EXPIRED = "❌ Виклик закінчився або вже використано."
INLINE_CHALLENGE_SELF_JOIN = "❌ Ви не можете приєднатися до власного виклику."
INLINE_CHALLENGE_NOT_FOUND = "❌ Виклик не знайдено."

# Inline Challenge Modes
INLINE_CHALLENGE_CASUAL_TITLE = "🎲 Виклик (Без рейтингу)"
INLINE_CHALLENGE_CASUAL_DESC = "Створити виклик без зміни рейтингу"
INLINE_CHALLENGE_RANKED_TITLE = "⚡ Виклик (Рейтинг)"
INLINE_CHALLENGE_RANKED_DESC = "Створити рейтинговий виклик"
INLINE_CHALLENGE_PRACTICE_TITLE = "📚 Виклик (Тренування)"
INLINE_CHALLENGE_PRACTICE_DESC = "Створити виклик для тренування"
INLINE_CHALLENGE_MSG_RANKED = "⚡ <b>Рейтинговий виклик на гру в Шашки!</b>\n\n{name} хоче зіграти рейтингову гру!\nНатисніть кнопку нижче, щоб приєднатися."
INLINE_CHALLENGE_MSG_PRACTICE = "📚 <b>Виклик на тренувальну гру в Шашки!</b>\n\n{name} хоче потренуватися!\nНатисніть кнопку нижче, щоб приєднатися."
PROFILE_TEMPLATE = (
    "👤 {name}\n"
    "⭐ Рейтинг: {rating}\n"
    "🎮 Ігор зіграно: {games}\n"
    "✅ Перемог: {wins}\n"
    "❌ Поразок: {losses}"
)
SETTINGS_TITLE = "Налаштування"
SETTINGS_NOTIFICATIONS = "🔔 Сповіщення (заглушка)"
SETTINGS_PREFER_RATED = "🎯 Віддавати перевагу рейтинговим іграм"
HELP_TEXT = (
    "❓ <b>Як грати</b>\n"
    "Виберіть режим гри в меню, робіть ходи натискаючи на дошку."
)
ABOUT_TEXT = (
    "ℹ️ Checkers UA — бот для гри в українські шашки. "
    "Вихідний код: https://github.com/ThatHunky/checkers-ua-bot"
)
