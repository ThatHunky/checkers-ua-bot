"""
Constants for callback data and configuration.
"""

# Menu callback data constants
MENU_MAIN = "menu_main"
MENU_PLAY = "menu_play"
MENU_PROFILE = "menu_profile"
MENU_RATING = "menu_rating"
MENU_SETTINGS = "menu_settings"
MENU_HELP = "menu_help"
MENU_ABOUT = "menu_about"

# Play mode callback data constants
PLAY_RATED = "play_rated"
PLAY_CASUAL = "play_casual"
GROUP_INVITE_RATED = "group_invite_rated"
GROUP_INVITE_CASUAL = "group_invite_casual"
INVITE_RATED = "invite_rated"
INVITE_CASUAL = "invite_casual"
JOIN_CODE = "join_code"
MM_CANCEL = "mm_cancel"
BACK_TO_PLAY = "back_to_play"

# Timeout constants
MESSAGE_EDIT_TIMEOUT = 10.0  # seconds
CALLBACK_DEDUP_WINDOW_MS = 500  # milliseconds
CALLBACK_DEDUP_CLEANUP_THRESHOLD = 1000  # max entries before cleanup
CALLBACK_DEDUP_CLEANUP_AGE_MS = 5000  # milliseconds - entries older than this are cleaned up

