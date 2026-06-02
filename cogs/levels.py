"""
Модуль для системы уровней и опыта за активность.
"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
import math

import config
from db.database import Database

logger = logging.getLogger(__name__)


class LevelsCog(commands.Cog):
    """Ког для системы уровней и опыта."""
    
    def __init__(self, bot: commands.Bot, db: Database):
        """
        Инициализация кога.
        
        Args:
            bot: Экземпляр бота
            db: Экземпляр базы данных
        """
        self.bot = bot
        self.db = db
    
    @app_commands.command(name="level", description="Показать уровень и опыт пользователя")
    @app_commands.describe(user="Пользователь (по умолчанию - вы)")
    async def level_command(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None
    ):
        """Показать уровень и опыт пользователя."""
        target_user = user or interaction.user
        
        try:
            level, exp_to_next, total_exp = await self.db.get_user_level(target_user.id)
            
            # Вычисляем опыт для текущего уровня
            exp_for_current_level = (level - 1) * (level - 1) * 100
            exp_in_current_level = total_exp - exp_for_current_level
            exp_needed_for_next = (level * level * 100) - exp_for_current_level
            
            # Процент прогресса до следующего уровня
            if exp_needed_for_next > 0:
                progress_percent = (exp_in_current_level / exp_needed_for_next) * 100
            else:
                progress_percent = 100
            
            embed = discord.Embed(
                title=f"⭐ Уровень {target_user.display_name}",
                color=discord.Color.gold()
            )
            
            embed.set_thumbnail(url=target_user.display_avatar.url)
            
            embed.add_field(
                name="📊 Текущий уровень",
                value=f"**{level}**",
                inline=True
            )
            
            embed.add_field(
                name="💎 Общий опыт",
                value=f"**{total_exp:,}**",
                inline=True
            )
            
            embed.add_field(
                name="📈 Опыт до следующего уровня",
                value=f"**{exp_to_next:,}** / **{exp_needed_for_next:,}**",
                inline=False
            )
            
            # Прогресс-бар
            filled_blocks = int(progress_percent / 10)
            progress_bar = "█" * filled_blocks + "░" * (10 - filled_blocks)
            embed.add_field(
                name="Прогресс",
                value=f"`{progress_bar}` {progress_percent:.1f}%",
                inline=False
            )
            
            embed.set_footer(text=f"Опыт в текущем уровне: {exp_in_current_level:,} / {exp_needed_for_next:,}")
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
            logger.info(f"Команда /level вызвана для пользователя {target_user.id}")
        
        except Exception as e:
            logger.error(f"Ошибка в level_command: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Произошла ошибка при получении уровня.",
                ephemeral=True
            )
    
    @app_commands.command(name="leaderboard", description="Топ пользователей по уровням")
    @app_commands.describe(limit="Количество пользователей в топе (по умолчанию 10)")
    async def leaderboard_command(
        self,
        interaction: discord.Interaction,
        limit: int = 10
    ):
        """Показать топ пользователей по уровням."""
        if limit < 1 or limit > 25:
            await interaction.response.send_message(
                "❌ Количество должно быть от 1 до 25.",
                ephemeral=True
            )
            return
        
        try:
            top_users = await self.db.get_top_levels(limit)
            
            if not top_users:
                await interaction.response.send_message(
                    "❌ Пока нет данных о уровнях пользователей.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="🏆 Топ по уровням",
                color=discord.Color.gold()
            )
            
            description_parts = []
            for i, (user_id, level, total_exp) in enumerate(top_users, 1):
                try:
                    user = await self.bot.fetch_user(user_id)
                    username = user.display_name or user.name
                except:
                    username = f"Пользователь {user_id}"
                
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                description_parts.append(
                    f"{medal} **{username}** - Уровень {level} ({total_exp:,} опыта)"
                )
            
            embed.description = "\n".join(description_parts)
            embed.set_footer(text=f"Показано топ {len(top_users)} пользователей")
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
            logger.info(f"Команда /leaderboard вызвана пользователем {interaction.user.id}")
        
        except Exception as e:
            logger.error(f"Ошибка в leaderboard_command: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Произошла ошибка при получении топа.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Функция для загрузки кога."""
    db = bot.db
    await bot.add_cog(LevelsCog(bot, db))


