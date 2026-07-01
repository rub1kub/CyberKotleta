"""
Привязка Minecraft-ника к Discord-пользователю и выдача whitelist через RCON.

Пользователь отправляет Minecraft-ник в выделенный канал. Бот добавляет ник
на сервер командой RCON, сохраняет привязку и меняет Discord-ник на Minecraft-ник.
"""

from __future__ import annotations

import asyncio
import logging
import re
import socket
import struct
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import config
from db.database import Database

logger = logging.getLogger(__name__)

MINECRAFT_NICK_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,16}$")
NO_MENTIONS = discord.AllowedMentions.none()
MAX_RCON_PACKET_SIZE = 1_048_576
RCON_AUTH_TYPE = 3
RCON_COMMAND_TYPE = 2
RCON_AUTH_REQUEST_ID = 67
RCON_COMMAND_REQUEST_ID = 68
RCON_COMMAND_FAILURE_MARKERS = (
    "Unknown or incomplete command",
    "Unknown command",
    "Incorrect argument",
    "No such command",
)


class RconError(Exception):
    """Ошибка выполнения RCON-команды."""


class RconAuthError(RconError):
    """Ошибка авторизации RCON."""


def _read_exact(connection: socket.socket, byte_count: int) -> bytes:
    chunks = []
    remaining = byte_count

    while remaining:
        chunk = connection.recv(remaining)
        if not chunk:
            raise RconError("RCON-соединение закрыто сервером")
        chunks.append(chunk)
        remaining -= len(chunk)

    return b"".join(chunks)


def _send_rcon_packet(
    connection: socket.socket,
    request_id: int,
    request_type: int,
    payload: str,
) -> None:
    payload_bytes = payload.encode("utf-8")
    body = struct.pack("<ii", request_id, request_type) + payload_bytes + b"\x00\x00"
    connection.sendall(struct.pack("<i", len(body)) + body)


def _receive_rcon_packet(connection: socket.socket) -> tuple[int, int, str]:
    packet_length = struct.unpack("<i", _read_exact(connection, 4))[0]
    if packet_length < 10 or packet_length > MAX_RCON_PACKET_SIZE:
        raise RconError(f"Некорректный размер RCON-пакета: {packet_length}")

    packet = _read_exact(connection, packet_length)
    request_id, response_type = struct.unpack("<ii", packet[:8])
    payload = packet[8:-2].decode("utf-8", errors="replace")
    return request_id, response_type, payload


def run_rcon_command(
    host: str,
    port: int,
    password: str,
    command: str,
    timeout_seconds: float,
) -> str:
    """Выполнить одну RCON-команду и вернуть текстовый ответ сервера."""
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds) as connection:
            connection.settimeout(timeout_seconds)

            _send_rcon_packet(connection, RCON_AUTH_REQUEST_ID, RCON_AUTH_TYPE, password)
            auth_request_id, _, _ = _receive_rcon_packet(connection)
            if auth_request_id == -1:
                raise RconAuthError("RCON отклонил пароль")

            _send_rcon_packet(connection, RCON_COMMAND_REQUEST_ID, RCON_COMMAND_TYPE, command)
            response_request_id, _, response_payload = _receive_rcon_packet(connection)
            if response_request_id not in {RCON_COMMAND_REQUEST_ID, RCON_AUTH_REQUEST_ID}:
                raise RconError(f"Неожиданный RCON request_id: {response_request_id}")

            return response_payload
    except socket.timeout as error:
        raise RconError("RCON не ответил вовремя") from error
    except OSError as error:
        raise RconError(f"Ошибка подключения к RCON: {error}") from error


class MinecraftWhitelistCog(commands.Cog):
    """Ког для Minecraft whitelist через RCON."""

    def __init__(self, bot: commands.Bot, db: Database):
        self.bot = bot
        self.db = db
        self._lock = asyncio.Lock()

    def _is_whitelist_channel(self, channel: discord.abc.GuildChannel) -> bool:
        return bool(config.MINECRAFT_WHITELIST_CHANNEL_ID) and channel.id == config.MINECRAFT_WHITELIST_CHANNEL_ID

    def _is_configured(self) -> bool:
        return bool(
            config.MINECRAFT_WHITELIST_CHANNEL_ID
            and config.MINECRAFT_RCON_HOST
            and config.MINECRAFT_RCON_PORT
            and config.MINECRAFT_RCON_PASSWORD
        )

    def _validate_nick(self, minecraft_nick: str) -> Optional[str]:
        if not MINECRAFT_NICK_PATTERN.fullmatch(minecraft_nick):
            return "Ник должен быть 3-16 символов: английские буквы, цифры и `_`."
        return None

    def _format_command(self, template: str, minecraft_nick: str) -> str:
        try:
            return template.format(nick=minecraft_nick)
        except KeyError as error:
            raise RconError(f"В RCON-шаблоне нет поддерживаемого плейсхолдера: {error}") from error

    async def _run_rcon_template(self, template: str, minecraft_nick: str) -> str:
        command = self._format_command(template, minecraft_nick)
        response = await asyncio.to_thread(
            run_rcon_command,
            config.MINECRAFT_RCON_HOST,
            config.MINECRAFT_RCON_PORT,
            config.MINECRAFT_RCON_PASSWORD,
            command,
            config.MINECRAFT_RCON_TIMEOUT_SECONDS,
        )
        if any(marker.lower() in response.lower() for marker in RCON_COMMAND_FAILURE_MARKERS):
            raise RconError("RCON вернул ошибку выполнения команды")
        return response

    async def _reply_to_message(self, message: discord.Message, content: str) -> None:
        try:
            await message.reply(content, mention_author=False, allowed_mentions=NO_MENTIONS)
        except discord.HTTPException as error:
            logger.warning(f"Не удалось ответить на сообщение {message.id}: {error}")

    async def _set_member_nickname(self, member: discord.Member, minecraft_nick: str) -> Optional[str]:
        if member.nick == minecraft_nick:
            return None

        try:
            await member.edit(nick=minecraft_nick, reason="Привязка Minecraft-ника")
            return None
        except discord.Forbidden:
            logger.warning(f"Нет прав изменить ник пользователя {member.id} на {minecraft_nick}")
            return "Discord-ник не изменён: у бота не хватает прав для этого участника."
        except discord.HTTPException as error:
            logger.warning(f"Discord API не изменил ник пользователя {member.id}: {error}")
            return "Discord-ник не изменён из-за ошибки Discord API."

    async def _restore_member_nickname(self, member: discord.Member, link: dict) -> Optional[str]:
        minecraft_nick = link["minecraft_nick"]
        if member.nick != minecraft_nick:
            return None

        try:
            await member.edit(nick=link["discord_nick_before"], reason="Отвязка Minecraft-ника")
            return None
        except discord.Forbidden:
            logger.warning(f"Нет прав восстановить ник пользователя {member.id}")
            return "Discord-ник не восстановлен: у бота не хватает прав."
        except discord.HTTPException as error:
            logger.warning(f"Discord API не восстановил ник пользователя {member.id}: {error}")
            return "Discord-ник не восстановлен из-за ошибки Discord API."

    async def _link_member(self, member: discord.Member, minecraft_nick: str) -> tuple[bool, str]:
        minecraft_nick = minecraft_nick.strip()
        validation_error = self._validate_nick(minecraft_nick)
        if validation_error:
            return False, f"❌ {validation_error}"

        if member.bot:
            return False, "❌ Ботам Minecraft-ники не привязываются."

        if not self._is_configured():
            return False, "❌ Minecraft whitelist сейчас не настроен. Админу нужно проверить `.env`."

        async with self._lock:
            existing_link = await self.db.get_minecraft_link(member.id)
            if existing_link:
                return (
                    False,
                    f"❌ У тебя уже привязан `{existing_link['minecraft_nick']}`. "
                    "Сначала используй `/mc-unlink`, потом привяжи новый ник.",
                )

            owner_id = await self.db.get_minecraft_link_owner(minecraft_nick)
            if owner_id and owner_id != member.id:
                return False, "❌ Этот Minecraft-ник уже привязан другим участником."

            try:
                response = await self._run_rcon_template(config.MINECRAFT_RCON_ADD_COMMAND, minecraft_nick)
                logger.info(f"RCON add выполнен для пользователя {member.id}, ник {minecraft_nick}: {response[:200]}")
            except RconAuthError as error:
                logger.error(f"RCON auth failed при привязке ника {minecraft_nick} для пользователя {member.id}: {error}")
                return False, "❌ RCON не принял пароль. Whitelist не изменён."
            except RconError as error:
                logger.error(f"RCON add failed для ника {minecraft_nick}, пользователь {member.id}: {error}")
                return False, "❌ Сервер Minecraft сейчас не принял команду whitelist. Попробуй позже."

            try:
                await self.db.set_minecraft_link(member.id, minecraft_nick, member.nick)
            except Exception as error:
                logger.error(f"Не удалось сохранить Minecraft-привязку {minecraft_nick} для {member.id}: {error}", exc_info=True)
                try:
                    await self._run_rcon_template(config.MINECRAFT_RCON_REMOVE_COMMAND, minecraft_nick)
                except RconError as rollback_error:
                    logger.error(f"RCON rollback failed для ника {minecraft_nick}: {rollback_error}")
                return False, "❌ Ник добавился в whitelist, но бот не смог сохранить привязку. Напиши админу."

        nickname_warning = await self._set_member_nickname(member, minecraft_nick)
        result = f"✅ `{minecraft_nick}` привязан и добавлен в whitelist."
        if nickname_warning:
            result = f"{result}\n⚠️ {nickname_warning}"
        return True, result

    async def _unlink_member(self, member: discord.Member, force: bool = False) -> tuple[bool, str]:
        if not self._is_configured() and not force:
            return False, "❌ Minecraft whitelist сейчас не настроен. Админу нужно проверить `.env`."

        async with self._lock:
            link = await self.db.get_minecraft_link(member.id)
            if not link:
                return False, "❌ У тебя нет привязанного Minecraft-ника."

            minecraft_nick = link["minecraft_nick"]
            if not force:
                try:
                    response = await self._run_rcon_template(config.MINECRAFT_RCON_REMOVE_COMMAND, minecraft_nick)
                    logger.info(f"RCON remove выполнен для пользователя {member.id}, ник {minecraft_nick}: {response[:200]}")
                except RconAuthError as error:
                    logger.error(f"RCON auth failed при отвязке ника {minecraft_nick} для пользователя {member.id}: {error}")
                    return False, "❌ RCON не принял пароль. Привязка не снята."
                except RconError as error:
                    logger.error(f"RCON remove failed для ника {minecraft_nick}, пользователь {member.id}: {error}")
                    return False, "❌ Сервер Minecraft сейчас не принял команду удаления. Попробуй позже."

            await self.db.remove_minecraft_link(member.id)

        nickname_warning = await self._restore_member_nickname(member, link)
        result = f"✅ `{minecraft_nick}` отвязан."
        if force:
            result = f"{result}\n⚠️ Force-режим не отправлял RCON remove."
        if nickname_warning:
            result = f"{result}\n⚠️ {nickname_warning}"
        return True, result

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Обработать Minecraft-ник в whitelist-канале."""
        if message.author.bot or not message.guild:
            return

        if not isinstance(message.channel, discord.abc.GuildChannel):
            return

        if not self._is_whitelist_channel(message.channel):
            return

        if not isinstance(message.author, discord.Member):
            return

        minecraft_nick = message.content.strip()
        success, response = await self._link_member(message.author, minecraft_nick)
        if not success and self._validate_nick(minecraft_nick):
            response = (
                "❌ Тут нужен только Minecraft-ник одним сообщением: "
                "3-16 символов, английские буквы, цифры и `_`."
            )

        await self._reply_to_message(message, response)

    @app_commands.command(name="mc-link", description="Привязать Minecraft-ник и добавить его в whitelist")
    @app_commands.describe(nick="Minecraft-ник: 3-16 символов, английские буквы, цифры и нижнее подчёркивание")
    async def mc_link(self, interaction: discord.Interaction, nick: str):
        """Slash-команда для привязки Minecraft-ника."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Команда доступна только на сервере.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        _, response = await self._link_member(interaction.user, nick)
        await interaction.followup.send(response, ephemeral=True, allowed_mentions=NO_MENTIONS)

    @app_commands.command(name="mc-unlink", description="Отвязать свой Minecraft-ник и убрать его из whitelist")
    async def mc_unlink(self, interaction: discord.Interaction):
        """Отвязать свой Minecraft-ник."""
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ Команда доступна только на сервере.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        _, response = await self._unlink_member(interaction.user)
        await interaction.followup.send(response, ephemeral=True, allowed_mentions=NO_MENTIONS)

    @app_commands.command(name="mc-unlink-user", description="Админ: отвязать Minecraft-ник пользователя")
    @app_commands.describe(
        member="Пользователь, у которого нужно снять привязку",
        force="Снять привязку только в базе, без RCON remove",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def mc_unlink_user(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        force: bool = False,
    ):
        """Админская отвязка Minecraft-ника."""
        if not interaction.guild:
            await interaction.response.send_message("❌ Команда доступна только на сервере.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        _, response = await self._unlink_member(member, force=force)
        await interaction.followup.send(response, ephemeral=True, allowed_mentions=NO_MENTIONS)


async def setup(bot: commands.Bot):
    """Функция для загрузки кога."""
    await bot.add_cog(MinecraftWhitelistCog(bot, bot.db))
