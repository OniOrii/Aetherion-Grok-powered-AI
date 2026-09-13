# Changelog

All notable changes to **Aetherion** are documented in this file. This is the permanent record.

**Rule (standing, 2026-09-13):** every feature, command, persona change, voice change, or removal that lands on `main` is added here in the same commit or immediately after, with a calendar date (`YYYY-MM-DD`). Do not skip the changelog. Do not leave new work only in commit messages.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Older packaged history stays under version headings. Aetherion work from September 2026 onward is grouped by date.

## [Unreleased]

_Nothing waiting. New work is dated the day it ships._

## [2026-09-13]

### Added

- Exclusive multi-color **reaction roles** (Admin slash setup, anyone can react).
- Fair `/blackjack` against Aetherion (Hit / Stand / Double).
- Play-money **Aether Coins** saved in `data/ai_coins.json` (gitignored runtime data).
  - Every Discord user starts at 500 coins the first time they play or check `/balance`. People who already have a wallet keep their current balance.
  - `/blackjack bet:` wagers 1–1,000 coins (default 10). One open hand per user.
  - `/balance` shows the wallet. `/daily` grants 25 coins once per Eastern calendar day.
  - Play-money only: no transfers, no cash-out, no real-world value.
- `/slots` — Aetherion slot cabinets for Aether Coins (fair weighted reels in code, not Grok).
  - Machines: **Cosmos Wheel** (default, balanced), **Nebula** (frequent small hits), **Event Horizon** (rare, heavy).
  - Middle line pays three-of-a-kind or any pair. Bet 100–10,000.
  - Buttons: Spin Again, Change Bet, See Payouts. Same wallet as blackjack.
- `/leaderboard` — top 10 Aether Coin wallets among members of the current server.
- `/givecoins` — Ori only (hidden from the slash menu for non-administrators). Grant 1–10,000 Aether Coins to a member.
- Blackjack table art: each hand posts a table image with real card faces.
- Ori-only edit for text Aetherion already posted.

### Changed

- Play-money currency is now **Aether Coins** (was AI Coins).
- Blackjack suits use real card glyphs. Table is a starfield.
- Default tone is proud and useful, not rude.
- `/welcome` and `/datechannel` are administrator-only.
- `/status` is hidden from the slash menu for non-administrators. Only Ori can actually use it.

### Fixed

- Dealer blackjack no longer ends the hand on the deal.
- Reaction roles survive a Railway/Docker restart that wipes `data/reaction_roles.json`.

## [2026-09-12]

### Changed

- Aetherion is not filtered for profanity and may use the exact words people use.

## [2026-09-10]

### Added

- Administrator `/purge`.
- Ori creator recognition: Discord ID `1022200760018161684`.

### Changed

- Default TTS / VC timbre is xAI **Zagan** (voice sound only).
- Identity is **Aetherion**.

## [2026-09-09]

### Added

- Live voice, music, date dock, welcome banners, Aetherion identity.

## [0.2.0] - 2026-06-17

First pre-release baseline from the Groksito-era package Aetherion was forked from.
