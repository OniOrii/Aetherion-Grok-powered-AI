# Changelog

All notable changes to **Aetherion** are documented in this file. This is the permanent record.

**Rule (standing, 2026-09-13):** every feature, command, persona change, voice change, or removal that lands on `main` is added here in the same commit or immediately after, with a calendar date (`YYYY-MM-DD`). Do not skip the changelog. Do not leave new work only in commit messages.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Older packaged history stays under version headings. Aetherion work from September 2026 onward is grouped by date.

## [Unreleased]

_Nothing waiting. New work is dated the day it ships._

## [2026-09-22]

### Removed

- **Gamemeca ranking loop:** the daily `refresh_ranking` background task from the Groksito fork is gone. Aetherion does not use that game-chart integration. The leftover module file stays so imports elsewhere do not break.

### Changed

- **`/audio` and Read aloud are English:** option is `style:` not `estilo:`. Replies and the rate-limit line are English. TTS language falls back to **en** instead of **es** even if an old setting still says Spanish.
- **Chat rate-limit copy:** "Easy — you already used your 6 requests this minute." instead of "Tranquilo campeon...".
- **`/help` matches live Aetherion:** overview and Server tools list `/logs`. Chat notes servers-only (no DMs) and the live `/ping` embed (gateway, command round-trip, servers, voice). Server tools describe `/status` pin vs 90s rotate. Hunt stays off the pages.
- **Aetherion surface branding:** user-facing Groksito labels are now Aetherion. Railway/startup banner art prints **AETHERION**, logs say Aetherion, README / GROK_OAUTH / ARCHITECTURE / dashboard titles match, `/help` and README say **Read aloud**, `.env.example` and `scripts/configure_env.py` prompts are English. Package path `src/groksito_discord`, loggers, CLI `groksito` (with `aetherion` alias), and imports are unchanged so Railway keeps booting. Deep rename later.

### Fixed

- **Slash registry guard:** `tests/test_slash_registry.py` fails if `/join` `/leave` `/audio` `/welcome` `/datechannel`, Read aloud, or the other live slashes disappear from source again, and if Hunt slashes come back. `/help` is checked against the same list.
- **Restored `/join` `/leave` `/audio` `/welcome` `/datechannel` and Apps → Read aloud.** Those handlers lived at the bottom of `slash_commands.py` and were deleted on 2026-09-16 when `/givesupply` was wired (`66981c3`, −232 lines after `/ping`). Later `/logs` `/autorole` `/ping` and Hunt-unregister edits never put them back. Same bodies as the 2026-09-15 restore; context menu label is **Read aloud**. Hunt stays unregistered.

### Removed

- **Aetherion Hunt:** the Ori-only WIP is gone. Dropped `/hunt` `/zoo` `/team` `/battle` `/raid` `/inv` `/weapon` `/givesupply`, Hunt help page, Hunt daily supplies on `/daily`, Hunt settings / `.env` keys, Hunt modules, tests, scripts, and asset packs. Command sync on the next deploy clears those slashes from Discord.

### Added

- **Auto-role (`/autorole`, Administrators):** pick one role; Aetherion gives it as soon as a person joins. Bots are skipped. If Rules Screening is on, the role is applied the moment they accept the rules (Discord will not keep roles on pending members). `/autorole` with no options shows the current role. `/autorole off:True` turns it off. Aetherion needs **Manage Roles**, and its role must sit above the join role. Administrator and managed roles are refused. Welcome banners and `/logs` join events are unchanged.

## [2026-09-21]

### Added

- **Rotating status:** Aetherion cycles a custom status bubble every **90s**. `/status` with text pins one line and stops the cycle. `/status rotate:True` turns rotation back on. `/status` with no text shows the current line. Ready no longer overwrites a saved presence with a hard-coded Cosmos watch.
- **No DMs:** Aetherion ignores private messages and slash commands used in DMs. It replies that it only works in a server and does not call Grok. Server chat and server slashes are unchanged.
- **Server logs (`/logs`, Administrators):** Carl-style event embeds in a channel you pick. Joins, leaves, kicks, bans, timeouts, nick/roles, voice, message delete/edit/purge, invites, channels, roles, emoji, and server settings. No Grok calls. Defaults cover the common events; menus toggle the rest.

### Fixed

- **Empty log channel:** `/logs` now posts a test embed when you set the channel, and the setup menu has **Send test**. Missing View / Send / Embed Links is reported instead of failing silently. Message events in the log channel itself are no longer swallowed. Listeners attach once and stay attached.

### Changed

- **Status bubbles:** rotation is custom-status only. Dropped Watching/Playing/Listening/Competing lines (The Cosmos, Hunt, the rift, poker, the stars, Crown Rift, God of AI!). Cycle is now the 25 Ori lines starting with "I can see you".
- **`/ping`:** gold embed now shows Discord gateway heartbeat ms, this slash command's round-trip, a short Excellent/Good/Okay/Slow label, server count, this server's name, and how many voice connections are up.
- **Log avatars:** person logs (join, leave, kick, ban, timeout, nick/roles, voice, message delete/edit, invites) show that user's Discord avatar as the embed thumbnail.

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
- **Hunt Astral + Primordial tiers (Ori only):** two Aetherion-original ranks above Mythic (`a` / `p`). Catalog **+12** animals (6 Astral sky-words, 6 Primordial origin-words; 62 total).
- **Hunt custom icon pipeline (Ori only):** optional Discord custom emojis for `/team` HUD stats, animal avatars, and weapon-row glyphs.

### Fixed

- **Hunt team settings animal picker truncation (Ori only):** Team Settings slot Select is paginated so every owned animal is reachable.
- **Hunt `/equip` animal autocomplete (Ori only):** suggestions are team members only.
- **Hunt cost vs wallet tens:** hunt cost is **10** Aether Coins so it matches wallet steps of 10.

### Added

- Hunt raid tiers, `/weapons` board, team UX polish, passives, unique weapon passives, Team Settings cog, gem durability, and the rest of the dated Hunt history through Test 3 remain recorded in git history from earlier 2026-09-16 commits.

## [2026-09-15]

### Added

- **Aetherion Hunt WIP (Test 1, Ori only):** `/hunt`, `/zoo`, `/sell`, `/team`, `/battle`.
- `/poker` **Hands** button next to My cards.

### Changed

- Command embeds use the gold cosmos look. New players start with **5,000** Aether Coins. `/daily` grants **2,000**. House wallet starts at **1,000,000**.

### Fixed

- Poker / blackjack / Connect Four result copy and animation fixes from this date remain in git history.

## [2026-09-14]

### Added

- `/help` topic pages. `/connect4`. `/poker` Texas Hold'em.

## [2026-09-13]

### Added

- Reaction roles, `/blackjack`, Aether Coins, `/slots`, `/leaderboard`, `/givecoins`, `/cointoss`.

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
