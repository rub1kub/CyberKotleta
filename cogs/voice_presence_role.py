"""
Автоматическая выдача роли пользователям, которые сейчас находятся в войсе.
"""

import logging
from typing import Optional

import discord
from discord.ext import commands, tasks

import config

logger = logging.getLogger(__name__)


class VoicePresenceRoleCog(commands.Cog):
    """Ког для роли текущего присутствия в голосовых каналах."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sync_voice_presence_roles_loop.start()

    def cog_unload(self):
        self.sync_voice_presence_roles_loop.cancel()

    def _get_target_guilds(self) -> list[discord.Guild]:
        if config.GUILD_ID:
            guild = self.bot.get_guild(config.GUILD_ID)
            return [guild] if guild else []
        return list(self.bot.guilds)

    def _find_voice_presence_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        return discord.utils.get(guild.roles, name=config.VOICE_PRESENCE_ROLE_NAME)

    def _member_is_in_voice(self, member: discord.Member) -> bool:
        return member.voice is not None and member.voice.channel is not None

    async def ensure_voice_presence_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        """Создать или обновить роль присутствия в войсе."""
        role = self._find_voice_presence_role(guild)
        role_color = discord.Color(config.VOICE_PRESENCE_ROLE_COLOR)

        if role is None:
            try:
                role = await guild.create_role(
                    name=config.VOICE_PRESENCE_ROLE_NAME,
                    color=role_color,
                    hoist=config.VOICE_PRESENCE_ROLE_HOIST,
                    mentionable=False,
                    reason="Роль для участников, которые сейчас находятся в войсе",
                )
                logger.info(f"Создана роль {role.name} ({role.id}) на сервере {guild.name}")
            except discord.Forbidden:
                logger.error(f"Нет прав для создания роли {config.VOICE_PRESENCE_ROLE_NAME} на сервере {guild.name}")
                return None
            except discord.HTTPException as e:
                logger.error(f"Ошибка Discord API при создании роли {config.VOICE_PRESENCE_ROLE_NAME}: {e}")
                return None

        update_kwargs = {}
        if role.color.value != config.VOICE_PRESENCE_ROLE_COLOR:
            update_kwargs["color"] = role_color
        if role.hoist != config.VOICE_PRESENCE_ROLE_HOIST:
            update_kwargs["hoist"] = config.VOICE_PRESENCE_ROLE_HOIST
        if role.mentionable:
            update_kwargs["mentionable"] = False

        if update_kwargs:
            try:
                await role.edit(**update_kwargs, reason="Синхронизация настроек роли присутствия в войсе")
            except discord.Forbidden:
                logger.error(f"Нет прав для изменения роли {role.name} ({role.id})")
            except discord.HTTPException as e:
                logger.error(f"Ошибка Discord API при изменении роли {role.name}: {e}")

        return role

    async def sync_member_voice_presence_role(self, member: discord.Member, role: discord.Role) -> bool:
        """Синхронизировать роль одного участника. Возвращает True, если были изменения."""
        if member.bot:
            return False

        is_in_voice = self._member_is_in_voice(member)
        has_role = role in member.roles

        if is_in_voice and not has_role:
            try:
                await member.add_roles(role, reason="Пользователь находится в голосовом канале")
                logger.info(f"Выдана роль {role.name} пользователю {member.id}")
                return True
            except discord.Forbidden:
                logger.error(f"Нет прав для выдачи роли {role.name} пользователю {member.id}")
            except discord.HTTPException as e:
                logger.error(f"Ошибка Discord API при выдаче роли {role.name} пользователю {member.id}: {e}")

        if not is_in_voice and has_role:
            try:
                await member.remove_roles(role, reason="Пользователь вышел из голосового канала")
                logger.info(f"Снята роль {role.name} у пользователя {member.id}")
                return True
            except discord.Forbidden:
                logger.error(f"Нет прав для снятия роли {role.name} у пользователя {member.id}")
            except discord.HTTPException as e:
                logger.error(f"Ошибка Discord API при снятии роли {role.name} у пользователя {member.id}: {e}")

        return False

    async def sync_guild_voice_presence_roles(self, guild: discord.Guild) -> tuple[int, int, int]:
        """Синхронизировать роль присутствия в войсе у всех участников сервера."""
        role = await self.ensure_voice_presence_role(guild)
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
                if await self.sync_member_voice_presence_role(member, role):
                    changed += 1
            except Exception as e:
                logger.error(f"Ошибка при синхронизации роли войса у пользователя {member.id}: {e}", exc_info=True)
                errors += 1

            checked += 1

        return checked, changed, errors

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """Выдать роль при входе в войс и снять при полном выходе из войса."""
        if member.bot:
            return

        if before.channel == after.channel:
            return

        role = await self.ensure_voice_presence_role(member.guild)
        if role:
            await self.sync_member_voice_presence_role(member, role)

    @tasks.loop(seconds=config.VOICE_PRESENCE_SYNC_INTERVAL_SECONDS)
    async def sync_voice_presence_roles_loop(self):
        """Периодическая защита от рассинхрона роли присутствия в войсе."""
        for guild in self._get_target_guilds():
            try:
                checked, changed, errors = await self.sync_guild_voice_presence_roles(guild)
                if changed or errors:
                    logger.info(
                        f"Синхронизация роли {config.VOICE_PRESENCE_ROLE_NAME}: "
                        f"проверено {checked}, изменений {changed}, ошибок {errors}"
                    )
            except Exception as e:
                logger.error(f"Ошибка синхронизации роли присутствия в войсе на сервере {guild.name}: {e}", exc_info=True)

    @sync_voice_presence_roles_loop.before_loop
    async def before_sync_voice_presence_roles_loop(self):
        await self.bot.wait_until_ready()
        logger.info("Периодическая синхронизация роли присутствия в войсе готова к запуску")


async def setup(bot: commands.Bot):
    """Функция для загрузки кога."""
    await bot.add_cog(VoicePresenceRoleCog(bot))
