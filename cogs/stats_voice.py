"""
Модуль для учёта времени в голосовых каналах.

Отслеживает входы и выходы пользователей из голосовых каналов
и сохраняет статистику в базу данных.
"""

import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime, timedelta

from db.database import Database

logger = logging.getLogger(__name__)


class StatsVoiceCog(commands.Cog):
    """Ког для учёта времени в голосовых каналах."""
    
    def __init__(self, bot: commands.Bot, db: Database):
        """
        Инициализация кога.
        
        Args:
            bot: Экземпляр бота
            db: Экземпляр базы данных
        """
        self.bot = bot
        self.db = db
        # Запускаем периодическую задачу сохранения времени для активных пользователей
        try:
            self.save_active_voice_time.start()
        except Exception as e:
            logger.error(f"Не удалось запустить периодическую задачу сохранения голосового времени: {e}")
    
    @tasks.loop(seconds=30)
    async def save_active_voice_time(self):
        """
        Периодическая задача для сохранения времени активных пользователей в голосовых каналах.
        
        Выполняется каждую минуту и сохраняет время для всех пользователей,
        которые находятся в голосовых каналах.
        """
        if not self.bot.is_ready():
            return
        
        now = datetime.now()
        
        for guild in self.bot.guilds:
            try:
                # Получаем все голосовые каналы
                for channel in guild.voice_channels:
                    # Игнорируем AFK канал
                    if channel == guild.afk_channel:
                        continue
                    
                    # Обрабатываем всех участников в канале
                    for member in channel.members:
                        if member.bot:
                            continue
                        
                        # Получаем время входа пользователя
                        _, last_join_ts = await self.db.get_voice_stats(member.id)
                        
                        if last_join_ts:
                            # Вычисляем время, проведённое в канале
                            time_diff = now - last_join_ts
                            seconds = int(time_diff.total_seconds())
                            
                            # Сохраняем время, если прошло минимум 15 секунд (чтобы не спамить БД)
                            if seconds >= 15:
                                # Добавляем время в статистику
                                await self.db.add_voice_time(member.id, seconds)
                                
                                # Начисляем опыт (1 опыт за минуту)
                                minutes_spent = seconds // 60
                                if minutes_spent > 0:
                                    new_level, total_exp, level_up = await self.db.add_experience(
                                        member.id, minutes_spent
                                    )
                                    if level_up:
                                        logger.info(
                                            f"Пользователь {member.id} повысил уровень до {new_level} "
                                            f"во время активности в голосовом канале!"
                                        )
                                
                                # Обновляем время входа на текущее
                                await self.db.set_voice_join_time(member.id, now)
                                
                                logger.debug(
                                    f"Сохранено {seconds} секунд голосового времени для "
                                    f"пользователя {member.id} (активный в канале)"
                                )
            except Exception as e:
                logger.error(f"Ошибка при сохранении времени активных пользователей в {guild.name}: {e}", exc_info=True)
    
    @save_active_voice_time.before_loop
    async def before_save_active_voice_time(self):
        """Ожидание готовности бота перед запуском периодической задачи."""
        await self.bot.wait_until_ready()
        logger.info("Периодическая задача сохранения голосового времени готова к запуску")
    
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        """
        Обработчик изменения состояния голосового канала.
        
        Учитывает:
        - Вход в голосовой канал
        - Выход из голосового канала
        - Переход между каналами
        - Переход в AFK канал (считается выходом)
        """
        # Игнорируем ботов
        if member.bot:
            return
        
        # Получаем текущее время
        now = datetime.now()
        
        # Сценарий 1: Пользователь зашёл в голосовой канал
        if before.channel is None and after.channel is not None:
            # Проверяем, что это не AFK канал
            afk_channel = member.guild.afk_channel
            if afk_channel is None or after.channel.id != afk_channel.id:
                await self.db.set_voice_join_time(member.id, now)
                logger.info(f"Пользователь {member.id} зашёл в голосовой канал {after.channel.name} (ID: {after.channel.id}) в {now}")
        
        # Сценарий 2: Пользователь вышел из голосового канала
        elif before.channel is not None and after.channel is None:
            await self._process_voice_exit(member.id, now)
            logger.debug(f"Пользователь {member.id} вышел из голосового канала")
        
        # Сценарий 3: Пользователь перешёл между каналами
        elif before.channel is not None and after.channel is not None:
            afk_channel = member.guild.afk_channel
            # Если перешёл в AFK канал - считаем выходом
            if afk_channel and after.channel.id == afk_channel.id:
                await self._process_voice_exit(member.id, now)
                logger.debug(f"Пользователь {member.id} перешёл в AFK канал")
            # Если перешёл из AFK в обычный - считаем входом
            elif afk_channel and before.channel.id == afk_channel.id:
                await self.db.set_voice_join_time(member.id, now)
                logger.debug(f"Пользователь {member.id} перешёл из AFK в обычный канал")
            # Обычный переход между каналами - не учитываем как выход/вход
            # Просто обновляем время входа
            else:
                # При переходе между каналами считаем, что время продолжается
                # Но обновляем время входа на текущее, чтобы при следующем выходе
                # считать время с момента последнего перехода
                await self.db.set_voice_join_time(member.id, now)
                logger.debug(f"Пользователь {member.id} перешёл между каналами")
        
        # Сценарий 4: Пользователь был отключён/заглушен (mute/deaf)
        # Это не считается выходом, просто обновляем статус
    
    async def _process_voice_exit(self, user_id: int, exit_time: datetime) -> None:
        """
        Обработать выход пользователя из голосового канала.
        
        Вычисляет время, проведённое в канале, и добавляет его в статистику.
        
        Args:
            user_id: ID пользователя
            exit_time: Время выхода
        """
        # Получаем время входа
        _, last_join_ts = await self.db.get_voice_stats(user_id)
        
        if last_join_ts:
            # Вычисляем разницу во времени
            time_diff = exit_time - last_join_ts
            seconds = int(time_diff.total_seconds())
            
            logger.debug(
                f"Выход из канала: пользователь {user_id}, "
                f"вход был {last_join_ts}, выход {exit_time}, разница {seconds} секунд"
            )
            
            # Засчитываем время даже если меньше минуты (но минимум 1 секунда)
            if seconds > 0:
                # Добавляем время в статистику
                await self.db.add_voice_time(user_id, seconds)
                logger.info(f"Добавлено {seconds} секунд голосового времени для пользователя {user_id}")
                
                # Начисляем опыт за время в голосовом канале (1 опыт за минуту)
                minutes_spent = seconds // 60
                if minutes_spent > 0:
                    new_level, total_exp, level_up = await self.db.add_experience(user_id, minutes_spent)
                    if level_up:
                        logger.info(f"Пользователь {user_id} повысил уровень до {new_level}!")
                else:
                    logger.debug(f"Пользователь {user_id} провёл {seconds} секунд (меньше минуты, опыт не начислен)")
            
            # Очищаем время входа
            await self.db.clear_voice_join_time(user_id)
        else:
            # Если времени входа нет, значит пользователь был в канале до перезапуска бота
            # Игнорируем это согласно требованиям
            logger.debug(f"Пользователь {user_id} вышел из канала, но время входа не зафиксировано (перезапуск бота)")


async def setup(bot: commands.Bot):
    """Функция для загрузки кога."""
    db = bot.db
    await bot.add_cog(StatsVoiceCog(bot, db))

