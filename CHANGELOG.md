# Changelog

All notable changes to **Aetherion** are documented in this file. This is the permanent record.

**Rule (standing, 2026-09-13):** every feature, command, persona change, voice change, or removal that lands on `main` is added here in the same commit or immediately after, with a calendar date (`YYYY-MM-DD`). Do not skip the changelog. Do not leave new work only in commit messages.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Older packaged history stays under version headings. Aetherion work from September 2026 onward is grouped by date.

## [Unreleased]

_Nothing waiting. New work is dated the day it ships._

## [2026-09-16]

### Added

- **Hunt Animals-grid parity (Ori only):** `/bestiary` (alias `/dex`) shows stats and short lore for a discovered animal. `/salvage` scraps a crate weapon into shards (blocks favorited weapons if marked). `/raid` spends a raid ticket for a tougher 3v3 PvE boss fight reusing battle helpers — no guild system. Daily hunt supplies grant 1 raid ticket. Inventory shows shards (`200`) and raid tickets (`300`).
- **Hunt catalog rebalance (OwO zoo rows):** animal catalog is now **50** with **10 of each** C/U/R/E/M (multiples of 5 for zoo packing). Trimmed excess commons/uncommons (recent theme-duplicates + trailing fillers: clay_crab, weed_sprite, mist_vole, peat_slug, glass_newt, sol_sparrow, rift_tick, moon_kit, storm_shrimp, mist_panther, peat_bear). Kept iconic early names. Added original Aetherion rare/epic/mythic names to fill each tier to 10. Weapons stay at 42 (style-based, not C/U/R/E/M). Hunt economy, cooldowns, and rarity weights unchanged. Casino, voice, and music untouched.
- **Aetherion Hunt Test 2 (Ori only):** thirty original weapons, weapon crates, lootboxes, and hunting/lucky/empower gems. `/inv`, `/lootbox`, `/crate`, `/use`, `/equip`. Hunt lootboxes drop at 5% (max 3/day). First battle win drops a crate (then 5%, max 3). Gems change hunt yield. Weapons add ATK and a strike/cleave/mend style. `/inv` uses the OwO inventory header (`050` lootbox, `100` crate). `/lootbox` uses the two-line gem reveal. Pet level cap is 50.
- **Aetherion Hunt Test 3:** `/battle` posts a 3v3 board image and edits the same message each turn. `/use hunting|lucky|empower` activates lootbox gems onto hunts (not onto pets). Hunt lootboxes drop at 5% (max 3/day). `/daily` grants Ori 5 lootboxes and 5 crates. `/sell` accepts a rarity or all. `/lootbox` can open many at once. Huntbot upgrades stay later.
- **Hunt Test 3 command wiring (Ori only):** `/weapon`, `/sacrifice`, `/rename`, and `/checklist` were already listed in `/help` and the changelog; they are now registered in `slash_hunt.py`. `/weapon` lists owned crate weapons and equipped animals. `/sacrifice` turns extra owned animals into Essence (sell-value table; keeps one if on the team). `/rename` sets or clears a nickname on an owned animal for 50 Aether Coins. `/checklist` shows C/U/R/E/M discovered vs missing from lifetime catches. Original Aetherion copy.

### Changed

- **Hunt animal progression (OwO feel-parity):** pets still start at **level 1 / 0 XP** (`level_of(0)==1`). Level curve now matches OwO `animalUtil.js` `getXP`/`toLvl`: XP to leave level `L` is **`L^4 + 1000`** (was flat `XP_PER_LEVEL=25`; L1→L2 needs **1001**). **OwO has no hard pet level cap** in leveling code (wiki soft milestone ~L101); **Aetherion product mandate sets `LEVEL_CAP=50`** in base and ext (base was 20). Hunt team XP uses OwO Manual Hunting / `animal.json` amounts for C–M: **Common 1, Uncommon 10, Rare 20, Epic 400, Mythical 1000** (replaces ext `{8,12,20,40,80}`; Special skipped). Per OwO `PET_LEVELING` / `catch.js`, **team pets only** gain that hunt XP — the newly caught animal does **not** unless it is already on the team (overrides any earlier CoS wording that awarded caught+team). `/hunt` still returns `xp_gain` so the catch line can show `| emoji gained **Nxp**!`. Battle base XP stays **200 / 100 / 50** (base no longer uses 40/25/15); ext win bonuses keep/extend OwO source streak + float-avg level-diff (`round(600 * diff)`) plus catchup mult. Stats still scale with `stats_for` (HP +6 / ATK +2 per level). Catalog expansion is a separate PR — unchanged here.
- **Hunt zoo + battle UX (OwO feel-parity):** `/zoo` uses unicode **superscript** owned counts (zero-padded to at least **2** digits like OwO `00`/`04`, growing with densest count), denser rank-row packing (mark + 3 spaces), OwO plant-header order (`🌳 🌱 🌿` on the right, mirrored), and a lifetime catch tally under Zoo Points (`M-#, E-#, R-#, U-#, C-#`). Unseen slots stay `❓`. `/battle` team fields stay OwO image-mode compact (`L. lvl emoji - weapon`); the board image labels **HP** / **WP** beside the bars; text battle-card fallback shows `` `{hp} HP` `{wp} WP` ``. Original Aetherion animals only — no OwO species names. Economy, ranks, and non-hunt games untouched.
- **Hunt rarity badges (Aetherion-owned):** added PNG letter tiles under `src/groksito_discord/discord/assets/hunt_ranks/` (fills `#9A4442` / `#388B9A` / `#D4A746` / `#4057E1` / `#9558EF` for C/U/R/E/M — not OwO assets). `rarity_mark()` prefers `HUNT_RANK_EMOJI_COMMON`…`MYTHIC` (`<:name:id>` from settings/.env); until those are set it falls back to unicode `🟥C` `🩵U` `🟨R` `🟦E` `🟪M`. `/zoo`, `/checklist`, and weapon lines share the same helper. Embed rarity colors match the badge fills. **Ori:** upload the five PNGs as Discord app/guild emojis (suggested names `aether_c`…`aether_m`) and paste the IDs into `.env`.
- **Hunt catch line (OwO shape):** `/hunt` is now `🌱 | {Name} spent {cost} ✦ and caught a/an **{rank}** {mark} {emoji}!` (rank mark restored on the catch line; trailing `!`). Multi-catches no longer use `+` appends — extras become `| You found:` emoji strip. Optional `| {pet} gained **{n}xp**!` lines when team XP is available. Zoo superscripts + battle polish from this branch kept.
- `/battle` now uses the OwO fight screen: author `{name} goes into battle!`, two inline team fields (`L. level` + weapon), a 3v3 HP/WP board image, and the same Discord message is edited every turn.
- `/battle` fights until one team is fully KO'd (safety cap 99), not a fixed 5 turns. Awards match OwO: 200 XP win / 100 tie / 50 lose, plus streak and higher-level bonus XP only on a win. Footer is `You won in N turns! Your team gained 200 xp + bonus xp! Streak: X` (or the lost-streak line). No PvE coin payout. Team fields are one line each. Result sits in the footer like OwO.

## [2026-09-15]

### Added

- **Aetherion Hunt WIP (Test 1, Ori only):** `/hunt`, `/zoo`, `/sell`, `/team`, `/battle`. Thirty original animals, Aether Coin hunt cost, menagerie save in `data/aether_hunt.json`, three-slot team, PvE wild battles with XP. Crates and huntbot are not in this slice. Non-Ori users are rejected.
- `/poker` **Hands** button next to My cards. Private chart of the ten ranks, including royal flush, with readable mini card examples and a short note under each rank. It does not read your hole cards.

### Changed

- `/hunt` is now the OwO-style one-liner (`spent 10 \u2726 and caught a common`). `/zoo` is the C/U/R/E/M grid with unseen animals, current owned counts, and lifetime **Zoo Points**. Selling does not wipe a discovered slot. `/team` and `/sell` only list animals you currently own.
- Command embeds use the gold cosmos look on `/help`, `/ping`, `/play`, `/blackjack`, `/balance`, `/daily`, `/leaderboard`, `/slots`, `/cointoss`, `/connect4`, `/poker`, and reaction-role panels.
- `/balance` and `/daily` now reply with gold wallet embeds instead of plain text.
- Poker caption bar sits below the bottom hands. Winner text wraps onto two lines instead of running off the bar.
- The Aether Coin mark used on `/slots` now sits next to coin amounts on blackjack, connect four, poker, `/balance`, `/daily`, `/leaderboard`, and `/givecoins`.
- `/poker` default buy-in is 200. Blinds scale with the buy-in (20/40 at 200, larger on bigger stacks). 10-coin tables stay blindless so they do not all-in on the post.
- Aetherion raises and calls more in `/poker` instead of checking every street or folding every raise. House raises size to the pot.
- New players start with **5,000** Aether Coins. `/daily` grants **2,000**.
- Aetherion has a house wallet that starts at **1,000,000**. Wins against players add to it, losses subtract, and it appears on `/leaderboard`.
- Aetherion plays `/poker` from its own hole cards and the board only. It can value-bet, fold junk, or bluff. It cannot see anyone else's hole cards.
- Aetherion no longer dumps the stack on ace-high. All-in and calling a shove need a pair or better, or a premium preflop hand. Bluffs stay small.
- Every coin game prints how much you won or lost at the end. New games should use `ai_coins.won_line`.

### Fixed

- `/poker` Hands embed says "Ranked strongest to weakest."
- `/poker` Hands suit symbols sit in the center of each mini card.
- `/poker` Hands cards were too small. Jacks read as J, ranks sit in the corners, and royal flush is the top row.
- `/poker` Hands no longer claims your current best hand. It is a reference chart only.
- `/poker` winner text stays in the embed title block and on the felt. The extra copy under the image is gone.
- `/blackjack` states the result once, in the embed title, including coins won or lost. The footer and the painted table line no longer repeat it.
- `/connect4` end text says Won / Lost / Push instead of only naming the pot.
- `/poker` showdown names each seat's Won / Lost amount vs the buy-in.
- Replies to Aetherion now read the message that was replied to, including Connect Four embeds and other game boards, plus recent chat with that user.
- Replies to a finished Connect Four board now keep the result text (embed title, fields, footer) and the match outcome, so "impossible to win against you" is treated as talk about that game instead of a new dare.
- Connect Four no longer flickers the whole board on each drop. The painted table is cached, only the falling chip is drawn, and Discord keeps one connect4.gif attachment instead of swapping GIF then PNG every turn.
- Connect Four no longer replays the falling chip before the next turn. After a drop the bot waits without editing the message, so Discord does not restart the GIF.
- `/poker` All-in updates the table right away instead of waiting through Aetherion's think and the board run.

## [2026-09-14]

### Added

- `/help` with topic pages (overview, chat, voice, games, coins, server) and a dropdown to switch pages.
- `/connect4` two-player Connect Four. Challenge a member, both stake the same Aether Coin bet, winner takes the pot. Draw returns both stakes.
- `/connect4` can be played against **Aetherion** (leave opponent empty). Painted cosmos board, house AI, Play Again.
- Connect Four discs now fall down the column each turn. Aetherion pauses to choose, then drops with the same animation.
- Connect Four drop animation is a single GIF per turn so the board does not flicker between holes.
- Connect Four drop GIFs play once and freeze on the landed disc. They no longer restart from the top.
- Connect Four GIFs no longer loop. The disc falls once, then the board freezes as a still image.
- `/poker` Texas Hold'em, 2-4 seats. Friends can Join, or Seat Aetherion. Fair house player uses only its own cards. Buy-in 10-1,000 Aether Coins. Fold / Check-Call / Raise / All-in. Hole cards stay private.

### Changed

- Poker table uses a felt oval, wider seats, and hole cards that sit side by side instead of overlapping.
- `/poker` Raise opens a box so you type the amount. End of hand names the winner, the hand, both hole cards, and stacks.
- Poker seat hole cards are larger again so they read at a glance. Community cards stay the same size so they do not overlap.
- Poker action line on the felt is larger and sits in a caption bar.

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
- `/slots` Cosmos Wheel, Nebula, Event Horizon. Bet 100-10,000. Same wallet as blackjack.
- `/leaderboard` and Ori-only `/givecoins`.
- Blackjack table art and Ori-only `/edit`.
- Blackjack **Play Again** + **Change Bet** after each hand.
- `/cointoss` Heads / Tails, 2% side landing at 2.5x, falling flip animation, custom Aether coin art. Bet 10-10,000.

### Changed

- `/slots` cabinet now animates and uses a tighter Pocket / Winnings / Net embed.
- Play-money currency is now **Aether Coins** (was AI Coins).
- Blackjack table is a starfield with real suit glyphs.
- Aether Coin bets and grants go by **10s**. Blackjack minimum is 10.
- `/daily` grants **500** Aether Coins.
- Slot pair and trip multipliers are **2x** the previous table.
- `/cointoss` uses a smaller coin that falls the full frame. Odds are **48% heads / 48% tails / 2% side**.
- Coin toss background is a sharp starfield with no planet.
- Slot reel rows keep dividers between symbols and wider row spacing.
- `/slots` uses a **corner thumbnail** for each cabinet.
- Coin toss uses **8** mid-air frames.
- README now matches live commands and states music is SoundCloud-only.

### Fixed

- Dealer blackjack no longer ends the hand on the deal.
- Reaction roles survive a Railway/Docker restart that wipes the save file.
- `/slots` cabinet thumbnail now draws a real PNG instead of a broken JPEG.
- CHANGELOG.md was restored after a later commit overwrote the older dated history.

### Removed

- The short-lived ~2% kinder payout bump on slots and blackjack.
- Unused photo-cabinet leftovers.
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
