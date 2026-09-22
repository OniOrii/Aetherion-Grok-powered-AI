# Changelog

All notable changes to **Aetherion** are documented in this file. This is the permanent record.

**Rule (standing, 2026-09-13):** every feature, command, persona change, voice change, or removal that lands on `main` is added here in the same commit or immediately after, with a calendar date (`YYYY-MM-DD`). Do not skip the changelog. Do not leave new work only in commit messages.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Older packaged history stays under version headings. Aetherion work from September 2026 onward is grouped by date.

## [Unreleased]

_Nothing waiting. New work is dated the day it ships._

## [2026-09-21]

### Added

- **Rotating status:** Aetherion cycles the profile status every **90s** (The Cosmos, Hunt, the rift, poker, the stars, Crown Rift, God of AI!). `/status` with text pins one line and stops the cycle. `/status rotate:True` turns rotation back on. `/status` with no text shows the current line. Ready no longer overwrites a saved presence with a hard-coded Cosmos watch.
- **No DMs:** Aetherion ignores private messages and slash commands used in DMs. It replies that it only works in a server and does not call Grok. Server chat and server slashes are unchanged.
- **Server logs (`/logs`, Administrators):** Carl-style event embeds in a channel you pick. Joins, leaves, kicks, bans, timeouts, nick/roles, voice, message delete/edit/purge, invites, channels, roles, emoji, and server settings. No Grok calls. Defaults cover the common events; menus toggle the rest.

### Fixed

- **Empty log channel:** `/logs` now posts a test embed when you set the channel, and the setup menu has **Send test**. Missing View / Send / Embed Links is reported instead of failing silently. Message events in the log channel itself are no longer swallowed. Listeners attach once and stay attached.

### Changed

- **`/ping`:** gold embed now shows Discord gateway heartbeat ms, this slash command's round-trip, a short Excellent/Good/Okay/Slow label, server count, this server's name, and how many voice connections are up.
- **Log avatars:** person logs (join, leave, kick, ban, timeout, nick, roles, voice, message delete/edit, invites) show that user's Discord avatar as the embed thumbnail.
