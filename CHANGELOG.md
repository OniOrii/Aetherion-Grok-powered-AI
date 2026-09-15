# Changelog

All notable changes to **Aetherion** are documented in this file. This is the permanent record.

**Rule (standing, 2026-09-13):** every feature, command, persona change, voice change, or removal that lands on `main` is added here in the same commit or immediately after, with a calendar date (`YYYY-MM-DD`). Do not skip the changelog. Do not leave new work only in commit messages.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Older packaged history stays under version headings. Aetherion work from September 2026 onward is grouped by date.

## [Unreleased]

_Nothing waiting. New work is dated the day it ships._

## [2026-09-14]

### Added

- `/help` with topic pages (overview, chat, voice, games, coins, server) and a dropdown to switch pages.
- `/connect4` \u2014 two-player Connect Four. Challenge a member, both stake the same Aether Coin bet, winner takes the pot. Draw returns both stakes.
- `/connect4` can be played against **Aetherion** (leave opponent empty). Painted cosmos board, house AI, Play Again.
- Connect Four discs now fall down the column each turn. Aetherion pauses to choose, then drops with the same animation.
- Connect Four drop animation is a single GIF per turn so the board does not flicker between holes.
- Connect Four drop GIFs play once and freeze on the landed disc. They no longer restart from the top.
- Connect Four GIFs no longer loop. The disc falls once, then the board freezes as a still image.
- `/poker` \u2014 Texas Hold'em, 2-4 seats. Friends can Join, or Seat Aetherion. Fair house player uses only its own cards. Buy-in 10-1,000 Aether Coins. Fold / Check-Call / Raise / All-in. Hole cards stay private.

### Changed

- Poker table uses a felt oval, wider seats, and hole cards that sit side by side instead of overlapping.
- `/poker` Raise opens a box so you type the amount. End of hand names the winner, the hand, both hole cards, and stacks.
- Poker seat hole cards are larger. Community cards stay the same size so they do not overlap.

### Fixed

- `/poker` no longer posts 10/10 blinds on a 10-coin buy-in. That all-inned both seats and made every button say you cannot act.
- `/poker` no longer leaves the last call line on the winner screen.
- `/poker` Deal no longer shows every seat's hole cards to the host. Each other player is DMed their own hand. My cards stays as backup.
- `/poker` no longer ends the hand after one call round. Flop, turn, and river each get their own betting round unless everyone is all-in.
- `/poker` all-in pots now flip flop, turn, and river one street at a time instead of jumping straight to the winner.

## [2026-09-13]

### Added

- Exclusive multi-color **reaction roles** (Admin slash setup, anyone can react).
- Fair `/blackjack` against Aetherion (Hit / Stand / Double).
- Play-money **Aether Coins** saved in `data/ai_coins.json`.
- `/slots` \u2014 Cosmos Wheel, Nebula, Event Horizon. Bet 100\u201310,000. Same wallet as blackjack.
- `/leaderboard` and Ori-only `/givecoins`.
- Blackjack table art and Ori-only `/edit`.
- Blackjack **Play Again** + **Change Bet** after each hand (same last stake, no retyping `/blackjack`).
- `/cointoss` \u2014 Heads / Tails, 2% side landing at 2.5x, falling flip animation, custom Aether coin art. Bet 10\u201310,000.

### Changed

- `/slots` cabinet now animates (spark reel \u2192 blur \u2192 land) and uses a tighter Pocket / Winnings / Net embed.
- Play-money currency is now **Aether Coins** (was AI Coins).
- Blackjack table is a starfield with real suit glyphs.
- Aether Coin bets and grants go by **10s**. Blackjack minimum is 10.
- `/daily` grants **500** Aether Coins.
- Slot pair and trip multipliers are **2x** the previous table.
- `/cointoss` uses a smaller coin that falls the full frame. Odds are **48% heads / 48% tails / 2% side**.
- Coin toss background is a sharp starfield with no planet. Side landings use their own standing-rim frame after the flip.
- Slot reel rows keep `|` dividers between symbols and wider row spacing.
- `/slots` uses a **corner thumbnail** for each cabinet (Cosmos, Nebula, Event Horizon). The large full-width embed image was removed because it kept breaking.
- Coin toss uses **8** mid-air frames.
- README now matches live commands (games, Aether Coins, reaction roles, admin tools) and states music is SoundCloud-only.

### Fixed

- Dealer blackjack no longer ends the hand on the deal.
- Reaction roles survive a Railway/Docker restart that wipes the save file.
- `/slots` cabinet thumbnail now draws a real PNG instead of a broken JPEG.
- CHANGELOG.md was restored after a later commit overwrote the older dated history.

### Removed

- The short-lived ~2% kinder payout bump on slots and blackjack.
- Unused photo-cabinet leftovers (`cabinet_cosmos.py`, `assets/slots/*.b64`).
- README claims that YouTube playback exists. `/play` still rejects YouTube links.

## [2026-09-12]

### Changed

- Aetherion is not filtered for profanity and may use the exact words people use.

## [2026-09-10]

### Added

- Administrator `/purge`. Ori creator recognition.

### Changed

- Default TTS / VC timbre is xAI **Zagan**. Identity is **Aetherion**.

## [2026-09-09]

### Added

- Live voice, music, date dock, welcome banners, Aetherion identity.

## [0.2.0] - 2026-06-17

First pre-release baseline from the Groksito-era package Aetherion was forked from.
