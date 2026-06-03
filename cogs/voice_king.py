"""
Недельный титул Войс-царя.

Роль выдаётся участнику с максимальным временем в голосовых каналах за текущую неделю.
При захвате трона бот публично объявляет смену лидера.
"""

import logging
import random
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from db.database import Database
from utils.formatting import format_time_seconds

logger = logging.getLogger(__name__)


CAPTURE_TEMPLATES = [
    "🎙 **ТРОН ЗАХВАЧЕН.** {new} выбил {old} из кресла Войс-царя. {old}, можешь пока погреть лавку запасных.",
    "👑 {new} забрал титул **Войс-царя**. {old}, твоя эпоха закончилась быстрее, чем оправдания после лива из войса.",
    "💀 {old} больше не Войс-царь. {new} прошёл мимо, забрал корону и оставил табличку «не мешать профессионалам».",
    "📉 {old} потерял трон. {new} теперь главный по войсу, а бывший царь официально переведён в массовку.",
    "🔥 {new} снёс {old} с вершины войса. Просим не плакать в микрофон — статистика слёз не учитывается.",
]

FIRST_CORONATION_TEMPLATES = [
    "🎙 {new} стал **Войс-царём недели**. Остальные пока изображают декоративный шум в канале.",
    "👑 На троне войса теперь {new}. Если кто-то против — статистика ждёт, рот не считается.",
    "🔥 {new} забрал первый титул **Войс-царя** на этой неделе. Остальным пора перестать быть фоном.",
]


class VoiceKingCog(commands.Cog):
    """Ког для недельного Войс-царя."""

    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db
        self.last_announced_leaders: dict[int, int] = {}
        self.sync_voice_king_loop.start()

    def cog_unload(self):
        self.sync_voice_king_loop.cancel()

    def _get_target_guilds(self) -> list[discord.Guild]:
        if config.GUILD_ID:
            guild = self.bot.get_guild(config.GUILD_ID)
            return [guild] if guild else []
        return list(self.bot.guilds)

    def _find_voice_king_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        role = discord.utils.get(guild.roles, name=config.VOICE_KING_ROLE_NAME)
        if role:
            return role

        known_prefixes = [
            f"{config.VOICE_KING_ROLE_NAME} — ",
            "🎙 Войс-царь — ",
        ]
        known_exact_names = [
            config.VOICE_KING_ROLE_NAME,
            "🎙 Войс-царь",
        ]

        return next(
            (
                role
                for role in guild.roles
                if role.name in known_exact_names
                or any(role.name.startswith(prefix) for prefix in known_prefixes)
            ),
            None,
        )

    def _get_current_role_holders(self, guild: discord.Guild, role: discord.Role) -> list[discord.Member]:
        return [member for member in guild.members if role in member.roles and not member.bot]

    def _iter_live_voice_members(self, guild: discord.Guild) -> list[discord.Member]:
        """Получить всех живых участников в обычных голосовых каналах."""
        members = []
        seen_member_ids = set()

        for channel in guild.voice_channels:
            if channel == guild.afk_channel:
                continue

            for member in channel.members:
                if member.bot or member.id in seen_member_ids:
                    continue

                seen_member_ids.add(member.id)
                members.append(member)

        return members

    def _member_is_online(self, member: discord.Member) -> bool:
        """Проверить, видит ли бот участника онлайн."""
        return member.status != discord.Status.offline

    async def _get_live_weekly_seconds(self, member: discord.Member, now: datetime) -> int:
        """Получить недельное время с учётом текущего несохранённого отрезка в войсе."""
        weekly_seconds = await self.db.get_weekly_voice_seconds(member.id)
        _, last_join_ts = await self.db.get_voice_stats(member.id)

        if not last_join_ts:
            return weekly_seconds

        active_seconds = max(0, int((now - last_join_ts).total_seconds()))
        return weekly_seconds + active_seconds

    async def _get_weekly_top_members(
        self,
        guild: discord.Guild,
        limit: int = 1000,
        online_only: bool = False,
    ) -> list[tuple[discord.Member, int]]:
        """Получить недельных лидеров среди участников сервера."""
        top = []
        for user_id, seconds in await self.db.get_top_weekly_voice(limit):
            member = guild.get_member(user_id)
            if member and not member.bot and (not online_only or self._member_is_online(member)):
                top.append((member, seconds))

        top.sort(key=lambda item: (-item[1], item[0].display_name.casefold(), item[0].id))
        return top

    def _build_role_name(self, seconds: Optional[int] = None) -> str:
        """Собрать название роли Войс-царя."""
        if seconds is None:
            return config.VOICE_KING_ROLE_NAME

        if seconds < 3600:
            minutes = max(1, seconds // 60)
            duration = f"{minutes}мин"
        else:
            duration = f"{seconds // 3600}ч"

        return f"{config.VOICE_KING_ROLE_NAME} — {duration}"[:100]

    async def _sync_role_name(self, role: discord.Role, seconds: Optional[int]) -> None:
        """Обновить название роли с текущими часами лидера."""
        target_name = self._build_role_name(seconds)
        if role.name == target_name:
            return

        try:
            await role.edit(name=target_name, reason="Обновление времени Войс-царя в названии роли")
            logger.info(f"Роль Войс-царя переименована: {target_name}")
        except discord.Forbidden:
            logger.error(f"Нет прав для переименования роли {role.name} ({role.id})")
        except discord.HTTPException as e:
            logger.error(f"Ошибка Discord API при переименовании роли {role.name}: {e}")

    async def ensure_voice_king_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        """Создать или обновить роль Войс-царя."""
        role = self._find_voice_king_role(guild)
        role_color = discord.Color(config.VOICE_KING_ROLE_COLOR)

        if role is None:
            try:
                role = await guild.create_role(
                    name=config.VOICE_KING_ROLE_NAME,
                    color=role_color,
                    hoist=config.VOICE_KING_ROLE_HOIST,
                    mentionable=False,
                    reason="Роль недельного лидера по времени в голосовых каналах",
                )
                logger.info(f"Создана роль {role.name} ({role.id}) на сервере {guild.name}")
            except discord.Forbidden:
                logger.error(f"Нет прав для создания роли {config.VOICE_KING_ROLE_NAME} на сервере {guild.name}")
                return None
            except discord.HTTPException as e:
                logger.error(f"Ошибка Discord API при создании роли {config.VOICE_KING_ROLE_NAME}: {e}")
                return None

        update_kwargs = {}
        if role.color.value != config.VOICE_KING_ROLE_COLOR:
            update_kwargs["color"] = role_color
        if role.hoist != config.VOICE_KING_ROLE_HOIST:
            update_kwargs["hoist"] = config.VOICE_KING_ROLE_HOIST
        if role.mentionable:
            update_kwargs["mentionable"] = False

        if update_kwargs:
            try:
                await role.edit(**update_kwargs, reason="Синхронизация настроек роли Войс-царя")
            except discord.Forbidden:
                logger.error(f"Нет прав для изменения роли {role.name} ({role.id})")
            except discord.HTTPException as e:
                logger.error(f"Ошибка Discord API при изменении роли {role.name}: {e}")

        return role

    def _find_announce_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        channel_id = config.VOICE_KING_ANNOUNCE_CHANNEL_ID
        if channel_id:
            channel = guild.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                logger.warning(f"Канал для анонса Войс-царя {channel_id} не найден на сервере {guild.name}")
                return None

            permissions = channel.permissions_for(guild.me)
            if not permissions.view_channel or not permissions.send_messages:
                logger.warning(f"Нет доступа к каналу для анонса Войс-царя {channel_id}")
                return None

            return channel

        candidates = []
        if guild.system_channel:
            candidates.append(guild.system_channel)
        candidates.extend(guild.text_channels)

        for channel in candidates:
            permissions = channel.permissions_for(guild.me)
            if permissions.view_channel and permissions.send_messages:
                return channel

        return None

    def _build_announcement(
        self,
        new_member: discord.Member,
        old_member: Optional[discord.Member],
        seconds: int,
    ) -> str:
        if old_member and config.VOICE_KING_TOXIC_ANNOUNCEMENTS:
            text = random.choice(CAPTURE_TEMPLATES).format(new=new_member.mention, old=old_member.mention)
        elif config.VOICE_KING_ANNOUNCE_FIRST_CORONATION:
            text = random.choice(FIRST_CORONATION_TEMPLATES).format(new=new_member.mention)
        else:
            text = f"🎙 {new_member.mention} стал **Войс-царём недели**."

        return f"{text}\n`Недельное время в войсе: {format_time_seconds(seconds)}`"

    async def _announce_new_king(
        self,
        guild: discord.Guild,
        new_member: discord.Member,
        old_member: Optional[discord.Member],
        seconds: int,
    ) -> None:
        channel = self._find_announce_channel(guild)
        if not channel:
            logger.warning(f"Канал для анонса Войс-царя не найден на сервере {guild.name}")
            return

        try:
            await channel.send(self._build_announcement(new_member, old_member, seconds))
        except discord.Forbidden:
            logger.error(f"Нет прав отправлять анонс Войс-царя в канал {channel.id}")
        except discord.HTTPException as e:
            logger.error(f"Ошибка Discord API при отправке анонса Войс-царя: {e}")

    async def _clear_voice_king_role(self, role: discord.Role, reason: str) -> int:
        """Снять роль Войс-царя со всех текущих держателей."""
        removed = 0
        for holder in self._get_current_role_holders(role.guild, role):
            try:
                await holder.remove_roles(role, reason=reason)
                removed += 1
            except (discord.Forbidden, discord.HTTPException) as e:
                logger.error(f"Не удалось снять роль Войс-царя у {holder.id}: {e}")

        await self._sync_role_name(role, None)
        return removed

    async def sync_guild_voice_king(self, guild: discord.Guild) -> tuple[int, int, int]:
        """Синхронизировать роль Войс-царя на сервере."""
        role = await self.ensure_voice_king_role(guild)
        if role is None:
            return 0, 0, 1

        if not guild.chunked:
            await guild.chunk()

        now = datetime.now()
        live_top = []

        for member in self._iter_live_voice_members(guild):
            seconds = await self._get_live_weekly_seconds(member, now)
            live_top.append((member, seconds))

        live_top.sort(key=lambda item: (-item[1], item[0].display_name.casefold(), item[0].id))

        leader_source = "voice"
        leader_candidates = live_top
        if not leader_candidates or leader_candidates[0][1] < config.VOICE_KING_MIN_SECONDS:
            leader_source = "online"
            leader_candidates = await self._get_weekly_top_members(guild, online_only=True)

        if not leader_candidates or leader_candidates[0][1] < config.VOICE_KING_MIN_SECONDS:
            leader_source = "weekly"
            leader_candidates = await self._get_weekly_top_members(guild)

        if not leader_candidates or leader_candidates[0][1] < config.VOICE_KING_MIN_SECONDS:
            removed = await self._clear_voice_king_role(role, "Нет недельного Войс-царя")
            return 0, removed, 0

        leader, leader_seconds = leader_candidates[0]
        has_top_tie = len(leader_candidates) > 1 and leader_candidates[1][1] == leader_seconds

        await self._sync_role_name(role, leader_seconds)
        if leader_source == "online":
            logger.info(
                f"Активных кандидатов в войсе нет; Войс-царём выбран онлайн-лидер недели "
                f"{leader.display_name} ({leader.id})"
            )
        elif leader_source == "weekly":
            logger.info(
                f"Активных и онлайн-кандидатов нет; Войс-царём выбран общий недельный лидер "
                f"{leader.display_name} ({leader.id})"
            )
        if has_top_tie:
            logger.info(
                f"Ничья Войс-царя на {format_time_seconds(leader_seconds)}; "
                f"по алфавиту выбран {leader.display_name} ({leader.id})"
            )

        holders = self._get_current_role_holders(guild, role)
        old_holder = next((member for member in holders if member.id != leader.id), None)
        changed = 0
        errors = 0

        for holder in holders:
            if holder.id == leader.id:
                continue
            try:
                await holder.remove_roles(role, reason="Войс-царь был обогнан")
                changed += 1
            except (discord.Forbidden, discord.HTTPException) as e:
                logger.error(f"Не удалось снять роль Войс-царя у {holder.id}: {e}")
                errors += 1

        had_role = role in leader.roles
        if not had_role:
            try:
                await leader.add_roles(role, reason="Недельный лидер по времени в голосовых каналах")
                changed += 1
            except (discord.Forbidden, discord.HTTPException) as e:
                logger.error(f"Не удалось выдать роль Войс-царя пользователю {leader.id}: {e}")
                errors += 1

        previous_announced_id = self.last_announced_leaders.get(guild.id)
        if previous_announced_id != leader.id and (old_holder or not had_role):
            await self._announce_new_king(guild, leader, old_holder, leader_seconds)
            self.last_announced_leaders[guild.id] = leader.id

        return len(leader_candidates), changed, errors

    @tasks.loop(seconds=config.VOICE_KING_SYNC_INTERVAL_SECONDS)
    async def sync_voice_king_loop(self):
        """Периодическая синхронизация Войс-царя."""
        for guild in self._get_target_guilds():
            try:
                checked, changed, errors = await self.sync_guild_voice_king(guild)
                if changed or errors:
                    logger.info(
                        f"Синхронизация {config.VOICE_KING_ROLE_NAME}: "
                        f"проверено {checked}, изменений {changed}, ошибок {errors}"
                    )
            except Exception as e:
                logger.error(f"Ошибка синхронизации Войс-царя на сервере {guild.name}: {e}", exc_info=True)

    @sync_voice_king_loop.before_loop
    async def before_sync_voice_king_loop(self):
        await self.bot.wait_until_ready()
        logger.info("Периодическая синхронизация Войс-царя готова к запуску")

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """Быстро пересобрать Войс-царя при входе/выходе недельного лидера в сеть."""
        if after.bot or before.status == after.status:
            return

        if config.GUILD_ID and after.guild.id != config.GUILD_ID:
            return

        try:
            await self.sync_guild_voice_king(after.guild)
        except Exception as e:
            logger.error(f"Ошибка синхронизации Войс-царя при смене онлайн-статуса {after.id}: {e}", exc_info=True)

    @app_commands.command(name="voice-king", description="Показать текущего Войс-царя и недельный топ войса")
    async def voice_king_command(self, interaction: discord.Interaction):
        """Показать текущего Войс-царя и недельный топ."""
        if not interaction.guild:
            await interaction.response.send_message("❌ Команда доступна только на сервере.", ephemeral=True)
            return

        top = await self.db.get_top_weekly_voice(10)
        if not top:
            await interaction.response.send_message("🎙 Пока никто не набрал время в войсе на этой неделе.", ephemeral=True)
            return

        lines = []
        for index, (user_id, seconds) in enumerate(top, 1):
            member = interaction.guild.get_member(user_id)
            name = member.mention if member else f"<@{user_id}>"
            prefix = "👑" if index == 1 else f"{index}."
            lines.append(f"{prefix} {name} — `{format_time_seconds(seconds)}`")

        embed = discord.Embed(
            title="🎙 Войс-царь недели",
            description="\n".join(lines),
            color=discord.Color(config.VOICE_KING_ROLE_COLOR),
        )
        embed.set_footer(text="Трон держится только до тех пор, пока тебя не обогнали.")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Функция для загрузки кога."""
    await bot.add_cog(VoiceKingCog(bot, bot.db))
