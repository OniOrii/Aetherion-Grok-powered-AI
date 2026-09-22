# Changelog

All notable changes to **Aetherion** are documented in this file. This is the permanent record.

**Rule (standing, 2026-09-13):** every feature, command, persona change, voice change, or removal that lands on `main` is added here in the same commit or immediately after, with a calendar date (`YYYY-MM-DD`). Do not skip the changelog. Do not leave new work only in commit messages.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Older packaged history stays under version headings. Aetherion work from September 2026 onward is grouped by date.

## [Unreleased]

_Nothing waiting. New work is dated the day it ships._

## [2026-09-22]

### Removed

- **Aetherion Hunt:** the Ori-only WIP is gone. Dropped `/hunt` `/zoo` `/team` `/battle` `/raid` `/inv` `/weapon` `/givesupply`, Hunt help page, Hunt daily supplies on `/daily`, Hunt settings / `.env` keys, Hunt modules, tests, scripts, and asset packs. Command sync on the next deploy clears those slashes from Discord.

### Added

- **Auto-role (`/autorole`, Administrators):** pick one role; Aetherion gives it as soon as a person joins. Bots are skipped. If Rules Screening is on, the role is applied the moment they accept the rules (Discord will not keep roles on pending members). `/autorole` with no options shows the current role. `/autorole off:True` turns it off. Aetherion needs **Manage Roles**, and its role must sit above the join role. Administrator and managed roles are refused. Welcome banners and `/logs` join events are unchanged.

## [2026-09-21]

### Added

- **Rotating status:** Aetherion cycles a custom status bubble every **90s**. `/status` with text pins one line and stops the cycle. `/status rotate:True` turns rotation back on. `/status` with no text shows the current line. Ready no longer overwrites a saved presence with a hard-coded Cosmos watch.
- **No DMs:** Aetherion ignores private messages and slash commands used in DMs. It replies that it only works in a server and does not call Grok. Server chat and server slashes are unchanged.
- **Server logs (`/logs`, Administrators):** Carl-style event embeds in a channel you pick. Joins, leaves, kicks, bans, timeouts, nick/roles, voice, message delete/edit/purge, invites, channels, roles, emoji, and server settings. No Grok calls. Defaults cover the common events; menus toggle the rest.

### Fixed

- **Empty log channel:** `/logs` now posts a test embed when you set the channel, and the setup menu has **Send test**. Missing View / Send / Embed Links is reported instead of failing silently. Message events in the log channel itself are no longer swallowed. Listeners attach once and stay attached.

### Changed

- **Status bubbles:** rotation is custom-status only. Dropped Watching/Playing/Listening/Competing lines. Cycle is now the 25 Ori lines starting with "I can see you".
- **`/ping`:** gold embed now shows Discord gateway heartbeat ms, this slash command's round-trip, a short Excellent/Good/Okay/Slow label, server count, this server's name, and how many voice connections are up.
- **Log avatars:** person logs (join, leave, kick, ban, timeout, nick, roles, voice, message delete/edit, invites) show that user's Discord avatar as the embed thumbnail.

Older dated history through 2026-09-09 and the 0.2.0 baseline stay in git history from before this Hunt-removal commit.
