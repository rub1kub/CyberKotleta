"""
Утилиты для работы с цветами ролей.

Поддерживает:
- HEX-формат (#ff0000 или ff0000)
- Предустановленные названия цветов (red, blue, neon_pink и т.п.)
"""

import re
from typing import Optional


# Предустановленные цвета
COLOR_PRESETS = {
    "red": 0xFF0000,
    "green": 0x00FF00,
    "blue": 0x0000FF,
    "yellow": 0xFFFF00,
    "orange": 0xFFA500,
    "purple": 0x800080,
    "pink": 0xFFC0CB,
    "cyan": 0x00FFFF,
    "white": 0xFFFFFF,
    "black": 0x000000,
    "gray": 0x808080,
    "grey": 0x808080,
    "neon_pink": 0xFF1493,
    "neon_green": 0x39FF14,
    "neon_blue": 0x00FFFF,
    "neon_yellow": 0xFFFF00,
    "neon_orange": 0xFF4500,
    "dark_red": 0x8B0000,
    "dark_green": 0x006400,
    "dark_blue": 0x00008B,
    "light_blue": 0xADD8E6,
    "light_green": 0x90EE90,
    "light_pink": 0xFFB6C1,
    "gold": 0xFFD700,
    "silver": 0xC0C0C0,
    "bronze": 0xCD7F32,
}


def parse_color(color_input: str) -> Optional[int]:
    """
    Парсинг цвета из строки.
    
    Поддерживает:
    - HEX формат: #ff0000 или ff0000
    - Предустановленные названия: red, blue, neon_pink и т.п.
    
    Args:
        color_input: Строка с цветом (HEX или название пресета)
    
    Returns:
        Цвет как integer (0x000000 - 0xFFFFFF) или None, если невалидный
    
    Raises:
        ValueError: Если цвет не может быть распознан
    """
    if not color_input:
        raise ValueError("Цвет не может быть пустым")
    
    color_input = color_input.strip().lower()
    
    # Проверка на предустановленный цвет
    if color_input in COLOR_PRESETS:
        return COLOR_PRESETS[color_input]
    
    # Проверка на HEX формат
    # Убираем # если есть
    hex_color = color_input.lstrip("#")
    
    # Проверяем, что это валидный HEX (6 символов, только 0-9, a-f)
    if not re.match(r"^[0-9a-f]{6}$", hex_color):
        raise ValueError(
            f"Неверный формат цвета: {color_input}. "
            f"Используйте HEX (#ff0000 или ff0000) или название пресета "
            f"({', '.join(list(COLOR_PRESETS.keys())[:5])}...)"
        )
    
    try:
        return int(hex_color, 16)
    except ValueError:
        raise ValueError(f"Не удалось преобразовать цвет: {color_input}")


def validate_color(color_value: int) -> bool:
    """
    Проверка, что цвет находится в допустимом диапазоне.
    
    Args:
        color_value: Значение цвета
    
    Returns:
        True, если цвет валидный
    """
    return 0 <= color_value <= 0xFFFFFF


def get_color_name(color_value: int) -> Optional[str]:
    """
    Получить название предустановленного цвета по значению.
    
    Args:
        color_value: Значение цвета
    
    Returns:
        Название цвета или None, если не найден
    """
    for name, value in COLOR_PRESETS.items():
        if value == color_value:
            return name
    return None


