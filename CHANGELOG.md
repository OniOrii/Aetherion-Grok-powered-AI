# Changelog

All notable changes to **Aetherion** are documented in this file. This is the permanent record.

**Rule (standing, 2026-09-13):** every feature, command, persona change, voice change, or removal that lands on `main` is added here in the same commit or immediately after, with a calendar date (`YYYY-MM-DD`). Do not skip the changelog. Do not leave new work only in commit messages.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Older packaged history stays under version headings. Aetherion work from September 2026 onward is grouped by date.

## [Unreleased]

_Nothing waiting. New work is dated the day it ships._

## [2026-09-26]

### Added

- **`/highlow`:** Higher or Lower on a 13-rank Aether card. Bet **10–10,000**. The shown card prices Higher and Lower separately (safe calls pay small, thin calls pay more). Same rank misses. Cash out after a hit, or climb up to six calls. Play Again / Change Bet stay on the table. Uses the same Aether Coin hold/settle path as blackjack.

## [2026-09-25]

### Added

- **`/top`:** lifetime activity board for this server. Sort by messages, voice, or level. Uses the same store as the `/profile` Activity page. Shows the top 10 and your rank. Command is registered next to `/profile`.

### Changed

- **`/top` names:** prints the server nick or username as plain text instead of a mention, so the board does not show raw `<@id>` when Discord cannot resolve it. People who left fall back to their Discord username.
- **Activity levels match MEE6:** XP to the next level is `5 * level² + 50 * level + 100`. Stored XP is unchanged, so displayed levels are recalculated on the next `/profile` or `/top`.
- **Voice XP only with company:** sitting alone in a voice channel still counts voice time, but grants no XP. XP starts when a second person is in the channel and stops when you are the last one left.
