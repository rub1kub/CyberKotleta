# CyberKotleta Core

[![Python checks](https://github.com/rub1kub/CyberKotleta/actions/workflows/python.yml/badge.svg)](https://github.com/rub1kub/CyberKotleta/actions/workflows/python.yml)

Production-minded Discord automation bot for the CyberKotleta community: custom roles, activity stats, levels, reputation, dynamic voice roles, and server-tag rewards.

This is a **vibe coding / AI-assisted engineering project**: the product was built through fast AI-assisted iteration, then hardened with normal engineering practices — modular architecture, environment-based configuration, secret hygiene, CI checks, and production runtime validation.

## Recruiter Snapshot

- **Project type:** real Discord community automation running on a live server.
- **Role:** solo engineer using AI as a force multiplier, not as a replacement for engineering judgment.
- **Stack:** Python 3.12, `discord.py`, async event handling, SQLite, GitHub Actions.
- **What it demonstrates:** API integration, production bot architecture, background jobs, data persistence, permissions handling, security cleanup, and shipping speed.
- **Code style:** small focused modules, cog-based feature separation, explicit configuration, readable operational scripts.

Read the short engineering write-up: [`CASE_STUDY.md`](CASE_STUDY.md).

## Why This Project Matters

Most Discord bots are either toy examples or one-off scripts. CyberKotleta Core is closer to a compact production system:

- it reacts to real-time Discord events;
- manages server roles safely under Discord permission constraints;
- persists activity data in SQLite;
- runs scheduled background synchronization jobs;
- exposes user-facing slash commands;
- separates public source code from private runtime configuration.

For a recruiter or hiring manager, this repo is evidence of practical execution: taking a messy live-server requirement, turning it into working automation, and then preparing it for public review without leaking secrets.

## Core Features

- **Custom roles** — users can create and manage one personal role with a custom name and color.
- **Role dividers** — automatic divider roles based on member role positions.
- **Activity stats** — tracks messages, command usage, and voice-channel time.
- **Levels and XP** — awards XP for messages, commands, and voice activity.
- **Reputation system** — awards reputation from `+`, `+rep` / `+реп`, and positive reactions.
- **Server tag reward** — grants `Six Seven 67` to users displaying the server tag.
- **Voice presence role** — grants `Сейчас в войсе` while a user is currently in a voice channel.
- **Admin sync tools** — manual commands and scripts for role maintenance.

## Engineering Highlights

- **Async-first design:** built around Discord gateway events and `discord.ext.tasks`.
- **Modular architecture:** features are split into cogs under `cogs/`.
- **Persistent data layer:** SQLite schema and async database adapter in `db/`.
- **Safe config model:** secrets and server-specific IDs are read from `.env`, not committed.
- **Operational resilience:** periodic sync jobs repair role drift after missed events or restarts.
- **Public repo hygiene:** runtime DB, logs, tokens, virtualenvs, and cache files are ignored.
- **CI baseline:** GitHub Actions compiles all Python files on every push and PR.

## Architecture

```text
Discord Gateway Events
        │
        ▼
CyberKotletaBot in main.py
        │
        ├── cogs/custom_roles.py          # Custom roles and divider-role automation
        ├── cogs/stats_voice.py           # Voice time tracking
        ├── cogs/stats_messages.py        # Message stats and XP
        ├── cogs/stats_commands.py        # /stats commands
        ├── cogs/levels.py                # Levels and leaderboard
        ├── cogs/reputation.py            # Reputation events and commands
        ├── cogs/server_tag_role.py       # Server-tag reward role
        └── cogs/voice_presence_role.py   # "Currently in voice" role
        │
        ▼
db/database.py + db/migrations.sql
        │
        ▼
SQLite runtime database
```

## Tech Stack

- **Language:** Python 3.12+
- **Discord API:** `discord.py`
- **Database:** SQLite via `aiosqlite`
- **Automation:** `discord.ext.tasks`
- **CI:** GitHub Actions

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env`, then run:

```bash
python main.py
```

## Configuration

All sensitive values are loaded from environment variables or local `.env`.

Required minimum:

```env
DISCORD_TOKEN=replace_with_discord_bot_token
CLIENT_ID=0
CLIENT_SECRET=replace_with_discord_client_secret
GUILD_ID=0
CHANNEL_ID_CUSTOM_ROLES=0
```

Divider roles:

```env
ROLE_DIVIDER_CUSTOM_ID=0
ROLE_DIVIDER_MEDALS_ID=0
ROLE_DIVIDER_MENTIONABLES_ID=0
ROLE_DIVIDER_CLANS_ID=0
ROLE_DIVIDER_OTHER_ID=0
```

`.env` is intentionally ignored by Git. Use `.env.example` as the public template.

## Discord Permissions

The bot needs:

- Manage Roles
- Read Messages / View Channels
- Send Messages
- Use Slash Commands
- Server Members Intent
- Message Content Intent
- Voice States Intent

The bot role must be above every role it creates, moves, assigns, or removes.

## Commands

### Custom Roles

- `/role create` — open a modal for custom role creation.
- `/role rename name:<name>` — rename your custom role.
- `/role color color:<hex|preset>` — change your custom role color.
- `/role delete` — delete your custom role.
- `/role setup` — post the static role-creation message with a button.

### Stats

- `/stats me` — show personal stats.
- `/stats user user:@member` — show another member's stats.
- `/stats top-voice limit:<1-20>` — voice-time leaderboard.
- `/stats top-messages limit:<1-20>` — message-count leaderboard.
- `/stats top-combined limit:<1-20>` — combined activity leaderboard.

### Levels and Reputation

- `/level [user]` — show level and XP.
- `/leaderboard [limit]` — level leaderboard.
- `/rep user [user]` — show reputation.
- `/rep top [limit]` — reputation leaderboard.

### Admin Tools

- `/sync-server-tag-role` — manually sync the server-tag reward role.
- `/move-colored-roles` — move color roles.
- `/create-colored-roles` — create and assign color roles.
- `/test-setup` — test slash-command registration.

## Dynamic Roles

### `Six Seven 67`

Automatically created and assigned to users whose Discord `primary_guild` points to the current server and whose server tag is visible.

```env
SERVER_TAG_ROLE_NAME=Six Seven 67
SERVER_TAG_ROLE_COLOR=16738740
SERVER_TAG_ROLE_HOIST=true
SERVER_TAG_SYNC_INTERVAL_MINUTES=60
```

### `Сейчас в войсе`

Automatically created and assigned while a member is currently in a voice channel. Removed when the member leaves voice.

```env
VOICE_PRESENCE_ROLE_NAME=Сейчас в войсе
VOICE_PRESENCE_ROLE_COLOR=3066993
VOICE_PRESENCE_ROLE_HOIST=true
VOICE_PRESENCE_SYNC_INTERVAL_SECONDS=60
```

## Database

The SQLite database is created automatically at `DATABASE_PATH`.

Main tables:

- `users`
- `custom_roles`
- `voice_stats`
- `messages_stats`
- `commands_stats`
- `user_levels`
- `reputation`
- `reputation_votes`

## Repository Structure

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

## Quality and Security

- Secrets are not hardcoded.
- `.env`, runtime databases, logs, virtualenvs, and cache files are ignored.
- GitHub Actions validates Python syntax.
- Runtime role sync jobs recover from Discord event misses and restarts.
- The public repository is sanitized from live-server secrets.

## Validation

```bash
python -m py_compile main.py config.py logging_config.py db/database.py cogs/*.py utils/*.py scripts/*.py
```

## Note on Vibe Coding

This project intentionally uses the term **vibe coding**, but not as “random prompts until something works.”

The workflow is:

1. use AI to move quickly from idea to working feature;
2. review and correct the architecture manually;
3. separate runtime secrets from public code;
4. add CI and operational documentation;
5. ship, observe logs, and iterate based on real behavior.

That is the practical value: faster delivery without skipping engineering responsibility.
