"""
Модуль для команды help и предложений по улучшению бота.
"""

import discord
from discord import app_commands
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)


class HelpCog(commands.Cog):
    """Ког для команды help."""
    
    def __init__(self, bot: commands.Bot):
        """
        Инициализация кога.
        
        Args:
            bot: Экземпляр бота
        """
        self.bot = bot
    
    @app_commands.command(name="help", description="Показать справку по командам бота")
    async def help_command(self, interaction: discord.Interaction):
        """Показать справку по всем командам бота (только для обычных пользователей)."""
        # Проверяем, что пользователь не администратор
        if interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ Эта команда доступна только для обычных пользователей.",
                ephemeral=True
            )
            return
        
        try:
            embed = discord.Embed(
                title="📚 Справка по командам CyberKotleta Core",
                description="Список всех доступных команд бота",
                color=discord.Color.blue()
            )
            
            # Команды для работы с ролями
            embed.add_field(
                name="🎨 Команды для кастомных ролей",
                value=(
                    "`/role create` - Создать кастомную роль (откроется форма)\n"
                    "`/role rename` - Переименовать свою кастомную роль\n"
                    "`/role color` - Изменить цвет своей кастомной роли\n"
                    "`/role delete` - Удалить свою кастомную роль\n"
                    "`/role check [пользователь]` - Проверить и выдать недостающие разделительные роли"
                ),
                inline=False
            )
            
            # Команды статистики
            embed.add_field(
                name="📊 Команды статистики",
                value=(
                    "`/stats me` - Показать вашу статистику\n"
                    "`/stats user @пользователь` - Показать статистику пользователя\n"
                    "`/stats top-voice [период]` - Топ по времени в голосовых каналах\n"
                    "`/stats top-messages [период]` - Топ по количеству сообщений\n"
                    "`/stats top-combined` - Комбинированный рейтинг (голос + сообщения)"
                ),
                inline=False
            )
            
            # Команды уровней (если будут добавлены)
            embed.add_field(
                name="⭐ Команды уровней",
                value=(
                    "`/level` - Показать ваш уровень и опыт\n"
                    "`/level @пользователь` - Показать уровень пользователя\n"
                    "`/leaderboard` - Топ по уровням"
                ),
                inline=False
            )
            
            # Команды репутации (если будут добавлены)
            embed.add_field(
                name="💚 Команды репутации",
                value=(
                    "`/rep @пользователь` - Показать репутацию пользователя\n"
                    "`/rep top` - Топ по репутации"
                ),
                inline=False
            )
            
            # Автоматические функции
            embed.add_field(
                name="🤖 Автоматические функции",
                value=(
                    "• Автоматическая выдача роли \"Участник\" при входе на сервер\n"
                    "• Автоматическая выдача разделительных ролей на основе позиций ваших ролей\n"
                    "• Автоматический учёт времени в голосовых каналах\n"
                    "• Автоматическая роль для пользователей, которые сейчас находятся в войсе\n"
                    "• Автоматический подсчёт сообщений и команд\n"
                    "• Автоматическое начисление опыта за активность\n"
                    "• Автоматическое начисление репутации за ответы \"+\" и реакции лайка\n"
                    "• Автоматическая выдача роли за отображаемый тег сервера"
                ),
                inline=False
            )
            
            embed.set_footer(text="CyberKotleta Core • Используйте команды для взаимодействия с ботом")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Команда /help вызвана пользователем {interaction.user.id}")
        
        except Exception as e:
            logger.error(f"Ошибка в help_command: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Произошла ошибка при отображении справки.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Функция для загрузки кога."""
    await bot.add_cog(HelpCog(bot))
