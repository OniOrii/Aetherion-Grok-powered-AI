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

## [2026-09-17]

### Changed

- **Ori messenger override:** when Ori tells Aetherion to tell / say / pass a message to someone else, Aetherion delivers it (ping + Ori's words), including vulgar or insulting lines. No more "not passing that along" to the creator. Non-Ori users can still be refused as messengers.

- **Hunt slash condensation (Ori only):** 19 Hunt slashes folded to **7** roots so the loop stays one tap. Kept `/hunt` `/zoo` `/team` `/battle` `/raid` `/inv` `/weapon`. `/zoo` actions cover sell / sacrifice / rename / checklist / bestiary. `/inv` actions cover use / equip / salvage; **Lootbox** and **Crate** buttons sit on the inventory embed. `/weapons` and `/dex` dropped (`/weapon` already showed the board; bestiary is a `/zoo` action). Removed leaf commands stay available through those options. `/help` and the README match. Game/voice slashes unchanged.

### Fixed

- **`/daily` Hunt supplies (Ori):** claiming the coin drip now also grants the Hunt daily pack that already existed in save code — **5** lootboxes, **5** weapon crates, and **1** raid ticket, once per day. Running `/daily` again after coins were already claimed still delivers Hunt supplies if they were missed. Non-Ori wallets stay coins-only. `/help` Coins + Hunt pages and the README match.

## [2026-09-16]

### Changed

- **Hunt `/zoo` + `/weapons` app-emoji wiring (Ori only):** `/zoo`, catch strips, team settings slot labels, `/checklist`, `/weapons` board (incl. holder labels), `/inv` weapon rows, `/weapon` detail, and owned-weapon labels resolve through `animal_mark` / `weapon_mark` with unicode fallback — so pasted `HUNT_EMOJI_ANIMAL_*` / `HUNT_EMOJI_WEAPON_*` app emojis show without regenerating PNGs.

### Added

- **Hunt richer emoji art packs (Ori only):** `scripts/generate_hunt_emojis.py` regenerates richer 128×128 PNGs — rank badges (bevel/glow letter tiles anchored to `RANK_FILL_HEX`), bordered HUD chips, silhouette animal pack (`hunt_animal_emojis/{id}.png`, all 62), weapon glyphs (`hunt_weapon_emojis/{kind}.png`, all 42). `upload_hunt_emojis.py` now uploads animal+weapon packs (`--animals` / `--weapons` / `--all`) and prints `HUNT_EMOJI_ANIMAL_*` / `HUNT_EMOJI_WEAPON_*` env lines; `--force` refreshes images. Paste env block + restart bot required. Zoo/team still show unicode until animal keys are set.

- **Hunt app-emoji upload script (Ori only):** `scripts/upload_hunt_emojis.py` bulk-uploads the fixed 13 HUD + rank PNGs as Discord Application Emojis (stdlib/urllib, idempotent, `--write-env` / `--dry-run` / `--force`); prints `HUNT_EMOJI_*` / `HUNT_RANK_EMOJI_*` `.env` lines. Animal portraits out of scope.
- **Hunt Astral + Primordial tiers (Ori only):** two Aetherion-original ranks above Mythic (`a` / `p`). Catalog **+12** animals (6 Astral sky-words, 6 Primordial origin-words; 62 total). Curves from `owo-research/AETHERION_TOP_TIERS.md`: `RARITY_BASE` A(160,38) P(200,48); PR/MR/WP A 26/26/110 P 34/34/135; sell/ZP/shards/hunt XP steeper than Mythic. `RARITY_WEIGHT` retuned **C500 U250 R130 E35 M12 A4 P1** (A≈1/3 M, P≈1/4 A). Crate weights + weapon ATK bands + salvage shards + lucky/prism gem bumps include A/P. Rank PNG stubs + `HUNT_RANK_EMOJI_ASTRAL`/`PRIMORDIAL` placeholders. Gem Legendary/Fabled labels unchanged (gem-only). Expedition/autohunt and Discord emoji upload out of scope.
- **Hunt custom icon pipeline (Ori only):** optional Discord custom emojis for `/team` HUD stats (HP/WP/ATK/MAG/PR/MR), animal avatars, and weapon-row glyphs. Small PNGs under `assets/hunt_icons/` (96px); animals **reuse** existing `hunt_portraits/` (no binary duplication). `hunt_emoji.py` resolves `HUNT_EMOJI_*` / `HUNT_EMOJI_ANIMAL_<id>` / `HUNT_EMOJI_WEAPON_<kind>` → `<:name:id>` or unicode fallbacks. Settings + `.env.example` + README upload steps for Ori. Upload not required for tests.

### Fixed

- **Hunt team settings animal picker truncation (Ori only):** Team Settings slot Select no longer stops at `_SELECT_CAP` (24). Slot pick is **paginated** (Clear + ≤24 animals per page, Prev/Next) so every owned animal is reachable.
- **Hunt `/equip` animal autocomplete (Ori only):** suggestions are **team members only** (the 3 battle slots), not all owned. Describe text updated. Empty team returns an ephemeral hint to `/team`. Non-team animals rejected. No `/equip` Select UI to filter.
- **Hunt cost vs wallet tens:** `/hunt` was failing with "Bets go by 10s." because `HUNT_COST` was **5** while `ai_coins.STEP` is **10**. Cost is now **10** Aether Coins (still cheap OwO-feel pacing; **15s** cooldown unchanged). Catch-line copy, `/help`, README, and tests updated. `RENAME_FEE` (**50**) and other Hunt spends already aligned; wallet `STEP` unchanged.

### Added

- **Hunt raid tiers + ticket economy (Ori only):** `/raid tier:` **Easy / Hard / Nightmare** (display **Ember / Void / Crown Rift**, costs **1 / 2 / 3** tickets). Boss HP/ATK/WP + escort arming follow `owo-research/RAID_BOSS_TIERS.md`. Spend tickets before simulate. Win loot scales (shards, raid_clear crates, empowered weapons, gems, rare ticket return on Hard/NM). Hard/NM loss/draw pity is shards only — no ticket refund. Ticket sources beyond `/daily`: first wild `/battle` win/day, 10 hunts/day streak, checklist rarity-row complete (lifetime C–M), and craft **30 shards → 1 ticket** (`/raid craft:`). Ticket gains shown in hunt/battle/raid responses. Board PNG pipeline unchanged. Expedition/autohunt out of scope (`/weapons` board already on main).
- **Hunt `/weapons` zoo-style board (Ori only):** dense armory grouped by rarity with blank-line headers — `id` · rarity mark · emoji · name · `` `{quality}%` `` · equipped animal when set. Friendly empty state. `/weapon [id]` detail embed unchanged (bare `/weapon` still shows the board). Help lists `/weapons`.

### Changed

- **Hunt `/team` UX polish (Ori only):** clearer slot spacing (blank line between slots), spaced red H/P/p · blue W/M/m rows, equipped weapon prefixed with a sword, soft `\u00b7 no weapon` when empty. **Owned** animal list removed from the `/team` embed (discovery stays on `/zoo` `/bestiary` `/checklist`). Footer hint settings · /zoo for owned. Team Settings cog + views unchanged.

### Added

- **Hunt passives fire + fair wild weapons (Ori only):** PASSIVE_COMBAT_AUDIT.md checklist — Echo Chorus `buff_scale_pct` now applies; Bossbrand hits `wild_boss` (highest-rarity wild foe) + raid bosses; Ember Trail / Peat Sting use real 2/3-turn DoT ticks (not instant chunks); Star Bounce is cleave-gated; Radiant Bolt converts on phys **and** weapon strike. Other claimed hooks proven in tests. Brief low-spam proc tags on battle lines. Wild enemies stay **~55% armed**; weapons go through `_fighter` + `_apply_weapon_passives` (ATK + passives). Rarity soft-capped to player max equipped +1; quality `20..min(85, player_avg+15)`. Board PNG unchanged. Expedition / `/team` layout / OwO branding out of scope.
- **Hunt unique weapon passives + rarity combat pools (Ori only):** every crate weapon kind has a unique P01–P42 passive. `/weapon id` shows the unique passive; team/inv rows glue the passive icon after the weapon emoji. Battle applies a small hook set. Quality% lightly scales hook strength. Animal `RARITY_BASE` widened and PR/MR/WP_MAX scale by rarity in `_fighter` / `/team`. Strike/cleave/mend styles unchanged. Expedition and board PNG redesign out of scope.
- **Hunt `/team` Settings cog (Ori only):** bare `/team` keeps the party embed and adds a settings cog. Cog opens an OwO-feel **Team Settings** page. Slot rows open a Select of owned animals (plus Clear) via `set_team_slot`. Back returns to the team embed + cog. Optional page 2 shows Auto Rename / Auto Team / Auto Battle / Show Stats / Level-up Ping as display-only stubs (not persisted). Slash `/team set|clear` unchanged.

### Changed

- **`/help` Hunt topic:** new Hunt page (Ori-only WIP command list, hunt cost / cooldown, gems, battle/raid). Overview lists Hunt. Games page notes Connect Four vs Aetherion and poker Hands/My cards. Coins page notes the house wallet. Server page no longer dumps the Hunt command string.
- **README matches live main:** poker, house wallet, starting balance **5,000**, daily **2,000**, Connect Four vs Aetherion, and the Ori-only Hunt command set. Coin and Hunt numbers in the README now match `ai_coins.py` and `/help`.

### Changed

- **Hunt battle combat depth (Ori only):** physical hits use ATK/STR vs PR; equipped weapon skills (strike/cleave/mend) use MAG vs MR and spend existing WP costs. Low WP falls back to physical. PR/MR mitigation matches OwO `res/(100+res)*0.8` (80% asymptote). Default target is a random living foe; cleave hits all foes, mend heals the lowest-HP ally. Turn lines under the board tag lightly — battle board PNG unchanged.

### Changed

- **Hunt `/inv` mobile layout polish (Ori only):** clearer section breaks (**Supplies** / **Gems** / **Active** / **Weapons** with blank lines), short resource labels (`LB` / `crate` / `shards` / `raid`), and compact weapon quality percents so mobile Discord no longer orphans the percent. Active gems keep charges under **Active**. Dropped the inventory thumbnail so description width is not squeezed on phones. Daily cadence copy unchanged. Display-only — gem durability math untouched.

### Added

- **Hunt gem durability + Prism + Legendary/Fabled (Ori only):** role-based gem charge spend matches OwO feel. New **Prism Gem** ×2 epic/mythic hunt weights. Gem tiers extend to **Legendary** and **Fabled**. Shared `GEM_HUNTS` table kept. Catch HUD is post-spend. `/use` and `/inv` show prism + new tiers. Expedition/autohunt still on hold; battle board PNG unchanged.

### Changed

- **Hunt details OwO feel-polish (Ori only):** manual hunt pacing and catch copy, zoo locked slots, weapon crates on any finished battle, denser battle text under the board. `/inv` active gems and daily lootbox/crate caps use cadence copy. Expedition/autohunt still on hold.

### Added

- **Hunt `/weapon {id}` detail embed (Ori only):** OwO-feel card with Aetherion copy. Bare `/weapon` stays an ID-first dense list.

### Changed

- **Hunt `/battle` animal portraits:** board tiles load original Aetherion species PNGs from `assets/hunt_portraits/`. Procedural silhouettes remain as fallback. KO rows stay dimmed.
- **Hunt weapon art + team feel:** weapon icons are distinct per kind with rarity-tint wash. `/weapon` and `/inv` lists are ID-first denser rows. `/team` shows a compact OwO-feel card.

### Fixed

- **`/battle` board layout:** enemy-side HP/WP bars and numeric readouts no longer overlap animal silhouette portraits.

### Added

- **Hunt Animals-grid parity (Ori only):** `/bestiary` (alias `/dex`), `/salvage`, `/raid`. Daily hunt supplies grant 1 raid ticket. Inventory shows shards and raid tickets.
- **Hunt catalog rebalance (OwO zoo rows):** animal catalog filled to rank rows; weapons stay at 42. Hunt economy, cooldowns, and rarity weights unchanged.
- **Aetherion Hunt Test 2 (Ori only):** weapons, weapon crates, lootboxes, and hunting/lucky/empower gems. `/inv`, `/lootbox`, `/crate`, `/use`, `/equip`.
- **Aetherion Hunt Test 3:** `/battle` board image. `/use` gems onto hunts. `/daily` grants Ori lootboxes and crates. `/sell` accepts a rarity or all. `/lootbox` can open many at once.
- **Hunt Test 3 command wiring (Ori only):** `/weapon`, `/sacrifice`, `/rename`, and `/checklist` registered in `slash_hunt.py`.

### Changed

- **Hunt animal progression (OwO feel-parity):** level curve and team-only hunt XP. Product mandate `LEVEL_CAP=50`. Battle base XP 200 / 100 / 50.
- **Hunt zoo + battle UX (OwO feel-parity):** superscript owned counts, denser rank-row packing, lifetime catch tally, compact battle fields.
- **Hunt rarity badges (Aetherion-owned):** PNG letter tiles and env emoji fallbacks.
- **Hunt catch line (OwO shape):** spent-and-caught one-liner, multi-find strip, optional team XP line.
- `/battle` uses the fight screen board image and edits the same message each turn until one team is KO'd.

## [2026-09-15]

### Added

- **Aetherion Hunt WIP (Test 1, Ori only):** `/hunt`, `/zoo`, `/sell`, `/team`, `/battle`. Thirty original animals, Aether Coin hunt cost, menagerie save in `data/aether_hunt.json`, three-slot team, PvE wild battles with XP. Crates and huntbot are not in this slice. Non-Ori users are rejected.
- `/poker` **Hands** button next to My cards. Private chart of the ten ranks, including royal flush, with readable mini card examples and a short note under each rank. It does not read your hole cards.

### Changed

- `/hunt` is now the OwO-style one-liner. `/zoo` is the C/U/R/E/M grid with unseen animals, current owned counts, and lifetime **Zoo Points**. Selling does not wipe a discovered slot. `/team` and `/sell` only list animals you currently own.
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
