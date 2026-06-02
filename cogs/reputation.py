"""
Модуль для системы репутации.
"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional

import config
from db.database import Database

logger = logging.getLogger(__name__)

# Эмодзи лайков для проверки реакций
LIKE_EMOJIS = ["👍", "❤️", "💚", "💙", "💜", "🧡", "💛", "⬆️", "✅", "⭐", "🌟", "💯"]


class ReputationCog(commands.Cog):
    """Ког для системы репутации."""
    
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
        Обработчик сообщений для начисления репутации.
        
        Проверяет:
        1. Ответы "+" на сообщения
        2. Ответы на сообщения "+реп"
        """
        # Игнорируем ботов
        if message.author.bot:
            return
        
        # Игнорируем личные сообщения
        if not isinstance(message.channel, (discord.TextChannel, discord.Thread)):
            return
        
        # Игнорируем исключённые каналы
        if message.channel.id in config.EXCLUDED_CHANNELS:
            return
        
        # Проверяем, является ли сообщение ответом
        if not message.reference or not message.reference.message_id:
            return
        
        try:
            # Получаем оригинальное сообщение
            original_message = await message.channel.fetch_message(message.reference.message_id)
            
            # Игнорируем, если оригинальное сообщение от бота
            if original_message.author.bot:
                return
            
            # Проверка 1: Ответ "+" на сообщение
            message_content = message.content.strip()
            if message_content == "+":
                # Начисляем репутацию автору оригинального сообщения
                success = await self.db.add_reputation(
                    voter_id=message.author.id,
                    target_id=original_message.author.id,
                    message_id=original_message.id,
                    vote_type="reply_plus"
                )
                if success:
                    logger.info(
                        f"Начислена репутация пользователю {original_message.author.id} "
                        f"за ответ '+' от {message.author.id}"
                    )
                return
            
            # Проверка 2: Ответ на сообщение "+реп"
            original_content = original_message.content.strip().lower()
            if "+реп" in original_content or "+rep" in original_content:
                # Начисляем репутацию автору сообщения "+реп"
                success = await self.db.add_reputation(
                    voter_id=message.author.id,
                    target_id=original_message.author.id,
                    message_id=original_message.id,
                    vote_type="reply_reputation"
                )
                if success:
                    logger.info(
                        f"Начислена репутация пользователю {original_message.author.id} "
                        f"за ответ на '+реп' от {message.author.id}"
                    )
        
        except discord.NotFound:
            # Оригинальное сообщение не найдено
            pass
        except Exception as e:
            logger.error(f"Ошибка при обработке ответа для репутации: {e}", exc_info=True)
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.Member):
        """
        Обработчик добавления реакций для начисления репутации.
        
        Проверяет реакции лайка на сообщения.
        """
        # Игнорируем ботов
        if user.bot:
            return
        
        # Проверяем, является ли реакция лайком
        reaction_str = str(reaction.emoji)
        if reaction_str not in LIKE_EMOJIS:
            return
        
        # Получаем сообщение
        message = reaction.message
        
        # Игнорируем, если сообщение от бота
        if message.author.bot:
            return
        
        # Игнорируем личные сообщения
        if not isinstance(message.channel, (discord.TextChannel, discord.Thread)):
            return
        
        # Игнорируем исключённые каналы
        if message.channel.id in config.EXCLUDED_CHANNELS:
            return
        
        try:
            # Начисляем репутацию автору сообщения
            success = await self.db.add_reputation(
                voter_id=user.id,
                target_id=message.author.id,
                message_id=message.id,
                vote_type="reaction_like"
            )
            if success:
                logger.info(
                    f"Начислена репутация пользователю {message.author.id} "
                    f"за реакцию лайка от {user.id}"
                )
        except Exception as e:
            logger.error(f"Ошибка при обработке реакции для репутации: {e}", exc_info=True)
    
    rep_group = app_commands.Group(name="rep", description="Команды репутации")
    
    @rep_group.command(name="user", description="Показать репутацию пользователя")
    @app_commands.describe(user="Пользователь (по умолчанию - вы)")
    async def rep_user_command(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """Показать репутацию пользователя."""
        target_user = user or interaction.user
        
        try:
            reputation = await self.db.get_user_reputation(target_user.id)
            
            embed = discord.Embed(
                title=f"💚 Репутация {target_user.display_name}",
                color=discord.Color.green() if reputation >= 0 else discord.Color.red()
            )
            
            embed.set_thumbnail(url=target_user.display_avatar.url)
            
            embed.add_field(
                name="📊 Репутация",
                value=f"**{reputation:,}**",
                inline=False
            )
            
            # Определяем статус репутации
            if reputation >= 100:
                status = "🌟 Легенда"
            elif reputation >= 50:
                status = "⭐ Известный"
            elif reputation >= 20:
                status = "👍 Уважаемый"
            elif reputation >= 10:
                status = "✅ Хороший"
            elif reputation >= 0:
                status = "👤 Новичок"
            else:
                status = "⚠️ Отрицательная"
            
            embed.add_field(
                name="Статус",
                value=status,
                inline=False
            )
            
            embed.set_footer(text="Репутация начисляется за ответы '+' и реакции лайка")
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
            logger.info(f"Команда /rep user вызвана для пользователя {target_user.id}")
        
        except Exception as e:
            logger.error(f"Ошибка в rep_user_command: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Произошла ошибка при получении репутации.",
                ephemeral=True
            )
    
    @rep_group.command(name="top", description="Топ пользователей по репутации")
    @app_commands.describe(limit="Количество пользователей в топе (по умолчанию 10)")
    async def rep_top_command(
        self,
        interaction: discord.Interaction,
        limit: int = 10
    ):
        """Показать топ пользователей по репутации."""
        if limit < 1 or limit > 25:
            await interaction.response.send_message(
                "❌ Количество должно быть от 1 до 25.",
                ephemeral=True
            )
            return
        
        try:
            top_users = await self.db.get_top_reputation(limit)
            
            if not top_users:
                await interaction.response.send_message(
                    "❌ Пока нет данных о репутации пользователей.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="🏆 Топ по репутации",
                color=discord.Color.green()
            )
            
            description_parts = []
            for i, (user_id, reputation) in enumerate(top_users, 1):
                try:
                    user = await self.bot.fetch_user(user_id)
                    username = user.display_name or user.name
                except:
                    username = f"Пользователь {user_id}"
                
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                description_parts.append(
                    f"{medal} **{username}** - {reputation:,} репутации"
                )
            
            embed.description = "\n".join(description_parts)
            embed.set_footer(text=f"Показано топ {len(top_users)} пользователей")
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
            logger.info(f"Команда /rep top вызвана пользователем {interaction.user.id}")
        
        except Exception as e:
            logger.error(f"Ошибка в rep_top_command: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Произошла ошибка при получении топа.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Функция для загрузки кога."""
    db = bot.db
    await bot.add_cog(ReputationCog(bot, db))

