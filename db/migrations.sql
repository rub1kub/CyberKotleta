-- SQL-схема базы данных для бота CyberKotleta Core

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица служебного состояния бота
CREATE TABLE IF NOT EXISTS bot_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица кастомных ролей
CREATE TABLE IF NOT EXISTS custom_roles (
    user_id INTEGER PRIMARY KEY,
    role_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Таблица статистики голосовых каналов
CREATE TABLE IF NOT EXISTS voice_stats (
    user_id INTEGER PRIMARY KEY,
    total_voice_seconds INTEGER DEFAULT 0,
    last_join_ts TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Таблица недельной статистики голосовых каналов
CREATE TABLE IF NOT EXISTS voice_weekly_stats (
    user_id INTEGER NOT NULL,
    week_start TEXT NOT NULL,
    total_voice_seconds INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, week_start),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Таблица статистики сообщений
CREATE TABLE IF NOT EXISTS messages_stats (
    user_id INTEGER PRIMARY KEY,
    total_messages INTEGER DEFAULT 0,
    last_message_ts TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Таблица статистики команд
CREATE TABLE IF NOT EXISTS commands_stats (
    user_id INTEGER PRIMARY KEY,
    total_commands INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Таблица уровней и опыта
CREATE TABLE IF NOT EXISTS user_levels (
    user_id INTEGER PRIMARY KEY,
    level INTEGER NOT NULL DEFAULT 1,
    experience INTEGER NOT NULL DEFAULT 0,
    total_experience INTEGER NOT NULL DEFAULT 0,
    last_message_ts TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Таблица репутации
CREATE TABLE IF NOT EXISTS reputation (
    user_id INTEGER PRIMARY KEY,
    total_reputation INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Таблица голосов репутации
CREATE TABLE IF NOT EXISTS reputation_votes (
    voter_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    vote_type TEXT NOT NULL CHECK(vote_type IN ('reply_plus', 'reply_reputation', 'reaction_like')),
    vote_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (voter_id, message_id, vote_type),
    FOREIGN KEY (voter_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Индексы для ускорения запросов
CREATE INDEX IF NOT EXISTS idx_voice_stats_total ON voice_stats(total_voice_seconds DESC);
CREATE INDEX IF NOT EXISTS idx_voice_weekly_stats_total ON voice_weekly_stats(week_start, total_voice_seconds DESC);
CREATE INDEX IF NOT EXISTS idx_messages_stats_total ON messages_stats(total_messages DESC);
CREATE INDEX IF NOT EXISTS idx_custom_roles_role_id ON custom_roles(role_id);
CREATE INDEX IF NOT EXISTS idx_user_levels_level ON user_levels(level DESC);
CREATE INDEX IF NOT EXISTS idx_user_levels_total_exp ON user_levels(total_experience DESC);
CREATE INDEX IF NOT EXISTS idx_reputation_total ON reputation(total_reputation DESC);
CREATE INDEX IF NOT EXISTS idx_reputation_votes_message ON reputation_votes(message_id);
