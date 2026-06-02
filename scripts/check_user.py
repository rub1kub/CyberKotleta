"""
Скрипт для проверки конкретного пользователя и выдачи разделительных ролей.
"""

import asyncio
import logging
import sys
import os

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord
from discord.ext import commands
import config
from logging_config import setup_logging

setup_logging(logging.INFO)
logger = logging.getLogger(__name__)

# ID пользователя для проверки
USER_ID = 476391268671291393

class UserCheckerClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guild_id = config.GUILD_ID

    async def on_ready(self):
        logger.info(f"Бот запущен: {self.user} (ID: {self.user.id})")
        
        target_guild = None
        if self.guild_id:
            target_guild = self.get_guild(self.guild_id)
            if not target_guild:
                logger.error(f"Сервер с ID {self.guild_id} не найден.")
                await self.close()
                return
        else:
            if not self.guilds:
                logger.error("Бот не находится ни на одном сервере!")
                await self.close()
                return
            target_guild = self.guilds[0]
            self.guild_id = target_guild.id

        logger.info(f"Найден сервер: {target_guild.name}")
        
        # Загружаем всех участников
        await target_guild.chunk()
        
        # Ищем пользователя
        member = target_guild.get_member(USER_ID)
        if not member:
            logger.error(f"Пользователь с ID {USER_ID} не найден на сервере.")
            await self.close()
            return
        
        logger.info(f"Найден пользователь: {member.display_name} ({member.id})")
        logger.info("=" * 60)
        logger.info("ИНФОРМАЦИЯ О РОЛЯХ ПОЛЬЗОВАТЕЛЯ:")
        logger.info("=" * 60)
        
        # Получаем все роли пользователя (кроме @everyone)
        user_roles = [role for role in member.roles if role.id != target_guild.id]
        user_roles_sorted = sorted(user_roles, key=lambda r: r.position, reverse=True)
        
        logger.info(f"\nВсего ролей: {len(user_roles)}")
        for i, role in enumerate(user_roles_sorted, 1):
            logger.info(f"  {i}. Позиция {role.position:3d} | ID: {role.id:20d} | {role.name}")
        
        if user_roles:
            positions = [role.position for role in user_roles]
            logger.info(f"\nМинимальная позиция: {min(positions)}")
            logger.info(f"Максимальная позиция: {max(positions)}")
        
        logger.info("\n" + "=" * 60)
        logger.info("РАЗДЕЛИТЕЛЬНЫЕ РОЛИ:")
        logger.info("=" * 60)
        
        # Проверяем разделительные роли
        divider_roles = []
        for divider_id, divider_position in config.DIVIDER_ROLES_BY_POSITION:
            divider_role = target_guild.get_role(divider_id)
            if divider_role:
                has_role = divider_role in member.roles
                divider_roles.append((divider_role, divider_position, has_role))
                status = "✅ ЕСТЬ" if has_role else "❌ НЕТ"
                logger.info(f"  {status} | Позиция {divider_position:3d} | {divider_role.name}")
        
        logger.info("\n" + "=" * 60)
        logger.info("АНАЛИЗ НУЖНЫХ РАЗДЕЛИТЕЛЬНЫХ РОЛЕЙ:")
        logger.info("=" * 60)
        
        # Анализируем, какие разделительные роли должны быть
        if user_roles:
            user_positions = [role.position for role in user_roles]
            min_position = min(user_positions)
            max_position = max(user_positions)
            
            needed_dividers = []
            
            for divider_index, (divider_id, divider_position) in enumerate(config.DIVIDER_ROLES_BY_POSITION):
                divider_role = target_guild.get_role(divider_id)
                if not divider_role:
                    continue
                
                if divider_index == 0:
                    # Первая разделительная роль (Прочее)
                    if min_position < divider_position:
                        needed_dividers.append(divider_role)
                        logger.info(f"  ✅ Нужна: {divider_role.name} (есть роли ниже позиции {divider_position})")
                else:
                    prev_divider_id, prev_divider_position = config.DIVIDER_ROLES_BY_POSITION[divider_index - 1]
                    has_roles_in_range = any(
                        prev_divider_position <= role.position < divider_position 
                        for role in user_roles
                    )
                    if has_roles_in_range:
                        needed_dividers.append(divider_role)
                        logger.info(f"  ✅ Нужна: {divider_role.name} (есть роли в диапазоне [{prev_divider_position}, {divider_position}))")
            
            # Проверяем самую высокую разделительную роль
            highest_divider_id, highest_divider_position = config.DIVIDER_ROLES_BY_POSITION[-1]
            if max_position >= highest_divider_position:
                highest_divider_role = target_guild.get_role(highest_divider_id)
                if highest_divider_role:
                    prev_highest_id, prev_highest_position = config.DIVIDER_ROLES_BY_POSITION[-2]
                    has_roles_in_highest_range = any(
                        prev_highest_position <= role.position < highest_divider_position 
                        for role in user_roles
                    )
                    if has_roles_in_highest_range and highest_divider_role not in needed_dividers:
                        needed_dividers.append(highest_divider_role)
                        logger.info(f"  ✅ Нужна: {highest_divider_role.name} (есть роли в диапазоне [{prev_highest_position}, {highest_divider_position}))")
            
            logger.info(f"\nВсего нужно разделительных ролей: {len(needed_dividers)}")
            
            # Выдаём недостающие роли
            missing_roles = [role for role in needed_dividers if role not in member.roles]
            if missing_roles:
                logger.info(f"\nВыдача недостающих ролей ({len(missing_roles)}):")
                for role in missing_roles:
                    try:
                        await member.add_roles(role, reason="Проверка и выдача разделительных ролей")
                        logger.info(f"  ✅ Выдана роль: {role.name}")
                    except discord.Forbidden:
                        logger.error(f"  ❌ Нет прав для выдачи роли: {role.name}")
                    except discord.HTTPException as e:
                        logger.error(f"  ❌ Ошибка при выдаче роли {role.name}: {e}")
            else:
                logger.info("\n✅ У пользователя уже есть все нужные разделительные роли!")
        else:
            logger.info("У пользователя нет ролей, требующих разделительных ролей.")
        
        await self.close()

    async def on_error(self, event_name, *args, **kwargs):
        logger.error(f"Ошибка в событии {event_name}: {sys.exc_info()[0].__name__}: {sys.exc_info()[1]}")

async def check_user():
    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True
    client = UserCheckerClient(intents=intents)
    try:
        await client.start(config.DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        await client.close()

if __name__ == "__main__":
    try:
        asyncio.run(check_user())
    except KeyboardInterrupt:
        logger.info("Скрипт остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске скрипта: {e}", exc_info=True)
        sys.exit(1)


