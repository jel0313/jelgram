"""ユーザーの定数。"""

USERNAME_PATTERN = r"^[a-z0-9_]{3,30}$"
# URL や画面の名前とぶつかるユーザー名は使わせない
RESERVED_USERNAMES = frozenset({"admin", "api", "me", "settings", "login", "logout", "jelgram"})

PROFILE_CACHE_KEY = "cache:profile:v1:{user_id}"
PROFILE_CACHE_SECONDS = 300
