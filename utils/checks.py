"""
Проверки для команд бота.

Содержит декораторы и функции для проверки условий выполнения команд.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def check_channel(channel_id: int):
    """
    Декоратор для проверки, что команда вызвана в определённом канале.
    
    Args:
        channel_id: ID канала, в котором разрешена команда
    
    Returns:
        Декоратор для команды
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.channel_id != channel_id:
            await interaction.response.send_message(
                f"Эта команда доступна только в канале <#{channel_id}>",
                ephemeral=True
            )
            return False
        return True
    
    return app_commands.check(predicate)


async def check_user_has_role(
    member: discord.Member,
    role_id: int,
    error_message: Optional[str] = None
) -> bool:
    """
    Проверить, есть ли у пользователя определённая роль.
    
    Args:
        member: Участник сервера
        role_id: ID роли для проверки
        error_message: Сообщение об ошибке (не используется, для совместимости)
    
    Returns:
        True, если у пользователя есть роль
    """
    return any(role.id == role_id for role in member.roles)


async def check_bot_permissions(
    guild: discord.Guild,
    required_permissions: discord.Permissions
) -> bool:
    """
    Проверить, есть ли у бота необходимые права.
    
    Args:
        guild: Сервер
        required_permissions: Требуемые права
    
    Returns:
        True, если у бота есть все необходимые права
    """
    bot_member = guild.me
    if not bot_member:
        return False
    
    return bot_member.guild_permissions >= required_permissions


def get_bot_role_position(guild: discord.Guild) -> Optional[int]:
    """
    Получить позицию роли бота в списке ролей сервера.
    
    Args:
        guild: Сервер
    
    Returns:
        Позиция роли бота или None, если бот не найден
    """
    bot_member = guild.me
    if not bot_member or not bot_member.top_role:
        return None
    
    return bot_member.top_role.position


