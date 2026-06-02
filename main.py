"""
Точка входа для бота CyberKotleta Core.

Инициализирует бота, загружает конфигурацию, настраивает логирование,
подключается к базе данных и загружает все коги.
"""

import asyncio
import logging
import sys

import discord
from discord import app_commands
from discord.ext import commands

import config
from logging_config import setup_logging
from db.database import Database

# Настройка логирования
setup_logging(logging.INFO)
logger = logging.getLogger(__name__)


class CyberKotletaBot(commands.Bot):
    """Основной класс бота."""
    
    def __init__(self):
        """Инициализация бота."""
        # Настройка intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None  # Отключаем встроенную команду help
        )
        
        # Инициализация базы данных
        self.db = Database(config.DATABASE_PATH)
    
    async def setup_hook(self):
        """Выполняется один раз при запуске бота."""
        logger.info("Инициализация бота...")
        
        # Обработчик ошибок для app_commands
        async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            logger.error(f"Ошибка в команде {interaction.command.name if interaction.command else 'unknown'}: {error}", exc_info=True)
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        f"❌ Произошла ошибка: {str(error)}",
                        ephemeral=True
                    )
                except:
                    pass
        
        self.tree.on_error = on_app_command_error
        
        # Подключение к БД
        await self.db.connect()
        await self.db.init_db()
        logger.info("База данных инициализирована")
        
        # Загрузка когов
        try:
            await self.load_extension("cogs.custom_roles")
            logger.info("Загружен ког: custom_roles")
            # Регистрируем persistent view для кнопки создания роли
            from cogs.custom_roles import CustomRolesCog, CreateRoleView
            # Находим загруженный ког
            cog = self.get_cog("CustomRolesCog")
            if cog:
                self.add_view(CreateRoleView(cog))
                logger.info("Зарегистрирован persistent view для создания ролей")
        except Exception as e:
            logger.error(f"Ошибка при загрузке кога custom_roles: {e}", exc_info=True)
        
        try:
            await self.load_extension("cogs.stats_voice")
            logger.info("Загружен ког: stats_voice")
        except Exception as e:
            logger.error(f"Ошибка при загрузке кога stats_voice: {e}", exc_info=True)
        
        try:
            await self.load_extension("cogs.stats_messages")
            logger.info("Загружен ког: stats_messages")
        except Exception as e:
            logger.error(f"Ошибка при загрузке кога stats_messages: {e}", exc_info=True)
        
        try:
            await self.load_extension("cogs.stats_commands")
            logger.info("Загружен ког: stats_commands")
        except Exception as e:
            logger.error(f"Ошибка при загрузке кога stats_commands: {e}", exc_info=True)
        
        try:
            await self.load_extension("cogs.help")
            logger.info("Загружен ког: help")
        except Exception as e:
            logger.error(f"Ошибка при загрузке кога help: {e}", exc_info=True)
        
        try:
            await self.load_extension("cogs.levels")
            logger.info("Загружен ког: levels")
        except Exception as e:
            logger.error(f"Ошибка при загрузке кога levels: {e}", exc_info=True)
        
        try:
            await self.load_extension("cogs.reputation")
            logger.info("Загружен ког: reputation")
        except Exception as e:
            logger.error(f"Ошибка при загрузке кога reputation: {e}", exc_info=True)

        try:
            await self.load_extension("cogs.server_tag_role")
            logger.info("Загружен ког: server_tag_role")
        except Exception as e:
            logger.error(f"Ошибка при загрузке кога server_tag_role: {e}", exc_info=True)

        try:
            await self.load_extension("cogs.voice_presence_role")
            logger.info("Загружен ког: voice_presence_role")
        except Exception as e:
            logger.error(f"Ошибка при загрузке кога voice_presence_role: {e}", exc_info=True)

        try:
            await self.load_extension("cogs.voice_king")
            logger.info("Загружен ког: voice_king")
        except Exception as e:
            logger.error(f"Ошибка при загрузке кога voice_king: {e}", exc_info=True)
        
        # Синхронизация команд
        if config.GUILD_ID:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(f"Команды синхронизированы для сервера {config.GUILD_ID}: {len(synced)} команд")
            for cmd in synced:
                logger.debug(f"  - {cmd.name} (ID: {cmd.id})")
        else:
            synced = await self.tree.sync()
            logger.info(f"Команды синхронизированы глобально: {len(synced)} команд")
            for cmd in synced:
                logger.debug(f"  - {cmd.name} (ID: {cmd.id})")
    
    async def on_ready(self):
        """Выполняется при готовности бота."""
        logger.info(f"Бот запущен: {self.user} (ID: {self.user.id})")
        logger.info(f"Подключено к {len(self.guilds)} серверам")
        
        # Устанавливаем статус
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="CyberKotleta"
        )
        await self.change_presence(activity=activity)
    
    async def close(self):
        """Закрытие бота и очистка ресурсов."""
        logger.info("Закрытие бота...")
        await self.db.close()
        await super().close()


async def main():
    """Основная функция запуска."""
    # Проверка конфигурации
    if not config.DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN не установлен в config.py!")
        sys.exit(1)
    
    if not config.GUILD_ID:
        logger.warning("GUILD_ID не установлен в config.py. Команды будут синхронизированы глобально.")
    
    # Создание и запуск бота
    bot = CyberKotletaBot()
    
    try:
        await bot.start(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске: {e}", exc_info=True)
        sys.exit(1)
