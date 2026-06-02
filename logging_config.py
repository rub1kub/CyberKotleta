"""
Настройка логирования для бота.

Логи выводятся в консоль с форматированием:
- Временная метка
- Уровень логирования
- Имя модуля
- Сообщение
"""

import logging
import sys
from datetime import datetime


def setup_logging(level: int = logging.INFO) -> None:
    """
    Настройка логирования.
    
    Args:
        level: Уровень логирования (по умолчанию INFO)
    """
    # Формат логов: [YYYY-MM-DD HH:MM:SS] LEVEL | module | message
    log_format = "[%(asctime)s] %(levelname)s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Настройка обработчика для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    
    # Установка уровня для discord.py (чтобы не было лишних сообщений)
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.INFO)


