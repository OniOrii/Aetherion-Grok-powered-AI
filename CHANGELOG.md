# Changelog

All notable changes to **Aetherion** are documented in this file. This is the permanent record.

**Rule (standing, 2026-09-13):** every feature, command, persona change, voice change, or removal that lands on `main` is added here in the same commit or immediately after, with a calendar date (`YYYY-MM-DD`). Do not skip the changelog. Do not leave new work only in commit messages.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Older packaged history stays under version headings. Aetherion work from September 2026 onward is grouped by date.

## [Unreleased]

_Nothing waiting. New work is dated the day it ships._

## [2026-09-17]

### Changed

- **Hunt slash condensation (Ori only):** 19 Hunt slashes folded to **7** roots so the loop stays one tap. Kept `/hunt` `/zoo` `/team` `/battle` `/raid` `/inv` `/weapon`. `/zoo` actions cover sell / sacrifice / rename / checklist / bestiary. `/inv` actions cover use / equip / salvage; **Lootbox** and **Crate** buttons sit on the inventory embed. `/weapons` and `/dex` dropped (`/weapon` already showed the board; bestiary is a `/zoo` action). Removed leaf commands stay available through those options. `/help` and the README match. Game/voice slashes unchanged.

### Fixed

- **`/daily` Hunt supplies (Ori):** claiming the coin drip now also grants the Hunt daily pack that already existed in save code — **5** lootboxes, **5** weapon crates, and **1** raid ticket, once per day. Running `/daily` again after coins were already claimed still delivers Hunt supplies if they were missed. Non-Ori wallets stay coins-only. `/help` Coins + Hunt pages and the README match.
