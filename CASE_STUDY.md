# CyberKotleta Core — Engineering Case Study

## Context

CyberKotleta Core was built for a live Discord community that needed practical automation around roles, activity tracking, reputation, and member engagement.

The goal was not to build a generic tutorial bot. The goal was to solve real community-management problems with a compact, maintainable Python system.

## Problem

Manual Discord role management does not scale well:

- custom roles require validation and permission-safe assignment;
- divider roles drift when users gain or lose roles;
- voice-channel activity is hard to measure reliably;
- reputation and levels need persistence;
- server-tag and voice-presence roles need ongoing synchronization.

## Solution

The bot is split into focused cogs:

- `custom_roles` handles user-created roles and divider-role automation;
- `stats_voice`, `stats_messages`, and `stats_commands` track activity;
- `levels` turns activity into XP and leaderboards;
- `reputation` rewards positive interactions;
- `server_tag_role` syncs rewards based on Discord `primary_guild`;
- `voice_presence_role` reflects live voice-channel presence.

## Engineering Decisions

- **Async Discord events:** real-time behavior is built around gateway events.
- **Periodic reconciliation:** scheduled tasks repair missed events and role drift.
- **SQLite persistence:** lightweight database fits the scale and deployment model.
- **Env-based config:** secrets and server-specific IDs stay out of public code.
- **Cog separation:** each feature has clear ownership and can be tested or changed independently.
- **Public repo hygiene:** runtime artifacts are excluded before publishing.

## AI-Assisted Workflow

This is a vibe coding project in the disciplined sense:

1. AI accelerates implementation and iteration.
2. Human review defines feature boundaries and safety constraints.
3. Logs and runtime behavior drive fixes.
4. The final repository is sanitized and documented for external review.

The result is not “prompt output.” It is a shipped system with production constraints.

## What This Demonstrates

- Practical API integration with Discord.
- Async Python programming.
- Database-backed state management.
- Role and permission safety.
- Operational thinking: logs, background jobs, restart recovery.
- Security awareness: secret cleanup, `.env`, `.gitignore`, CI.
- Ability to ship useful automation quickly without abandoning maintainability.

## Next Improvements

- Add automated tests around color parsing and database methods.
- Add rotating log handlers.
- Add Docker deployment.
- Add backup automation for SQLite.
- Add richer analytics windows for weekly/monthly stats.
