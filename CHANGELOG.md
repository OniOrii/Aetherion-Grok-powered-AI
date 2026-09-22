# Changelog

All notable changes to **Aetherion** are documented in this file. This is the permanent record.

**Rule (standing, 2026-09-13):** every feature, command, persona change, voice change, or removal that lands on `main` is added here in the same commit or immediately after, with a calendar date (`YYYY-MM-DD`). Do not skip the changelog. Do not leave new work only in commit messages.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Older packaged history stays under version headings. Aetherion work from September 2026 onward is grouped by date.

## [Unreleased]

_Nothing waiting. New work is dated the day it ships._

## [2026-09-21]

### Added

- **Server logs (`/logs`, Administrators):** Carl-style event embeds in a channel you pick. Joins, leaves, kicks, bans, timeouts, nick/roles, voice, message delete/edit/purge, invites, channels, roles, emoji, and server settings. No Grok calls. Defaults cover the common events; menus toggle the rest.

### Fixed

- **Empty log channel:** `/logs` now posts a test embed when you set the channel, and the setup menu has **Send test**. Missing View / Send / Embed Links is reported instead of failing silently. Message events in the log channel itself are no longer swallowed. Listeners attach once and stay attached.

### Changed

- **`/ping`:** gold embed now shows Discord gateway heartbeat ms, this slash command's round-trip, a short Excellent/Good/Okay/Slow label, server count, this server's name, and how many voice connections are up.
- **Log avatars:** person logs (join, leave, kick, ban, timeout, nick, roles, voice, message delete/edit, invites) show that user's Discord avatar as the embed thumbnail.

## [2026-09-17]

### Changed

- **Ori messenger override:** when Ori tells Aetherion to tell / say / pass a message to someone else, Aetherion delivers it (ping + Ori's words), including vulgar or insulting lines. No more "not passing that along" to the creator. Non-Ori users can still be refused as messengers.

- **Hunt slash condensation (Ori only):** 19 Hunt slashes folded to **7** roots so the loop stays one tap. Kept `/hunt` `/zoo` `/team` `/battle` `/raid` `/inv` `/weapon`. `/zoo` actions cover sell / sacrifice / rename / checklist / bestiary. `/inv` actions cover use / equip / salvage; **Lootbox** and **Crate** buttons sit on the inventory embed. `/weapons` and `/dex` dropped (`/weapon` already showed the board; bestiary is a `/zoo` action). Removed leaf commands stay available through those options. `/help` and the README match. Game/voice slashes unchanged.

### Fixed

- **`/daily` Hunt supplies (Ori):** claiming the coin drip now also grants the Hunt daily pack that already existed in save code — **5** lootboxes, **5** weapon crates, and **1** raid ticket, once per day. Running `/daily` again after coins were already claimed still delivers Hunt supplies if they were missed. Non-Ori wallets stay coins-only. `/help` Coins + Hunt pages and the README match.
