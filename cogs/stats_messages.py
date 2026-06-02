"""
Модуль для учёта сообщений пользователей.

Подсчитывает количество сообщений в текстовых каналах,
исключая ботов и служебные каналы.
"""

import discord
from discord.ext import commands
import logging

import config
from db.database import Database

logger = logging.getLogger(__name__)


class StatsMessagesCog(commands.Cog):
    """Ког для учёта сообщений."""
    
    def __init__(self, bot: commands.Bot, db: Database):
        """
        Инициализация кога.
        
        Args:
            bot: Экземпляр бота
            db: Экземпляр базы данных
        """
        self.bot = bot
        self.db = db
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Обработчик новых сообщений.
        
        Учитывает сообщения пользователей, игнорируя:
        - Сообщения ботов
        - Сообщения в исключённых каналах
        - Системные сообщения
        """
        # Игнорируем ботов
        if message.author.bot:
            return
        
        # Игнорируем личные сообщения (DM)
        if not isinstance(message.channel, (discord.TextChannel, discord.Thread)):
            return
        
        # Игнорируем исключённые каналы
        if message.channel.id in config.EXCLUDED_CHANNELS:
            return
        
        # Игнорируем системные сообщения
        if message.type != discord.MessageType.default:
            return
        
        # Увеличиваем счётчик сообщений
        try:
            await self.db.increment_messages(message.author.id)
            logger.debug(f"Учтено сообщение от пользователя {message.author.id} в канале {message.channel.id}")
            
            # Начисляем опыт за сообщение (1-5 опыта в зависимости от длины)
            message_length = len(message.content)
            if message_length > 0:
                # 1 опыт за сообщение до 50 символов, +1 за каждые 50 символов, максимум 5
                exp_gained = min(1 + (message_length // 50), 5)
                new_level, total_exp, level_up = await self.db.add_experience(message.author.id, exp_gained)
                
                if level_up:
                    logger.info(f"Пользователь {message.author.id} повысил уровень до {new_level}!")
                    # Опционально: можно отправить уведомление о повышении уровня
        except Exception as e:
            logger.error(f"Ошибка при учёте сообщения: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    """Функция для загрузки кога."""
    db = bot.db
    await bot.add_cog(StatsMessagesCog(bot, db))

