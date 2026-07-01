"""
Автоматическая выдача роли за установленный тег сервера.

Проверяет поле user.primary_guild в Discord API. Роль выдаётся только тем
пользователям, которые отображают тег текущего сервера.
"""

import asyncio
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config

logger = logging.getLogger(__name__)


class ServerTagRoleCog(commands.Cog):
    """Ког для роли за отображаемый тег сервера."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sync_server_tag_roles_loop.start()

    def cog_unload(self):
        self.sync_server_tag_roles_loop.cancel()

    def _get_target_guilds(self) -> list[discord.Guild]:
        if config.GUILD_ID:
            guild = self.bot.get_guild(config.GUILD_ID)
            return [guild] if guild else []
        return list(self.bot.guilds)

    def _find_reference_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        reference_role_id = getattr(config, "SERVER_TAG_REFERENCE_ROLE_ID", 0)
        if reference_role_id:
            role = guild.get_role(reference_role_id)
            if role:
                return role

        for role_name in config.SERVER_TAG_REFERENCE_ROLE_NAMES:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                return role

        return None

    def _find_tag_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        role_id = getattr(config, "SERVER_TAG_ROLE_ID", 0)
        if role_id:
            role = guild.get_role(role_id)
            if role:
                return role

            logger.error(f"Роль за тег сервера с ID {role_id} не найдена на сервере {guild.name}")
            return None

        return discord.utils.get(guild.roles, name=config.SERVER_TAG_ROLE_NAME)

    async def ensure_tag_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        """Получить, создать или обновить роль за тег сервера."""
        role = self._find_tag_role(guild)
        if getattr(config, "SERVER_TAG_ROLE_ID", 0):
            return role

        reference_role = self._find_reference_role(guild)
        role_color = discord.Color(config.SERVER_TAG_ROLE_COLOR)

        if role is None:
            try:
                role = await guild.create_role(
                    name=config.SERVER_TAG_ROLE_NAME,
                    color=role_color,
                    hoist=config.SERVER_TAG_ROLE_HOIST,
                    mentionable=False,
                    reason="Роль за установленный тег сервера",
                )
                logger.info(f"Создана роль {role.name} ({role.id}) на сервере {guild.name}")
            except discord.Forbidden:
                logger.error(f"Нет прав для создания роли {config.SERVER_TAG_ROLE_NAME} на сервере {guild.name}")
                return None
            except discord.HTTPException as e:
                logger.error(f"Ошибка Discord API при создании роли {config.SERVER_TAG_ROLE_NAME}: {e}")
                return None

        update_kwargs = {}
        if role.color.value != config.SERVER_TAG_ROLE_COLOR:
            update_kwargs["color"] = role_color
        if role.hoist != config.SERVER_TAG_ROLE_HOIST:
            update_kwargs["hoist"] = config.SERVER_TAG_ROLE_HOIST
        if role.mentionable:
            update_kwargs["mentionable"] = False

        if update_kwargs:
            try:
                await role.edit(**update_kwargs, reason="Синхронизация настроек роли за тег сервера")
            except discord.Forbidden:
                logger.error(f"Нет прав для изменения роли {role.name} ({role.id})")
            except discord.HTTPException as e:
                logger.error(f"Ошибка Discord API при изменении роли {role.name}: {e}")

        if reference_role and role.position <= reference_role.position:
            try:
                await role.edit(
                    position=reference_role.position + 1,
                    reason="Размещение роли за тег сервера выше роли Участник",
                )
            except discord.Forbidden:
                logger.error(
                    f"Нет прав для перемещения роли {role.name} выше {reference_role.name}. "
                    "Проверьте, что роль бота находится выше этих ролей."
                )
            except discord.HTTPException as e:
                logger.error(f"Ошибка Discord API при перемещении роли {role.name}: {e}")
        elif not reference_role:
            logger.warning(
                f"Опорная роль для {config.SERVER_TAG_ROLE_NAME} не найдена. "
                f"Проверьте SERVER_TAG_REFERENCE_ROLE_ID или SERVER_TAG_REFERENCE_ROLE_NAMES."
            )

        return role

    async def user_has_current_server_tag(self, member: discord.Member) -> bool:
        """Проверить, отображает ли пользователь тег текущего сервера."""
        try:
            raw_user = await self.bot.http.get_user(member.id)
        except discord.NotFound:
            return False
        except discord.HTTPException as e:
            logger.warning(f"Не удалось получить пользователя {member.id} для проверки тега: {e}")
            return False

        primary_guild = raw_user.get("primary_guild") if isinstance(raw_user, dict) else None
        if not primary_guild:
            return False

        identity_guild_id = primary_guild.get("identity_guild_id")
        identity_enabled = primary_guild.get("identity_enabled")
        tag = primary_guild.get("tag")
        expected_tag = getattr(config, "SERVER_TAG_VALUE", "")
        has_expected_tag = str(tag) == expected_tag if expected_tag else tag is not None

        try:
            identity_guild_id = int(identity_guild_id)
        except (TypeError, ValueError):
            return False

        return (
            identity_enabled is True
            and has_expected_tag
            and identity_guild_id is not None
            and identity_guild_id == member.guild.id
        )

    async def sync_member_tag_role(self, member: discord.Member, role: discord.Role) -> bool:
        """Синхронизировать роль у одного участника. Возвращает True, если были изменения."""
        if member.bot:
            return False

        has_server_tag = await self.user_has_current_server_tag(member)
        has_role = role in member.roles

        if has_server_tag and not has_role:
            try:
                await member.add_roles(role, reason="Пользователь установил тег сервера")
                logger.info(f"Выдана роль {role.name} пользователю {member.id}")
                return True
            except discord.Forbidden:
                logger.error(f"Нет прав для выдачи роли {role.name} пользователю {member.id}")
            except discord.HTTPException as e:
                logger.error(f"Ошибка Discord API при выдаче роли {role.name} пользователю {member.id}: {e}")

        if not has_server_tag and has_role:
            try:
                await member.remove_roles(role, reason="Пользователь не отображает тег сервера")
                logger.info(f"Снята роль {role.name} у пользователя {member.id}")
                return True
            except discord.Forbidden:
                logger.error(f"Нет прав для снятия роли {role.name} у пользователя {member.id}")
            except discord.HTTPException as e:
                logger.error(f"Ошибка Discord API при снятии роли {role.name} у пользователя {member.id}: {e}")

        return False

    async def sync_guild_tag_roles(self, guild: discord.Guild) -> tuple[int, int, int]:
        """Синхронизировать роль за тег сервера у всех участников."""
        role = await self.ensure_tag_role(guild)
        if role is None:
            return 0, 0, 1

        if not guild.chunked:
            await guild.chunk()

        checked = 0
        changed = 0
        errors = 0

        for member in guild.members:
            if member.bot:
                continue

            try:
                if await self.sync_member_tag_role(member, role):
                    changed += 1
            except Exception as e:
                logger.error(f"Ошибка при синхронизации роли за тег у пользователя {member.id}: {e}", exc_info=True)
                errors += 1

            checked += 1
            await asyncio.sleep(config.SERVER_TAG_REQUEST_DELAY_SECONDS)

        return checked, changed, errors

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Проверить нового участника при входе на сервер."""
        role = await self.ensure_tag_role(member.guild)
        if role:
            await self.sync_member_tag_role(member, role)

    @tasks.loop(minutes=config.SERVER_TAG_SYNC_INTERVAL_MINUTES)
    async def sync_server_tag_roles_loop(self):
        """Периодическая синхронизация роли за тег сервера."""
        for guild in self._get_target_guilds():
            try:
                logger.info(f"Начало синхронизации роли {config.SERVER_TAG_ROLE_NAME} на сервере {guild.name}")
                checked, changed, errors = await self.sync_guild_tag_roles(guild)
                logger.info(
                    f"Синхронизация роли {config.SERVER_TAG_ROLE_NAME} завершена: "
                    f"проверено {checked}, изменений {changed}, ошибок {errors}"
                )
            except Exception as e:
                logger.error(f"Ошибка синхронизации роли за тег сервера {guild.name}: {e}", exc_info=True)

    @sync_server_tag_roles_loop.before_loop
    async def before_sync_server_tag_roles_loop(self):
        await self.bot.wait_until_ready()
        logger.info("Периодическая синхронизация роли за тег сервера готова к запуску")

    @app_commands.command(name="sync-server-tag-role", description="[ADMIN] Синхронизировать роль за тег сервера")
    @app_commands.default_permissions(administrator=True)
    async def sync_server_tag_role_command(self, interaction: discord.Interaction):
        """Ручная синхронизация роли за тег сервера."""
        if not interaction.guild:
            await interaction.response.send_message("❌ Команда доступна только на сервере.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            checked, changed, errors = await self.sync_guild_tag_roles(interaction.guild)
            await interaction.followup.send(
                f"✅ Синхронизация завершена.\n"
                f"• Проверено участников: {checked}\n"
                f"• Изменений ролей: {changed}\n"
                f"• Ошибок: {errors}",
                ephemeral=True,
            )
        except Exception as e:
            logger.error(f"Ошибка в sync_server_tag_role_command: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Ошибка синхронизации: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    """Функция для загрузки кога."""
    await bot.add_cog(ServerTagRoleCog(bot))
