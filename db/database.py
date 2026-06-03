"""
Модуль для работы с базой данных SQLite.

Использует aiosqlite для асинхронных операций.
"""

import aiosqlite
import logging
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с базой данных."""
    
    def __init__(self, db_path: str):
        """
        Инициализация подключения к БД.
        
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    def get_current_week_start(self) -> str:
        """Получить дату начала текущей недели в ISO-формате."""
        now = datetime.now().date()
        week_start = now - timedelta(days=now.weekday())
        return week_start.isoformat()
    
    async def connect(self) -> None:
        """Установка подключения к БД."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        logger.info(f"Подключение к БД установлено: {self.db_path}")
    
    async def close(self) -> None:
        """Закрытие подключения к БД."""
        if self._connection:
            await self._connection.close()
            logger.info("Подключение к БД закрыто")
    
    async def init_db(self) -> None:
        """Инициализация БД: создание таблиц из migrations.sql."""
        if not self._connection:
            await self.connect()
        
        migrations_path = Path(__file__).parent / "migrations.sql"
        
        if not migrations_path.exists():
            logger.error(f"Файл миграций не найден: {migrations_path}")
            return
        
        with open(migrations_path, "r", encoding="utf-8") as f:
            sql_script = f.read()
        
        await self._connection.executescript(sql_script)
        await self._connection.commit()
        logger.info("База данных инициализирована")
    
    # Методы для работы с пользователями
    async def ensure_user(self, user_id: int) -> None:
        """Создать запись пользователя, если её нет."""
        await self._connection.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (user_id,)
        )
        await self._connection.commit()

    async def get_state(self, key: str) -> Optional[str]:
        """Получить служебное значение состояния бота."""
        cursor = await self._connection.execute(
            "SELECT value FROM bot_state WHERE key = ?",
            (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else None

    async def set_state(self, key: str, value: str) -> None:
        """Установить служебное значение состояния бота."""
        await self._connection.execute(
            """INSERT INTO bot_state (key, value, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(key) DO UPDATE
               SET value = excluded.value,
                   updated_at = CURRENT_TIMESTAMP""",
            (key, value)
        )
        await self._connection.commit()
    
    # Методы для работы с кастомными ролями
    async def get_custom_role(self, user_id: int) -> Optional[int]:
        """
        Получить ID кастомной роли пользователя.
        
        Returns:
            ID роли или None, если роли нет
        """
        await self.ensure_user(user_id)
        cursor = await self._connection.execute(
            "SELECT role_id FROM custom_roles WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row["role_id"] if row else None
    
    async def set_custom_role(self, user_id: int, role_id: int) -> None:
        """Установить кастомную роль пользователю."""
        await self.ensure_user(user_id)
        await self._connection.execute(
            "INSERT OR REPLACE INTO custom_roles (user_id, role_id) VALUES (?, ?)",
            (user_id, role_id)
        )
        await self._connection.commit()
        logger.info(f"Кастомная роль {role_id} установлена для пользователя {user_id}")
    
    async def remove_custom_role(self, user_id: int) -> None:
        """Удалить кастомную роль пользователя."""
        await self._connection.execute(
            "DELETE FROM custom_roles WHERE user_id = ?",
            (user_id,)
        )
        await self._connection.commit()
        logger.info(f"Кастомная роль удалена для пользователя {user_id}")
    
    async def get_user_by_role_id(self, role_id: int) -> Optional[int]:
        """Получить user_id по role_id кастомной роли."""
        cursor = await self._connection.execute(
            "SELECT user_id FROM custom_roles WHERE role_id = ?",
            (role_id,)
        )
        row = await cursor.fetchone()
        return row["user_id"] if row else None
    
    # Методы для статистики голосовых каналов
    async def get_voice_stats(self, user_id: int) -> Tuple[int, Optional[datetime]]:
        """
        Получить статистику голосовых каналов пользователя.
        
        Returns:
            Кортеж (total_voice_seconds, last_join_ts)
        """
        await self.ensure_user(user_id)
        cursor = await self._connection.execute(
            "SELECT total_voice_seconds, last_join_ts FROM voice_stats WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            total_seconds = row["total_voice_seconds"] or 0
            last_join_ts = row["last_join_ts"]
            
            # Парсим строку TIMESTAMP в datetime объект
            if last_join_ts:
                if isinstance(last_join_ts, str):
                    try:
                        # SQLite хранит даты в формате ISO 8601: YYYY-MM-DD HH:MM:SS
                        last_join_ts = datetime.strptime(last_join_ts, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        # Пробуем альтернативный формат с микросекундами
                        try:
                            last_join_ts = datetime.strptime(last_join_ts, "%Y-%m-%d %H:%M:%S.%f")
                        except ValueError:
                            logger.warning(f"Не удалось распарсить last_join_ts для пользователя {user_id}: {last_join_ts}")
                            last_join_ts = None
                elif not isinstance(last_join_ts, datetime):
                    logger.warning(f"Неожиданный тип last_join_ts для пользователя {user_id}: {type(last_join_ts)}")
                    last_join_ts = None
            
            return total_seconds, last_join_ts
        return 0, None
    
    async def set_voice_join_time(self, user_id: int, join_time: datetime) -> None:
        """Установить время входа в голосовой канал."""
        await self.ensure_user(user_id)
        logger.debug(f"Сохранение времени входа для пользователя {user_id}: {join_time} (тип: {type(join_time)})")
        await self._connection.execute(
            """INSERT INTO voice_stats (user_id, last_join_ts)
               VALUES (?, ?)
               ON CONFLICT(user_id) DO UPDATE SET last_join_ts = ?""",
            (user_id, join_time, join_time)
        )
        await self._connection.commit()
        logger.debug(f"Время входа успешно сохранено для пользователя {user_id}")
    
    async def add_voice_time(self, user_id: int, seconds: int) -> None:
        """Добавить время в голосовом канале."""
        await self.ensure_user(user_id)
        week_start = self.get_current_week_start()
        await self._connection.execute(
            """INSERT INTO voice_stats (user_id, total_voice_seconds)
               VALUES (?, ?)
               ON CONFLICT(user_id) DO UPDATE
               SET total_voice_seconds = total_voice_seconds + ?""",
            (user_id, seconds, seconds)
        )
        await self._connection.execute(
            """INSERT INTO voice_weekly_stats (user_id, week_start, total_voice_seconds)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, week_start) DO UPDATE
               SET total_voice_seconds = total_voice_seconds + ?""",
            (user_id, week_start, seconds, seconds)
        )
        await self._connection.commit()

    async def get_top_weekly_voice(self, limit: int = 10, week_start: Optional[str] = None) -> List[Tuple[int, int]]:
        """
        Получить топ пользователей по времени в голосовых каналах за неделю.

        Returns:
            Список кортежей (user_id, total_voice_seconds)
        """
        target_week = week_start or self.get_current_week_start()
        cursor = await self._connection.execute(
            """SELECT user_id, total_voice_seconds
               FROM voice_weekly_stats
               WHERE week_start = ?
               ORDER BY total_voice_seconds DESC
               LIMIT ?""",
            (target_week, limit)
        )
        rows = await cursor.fetchall()
        return [(row["user_id"], row["total_voice_seconds"] or 0) for row in rows]

    async def get_weekly_voice_seconds(self, user_id: int, week_start: Optional[str] = None) -> int:
        """Получить недельное время пользователя в голосовых каналах."""
        await self.ensure_user(user_id)
        target_week = week_start or self.get_current_week_start()
        cursor = await self._connection.execute(
            """SELECT total_voice_seconds
               FROM voice_weekly_stats
               WHERE user_id = ? AND week_start = ?""",
            (user_id, target_week)
        )
        row = await cursor.fetchone()
        return (row["total_voice_seconds"] or 0) if row else 0

    async def clear_voice_join_time(self, user_id: int) -> None:
        """Очистить время входа в голосовой канал."""
        await self._connection.execute(
            "UPDATE voice_stats SET last_join_ts = NULL WHERE user_id = ?",
            (user_id,)
        )
        await self._connection.commit()
    
    # Методы для статистики сообщений
    async def increment_messages(self, user_id: int) -> None:
        """Увеличить счётчик сообщений пользователя."""
        await self.ensure_user(user_id)
        now = datetime.now()
        await self._connection.execute(
            """INSERT INTO messages_stats (user_id, total_messages, last_message_ts)
               VALUES (?, 1, ?)
               ON CONFLICT(user_id) DO UPDATE
               SET total_messages = total_messages + 1,
                   last_message_ts = ?""",
            (user_id, now, now)
        )
        await self._connection.commit()
    
    async def get_messages_stats(self, user_id: int) -> Tuple[int, Optional[datetime]]:
        """
        Получить статистику сообщений пользователя.
        
        Returns:
            Кортеж (total_messages, last_message_ts)
        """
        await self.ensure_user(user_id)
        cursor = await self._connection.execute(
            "SELECT total_messages, last_message_ts FROM messages_stats WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return row["total_messages"] or 0, row["last_message_ts"]
        return 0, None
    
    # Методы для статистики команд
    async def increment_commands(self, user_id: int) -> None:
        """Увеличить счётчик команд пользователя."""
        await self.ensure_user(user_id)
        await self._connection.execute(
            """INSERT INTO commands_stats (user_id, total_commands)
               VALUES (?, 1)
               ON CONFLICT(user_id) DO UPDATE
               SET total_commands = total_commands + 1""",
            (user_id,)
        )
        await self._connection.commit()
    
    async def get_commands_stats(self, user_id: int) -> int:
        """Получить количество команд пользователя."""
        await self.ensure_user(user_id)
        cursor = await self._connection.execute(
            "SELECT total_commands FROM commands_stats WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row["total_commands"] if row and row["total_commands"] else 0
    
    # Методы для рейтингов
    async def get_top_voice(self, limit: int = 10) -> List[Tuple[int, int]]:
        """
        Получить топ пользователей по времени в голосовых каналах.
        
        Returns:
            Список кортежей (user_id, total_voice_seconds)
        """
        cursor = await self._connection.execute(
            """SELECT user_id, total_voice_seconds
               FROM voice_stats
               ORDER BY total_voice_seconds DESC
               LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [(row["user_id"], row["total_voice_seconds"] or 0) for row in rows]
    
    async def get_top_messages(self, limit: int = 10) -> List[Tuple[int, int]]:
        """
        Получить топ пользователей по количеству сообщений.
        
        Returns:
            Список кортежей (user_id, total_messages)
        """
        cursor = await self._connection.execute(
            """SELECT user_id, total_messages
               FROM messages_stats
               ORDER BY total_messages DESC
               LIMIT ?""",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [(row["user_id"], row["total_messages"] or 0) for row in rows]
    
    async def get_combined_stats(self) -> List[Tuple[int, int, int]]:
        """
        Получить комбинированную статистику всех пользователей.
        
        Returns:
            Список кортежей (user_id, total_voice_seconds, total_messages)
        """
        # SQLite не поддерживает FULL OUTER JOIN, используем UNION ALL
        cursor = await self._connection.execute(
            """SELECT user_id, total_voice_seconds, 0 as total_messages
               FROM voice_stats
               UNION ALL
               SELECT user_id, 0 as total_voice_seconds, total_messages
               FROM messages_stats"""
        )
        # Группируем в Python
        stats_dict = {}
        rows = await cursor.fetchall()
        for row in rows:
            user_id = row["user_id"]
            if user_id not in stats_dict:
                stats_dict[user_id] = [0, 0]
            stats_dict[user_id][0] += row["total_voice_seconds"] or 0
            stats_dict[user_id][1] += row["total_messages"] or 0
        
        return [(uid, voice, msg) for uid, (voice, msg) in stats_dict.items()]
    
    # Методы для работы с уровнями
    async def ensure_user_level(self, user_id: int) -> None:
        """Создать запись уровня пользователя, если её нет."""
        await self.ensure_user(user_id)
        await self._connection.execute(
            "INSERT OR IGNORE INTO user_levels (user_id, level, experience, total_experience) VALUES (?, 1, 0, 0)",
            (user_id,)
        )
        await self._connection.commit()
    
    async def add_experience(self, user_id: int, exp: int) -> Tuple[int, int, bool]:
        """
        Добавить опыт пользователю и обновить уровень.
        
        Args:
            user_id: ID пользователя
            exp: Количество опыта для добавления
            
        Returns:
            Кортеж (новый уровень, общий опыт, был ли повышение уровня)
        """
        await self.ensure_user_level(user_id)
        
        # Получаем текущие данные
        cursor = await self._connection.execute(
            "SELECT level, total_experience FROM user_levels WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            old_level = 1
            old_total_exp = 0
        else:
            old_level = row["level"]
            old_total_exp = row["total_experience"]
        
        # Вычисляем новый общий опыт
        new_total_exp = old_total_exp + exp
        
        # Вычисляем новый уровень по формуле: level = floor(sqrt(total_experience / 100)) + 1
        import math
        new_level = int(math.floor(math.sqrt(new_total_exp / 100))) + 1
        
        # Вычисляем опыт до следующего уровня
        exp_for_current_level = (new_level - 1) * (new_level - 1) * 100
        exp_needed_for_next = (new_level * new_level * 100) - new_total_exp
        
        # Обновляем данные
        await self._connection.execute(
            """UPDATE user_levels 
               SET level = ?, total_experience = ?, experience = ?
               WHERE user_id = ?""",
            (new_level, new_total_exp, exp_needed_for_next, user_id)
        )
        
        await self._connection.commit()
        
        level_up = new_level > old_level
        return new_level, new_total_exp, level_up
    
    async def get_user_level(self, user_id: int) -> Tuple[int, int, int]:
        """
        Получить уровень и опыт пользователя.
        
        Returns:
            Кортеж (level, experience, total_experience)
        """
        await self.ensure_user_level(user_id)
        cursor = await self._connection.execute(
            "SELECT level, experience, total_experience FROM user_levels WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return row["level"], row["experience"], row["total_experience"]
        return 1, 0, 0
    
    async def get_top_levels(self, limit: int = 10) -> List[Tuple[int, int, int]]:
        """
        Получить топ пользователей по уровням.
        
        Returns:
            Список кортежей (user_id, level, total_experience)
        """
        cursor = await self._connection.execute(
            "SELECT user_id, level, total_experience FROM user_levels ORDER BY total_experience DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [(row["user_id"], row["level"], row["total_experience"]) for row in rows]
    
    # Методы для работы с репутацией
    async def ensure_user_reputation(self, user_id: int) -> None:
        """Создать запись репутации пользователя, если её нет."""
        await self.ensure_user(user_id)
        await self._connection.execute(
            "INSERT OR IGNORE INTO reputation (user_id, total_reputation) VALUES (?, 0)",
            (user_id,)
        )
        await self._connection.commit()
    
    async def add_reputation(self, voter_id: int, target_id: int, message_id: int, vote_type: str) -> bool:
        """
        Добавить репутацию пользователю.
        
        Args:
            voter_id: ID пользователя, который голосует
            target_id: ID пользователя, которому начисляется репутация
            message_id: ID сообщения
            vote_type: Тип голоса ('reply_plus', 'reply_reputation', 'reaction_like')
            
        Returns:
            True если репутация была добавлена, False если уже был голос
        """
        # Проверяем, не голосовал ли уже этот пользователь за это сообщение этим типом голоса
        cursor = await self._connection.execute(
            "SELECT 1 FROM reputation_votes WHERE voter_id = ? AND message_id = ? AND vote_type = ?",
            (voter_id, message_id, vote_type)
        )
        if await cursor.fetchone():
            return False  # Уже голосовал
        
        # Проверяем, что пользователь не голосует за себя
        if voter_id == target_id:
            return False
        
        # Добавляем голос
        await self._connection.execute(
            "INSERT INTO reputation_votes (voter_id, target_id, message_id, vote_type) VALUES (?, ?, ?, ?)",
            (voter_id, target_id, message_id, vote_type)
        )
        
        # Увеличиваем репутацию
        await self.ensure_user_reputation(target_id)
        await self._connection.execute(
            """UPDATE reputation 
               SET total_reputation = total_reputation + 1 
               WHERE user_id = ?""",
            (target_id,)
        )
        
        await self._connection.commit()
        return True
    
    async def get_user_reputation(self, user_id: int) -> int:
        """Получить репутацию пользователя."""
        await self.ensure_user_reputation(user_id)
        cursor = await self._connection.execute(
            "SELECT total_reputation FROM reputation WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row["total_reputation"] if row else 0
    
    async def get_top_reputation(self, limit: int = 10) -> List[Tuple[int, int]]:
        """
        Получить топ пользователей по репутации.
        
        Returns:
            Список кортежей (user_id, total_reputation)
        """
        cursor = await self._connection.execute(
            "SELECT user_id, total_reputation FROM reputation ORDER BY total_reputation DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [(row["user_id"], row["total_reputation"]) for row in rows]
