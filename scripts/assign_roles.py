"""
Скрипт для выдачи ролей всем участникам сервера.

Выдаёт:
- Роль "Участник" всем обычным пользователям
- Роль "Бот" всем ботам
"""

import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

import discord
from discord.ext import commands
import logging

import config
from logging_config import setup_logging

# Настройка логирования
setup_logging(logging.INFO)
logger = logging.getLogger(__name__)


async def assign_roles():
    """Выдать роли всем участникам сервера."""
    # Проверка конфигурации
    if not config.DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN не установлен в config.py!")
        return
    
    # Если GUILD_ID не установлен, попробуем найти сервер автоматически
    target_guild_id = config.GUILD_ID
    
    # Настройка intents
    intents = discord.Intents.default()
    intents.members = True
    intents.guilds = True
    
    # Создаём клиент
    client = discord.Client(intents=intents)
    
    @client.event
    async def on_ready():
        """Выполняется при готовности бота."""
        logger.info(f"Бот запущен: {client.user} (ID: {client.user.id})")
        
        # Получаем сервер
        if target_guild_id:
            guild = client.get_guild(target_guild_id)
            if not guild:
                logger.error(f"Сервер с ID {target_guild_id} не найден!")
                await client.close()
                return
        else:
            # Ищем сервер автоматически (берём первый доступный)
            guilds = list(client.guilds)
            if not guilds:
                logger.error("Бот не находится ни на одном сервере!")
                await client.close()
                return
            
            guild = guilds[0]
            logger.info(f"GUILD_ID не установлен, используем первый доступный сервер: {guild.name} (ID: {guild.id})")
            logger.info(f"Для постоянного использования установите GUILD_ID = {guild.id} в config.py")
        
        logger.info(f"Найден сервер: {guild.name}")
        
        # Ищем роли
        member_role = None
        bot_role = None
        
        # Ищем роль "Участник" (пробуем разные варианты названий)
        role_names_member = ["Участник", "участник", "Member", "member", "Member", "Member"]
        role_names_bot = ["Бот", "бот", "Bot", "bot", "Bots", "bots"]
        
        for role in guild.roles:
            role_name_lower = role.name.lower()
            
            # Проверяем роль "Участник"
            if not member_role:
                for name in role_names_member:
                    if role_name_lower == name.lower():
                        member_role = role
                        logger.info(f"Найдена роль 'Участник': {role.name} (ID: {role.id})")
                        break
            
            # Проверяем роль "Бот"
            if not bot_role:
                for name in role_names_bot:
                    if role_name_lower == name.lower():
                        bot_role = role
                        logger.info(f"Найдена роль 'Бот': {role.name} (ID: {role.id})")
                        break
        
        if not member_role:
            logger.error("Роль 'Участник' не найдена! Проверьте название роли на сервере.")
            logger.info("Доступные роли на сервере:")
            for role in sorted(guild.roles, key=lambda r: r.position, reverse=True):
                logger.info(f"  - {role.name} (ID: {role.id})")
            await client.close()
            return
        
        if not bot_role:
            logger.warning("Роль 'Бот' не найдена. Ботам не будет выдана роль.")
        
        # Получаем всех участников
        logger.info("Загружаем список участников...")
        members = []
        async for member in guild.fetch_members(limit=None):
            members.append(member)
        
        logger.info(f"Найдено {len(members)} участников")
        
        # Проверяем права бота
        bot_member = guild.get_member(client.user.id)
        if not bot_member:
            logger.error("Бот не найден на сервере!")
            await client.close()
            return
        
        # Проверяем, может ли бот выдавать роли
        if not bot_member.guild_permissions.manage_roles:
            logger.error("У бота нет прав 'Управление ролями'!")
            await client.close()
            return
        
        # Проверяем позицию роли относительно роли бота
        bot_top_role = bot_member.top_role
        if member_role.position >= bot_top_role.position:
            logger.warning(f"Роль 'Участник' ({member_role.position}) находится выше или на уровне роли бота ({bot_top_role.position})!")
            logger.warning("Бот не сможет выдать эту роль. Переместите роль 'Участник' ниже роли бота в настройках сервера.")
            await client.close()
            return
        
        if bot_role and bot_role.position >= bot_top_role.position:
            logger.warning(f"Роль 'Бот' ({bot_role.position}) находится выше или на уровне роли бота ({bot_top_role.position})!")
            logger.warning("Бот не сможет выдать эту роль. Переместите роль 'Бот' ниже роли бота в настройках сервера.")
            bot_role = None  # Отключаем выдачу роли бота
        
        # Выдаём роли
        member_count = 0
        bot_count = 0
        skipped_count = 0
        error_count = 0
        
        logger.info("Начинаем выдачу ролей...")
        
        for idx, member in enumerate(members, 1):
            try:
                # Проверяем, есть ли уже нужная роль
                if member.bot:
                    if bot_role and bot_role not in member.roles:
                        await member.add_roles(bot_role, reason="Автоматическая выдача роли бота")
                        bot_count += 1
                        if bot_count % 10 == 0:
                            logger.info(f"Выдано ролей 'Бот': {bot_count}/{len([m for m in members if m.bot])}")
                    else:
                        skipped_count += 1
                else:
                    if member_role not in member.roles:
                        await member.add_roles(member_role, reason="Автоматическая выдача роли участника")
                        member_count += 1
                        if member_count % 50 == 0:
                            logger.info(f"Выдано ролей 'Участник': {member_count}/{len([m for m in members if not m.bot])}")
                    else:
                        skipped_count += 1
                
                # Небольшая задержка, чтобы не превысить лимиты API
                if idx % 10 == 0:
                    await asyncio.sleep(0.5)
                else:
                    await asyncio.sleep(0.1)
                
            except discord.Forbidden:
                # Пропускаем, если нет прав (роль выше или другие проблемы)
                skipped_count += 1
                if error_count < 5:  # Показываем только первые 5 ошибок
                    logger.debug(f"Нет прав для выдачи роли пользователю {member.display_name} ({member.id})")
                error_count += 1
            except discord.HTTPException as e:
                if error_count < 5:
                    logger.debug(f"Ошибка при выдаче роли пользователю {member.display_name} ({member.id}): {e}")
                error_count += 1
            except Exception as e:
                if error_count < 5:
                    logger.error(f"Неожиданная ошибка для пользователя {member.display_name} ({member.id}): {e}")
                error_count += 1
        
        logger.info("=" * 50)
        logger.info("РЕЗУЛЬТАТЫ:")
        logger.info(f"  - Выдано ролей 'Участник': {member_count}")
        if bot_role:
            logger.info(f"  - Выдано ролей 'Бот': {bot_count}")
        logger.info(f"  - Пропущено (уже есть роль): {skipped_count}")
        logger.info(f"  - Ошибок/нет прав: {error_count}")
        logger.info(f"  - Всего обработано: {len(members)}")
        logger.info("=" * 50)
        
        await client.close()
    
    try:
        await client.start(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Прервано пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        await client.close()


if __name__ == "__main__":
    try:
        asyncio.run(assign_roles())
    except KeyboardInterrupt:
        logger.info("Скрипт остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске: {e}", exc_info=True)
        sys.exit(1)

