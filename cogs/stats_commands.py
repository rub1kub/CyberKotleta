"""
Модуль для команд статистики и учёта использования команд.

Предоставляет slash-команды для просмотра статистики:
- /stats me - личная статистика
- /stats user - статистика пользователя
- /stats top-voice - топ по времени в голосовых каналах
- /stats top-messages - топ по сообщениям
- /stats top-combined - комбинированный рейтинг
"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional

import config
from db.database import Database
from utils.formatting import (
    create_stats_embed,
    create_top_embed,
    format_time_seconds,
    format_combined_value
)

logger = logging.getLogger(__name__)


class StatsCommandsCog(commands.Cog):
    """Ког для команд статистики."""
    
    def __init__(self, bot: commands.Bot, db: Database):
        """
        Инициализация кога.
        
        Args:
            bot: Экземпляр бота
            db: Экземпляр базы данных
        """
        self.bot = bot
        self.db = db
    
    stats_group = app_commands.Group(name="stats", description="Статистика активности")
    
    @commands.Cog.listener()
    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        command: app_commands.Command
    ):
        """
        Обработчик успешного выполнения команды.
        
        Учитывает использование команд пользователями.
        """
        # Игнорируем ботов
        if interaction.user.bot:
            return
        
        # Игнорируем команды статистики (чтобы не засорять статистику)
        # Проверяем имя команды (для подкоманд группы это будет имя подкоманды)
        command_name = getattr(command, 'name', str(command))
        # Игнорируем команды статистики и управления ролями
        if command_name in ["me", "user", "top-voice", "top-messages", "top-combined", "create", "rename", "color", "delete"]:
            return
        
        try:
            await self.db.increment_commands(interaction.user.id)
            logger.debug(f"Учтена команда {command.name} от пользователя {interaction.user.id}")
            
            # Начисляем опыт за использование команды (2 опыта)
            new_level, total_exp, level_up = await self.db.add_experience(interaction.user.id, 2)
            if level_up:
                logger.info(f"Пользователь {interaction.user.id} повысил уровень до {new_level}!")
        except Exception as e:
            logger.error(f"Ошибка при учёте команды: {e}", exc_info=True)
    
    @stats_group.command(name="me", description="Показать вашу статистику")
    async def stats_me(self, interaction: discord.Interaction):
        """Показать личную статистику пользователя."""
        try:
            # Получаем статистику
            voice_seconds, _ = await self.db.get_voice_stats(interaction.user.id)
            messages, _ = await self.db.get_messages_stats(interaction.user.id)
            commands = await self.db.get_commands_stats(interaction.user.id)
            
            # Создаём embed
            embed = create_stats_embed(
                interaction.user,
                voice_seconds,
                messages,
                commands,
                title="Ваша статистика"
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Ошибка в stats_me: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Произошла ошибка при получении статистики.",
                ephemeral=True
            )
    
    @stats_group.command(name="user", description="Показать статистику пользователя")
    @app_commands.describe(user="Пользователь, статистику которого нужно показать")
    async def stats_user(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):
        """Показать статистику указанного пользователя."""
        try:
            # Получаем статистику
            voice_seconds, _ = await self.db.get_voice_stats(user.id)
            messages, _ = await self.db.get_messages_stats(user.id)
            commands = await self.db.get_commands_stats(user.id)
            
            # Создаём embed
            embed = create_stats_embed(
                user,
                voice_seconds,
                messages,
                commands,
                title=f"Статистика {user.display_name}"
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Ошибка в stats_user: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Произошла ошибка при получении статистики.",
                ephemeral=True
            )
    
    @stats_group.command(name="top-voice", description="Топ пользователей по времени в голосовых каналах")
    @app_commands.describe(limit="Количество участников в топе (по умолчанию 10)")
    async def stats_top_voice(
        self,
        interaction: discord.Interaction,
        limit: Optional[int] = 10
    ):
        """Показать топ пользователей по времени в голосовых каналах."""
        try:
            if limit < 1 or limit > 20:
                await interaction.response.send_message(
                    "❌ Лимит должен быть от 1 до 20.",
                    ephemeral=True
                )
                return
            
            # Получаем топ
            top_list = await self.db.get_top_voice(limit)
            
            if not top_list:
                await interaction.response.send_message(
                    "📊 Пока нет данных о времени в голосовых каналах.",
                    ephemeral=True
                )
                return
            
            # Формируем описание
            description = "Рейтинг участников по времени, проведённому в голосовых каналах."
            
            # Создаём embed
            embed = create_top_embed(
                title="🏆 Топ по времени в голосовых каналах",
                description=description,
                entries=top_list,
                guild=interaction.guild,
                value_formatter=format_time_seconds
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Ошибка в stats_top_voice: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Произошла ошибка при получении рейтинга.",
                ephemeral=True
            )
    
    @stats_group.command(name="top-messages", description="Топ пользователей по количеству сообщений")
    @app_commands.describe(limit="Количество участников в топе (по умолчанию 10)")
    async def stats_top_messages(
        self,
        interaction: discord.Interaction,
        limit: Optional[int] = 10
    ):
        """Показать топ пользователей по количеству сообщений."""
        try:
            if limit < 1 or limit > 20:
                await interaction.response.send_message(
                    "❌ Лимит должен быть от 1 до 20.",
                    ephemeral=True
                )
                return
            
            # Получаем топ
            top_list = await self.db.get_top_messages(limit)
            
            if not top_list:
                await interaction.response.send_message(
                    "📊 Пока нет данных о сообщениях.",
                    ephemeral=True
                )
                return
            
            # Формируем описание
            description = "Рейтинг участников по количеству отправленных сообщений."
            
            # Создаём embed
            embed = create_top_embed(
                title="🏆 Топ по сообщениям",
                description=description,
                entries=top_list,
                guild=interaction.guild,
                value_formatter=lambda x: f"{x:,} сообщений"
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Ошибка в stats_top_messages: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Произошла ошибка при получении рейтинга.",
                ephemeral=True
            )
    
    @stats_group.command(name="top-combined", description="Комбинированный рейтинг активности")
    @app_commands.describe(limit="Количество участников в топе (по умолчанию 10)")
    async def stats_top_combined(
        self,
        interaction: discord.Interaction,
        limit: Optional[int] = 10
    ):
        """
        Показать комбинированный рейтинг активности.
        
        Формула: (голос_часы * VOICE_WEIGHT) + (сообщения * MESSAGES_WEIGHT)
        """
        try:
            if limit < 1 or limit > 20:
                await interaction.response.send_message(
                    "❌ Лимит должен быть от 1 до 20.",
                    ephemeral=True
                )
                return
            
            # Получаем комбинированную статистику
            all_stats = await self.db.get_combined_stats()
            
            if not all_stats:
                await interaction.response.send_message(
                    "📊 Пока нет данных для комбинированного рейтинга.",
                    ephemeral=True
                )
                return
            
            # Вычисляем комбинированный score для каждого пользователя
            # Формула: (voice_hours * VOICE_WEIGHT) + (messages * MESSAGES_WEIGHT)
            scored_stats = []
            for user_id, voice_seconds, messages in all_stats:
                voice_hours = voice_seconds / 3600  # Конвертируем секунды в часы
                score = (voice_hours * config.COMBINED_RATING_VOICE_WEIGHT) + \
                        (messages * config.COMBINED_RATING_MESSAGES_WEIGHT)
                scored_stats.append((user_id, voice_seconds, messages, score))
            
            # Сортируем по score
            scored_stats.sort(key=lambda x: x[3], reverse=True)
            
            # Берём топ
            top_list = scored_stats[:limit]
            
            # Формируем список для embed'а (user_id, score)
            top_for_embed = [(entry[0], entry[3]) for entry in top_list]
            
            # Формируем описание
            description = (
                f"Комбинированный рейтинг активности.\n"
                f"Формула: (голос_часы × {config.COMBINED_RATING_VOICE_WEIGHT}) + "
                f"(сообщения × {config.COMBINED_RATING_MESSAGES_WEIGHT})"
            )
            
            # Создаём embed
            embed = create_top_embed(
                title="🏆 Комбинированный рейтинг",
                description=description,
                entries=top_for_embed,
                guild=interaction.guild,
                value_formatter=lambda x: f"{x:.1f} баллов"
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Ошибка в stats_top_combined: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Произошла ошибка при получении рейтинга.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Функция для загрузки кога."""
    db = bot.db
    await bot.add_cog(StatsCommandsCog(bot, db))

