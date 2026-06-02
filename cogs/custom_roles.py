"""
Модуль для работы с кастомными ролями пользователей.

Обеспечивает:
- Создание кастомных ролей через slash-команды
- Автоматическую выдачу разделительных ролей
- Валидацию названий и цветов
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Modal, TextInput, Button, View
import logging
from typing import Optional, Tuple, List

import config
from db.database import Database
from utils.colors import parse_color, COLOR_PRESETS
from utils.checks import check_channel, get_bot_role_position

logger = logging.getLogger(__name__)


class CreateRoleModal(Modal, title="Создание кастомной роли"):
    """Модальное окно для создания кастомной роли."""
    
    name_input = TextInput(
        label="Название роли",
        placeholder="Введите название роли (2-32 символа)",
        min_length=2,
        max_length=32,
        required=True
    )
    
    color_input = TextInput(
        label="Цвет роли",
        placeholder="HEX (#ff0000) или название (red, blue, neon_pink...)",
        min_length=1,
        max_length=50,
        required=True
    )
    
    def __init__(self, cog_instance):
        super().__init__()
        self.cog = cog_instance
    
    async def on_submit(self, interaction: discord.Interaction):
        """Обработка отправки формы."""
        name = self.name_input.value.strip()
        color = self.color_input.value.strip()
        
        # Вызываем метод создания роли из кога
        await self.cog._create_role_from_modal(interaction, name, color)


class CreateRoleView(View):
    """View с кнопкой для создания роли."""
    
    def __init__(self, cog_instance):
        super().__init__(timeout=None)
        self.cog = cog_instance
    
    @discord.ui.button(label="✨ Создать роль", style=discord.ButtonStyle.primary, emoji="✨", custom_id="create_role_button")
    async def create_button(self, button_interaction: discord.Interaction, button: Button):
        """Обработчик нажатия кнопки создания роли."""
        # Проверка канала
        if button_interaction.channel_id != config.CHANNEL_ID_CUSTOM_ROLES:
            await button_interaction.response.send_message(
                f"❌ Эта команда доступна только в канале <#{config.CHANNEL_ID_CUSTOM_ROLES}>",
                ephemeral=True
            )
            return
        
        # Проверяем, есть ли уже роль
        old_role_id = await self.cog.db.get_custom_role(button_interaction.user.id)
        if old_role_id:
            await button_interaction.response.send_message(
                "❌ У вас уже есть кастомная роль! Используйте `/role rename` или `/role color` для изменения.",
                ephemeral=True
            )
            return
        
        # Открываем модальное окно
        modal = CreateRoleModal(self.cog)
        await button_interaction.response.send_modal(modal)


class CustomRolesCog(commands.Cog):
    """Ког для управления кастомными ролями."""
    
    def __init__(self, bot: commands.Bot, db: Database):
        """
        Инициализация кога.
        
        Args:
            bot: Экземпляр бота
            db: Экземпляр базы данных
        """
        self.bot = bot
        self.db = db
        # Запускаем периодическую задачу проверки всех участников
        self.check_all_members_loop.start()

    def _get_dividers_sorted(self, guild: discord.Guild) -> list[tuple[int, int]]:
        """
        Возвращает разделители с их актуальными позициями, отсортированные по позиции.
        Если роль не найдена, используется позиция из конфига как запасной вариант.
        """
        fallback_positions = {role_id: pos for role_id, pos in config.DIVIDER_ROLES_BY_POSITION}
        dividers: list[tuple[int, int]] = []

        for divider_id in config.ROLE_GROUP_DIVIDERS.values():
            role = guild.get_role(divider_id) if guild else None
            position = role.position if role else fallback_positions.get(divider_id, 0)
            dividers.append((divider_id, position))

        dividers.sort(key=lambda item: item[1])
        return dividers
    
    @commands.Cog.listener()
    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ):
        """Обработчик ошибок команд."""
        logger.error(f"Ошибка в команде {interaction.command.name if interaction.command else 'unknown'}: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"❌ Произошла ошибка: {str(error)}",
                ephemeral=True
            )
    
    def validate_role_name(self, name: str, guild: discord.Guild) -> Tuple[bool, Optional[str]]:
        """
        Валидация названия роли.
        
        Args:
            name: Название роли
            guild: Сервер
        
        Returns:
            Кортеж (валидно, сообщение_об_ошибке)
        """
        # Проверка длины
        if len(name) < config.ROLE_NAME_MIN_LENGTH:
            return False, f"Название роли должно содержать минимум {config.ROLE_NAME_MIN_LENGTH} символа"
        
        if len(name) > config.ROLE_NAME_MAX_LENGTH:
            return False, f"Название роли не должно превышать {config.ROLE_NAME_MAX_LENGTH} символов"
        
        # Проверка на стоп-слова
        name_lower = name.lower()
        for blocked_word in config.ROLE_NAME_BLOCKED_WORDS:
            if blocked_word.lower() in name_lower:
                return False, f"Название роли содержит запрещённое слово: {blocked_word}"
        
        # Проверка на конфликт с существующими важными ролями
        # Проверяем разделительные роли
        for divider_id in config.ROLE_GROUP_DIVIDERS.values():
            divider_role = guild.get_role(divider_id)
            if divider_role and divider_role.name.lower() == name_lower:
                return False, "Название роли совпадает с разделительной ролью"
        
        # Проверяем роль бота
        bot_member = guild.me
        if bot_member and bot_member.top_role and bot_member.top_role.name.lower() == name_lower:
            return False, "Название роли совпадает с ролью бота"
        
        return True, None
    
    async def member_has_group_roles(self, member: discord.Member, group: str) -> bool:
        """
        Проверяет, есть ли у участника роли из указанной группы.
        
        Для группы "custom" проверяет по БД (точная проверка кастомных ролей).
        Для остальных групп определяет по фактическим позициям между разделителями.
        
        Args:
            member: Участник сервера
            group: Название группы (custom, medals, mentionables, other, clans)
        
        Returns:
            True, если есть роли из этой группы
        """
        if not member.guild:
            return False
        
        # Для кастомных ролей - точная проверка через БД
        if group == "custom":
            custom_role_id = await self.db.get_custom_role(member.id)
            if not custom_role_id:
                return False
            # Проверяем, что роль действительно есть у пользователя на сервере
            return any(role.id == custom_role_id for role in member.roles)
        
        divider_id = config.ROLE_GROUP_DIVIDERS.get(group)
        if not divider_id:
            return False

        dividers = self._get_dividers_sorted(member.guild)
        divider_index = next((i for i, (d_id, _) in enumerate(dividers) if d_id == divider_id), None)
        if divider_index is None:
            return False

        divider_ids = set(config.ROLE_GROUP_DIVIDERS.values())
        member_roles = [
            role for role in member.roles
            if role.id != member.guild.id and role.id not in divider_ids
        ]
        if not member_roles:
            return False

        divider_pos = dividers[divider_index][1]
        is_first = divider_index == 0
        is_last = divider_index == len(dividers) - 1
        prev_pos = dividers[divider_index - 1][1] if not is_first else None

        if is_first:
            return any(role.position < divider_pos for role in member_roles)
        if is_last:
            return any(role.position >= prev_pos for role in member_roles)

        return any(prev_pos <= role.position < divider_pos for role in member_roles)
    
    async def get_role_position(self, guild: discord.Guild) -> int:
        """
        Получить позицию для новой кастомной роли.
        
        Кастомные роли должны быть размещены между разделителями:
        - "Медали" (позиция 33) - нижняя граница
        - "Кастомные роли" (позиция 42) - верхняя граница
        
        Новые роли размещаются в диапазоне 34-41, выше существующих кастомных ролей.
        
        Args:
            guild: Сервер
        
        Returns:
            Позиция для роли
        """
        # Находим разделители
        medals_divider_id = config.ROLE_GROUP_DIVIDERS.get("medals")
        custom_divider_id = config.ROLE_GROUP_DIVIDERS.get("custom")
        
        medals_role = guild.get_role(medals_divider_id) if medals_divider_id else None
        custom_divider_role = guild.get_role(custom_divider_id) if custom_divider_id else None
        
        if not medals_role or not custom_divider_role:
            # Фолбэк: если разделители не найдены, используем старую логику
            bot_position = get_bot_role_position(guild)
            if bot_position is None:
                return 0
            if custom_divider_role:
                return custom_divider_role.position - 1
            return bot_position - 1
        
        # Определяем диапазон: между "Медали" (33) и "Кастомные роли" (42)
        medals_position = medals_role.position
        custom_position = custom_divider_role.position
        
        # Нижняя граница: сразу выше "Медали"
        min_position = medals_position + 1
        # Верхняя граница: сразу ниже "Кастомные роли"
        max_position = custom_position - 1
        
        # Находим самую высокую позицию среди существующих кастомных ролей в этом диапазоне
        # Получаем все кастомные роли из БД
        highest_custom_position = min_position - 1  # Начальное значение ниже минимума
        
        for role in guild.roles:
            # Проверяем, что роль в нужном диапазоне
            if min_position <= role.position <= max_position:
                # Проверяем, является ли это кастомной ролью (есть в БД)
                user_id = await self.db.get_user_by_role_id(role.id)
                if user_id:
                    highest_custom_position = max(highest_custom_position, role.position)
        
        # Новая роль должна быть выше всех существующих кастомных ролей
        target_position = highest_custom_position + 1
        
        # Но не выше максимальной позиции
        if target_position > max_position:
            target_position = max_position
        
        # И не ниже минимальной
        if target_position < min_position:
            target_position = min_position
        
        return target_position
    
    async def ensure_divider_role(self, member: discord.Member, group: str) -> None:
        """
        Убедиться, что у пользователя есть разделительная роль для группы.
        
        Args:
            member: Участник сервера
            group: Название группы (custom, medals, etc.)
        """
        divider_id = config.ROLE_GROUP_DIVIDERS.get(group)
        if not divider_id:
            return
        
        if not await self.member_has_group_roles(member, group):
            return
        
        divider_role = member.guild.get_role(divider_id)
        if not divider_role:
            logger.warning(f"Разделительная роль {divider_id} не найдена на сервере")
            return
        
        # Проверяем, есть ли уже эта роль
        if divider_role in member.roles:
            return
        
        try:
            await member.add_roles(divider_role, reason="Автоматическая выдача разделительной роли")
            logger.info(f"Выдана разделительная роль {group} пользователю {member.id}")
        except discord.Forbidden:
            logger.error(f"Нет прав для выдачи разделительной роли {divider_id}")
        except discord.HTTPException as e:
            logger.error(f"Ошибка при выдаче разделительной роли: {e}")
    
    async def check_and_remove_dividers(self, member: discord.Member) -> None:
        """
        Проверить и удалить разделительные роли, которые не должны быть у пользователя
        на основе наличия ролей из групп.
        
        Args:
            member: Участник сервера
        """
        if not config.AUTO_REMOVE_DIVIDERS:
            return
        
        needed_dividers = await self.get_divider_roles_by_position(member)
        needed_divider_ids = {role.id for role in needed_dividers}
        member_role_ids = {role.id for role in member.roles}

        for divider_id, _ in self._get_dividers_sorted(member.guild):
            if divider_id in member_role_ids and divider_id not in needed_divider_ids:
                divider_role = member.guild.get_role(divider_id)
                if divider_role:
                    try:
                        await member.remove_roles(
                            divider_role,
                            reason="Автоматическое снятие разделительной роли (нет ролей из группы)"
                        )
                        logger.info(f"Снята разделительная роль {divider_role.name} у пользователя {member.id}")
                    except discord.Forbidden:
                        logger.error(f"Нет прав для снятия разделительной роли {divider_id}")
                    except discord.HTTPException as e:
                        logger.error(f"Ошибка при снятии разделительной роли: {e}")
    
    role_group = app_commands.Group(name="role", description="Управление кастомными ролями")
    
    @role_group.command(name="create", description="Создать кастомную роль (открывает форму)")
    async def role_create(self, interaction: discord.Interaction):
        """Создать кастомную роль через модальное окно."""
        # Проверка канала
        if interaction.channel_id != config.CHANNEL_ID_CUSTOM_ROLES:
            await interaction.response.send_message(
                f"❌ Эта команда доступна только в канале <#{config.CHANNEL_ID_CUSTOM_ROLES}>",
                ephemeral=True
            )
            return
        
        # Открываем модальное окно
        modal = CreateRoleModal(self)
        await interaction.response.send_modal(modal)
    
    async def _create_role_from_modal(self, interaction: discord.Interaction, name: str, color: str):
        """Внутренний метод для создания роли из модального окна."""
        # Проверка канала
        if interaction.channel_id != config.CHANNEL_ID_CUSTOM_ROLES:
            await interaction.response.send_message(
                f"❌ Эта команда доступна только в канале <#{config.CHANNEL_ID_CUSTOM_ROLES}>",
                ephemeral=True
            )
            return
        
        try:
            # Валидация названия
            is_valid, error_msg = self.validate_role_name(name, interaction.guild)
            if not is_valid:
                await interaction.response.send_message(
                    f"❌ {error_msg}",
                    ephemeral=True
                )
                return
            
            # Парсинг цвета
            try:
                color_value = parse_color(color)
            except ValueError as e:
                await interaction.response.send_message(
                    f"❌ Ошибка цвета: {e}",
                    ephemeral=True
                )
                return
            
            # Проверка, есть ли уже кастомная роль у пользователя
            old_role_id = await self.db.get_custom_role(interaction.user.id)
            if old_role_id:
                old_role = interaction.guild.get_role(old_role_id)
                if old_role:
                    if config.DELETE_OLD_CUSTOM_ROLE:
                        # Удаляем старую роль
                        try:
                            await old_role.delete(reason="Замена кастомной роли")
                            logger.info(f"Удалена старая кастомная роль {old_role_id} пользователя {interaction.user.id}")
                        except discord.Forbidden:
                            if not interaction.response.is_done():
                                await interaction.response.send_message(
                                    "❌ Нет прав для удаления старой роли. Обратитесь к администратору.",
                                    ephemeral=True
                                )
                            return
                        except discord.HTTPException as e:
                            logger.error(f"Ошибка при удалении старой роли: {e}")
                            if not interaction.response.is_done():
                                await interaction.response.send_message(
                                    "❌ Ошибка при удалении старой роли. Попробуйте позже.",
                                    ephemeral=True
                                )
                            return
                    else:
                        # Просто снимаем старую роль
                        try:
                            await interaction.user.remove_roles(old_role, reason="Замена кастомной роли")
                        except discord.Forbidden:
                            pass
                        except discord.HTTPException as e:
                            logger.error(f"Ошибка при снятии старой роли: {e}")
            
            # Определяем позицию для роли
            role_position = await self.get_role_position(interaction.guild)
            
            # Создаём роль
            try:
                new_role = await interaction.guild.create_role(
                    name=name,
                    color=discord.Color(color_value),
                    reason=f"Кастомная роль для {interaction.user}"
                )
                
                # Устанавливаем позицию
                try:
                    await new_role.edit(position=role_position)
                except discord.Forbidden:
                    logger.warning(f"Не удалось установить позицию роли {new_role.id}")
                
                # Выдаём роль пользователю
                await interaction.user.add_roles(new_role, reason="Создание кастомной роли")
                
                # Сохраняем в БД
                await self.db.set_custom_role(interaction.user.id, new_role.id)
                
                # Добавляем в группу кастомных ролей
                if new_role.id not in config.ROLE_GROUPS["custom"]:
                    config.ROLE_GROUPS["custom"].append(new_role.id)
                
                # Выдаём разделительную роль
                await self.ensure_divider_role(interaction.user, "custom")
                
                logger.info(f"Создана кастомная роль {new_role.id} ({name}) для пользователя {interaction.user.id}")
                
                await interaction.response.send_message(
                    f"✅ Роль **{name}** успешно создана и выдана!",
                    ephemeral=True
                )
                
            except discord.Forbidden:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ У бота нет прав для создания ролей. Обратитесь к администратору.",
                        ephemeral=True
                    )
            except discord.HTTPException as e:
                logger.error(f"Ошибка при создании роли: {e}")
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ошибка при создании роли. Попробуйте позже.",
                        ephemeral=True
                    )
                
        except Exception as e:
            logger.error(f"Неожиданная ошибка в _create_role_from_modal: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Произошла ошибка. Попробуйте позже.",
                    ephemeral=True
                )
    
    @role_group.command(name="rename", description="Переименовать свою кастомную роль")
    @app_commands.describe(name="Новое название роли (2-32 символа)")
    async def role_rename(
        self,
        interaction: discord.Interaction,
        name: str
    ):
        """Переименовать кастомную роль."""
        # Проверка канала
        if interaction.channel_id != config.CHANNEL_ID_CUSTOM_ROLES:
            await interaction.response.send_message(
                f"❌ Эта команда доступна только в канале <#{config.CHANNEL_ID_CUSTOM_ROLES}>",
                ephemeral=True
            )
            return
        
        try:
            # Проверка наличия кастомной роли
            role_id = await self.db.get_custom_role(interaction.user.id)
            if not role_id:
                await interaction.response.send_message(
                    "❌ У вас нет кастомной роли. Создайте её командой `/role create`.",
                    ephemeral=True
                )
                return
            
            role = interaction.guild.get_role(role_id)
            if not role:
                await interaction.response.send_message(
                    "❌ Ваша кастомная роль не найдена на сервере.",
                    ephemeral=True
                )
                await self.db.remove_custom_role(interaction.user.id)
                return
            
            # Валидация названия
            is_valid, error_msg = self.validate_role_name(name, interaction.guild)
            if not is_valid:
                await interaction.response.send_message(
                    f"❌ {error_msg}",
                    ephemeral=True
                )
                return
            
            # Переименовываем
            try:
                await role.edit(name=name, reason=f"Переименование кастомной роли пользователем {interaction.user}")
                logger.info(f"Переименована кастомная роль {role_id} в {name} пользователем {interaction.user.id}")
                
                await interaction.response.send_message(
                    f"✅ Роль переименована в **{name}**!",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ У бота нет прав для изменения ролей.",
                    ephemeral=True
                )
            except discord.HTTPException as e:
                logger.error(f"Ошибка при переименовании роли: {e}")
                await interaction.response.send_message(
                    "❌ Ошибка при переименовании роли.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Неожиданная ошибка в role_rename: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Произошла ошибка. Попробуйте позже.",
                ephemeral=True
            )
    
    @role_group.command(name="color", description="Изменить цвет своей кастомной роли")
    @app_commands.describe(color="Новый цвет роли (HEX: #ff0000 или название: red, blue, neon_pink)")
    async def role_color(
        self,
        interaction: discord.Interaction,
        color: str
    ):
        """Изменить цвет кастомной роли."""
        # Проверка канала
        if interaction.channel_id != config.CHANNEL_ID_CUSTOM_ROLES:
            await interaction.response.send_message(
                f"❌ Эта команда доступна только в канале <#{config.CHANNEL_ID_CUSTOM_ROLES}>",
                ephemeral=True
            )
            return
        
        try:
            # Проверка наличия кастомной роли
            role_id = await self.db.get_custom_role(interaction.user.id)
            if not role_id:
                await interaction.response.send_message(
                    "❌ У вас нет кастомной роли. Создайте её командой `/role create`.",
                    ephemeral=True
                )
                return
            
            role = interaction.guild.get_role(role_id)
            if not role:
                await interaction.response.send_message(
                    "❌ Ваша кастомная роль не найдена на сервере.",
                    ephemeral=True
                )
                await self.db.remove_custom_role(interaction.user.id)
                return
            
            # Парсинг цвета
            try:
                color_value = parse_color(color)
            except ValueError as e:
                await interaction.response.send_message(
                    f"❌ Ошибка цвета: {e}",
                    ephemeral=True
                )
                return
            
            # Изменяем цвет
            try:
                await role.edit(color=discord.Color(color_value), reason=f"Изменение цвета кастомной роли пользователем {interaction.user}")
                logger.info(f"Изменён цвет кастомной роли {role_id} пользователем {interaction.user.id}")
                
                await interaction.response.send_message(
                    f"✅ Цвет роли изменён!",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ У бота нет прав для изменения ролей.",
                    ephemeral=True
                )
            except discord.HTTPException as e:
                logger.error(f"Ошибка при изменении цвета роли: {e}")
                await interaction.response.send_message(
                    "❌ Ошибка при изменении цвета роли.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Неожиданная ошибка в role_color: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Произошла ошибка. Попробуйте позже.",
                ephemeral=True
            )
    
    @role_group.command(name="delete", description="Удалить свою кастомную роль")
    async def role_delete(self, interaction: discord.Interaction):
        """Удалить кастомную роль."""
        # Проверка канала
        if interaction.channel_id != config.CHANNEL_ID_CUSTOM_ROLES:
            await interaction.response.send_message(
                f"❌ Эта команда доступна только в канале <#{config.CHANNEL_ID_CUSTOM_ROLES}>",
                ephemeral=True
            )
            return
        
        try:
            # Проверка наличия кастомной роли
            role_id = await self.db.get_custom_role(interaction.user.id)
            if not role_id:
                await interaction.response.send_message(
                    "❌ У вас нет кастомной роли.",
                    ephemeral=True
                )
                return
            
            role = interaction.guild.get_role(role_id)
            if not role:
                await interaction.response.send_message(
                    "❌ Ваша кастомная роль не найдена на сервере.",
                    ephemeral=True
                )
                await self.db.remove_custom_role(interaction.user.id)
                return
            
            # Удаляем роль
            try:
                await role.delete(reason=f"Удаление кастомной роли пользователем {interaction.user}")
                await self.db.remove_custom_role(interaction.user.id)
                
                # Удаляем из группы
                if role_id in config.ROLE_GROUPS["custom"]:
                    config.ROLE_GROUPS["custom"].remove(role_id)
                
                logger.info(f"Удалена кастомная роль {role_id} пользователем {interaction.user.id}")
                
                await interaction.response.send_message(
                    "✅ Кастомная роль удалена!",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "❌ У бота нет прав для удаления ролей.",
                    ephemeral=True
                )
            except discord.HTTPException as e:
                logger.error(f"Ошибка при удалении роли: {e}")
                await interaction.response.send_message(
                    "❌ Ошибка при удалении роли.",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Неожиданная ошибка в role_delete: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ Произошла ошибка. Попробуйте позже.",
                ephemeral=True
            )
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Обработчик входа нового участника на сервер.
        
        Автоматически выдаёт роль "Участник" при входе.
        """
        # Игнорируем ботов (им выдаётся роль "Бот" отдельно)
        if member.bot:
            return
        
        # Ищем роль "Участник"
        member_role = None
        role_names = ["Участник", "участник", "Member", "member"]
        
        for role in member.guild.roles:
            if role.name.lower() in [name.lower() for name in role_names]:
                member_role = role
                break
        
        if not member_role:
            logger.warning(f"Роль 'Участник' не найдена на сервере {member.guild.name}")
            return
        
        # Проверяем, есть ли уже эта роль
        if member_role in member.roles:
            return
        
        # Выдаём роль
        try:
            await member.add_roles(member_role, reason="Автоматическая выдача роли при входе на сервер")
            logger.info(f"Выдана роль 'Участник' новому участнику {member.display_name} ({member.id})")
        except discord.Forbidden:
            logger.error(f"Нет прав для выдачи роли 'Участник' пользователю {member.id}")
        except discord.HTTPException as e:
            logger.error(f"Ошибка при выдаче роли 'Участник' пользователю {member.id}: {e}")
    
    async def get_divider_roles_by_position(self, member: discord.Member) -> list[discord.Role]:
        """
        Определяет, какие разделительные роли нужно выдать пользователю
        на основе наличия ролей из соответствующих групп.
        
        Для группы "custom" проверяет по БД, для остальных - по позициям.
        
        Args:
            member: Участник сервера
            
        Returns:
            Список разделительных ролей, которые нужно выдать
        """
        if not member.guild:
            return []
        
        divider_roles_to_give = []
        
        # Проверяем в порядке реальных позиций разделителей
        divider_id_to_group = {v: k for k, v in config.ROLE_GROUP_DIVIDERS.items()}
        for divider_id, _ in self._get_dividers_sorted(member.guild):
            group = divider_id_to_group.get(divider_id)
            if not group:
                continue
            # Проверяем, есть ли у пользователя роли из этой группы
            if await self.member_has_group_roles(member, group):
                divider_role = member.guild.get_role(divider_id)
                if divider_role:
                    divider_roles_to_give.append(divider_role)
        
        return divider_roles_to_give
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """
        Обработчик изменения ролей участника.
        
        Автоматически выдаёт разделительные роли на основе групп ролей пользователя.
        """
        # Проверяем, изменились ли роли
        before_roles = {role.id for role in before.roles}
        after_roles = {role.id for role in after.roles}
        
        if before_roles == after_roles:
            return
        
        # Определяем, какие разделительные роли нужно выдать на основе позиций
        divider_roles = await self.get_divider_roles_by_position(after)
        
        # Выдаём все нужные разделительные роли
        for divider_role in divider_roles:
            if divider_role and divider_role not in after.roles:
                try:
                    await after.add_roles(divider_role, reason="Автоматическая выдача разделительной роли на основе позиций")
                    logger.info(f"Выдана разделительная роль {divider_role.name} пользователю {after.id} на основе позиций ролей")
                except discord.Forbidden:
                    logger.error(f"Нет прав для выдачи разделительной роли {divider_role.id}")
                except discord.HTTPException as e:
                    logger.error(f"Ошибка при выдаче разделительной роли: {e}")
        
        if config.AUTO_REMOVE_DIVIDERS:
            await self.check_and_remove_dividers(after)
    
    @tasks.loop(minutes=10)
    async def check_all_members_loop(self):
        """
        Периодическая задача для проверки всех участников сервера
        и выдачи недостающих разделительных ролей.
        """
        logger.info("Начало периодической проверки всех участников на разделительные роли")
        
        # Получаем все гильдии, к которым подключен бот
        for guild in self.bot.guilds:
            try:
                # Убеждаемся, что все участники загружены
                if not guild.chunked:
                    await guild.chunk()
                
                total_members = len(guild.members)
                checked = 0
                roles_given = 0
                errors = 0
                
                logger.info(f"Проверка участников сервера {guild.name} ({total_members} участников)")
                
                for member in guild.members:
                    # Пропускаем ботов
                    if member.bot:
                        continue
                    
                    try:
                        # Определяем, какие разделительные роли нужно выдать
                        divider_roles = await self.get_divider_roles_by_position(member)
                        
                        # Выдаём недостающие разделительные роли
                        for divider_role in divider_roles:
                            if divider_role and divider_role not in member.roles:
                                try:
                                    await member.add_roles(
                                        divider_role, 
                                        reason="Периодическая проверка разделительных ролей"
                                    )
                                    roles_given += 1
                                    logger.debug(
                                        f"Выдана разделительная роль {divider_role.name} "
                                        f"пользователю {member.id} ({member.display_name})"
                                    )
                                except discord.Forbidden:
                                    logger.warning(f"Нет прав для выдачи роли {divider_role.id} пользователю {member.id}")
                                    errors += 1
                                except discord.HTTPException as e:
                                    logger.error(f"Ошибка при выдаче роли пользователю {member.id}: {e}")
                                    errors += 1
                                
                                if config.AUTO_REMOVE_DIVIDERS:
                                    await self.check_and_remove_dividers(member)
                        
                        checked += 1
                        
                        # Логируем прогресс каждые 50 участников
                        if checked % 50 == 0:
                            logger.info(f"Проверено {checked}/{total_members} участников, выдано ролей: {roles_given}")
                    
                    except Exception as e:
                        logger.error(f"Ошибка при проверке участника {member.id}: {e}", exc_info=True)
                        errors += 1
                
                logger.info(
                    f"Завершена проверка сервера {guild.name}: "
                    f"проверено {checked} участников, выдано {roles_given} ролей, ошибок: {errors}"
                )
            
            except Exception as e:
                logger.error(f"Ошибка при проверке сервера {guild.name}: {e}", exc_info=True)
        
        logger.info("Завершена периодическая проверка всех участников")
    
    @check_all_members_loop.before_loop
    async def before_check_all_members_loop(self):
        """Ожидание готовности бота перед запуском периодической задачи."""
        await self.bot.wait_until_ready()
        logger.info("Периодическая задача проверки участников готова к запуску")
    
    async def check_member_roles(self, member: discord.Member) -> List[discord.Role]:
        """
        Проверяет участника и возвращает список разделительных ролей, которые нужно выдать.
        
        Args:
            member: Участник сервера
            
        Returns:
            Список разделительных ролей, которые были выданы
        """
        divider_roles = await self.get_divider_roles_by_position(member)
        given_roles = []
        
        for divider_role in divider_roles:
            if divider_role and divider_role not in member.roles:
                try:
                    await member.add_roles(
                        divider_role,
                        reason="Ручная проверка разделительных ролей"
                    )
                    given_roles.append(divider_role)
                    logger.info(f"Выдана разделительная роль {divider_role.name} пользователю {member.id}")
                except discord.Forbidden:
                    logger.error(f"Нет прав для выдачи разделительной роли {divider_role.id}")
                except discord.HTTPException as e:
                    logger.error(f"Ошибка при выдаче разделительной роли: {e}")
        
        return given_roles
    
    @app_commands.command(name="test-setup", description="Тестовая команда для проверки")
    async def test_setup(self, interaction: discord.Interaction):
        """Тестовая команда."""
        await interaction.response.send_message("✅ Тестовая команда работает!", ephemeral=True)
        logger.info(f"Тестовая команда вызвана пользователем {interaction.user.id}")
    
    @app_commands.command(name="move-colored-roles", description="[ADMIN] Переместить цветные роли выше 'Медали'")
    @app_commands.default_permissions(administrator=True)
    async def move_colored_roles_cmd(self, interaction: discord.Interaction):
        """
        Перемещает существующие цветные роли выше разделителя 'Медали'.
        Требует права администратора.
        """
        await interaction.response.defer(ephemeral=True)
        
        try:
            color_role_names = [
                "Red", "Green", "Blue", "Yellow", "Orange", "Purple", "Pink",
                "Cyan", "White", "Black", "Gray", "Grey", "Neon Pink", "Neon Green", "Neon Blue"
            ]
            
            medals_divider_id = config.ROLE_GROUP_DIVIDERS.get("medals")
            medals_role = interaction.guild.get_role(medals_divider_id) if medals_divider_id else None
            
            if not medals_role:
                await interaction.followup.send("❌ Разделитель 'Медали' не найден", ephemeral=True)
                return
            
            # Находим все цветные роли
            colored_roles = []
            for role_name in color_role_names:
                role = discord.utils.get(interaction.guild.roles, name=role_name)
                if role:
                    colored_roles.append(role)
            
            if not colored_roles:
                await interaction.followup.send("❌ Цветные роли не найдены на сервере", ephemeral=True)
                return
            
            # Перемещаем роли выше разделителя "Медали"
            try:
                base_position = medals_role.position + 1
                position_updates = {
                    role: base_position + idx for idx, role in enumerate(colored_roles)
                }
                await interaction.guild.edit_role_positions(positions=position_updates)
                
                msg = f"✅ Успешно перемещено {len(colored_roles)} цветных ролей выше разделителя 'Медали'\n"
                msg += f"Новая позиция начинается с {base_position}"
                
                await interaction.followup.send(msg, ephemeral=True)
                logger.info(f"Цветные роли перемещены выше 'Медали' ({interaction.user.id})")
                
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ Нет прав для перемещения ролей. Убедитесь, что:\n"
                    "• У бота есть право 'Manage Roles'\n"
                    "• Роль бота находится выше перемещаемых ролей",
                    ephemeral=True
                )
            except discord.HTTPException as e:
                await interaction.followup.send(f"❌ Ошибка Discord API: {e}", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Ошибка в move_colored_roles_cmd: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Неожиданная ошибка: {e}", ephemeral=True)
    
    @app_commands.command(name="create-colored-roles", description="[ADMIN] Создать и выдать цветные роли")
    @app_commands.default_permissions(administrator=True)
    async def create_colored_roles_cmd(self, interaction: discord.Interaction):
        """
        Создаёт 15 цветных ролей выше разделителя 'Медали' и выдает их случайно всем пользователям.
        Требует права администратора.
        """
        await interaction.response.defer(ephemeral=True)
        
        try:
            from utils.colors import parse_color
            import random
            
            color_names = [
                "red", "green", "blue", "yellow", "orange", "purple", "pink", 
                "cyan", "white", "black", "gray", "grey", "neon_pink", "neon_green", "neon_blue"
            ]
            
            medals_divider_id = config.ROLE_GROUP_DIVIDERS.get("medals")
            medals_role = interaction.guild.get_role(medals_divider_id) if medals_divider_id else None
            
            if not medals_role:
                await interaction.followup.send("❌ Разделитель 'Медали' не найден", ephemeral=True)
                return
            
            created_roles = []
            existing_count = 0
            
            # Создание ролей
            for color_name in color_names:
                role_name = color_name.replace("_", " ").title()
                existing = discord.utils.get(interaction.guild.roles, name=role_name)
                
                if existing:
                    created_roles.append(existing)
                    existing_count += 1
                    continue
                
                color_value = parse_color(color_name)
                role = await interaction.guild.create_role(
                    name=role_name,
                    color=discord.Color(color_value),
                    reason=f"Цветные роли (команда от {interaction.user})"
                )
                created_roles.append(role)
            
            # Перемещение ролей
            if created_roles:
                try:
                    base_position = medals_role.position + 1
                    position_updates = {
                        role: base_position + idx for idx, role in enumerate(created_roles)
                    }
                    await interaction.guild.edit_role_positions(positions=position_updates)
                except (discord.Forbidden, discord.HTTPException):
                    pass  # Пропускаем если нет прав
            
            # Выдача ролей участникам
            members = [m for m in interaction.guild.members if not m.bot]
            total_given = 0
            
            for member in members:
                role = random.choice(created_roles)
                try:
                    await member.add_roles(role, reason="Случайная выдача цветной роли")
                    total_given += 1
                except:
                    pass
            
            msg = f"✅ Готово!\n"
            msg += f"• Создано новых ролей: {len(created_roles) - existing_count}\n"
            msg += f"• Использовано существующих: {existing_count}\n"
            msg += f"• Выдано ролей: {total_given} участникам"
            
            await interaction.followup.send(msg, ephemeral=True)
            logger.info(f"Цветные роли созданы и выданы ({interaction.user.id})")
            
        except Exception as e:
            logger.error(f"Ошибка в create_colored_roles_cmd: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Ошибка: {e}", ephemeral=True)
    
    @role_group.command(name="setup", description="Отправить статичное сообщение с кнопкой создания роли")
    async def role_setup(self, interaction: discord.Interaction):
        """Отправить статичное информационное сообщение с кнопкой для создания роли."""
        try:
            logger.info(f"Команда /role setup вызвана пользователем {interaction.user.id} ({interaction.user.name}) в канале {interaction.channel_id}")
            
            # Проверка прав (мягкая проверка)
            if not interaction.user.guild_permissions.manage_messages:
                logger.warning(f"Пользователь {interaction.user.id} не имеет прав manage_messages")
                await interaction.response.send_message(
                    "❌ У вас нет прав для использования этой команды. Нужны права 'Управление сообщениями'.",
                    ephemeral=True
                )
                return
            
            # Проверка канала
            if interaction.channel_id != config.CHANNEL_ID_CUSTOM_ROLES:
                logger.warning(f"Попытка использовать /role setup в неправильном канале: {interaction.channel_id} (ожидался {config.CHANNEL_ID_CUSTOM_ROLES})")
                await interaction.response.send_message(
                    f"❌ Эта команда доступна только в канале <#{config.CHANNEL_ID_CUSTOM_ROLES}>",
                    ephemeral=True
                )
                return
            
            # Создаём embed с описанием
            color_list = ', '.join(list(COLOR_PRESETS.keys())[:15])
            embed = discord.Embed(
                title="🎨 Кастомные роли",
                description=(
                    "Создайте свою уникальную роль с выбранным названием и цветом!\n\n"
                    "**📋 Правила:**\n"
                    "• Один пользователь может иметь только **одну** кастомную роль\n"
                    "• Название роли: **2-32 символа**\n"
                    "• Цвет можно указать в формате HEX (`#ff0000`) или использовать предустановленные названия\n\n"
                    f"**🎨 Доступные цвета:**\n"
                    f"`{color_list}...`\n\n"
                    "**⚙️ Команды:**\n"
                    "• Нажмите кнопку ниже или используйте `/role create` - Создать новую роль\n"
                    "• `/role rename` - Переименовать свою роль\n"
                    "• `/role color` - Изменить цвет своей роли\n"
                    "• `/role delete` - Удалить свою роль\n\n"
                    "**💡 Совет:** Нажмите кнопку ниже, чтобы быстро создать роль!"
                ),
                color=discord.Color.blue()
            )
            embed.set_footer(text="Кастомные роли • CyberKotleta")
            
            # Создаём View с кнопкой
            view = CreateRoleView(self)
            
            await interaction.response.send_message(embed=embed, view=view)
            logger.info(f"✅ Отправлено статичное информационное сообщение о кастомных ролях в канал {interaction.channel_id}")
            
        except Exception as e:
            logger.error(f"Ошибка в role_setup: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"❌ Произошла ошибка: {str(e)}",
                    ephemeral=True
                )


async def setup(bot: commands.Bot):
    """Функция для загрузки кога."""
    # Получаем экземпляр БД из бота
    db = bot.db
    await bot.add_cog(CustomRolesCog(bot, db))

