"""
Скрипт для получения информации о ролях по их ID.
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

# ID ролей для проверки
ROLE_IDS = [
    1190212668192215081,  # Самая высокая позиция
    1190212668167045171,
    1190212668133494855,
    1190212668099936319,
    1190212668099936324,  # Самая низкая позиция
]

class RoleInfoClient(discord.Client):
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
            logger.info(f"GUILD_ID не установлен, используем первый доступный сервер: {target_guild.name} (ID: {target_guild.id})")

        logger.info(f"Найден сервер: {target_guild.name}")
        logger.info("=" * 60)
        logger.info("ИНФОРМАЦИЯ О РОЛЯХ:")
        logger.info("=" * 60)
        
        # Получаем все роли сервера и сортируем по позиции (от высокой к низкой)
        all_roles = sorted(target_guild.roles, key=lambda r: r.position, reverse=True)
        
        # Выводим информацию о запрошенных ролях
        for role_id in ROLE_IDS:
            role = target_guild.get_role(role_id)
            if role:
                logger.info(f"\nРоль ID: {role_id}")
                logger.info(f"  Название: {role.name}")
                logger.info(f"  Позиция: {role.position} (чем выше, тем выше роль в списке)")
                logger.info(f"  Цвет: {role.color}")
                logger.info(f"  Упоминаемая: {role.mentionable}")
                logger.info(f"  Показывается отдельно: {role.hoist}")
            else:
                logger.warning(f"Роль с ID {role_id} не найдена на сервере!")
        
        logger.info("\n" + "=" * 60)
        logger.info("ВСЕ РОЛИ СЕРВЕРА (от высокой к низкой позиции):")
        logger.info("=" * 60)
        for i, role in enumerate(all_roles, 1):
            marker = " ← ЗАПРОШЕННАЯ" if role.id in ROLE_IDS else ""
            logger.info(f"{i:3d}. Позиция {role.position:3d} | ID: {role.id:20d} | {role.name}{marker}")
        
        logger.info("\n" + "=" * 60)
        logger.info("ПРОВЕРКА ЛОГИКИ РАЗДЕЛИТЕЛЬНЫХ РОЛЕЙ:")
        logger.info("=" * 60)
        
        # Проверяем позиции ролей
        role_positions = {}
        for role_id in ROLE_IDS:
            role = target_guild.get_role(role_id)
            if role:
                role_positions[role_id] = role.position
        
        # Сортируем по позиции (от низкой к высокой)
        sorted_roles = sorted(role_positions.items(), key=lambda x: x[1])
        
        logger.info("\nПорядок ролей (от низкой к высокой позиции):")
        for i, (role_id, position) in enumerate(sorted_roles, 1):
            role = target_guild.get_role(role_id)
            logger.info(f"  {i}. Позиция {position:3d} | ID: {role_id} | {role.name}")
        
        logger.info("\nЛогика выдачи разделительных ролей:")
        logger.info("  - Если есть роли ниже позиции {} → выдать роль {}".format(
            sorted_roles[0][1], sorted_roles[0][0]
        ))
        for i in range(1, len(sorted_roles)):
            prev_role_id, prev_pos = sorted_roles[i-1]
            curr_role_id, curr_pos = sorted_roles[i]
            prev_role = target_guild.get_role(prev_role_id)
            curr_role = target_guild.get_role(curr_role_id)
            logger.info("  - Если есть роли от позиции {} до {} → выдать роль {} ({})".format(
                prev_pos, curr_pos, curr_role_id, curr_role.name
            ))
        
        await self.close()

    async def on_error(self, event_name, *args, **kwargs):
        logger.error(f"Ошибка в событии {event_name}: {sys.exc_info()[0].__name__}: {sys.exc_info()[1]}")

async def get_roles_info():
    intents = discord.Intents.default()
    intents.guilds = True
    client = RoleInfoClient(intents=intents)
    try:
        await client.start(config.DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        await client.close()

if __name__ == "__main__":
    try:
        asyncio.run(get_roles_info())
    except KeyboardInterrupt:
        logger.info("Скрипт остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске скрипта: {e}", exc_info=True)
        sys.exit(1)

