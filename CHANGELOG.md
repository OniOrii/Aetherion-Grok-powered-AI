# Changelog

All notable changes to **Aetherion** are documented in this file. This is the permanent record.

**Rule (standing, 2026-09-13):** every feature, command, persona change, voice change, or removal that lands on `main` is added here in the same commit or immediately after, with a calendar date (`YYYY-MM-DD`). Do not skip the changelog. Do not leave new work only in commit messages.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Older packaged history stays under version headings. Aetherion work from September 2026 onward is grouped by date.

## [Unreleased]

_Nothing waiting. New work is dated the day it ships._

## [2026-09-15]

### Changed

- Command embeds use the gold cosmos look: `\u2726` titles, sentence case, and punctuation on `/help`, `/ping`, `/play`, `/blackjack`, `/balance`, `/daily`, `/leaderboard`, `/slots`, `/cointoss`, `/connect4`, `/poker`, and reaction-role panels.
- `/balance` and `/daily` now reply with gold wallet embeds instead of plain text.
- Poker caption bar sits below the bottom hands. Winner text wraps onto two lines instead of running off the bar.
- The Aether Coin mark used on `/slots` (`\u2726`) now sits next to coin amounts on blackjack, connect four, poker, `/balance`, `/daily`, `/leaderboard`, and `/givecoins`.
- `/poker` default buy-in is 200. Blinds scale with the buy-in (20/40 at 200, larger on bigger stacks). 10-coin tables stay blindless so they do not all-in on the post.
- Aetherion raises and calls more in `/poker` instead of checking every street or folding every raise. House raises size to the pot.
- New players start with **5,000** Aether Coins. `/daily` grants **2,000**.
- Aetherion has a house wallet that starts at **1,000,000**. Wins against players add to it, losses subtract, and it appears on `/leaderboard`.
- Aetherion plays `/poker` from its own hole cards and the board only. It can value-bet, fold junk, or bluff. It cannot see anyone else's hole cards.
- Aetherion no longer dumps the stack on ace-high. All-in and calling a shove need a pair or better, or a premium preflop hand. Bluffs stay small.

### Fixed

- `/blackjack` states the result once, in the embed title. The footer and the painted table line no longer repeat it.
- Replies to Aetherion now read the message that was replied to, including Connect Four embeds and other game boards, plus recent chat with that user.
- Replies to a finished Connect Four board now keep the result text (embed title, fields, footer) and the match outcome, so "impossible to win against you" is treated as talk about that game instead of a new dare.
- Connect Four no longer flickers the whole board on each drop. The painted table is cached, only the falling chip is drawn, and Discord keeps one connect4.gif attachment instead of swapping GIF then PNG every turn.
- Connect Four no longer replays the falling chip before the next turn. After a drop the bot waits without editing the message, so Discord does not restart the GIF.
- `/poker` All-in updates the table right away instead of waiting through Aetherion's think and the board run.

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
- Poker seat hole cards are larger again so they read at a glance. Community cards stay the same size so they do not overlap.
- Poker action line on the felt ("OniOrii is all-in.") is larger and sits in a caption bar.

### Fixed

- `/poker` no longer posts 10/10 blinds on a 10-coin buy-in. That all-inned both seats and made every button say you cannot act.
- `/poker` no longer leaves the last call line on the winner screen.
- `/poker` Deal no longer DMs hole cards. Every seat taps **My cards** for a private hand.
- `/poker` no longer ends the hand after one call round. Flop, turn, and river each get their own betting round unless everyone is all-in.
- `/poker` all-in pots now flip flop, turn, and river one street at a time instead of jumping straight to the winner.
- `/poker` no longer gets stuck on "Wait a second" after an all-in. The table message is edited directly, and the busy lock always clears.

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

- Administrator `/purge`. Ori only creator recognition.

### Changed

- Default TTS / VC timbre is xAI **Zagan**. Identity is **Aetherion**.

## [2026-09-09]

### Added

- Live voice, music, date dock, welcome banners, Aetherion identity.

## [0.2.0] - 2026-06-17

First pre-release baseline from the Groksito-era package Aetherion was forked from.
