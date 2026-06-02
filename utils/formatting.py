"""
Утилиты для форматирования данных и создания embed'ов.
"""

import discord
from typing import Optional, Callable
from datetime import datetime, timedelta


def format_time_seconds(seconds: int) -> str:
    """
    Форматировать время в секундах в читаемый формат.
    
    Формат: "Xч Yм Zс" или "Yм Zс" или "Zс"
    
    Args:
        seconds: Время в секундах
    
    Returns:
        Отформатированная строка
    """
    if seconds < 0:
        return "0с"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}ч")
    if minutes > 0:
        parts.append(f"{minutes}м")
    if secs > 0 or not parts:
        parts.append(f"{secs}с")
    
    return " ".join(parts)


def format_time_hours_minutes(seconds: int) -> str:
    """
    Форматировать время в формате "ЧЧ:ММ:СС".
    
    Args:
        seconds: Время в секундах
    
    Returns:
        Отформатированная строка "ЧЧ:ММ:СС"
    """
    if seconds < 0:
        return "00:00:00"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def create_stats_embed(
    user: discord.Member,
    voice_seconds: int,
    messages: int,
    commands: int,
    title: str = "Статистика"
) -> discord.Embed:
    """
    Создать embed со статистикой пользователя.
    
    Args:
        user: Пользователь Discord
        voice_seconds: Время в голосовых каналах (секунды)
        messages: Количество сообщений
        commands: Количество команд
        title: Заголовок embed'а
    
    Returns:
        Объект discord.Embed
    """
    embed = discord.Embed(
        title=title,
        color=user.color if user.color.value != 0 else discord.Color.blue()
    )
    
    embed.set_author(name=str(user), icon_url=user.display_avatar.url)
    
    embed.add_field(
        name="🎤 Время в голосовых каналах",
        value=format_time_seconds(voice_seconds),
        inline=True
    )
    
    embed.add_field(
        name="💬 Сообщений",
        value=f"{messages:,}",
        inline=True
    )
    
    embed.add_field(
        name="⚡ Команд использовано",
        value=f"{commands:,}",
        inline=True
    )
    
    embed.set_footer(text=f"ID: {user.id}")
    embed.timestamp = datetime.now()
    
    return embed


def create_top_embed(
    title: str,
    description: str,
    entries: list,
    guild: discord.Guild,
    value_formatter: Callable = str
) -> discord.Embed:
    """
    Создать embed с топ-рейтингом.
    
    Args:
        title: Заголовок embed'а
        description: Описание
        entries: Список кортежей (user_id, value) или (user_id, value1, value2, ...)
        guild: Сервер Discord
        value_formatter: Функция для форматирования значения
    
    Returns:
        Объект discord.Embed
    """
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.gold()
    )
    
    if not entries:
        embed.add_field(
            name="Пусто",
            value="Пока нет данных для отображения",
            inline=False
        )
        return embed
    
    # Формируем строку с рейтингом
    ranking_text = []
    for idx, entry in enumerate(entries, 1):  # Используем все переданные entries
        user_id = entry[0]
        member = guild.get_member(user_id)
        
        if member:
            username = member.display_name
        else:
            username = f"<@{user_id}>"
        
        # Форматируем значение
        if len(entry) == 2:
            value = value_formatter(entry[1])
        else:
            # Для комбинированного рейтинга может быть несколько значений
            value = value_formatter(entry[1:])
        
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
        ranking_text.append(f"{medal} **{username}** — {value}")
    
    embed.add_field(
        name="Рейтинг",
        value="\n".join(ranking_text) if ranking_text else "Нет данных",
        inline=False
    )
    
    embed.set_footer(text=f"Всего участников: {len(entries)}")
    embed.timestamp = datetime.now()
    
    return embed


def format_combined_value(values: tuple) -> str:
    """
    Форматировать значение для комбинированного рейтинга.
    
    Args:
        values: Кортеж (voice_seconds, messages) или (voice_seconds, messages, score)
    
    Returns:
        Отформатированная строка
    """
    if len(values) >= 3:
        # Если есть готовый score
        return f"{values[2]:.1f} баллов"
    elif len(values) == 2:
        voice_seconds, messages = values
        return f"{format_time_seconds(voice_seconds)}, {messages:,} сообщений"
    else:
        return str(values[0])

