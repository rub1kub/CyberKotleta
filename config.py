"""
Конфигурация CyberKotleta Core.

Значения читаются из переменных окружения или локального файла `.env`.
Файл `.env` не должен попадать в GitHub.
"""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv(path: str = ".env") -> None:
    """Загрузить простые KEY=VALUE строки из .env без внешних зависимостей."""
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int = 0) -> int:
    value = _env(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float = 0.0) -> float:
    value = _env(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env(name)
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "y", "on"}


def _env_csv(name: str, default: list[str] | None = None) -> list[str]:
    value = _env(name)
    if not value:
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_int_list(name: str, default: list[int] | None = None) -> list[int]:
    result = []
    for item in _env_csv(name):
        try:
            result.append(int(item))
        except ValueError:
            continue
    return result or (default or [])


_load_dotenv()

# Discord токены и ID
DISCORD_TOKEN = _env("DISCORD_TOKEN")
CLIENT_ID = _env_int("CLIENT_ID")
CLIENT_SECRET = _env("CLIENT_SECRET")
DISCORD_PRESENCES_INTENT = _env_bool("DISCORD_PRESENCES_INTENT", False)

# ID сервера и каналов
GUILD_ID = _env_int("GUILD_ID")
CHANNEL_ID_CUSTOM_ROLES = _env_int("CHANNEL_ID_CUSTOM_ROLES")

# Разделительные роли
ROLE_GROUP_DIVIDERS = {
    "custom": _env_int("ROLE_DIVIDER_CUSTOM_ID"),
    "medals": _env_int("ROLE_DIVIDER_MEDALS_ID"),
    "mentionables": _env_int("ROLE_DIVIDER_MENTIONABLES_ID"),
    "clans": _env_int("ROLE_DIVIDER_CLANS_ID"),
    "other": _env_int("ROLE_DIVIDER_OTHER_ID"),
}

# Порядок разделительных ролей от низкой к высокой позиции
DIVIDER_ROLES_BY_POSITION = [
    (ROLE_GROUP_DIVIDERS["other"], _env_int("ROLE_DIVIDER_OTHER_POSITION")),
    (ROLE_GROUP_DIVIDERS["clans"], _env_int("ROLE_DIVIDER_CLANS_POSITION")),
    (ROLE_GROUP_DIVIDERS["mentionables"], _env_int("ROLE_DIVIDER_MENTIONABLES_POSITION")),
    (ROLE_GROUP_DIVIDERS["medals"], _env_int("ROLE_DIVIDER_MEDALS_POSITION")),
    (ROLE_GROUP_DIVIDERS["custom"], _env_int("ROLE_DIVIDER_CUSTOM_POSITION")),
]

# Группы ролей - роли определяются автоматически по позициям
ROLE_GROUPS = {
    "custom": [],
    "medals": [],
    "mentionables": [],
    "other": [],
    "clans": [],
}

# Настройки поведения
DELETE_OLD_CUSTOM_ROLE = _env_bool("DELETE_OLD_CUSTOM_ROLE", True)
AUTO_REMOVE_DIVIDERS = _env_bool("AUTO_REMOVE_DIVIDERS", True)

# Роль за установленный тег сервера
SERVER_TAG_ROLE_ID = _env_int("SERVER_TAG_ROLE_ID")
SERVER_TAG_ROLE_NAME = _env("SERVER_TAG_ROLE_NAME", "Six Seven 67")
SERVER_TAG_VALUE = _env("SERVER_TAG_VALUE")
SERVER_TAG_ROLE_COLOR = _env_int("SERVER_TAG_ROLE_COLOR", 0xFF69B4)
SERVER_TAG_ROLE_HOIST = _env_bool("SERVER_TAG_ROLE_HOIST", True)
SERVER_TAG_REFERENCE_ROLE_ID = _env_int("SERVER_TAG_REFERENCE_ROLE_ID")
SERVER_TAG_REFERENCE_ROLE_NAMES = _env_csv(
    "SERVER_TAG_REFERENCE_ROLE_NAMES",
    ["Участник", "участник", "Member", "member"],
)
SERVER_TAG_SYNC_INTERVAL_MINUTES = _env_int("SERVER_TAG_SYNC_INTERVAL_MINUTES", 60)
SERVER_TAG_REQUEST_DELAY_SECONDS = _env_float("SERVER_TAG_REQUEST_DELAY_SECONDS", 1.0)

# Роль для пользователей, которые сейчас находятся в голосовом канале
VOICE_PRESENCE_ROLE_NAME = _env("VOICE_PRESENCE_ROLE_NAME", "Сейчас в войсе")
VOICE_PRESENCE_ROLE_COLOR = _env_int("VOICE_PRESENCE_ROLE_COLOR", 0x2ECC71)
VOICE_PRESENCE_ROLE_HOIST = _env_bool("VOICE_PRESENCE_ROLE_HOIST", True)
VOICE_PRESENCE_SYNC_INTERVAL_SECONDS = _env_int("VOICE_PRESENCE_SYNC_INTERVAL_SECONDS", 60)

# Роль недельного лидера по времени в голосовых каналах
VOICE_KING_ROLE_NAME = _env("VOICE_KING_ROLE_NAME", "🎙 Войс-царь недели")
VOICE_KING_ROLE_COLOR = _env_int("VOICE_KING_ROLE_COLOR", 0xF1C40F)
VOICE_KING_ROLE_HOIST = _env_bool("VOICE_KING_ROLE_HOIST", True)
VOICE_KING_SYNC_INTERVAL_SECONDS = _env_int("VOICE_KING_SYNC_INTERVAL_SECONDS", 60)
VOICE_KING_MIN_SECONDS = _env_int("VOICE_KING_MIN_SECONDS", 1)
VOICE_KING_ANNOUNCE_CHANNEL_ID = _env_int("VOICE_KING_ANNOUNCE_CHANNEL_ID")
VOICE_KING_TOXIC_ANNOUNCEMENTS = _env_bool("VOICE_KING_TOXIC_ANNOUNCEMENTS", True)
VOICE_KING_ANNOUNCE_FIRST_CORONATION = _env_bool("VOICE_KING_ANNOUNCE_FIRST_CORONATION", True)

# Валидация названий ролей
ROLE_NAME_MIN_LENGTH = _env_int("ROLE_NAME_MIN_LENGTH", 2)
ROLE_NAME_MAX_LENGTH = _env_int("ROLE_NAME_MAX_LENGTH", 32)
ROLE_NAME_BLOCKED_WORDS = _env_csv(
    "ROLE_NAME_BLOCKED_WORDS",
    [
        "admin",
        "administrator",
        "модератор",
        "moderator",
        "бот",
        "bot",
        "cyberkotleta",
        "core",
        "разделитель",
        "divider",
    ],
)

# Каналы, исключённые из статистики сообщений
EXCLUDED_CHANNELS = _env_int_list("EXCLUDED_CHANNELS")

# Коэффициенты для комбинированного рейтинга
COMBINED_RATING_VOICE_WEIGHT = _env_float("COMBINED_RATING_VOICE_WEIGHT", 2.0)
COMBINED_RATING_MESSAGES_WEIGHT = _env_float("COMBINED_RATING_MESSAGES_WEIGHT", 1.0)

# Путь к базе данных
DATABASE_PATH = _env("DATABASE_PATH", "cyberkotleta.db")
