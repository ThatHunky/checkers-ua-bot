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
PIECE_WHITE = "🟡"        # Yellow man
PIECE_WHITE_KING = "💛"   # Yellow king (heart)
PIECE_RED = "🔵"          # Blue man
PIECE_RED_KING = "💙"     # Blue king (heart)

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
