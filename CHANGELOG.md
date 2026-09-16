# Changelog

All notable changes to **Aetherion** are documented in this file. This is the permanent record.

**Rule (standing, 2026-09-13):** every feature, command, persona change, voice change, or removal that lands on `main` is added here in the same commit or immediately after, with a calendar date (`YYYY-MM-DD`). Do not skip the changelog. Do not leave new work only in commit messages.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Older packaged history stays under version headings. Aetherion work from September 2026 onward is grouped by date.

## [Unreleased]

_Nothing waiting. New work is dated the day it ships._

## [2026-09-16]

### Added

- **Aetherion Hunt Test 2 (Ori only):** thirty original weapons, weapon crates, lootboxes, and hunting/lucky/empower gems. `/inv`, `/lootbox`, `/crate`, `/use`, `/equip`. Hunt lootboxes drop at 5% (max 3/day). First battle win drops a crate (then 5%, max 3). Gems change hunt yield. Weapons add ATK and a strike/cleave/mend style. `/inv` uses the OwO inventory header (`050` lootbox, `100` crate). `/lootbox` uses the two-line gem reveal. Pet level cap is 50.
- **Aetherion Hunt Test 3:** `/battle` posts a 3v3 board image and edits the same message each turn. `/use hunting|lucky|empower` activates lootbox gems onto hunts (not onto pets). Hunt lootboxes drop at 5% (max 3/day). `/daily` grants Ori 5 lootboxes and 5 crates. `/sell` accepts a rarity or all. `/lootbox` can open many at once. `/weapon`, `/sacrifice` (essence), `/rename`, and `/checklist` match the OwO hunt loop. Huntbot upgrades stay later.
