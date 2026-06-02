# CyberKotleta Core

Discord-бот для сервера CyberKotleta: кастомные роли, автоматические разделители, статистика активности, уровни, репутация, динамическая роль для участников в войсе и награда за тег сервера.

Это **вайбкодинг-проект с AI-assisted разработкой**: фичи быстро собирались через итерации с ИИ, после чего приводились к нормальному инженерному виду — модульная архитектура, конфигурация через `.env`, защита секретов, SQLite-схема, фоновые задачи и проверка на реальном сервере.

## Коротко о проекте

- **Тип проекта:** рабочий Discord-бот для живого комьюнити.
- **Роль разработки:** solo-разработка с использованием ИИ как ускорителя.
- **Стек:** Python 3.12, `discord.py`, `aiosqlite`, SQLite.
- **Ключевые темы:** Discord API, асинхронные события, фоновые задачи, роли, права, база данных, эксплуатация.
- **Подход:** быстро доставлять фичи, но не оставлять проект в состоянии одноразового скрипта.

Подробный разбор решений: [`CASE_STUDY.md`](CASE_STUDY.md).

## Возможности

- **Кастомные роли** — пользователь создаёт одну персональную роль с выбранным названием и цветом.
- **Автоматические разделители** — бот выдаёт роли-разделители по фактическим позициям ролей участника.
- **Статистика активности** — учёт сообщений, команд и времени в голосовых каналах.
- **Уровни и опыт** — опыт начисляется за сообщения, команды и активность в войсе.
- **Репутация** — начисление за ответы `+`, `+rep` / `+реп` и позитивные реакции.
- **Роль за тег сервера** — `Six Seven 67` для пользователей, которые отображают тег сервера.
- **Роль присутствия в войсе** — `Сейчас в войсе` для пользователей, которые прямо сейчас находятся в голосовом канале.
- **Войс-царь недели** — отбираемый титул для лидера недельного войс-топа с публичными анонсами захвата трона.
- **Админ-инструменты** — ручная синхронизация и служебные команды для обслуживания ролей.

## Инженерные детали

- **Асинхронная архитектура:** обработка gateway events Discord и фоновых задач через `discord.ext.tasks`.
- **Модульность:** каждая крупная функция вынесена в отдельный cog.
- **Хранение состояния:** SQLite + `aiosqlite`.
- **Безопасная конфигурация:** секреты и серверные ID читаются из `.env`, а не хранятся в коде.
- **Самовосстановление:** периодические синхронизации исправляют рассинхрон ролей после рестартов или пропущенных событий.
- **Готовность к публикации:** `.env`, база, логи, venv и cache-файлы исключены из Git.

## Архитектура

```text
Discord Gateway Events
        │
        ▼
CyberKotletaBot в main.py
        │
        ├── cogs/custom_roles.py          # Кастомные роли и разделители
        ├── cogs/stats_voice.py           # Учёт времени в войсе
        ├── cogs/stats_messages.py        # Сообщения и опыт
        ├── cogs/stats_commands.py        # Команды /stats
        ├── cogs/levels.py                # Уровни и leaderboard
        ├── cogs/reputation.py            # Репутация
        ├── cogs/server_tag_role.py       # Роль за тег сервера
        ├── cogs/voice_presence_role.py   # Роль "Сейчас в войсе"
        └── cogs/voice_king.py            # Недельный Войс-царь
        │
        ▼
db/database.py + db/migrations.sql
        │
        ▼
SQLite database
```

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

Для разделительных ролей:

```env
ROLE_DIVIDER_CUSTOM_ID=0
ROLE_DIVIDER_MEDALS_ID=0
ROLE_DIVIDER_MENTIONABLES_ID=0
ROLE_DIVIDER_CLANS_ID=0
ROLE_DIVIDER_OTHER_ID=0
```

Файл `.env` не коммитится. В репозитории лежит только безопасный шаблон `.env.example`.

## Права Discord

Боту нужны:

- Manage Roles
- Read Messages / View Channels
- Send Messages
- Use Slash Commands
- Server Members Intent
- Message Content Intent
- Voice States Intent

Роль бота должна находиться выше всех ролей, которые бот создаёт, перемещает, выдаёт или снимает.

## Команды

### Кастомные роли

- `/role create` — открыть форму создания кастомной роли.
- `/role rename name:<name>` — переименовать свою роль.
- `/role color color:<hex|preset>` — изменить цвет роли.
- `/role delete` — удалить свою кастомную роль.
- `/role setup` — отправить сообщение с кнопкой создания роли.

### Статистика

- `/stats me` — личная статистика.
- `/stats user user:@member` — статистика пользователя.
- `/stats top-voice limit:<1-20>` — топ по времени в войсе.
- `/stats top-messages limit:<1-20>` — топ по сообщениям.
- `/stats top-combined limit:<1-20>` — комбинированный рейтинг активности.
- `/voice-king` — текущий Войс-царь и недельный топ войса.

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

## Динамические роли

### `Six Seven 67`

Роль создаётся автоматически и выдаётся пользователям, у которых `primary_guild` в Discord API указывает на текущий сервер и включено отображение server tag.

```env
SERVER_TAG_ROLE_NAME=Six Seven 67
SERVER_TAG_ROLE_COLOR=16738740
SERVER_TAG_ROLE_HOIST=true
SERVER_TAG_SYNC_INTERVAL_MINUTES=60
```

### `Сейчас в войсе`

Роль создаётся автоматически, выдаётся при входе в голосовой канал и снимается при выходе.

```env
VOICE_PRESENCE_ROLE_NAME=Сейчас в войсе
VOICE_PRESENCE_ROLE_COLOR=3066993
VOICE_PRESENCE_ROLE_HOIST=true
VOICE_PRESENCE_SYNC_INTERVAL_SECONDS=60
```

### `🎙 Войс-царь недели`

Роль выдаётся только одному участнику — лидеру текущей недели по времени в голосовых каналах.
Если другой участник обгоняет лидера, бот снимает роль со старого царя, выдаёт новому и публично объявляет захват трона.
Синхронизация идёт каждую минуту, а название роли обновляется в формате `🎙 Войс-царь недели — 393ч`.
Канал для анонсов задаётся через `VOICE_KING_ANNOUNCE_CHANNEL_ID`.

```env
VOICE_KING_ROLE_NAME=🎙 Войс-царь недели
VOICE_KING_ROLE_COLOR=15844367
VOICE_KING_ROLE_HOIST=true
VOICE_KING_SYNC_INTERVAL_SECONDS=60
VOICE_KING_MIN_SECONDS=1
VOICE_KING_ANNOUNCE_CHANNEL_ID=0
VOICE_KING_TOXIC_ANNOUNCEMENTS=true
VOICE_KING_ANNOUNCE_FIRST_CORONATION=true
```

## База данных

SQLite-файл создаётся автоматически по пути `DATABASE_PATH`.

Основные таблицы:

- `users`
- `custom_roles`
- `voice_stats`
- `voice_weekly_stats`
- `messages_stats`
- `commands_stats`
- `user_levels`
- `reputation`
- `reputation_votes`

## Структура

```text
CyberKotleta/
├── cogs/                  # Discord cogs
├── db/                    # SQLite schema и database adapter
├── scripts/               # Служебные скрипты
├── utils/                 # Утилиты
├── config.py              # Конфигурация через env/.env
├── logging_config.py      # Настройка логирования
├── main.py                # Точка входа
├── requirements.txt       # Python-зависимости
└── README.md
```

## Проверка

```bash
python -m py_compile main.py config.py logging_config.py db/database.py cogs/*.py utils/*.py scripts/*.py
```

## Безопасность

- Секреты не захардкожены в коде.
- `.env`, runtime-база, логи, виртуальное окружение и cache-файлы игнорируются.
- Публичный репозиторий очищен от токенов и приватных runtime-артефактов.
- Старые токены, которые когда-либо попадали в код, нужно отзывать в Discord Developer Portal.

## Про вайбкодинг

В этом проекте вайбкодинг — это не «рандомно нагенерировать код и надеяться, что работает».

Подход такой:

1. быстро собрать рабочую фичу с помощью ИИ;
2. проверить поведение на реальном сервере;
3. исправить архитектуру и edge cases;
4. вынести секреты и runtime-настройки;
5. задокументировать эксплуатацию;
6. пушить изменения в GitHub.

То есть ИИ используется как ускоритель, а ответственность за итоговую систему остаётся инженерной.
