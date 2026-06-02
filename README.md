# CyberKotleta Core

Discord-бот для комьюнити-сервера CyberKotleta: кастомные роли, автоматические разделители, статистика активности, уровни, репутация и динамические роли за присутствие в войсе или отображаемый тег сервера.

## Возможности

- **Кастомные роли** — пользователи создают одну персональную роль с названием и цветом.
- **Разделительные роли** — бот автоматически выдаёт роли-разделители по позициям ролей участника.
- **Статистика активности** — сообщения, команды и время в голосовых каналах.
- **Уровни и опыт** — опыт начисляется за сообщения, команды и голосовую активность.
- **Репутация** — начисление за ответы `+`, `+rep`/`+реп` и реакции лайка.
- **Server tag role** — роль `Six Seven 67` для пользователей, которые отображают тег сервера.
- **Voice presence role** — роль `Сейчас в войсе` для пользователей, которые прямо сейчас находятся в голосовом канале.

## Стек

- Python 3.12+
- `discord.py`
- `aiosqlite`
- SQLite

## Быстрый старт

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Заполните `.env`, затем запустите:

```bash
python main.py
```

## Конфигурация

Все чувствительные значения читаются из переменных окружения или локального `.env`.

Минимально нужны:

```env
DISCORD_TOKEN=replace_with_discord_bot_token
CLIENT_ID=0
CLIENT_SECRET=replace_with_discord_client_secret
GUILD_ID=0
CHANNEL_ID_CUSTOM_ROLES=0
```

Для разделительных ролей заполните:

```env
ROLE_DIVIDER_CUSTOM_ID=0
ROLE_DIVIDER_MEDALS_ID=0
ROLE_DIVIDER_MENTIONABLES_ID=0
ROLE_DIVIDER_CLANS_ID=0
ROLE_DIVIDER_OTHER_ID=0
```

`.env` не коммитится. Для публичного репозитория используйте только `.env.example`.

## Discord permissions

Боту нужны:

- Manage Roles
- Read Messages/View Channels
- Send Messages
- Use Slash Commands
- Server Members Intent
- Message Content Intent
- Voice States Intent

Роль бота должна находиться выше ролей, которые он создаёт, двигает, выдаёт или снимает.

## Команды

### Кастомные роли

- `/role create` — открыть форму создания кастомной роли.
- `/role rename name:<name>` — переименовать свою роль.
- `/role color color:<hex|preset>` — изменить цвет своей роли.
- `/role delete` — удалить свою кастомную роль.
- `/role setup` — отправить сообщение с кнопкой создания роли.

### Статистика

- `/stats me` — личная статистика.
- `/stats user user:@member` — статистика пользователя.
- `/stats top-voice limit:<1-20>` — топ по времени в войсе.
- `/stats top-messages limit:<1-20>` — топ по сообщениям.
- `/stats top-combined limit:<1-20>` — комбинированный рейтинг.

### Уровни и репутация

- `/level [user]` — уровень и опыт пользователя.
- `/leaderboard [limit]` — топ по уровням.
- `/rep user [user]` — репутация пользователя.
- `/rep top [limit]` — топ по репутации.

### Админ-команды

- `/sync-server-tag-role` — ручная синхронизация роли за тег сервера.
- `/move-colored-roles` — переместить цветные роли.
- `/create-colored-roles` — создать и выдать цветные роли.
- `/test-setup` — тестовая проверка slash-команд.

## Роли

### `Six Seven 67`

Роль создаётся автоматически и выдаётся пользователям, у которых `primary_guild` в Discord API указывает на текущий сервер и включено отображение server tag.

Настройки:

```env
SERVER_TAG_ROLE_NAME=Six Seven 67
SERVER_TAG_ROLE_COLOR=16738740
SERVER_TAG_ROLE_HOIST=true
SERVER_TAG_SYNC_INTERVAL_MINUTES=60
```

### `Сейчас в войсе`

Роль создаётся автоматически, выдаётся при входе в голосовой канал и снимается при выходе.

Настройки:

```env
VOICE_PRESENCE_ROLE_NAME=Сейчас в войсе
VOICE_PRESENCE_ROLE_COLOR=3066993
VOICE_PRESENCE_ROLE_HOIST=true
VOICE_PRESENCE_SYNC_INTERVAL_SECONDS=60
```

## База данных

SQLite-файл создаётся автоматически по пути `DATABASE_PATH`.

Основные таблицы:

- `users`
- `custom_roles`
- `voice_stats`
- `messages_stats`
- `commands_stats`
- `user_levels`
- `reputation`
- `reputation_votes`

## Структура

```text
CyberKotleta/
├── cogs/                  # Discord cogs
├── db/                    # SQLite schema and database adapter
├── scripts/               # Maintenance scripts
├── utils/                 # Helpers
├── config.py              # Env-based configuration
├── logging_config.py      # Logging setup
├── main.py                # Bot entrypoint
├── requirements.txt       # Python dependencies
└── README.md
```

## Безопасность перед публикацией

Перед push в GitHub:

- отзовите старые Discord-токены, если они когда-либо были в коде;
- убедитесь, что `.env`, `*.db`, `*.log`, `venv/` и `__pycache__/` не попадают в Git;
- включите GitHub Secret Scanning и Push Protection;
- не коммитьте реальные ID приватных каналов, если не хотите раскрывать структуру сервера.

## Проверка

```bash
python -m py_compile main.py config.py logging_config.py db/database.py cogs/*.py utils/*.py scripts/*.py
```
