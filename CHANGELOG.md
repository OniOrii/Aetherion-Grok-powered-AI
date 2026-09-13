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
  - `/reactionrole post` — post a panel in the current channel. One color per person on that message.
  - `/reactionrole add` — bind an emoji to a role (uses the last posted panel if no message ID is given).
  - `/reactionrole remove` — unlink an emoji.
  - `/reactionrole list` — show mappings on this server.
  - `/reactionrole colors` — admin-only. Creates the 12 two-color gradient roles and posts a ready panel in the current channel.
  - Switching colors removes the old color role and the old reaction. Removing a reaction drops that role.
  - Stored per guild in `data/reaction_roles.json` (gitignored runtime data).
- Standing rule: every future Aetherion addition is dated and written into this changelog.
- Ori-only edit for text Aetherion already posted.
  - `/edit` — message link or ID, plus optional replacement text. Leave text empty to open an editor with the current wording.
  - Right-click an Aetherion message → Apps → **Edit Aetherion text** to open the same editor.
  - Locked to Ori (Discord ID `1022200760018161684`). Hidden from the slash menu for non-administrators. Other people cannot change Aetherion messages.
  - Only works on messages Aetherion posted. Discord does not let anyone edit another user's text.

### Changed

- Default tone is proud and useful, not rude. Does not treat a straight question as trolling.
- When Ori (Discord ID `1022200760018161684`) pings or mentions Aetherion, replies stay respectful and helpful. Never talks back to Ori.
- `/welcome` and `/datechannel` are administrator-only and hidden from the slash menu for everyone else.

## [2026-09-12]

### Changed

- Aetherion is not filtered for profanity and may use the exact words people use.

## [2026-09-10]

### Added

- Administrator `/purge` (Dyno-style): delete 1–100 recent messages in the current channel.
  - Confirmation buttons before anything is deleted.
  - Pinned messages are kept.
  - Needs Manage Messages and Read Message History.
- Ori creator recognition: Discord ID `1022200760018161684` is treated as Aetherion's creator/Master in text and voice.

### Changed

- Default TTS / VC timbre is xAI **Zagan** (voice sound only).
- Identity is **Aetherion**, a proud AI intelligence.
- Proud, non-submissive tone. Does not suck up to anyone except the creator relationship above.
- `/audio` default voice choice is Zagan.
- Live voice sessions force the Zagan voice id on join.

## [2026-09-09]

### Added

- Last-10 per-user conversation memory for text chat and voice (used when Aetherion needs to recall something).
- Name-address: saying Aetherion / Ethereon / Aetheron / Groksito counts as talking to the bot, same as a ping.
- Voice wake-word aliases, including **Ethereum** and **Iberian** (common STT mishears of Aetherion), plus Atherion, Aetherian, A Theory on, Athena, Theorion, Atheorion, and others.
- Live Discord voice session: `/join` / `/leave`, DAVE decrypt, wake word, TTS back into the channel, Agent Tools web search.
- Music on the same voice connection (no Lavalink): say **Aetherion play …** or use slash commands.
- `/play`, `/pause` (toggles resume), `/stop` for SoundCloud tracks.
- `/datechannel` Eastern-midnight date dock and `/welcome` banners.
- `aetherion` console script (Railway still accepts `groksito`).
- `yt-dlp` for resolving SoundCloud play queries.
- Voice-only light reasoning (`VOICE_REASONING_EFFORT=low`) so spoken answers start sooner; text chat still uses full `GROK_MODEL`.

### Changed

- `/play` and “Aetherion play …” search SoundCloud first and only.
- System prompt identity so Aetherion answers as itself and stays on the current thread in text chat.
- Project metadata, dashboard, and user-facing strings rebranded from Groksito to Aetherion.
- Package import path remains `groksito_discord` so existing deploys keep starting.
- Date dock sleeps until 12:00 AM Eastern instead of polling every 10 minutes.
- Voice decrypt falls back to the member who ran `/join` when Discord has not mapped their SSRC yet.
- Discord presence activity is **The Cosmos**.

### Fixed

- `/join` from a second member could connect the bot but never transcribe their voice.
- Play requests that started with extra STT noise (`Atherion - Play …`) skipped the music handler.
- YouTube storyboard images were incorrectly treated as audio (before SoundCloud-only).
- Empty YouTube formats and googlevideo 403s during the old multi-source music path.

### Removed

- YouTube music playback, YouTube cookie settings (`YOUTUBE_COOKIES`, `YOUTUBE_COOKIES_B64`, `YOUTUBE_COOKIES_FILE`), and `YOUTUBE_COOKIES.md`.
- Mixcloud, Audiomack, Invidious, and Piped music fallbacks.
- Upstream `CONTRIBUTING.md`.
- Slash commands `/stmchr`, `/versus`, `/topkorea`, `/topgames`, `/steamchart`, `/mislimites`.

## [0.2.0] - 2026-06-17

First pre-release baseline. Seeded from merged work on `main` through the modernization
roadmap, native-behavior improvements, and release automation. This is the Groksito-era
package baseline Aetherion was forked from.

### Added

- Long Discord responses split across multiple messages instead of truncating (message splitting, #92)
- Proactive native `web_search` + `x_search` for time-sensitive and live topics (native search, #91)
- Prompt caching improvements: stable single system-message prefix and folded dynamic context (prompt caching, #93)
- `/versus` slash command comparing games on Steam and Twitch (#54)
- `/audio` TTS help embed documenting xAI Speech Tags (#56)
- GitHub Actions CI workflow: pytest matrix, packaging validation, Docker builds (#67, #101)
- GitHub Actions release workflow: GitHub Releases, Python sdist/wheel artifacts, GHCR Docker images (release, #96, #101)
- GitHub Actions community standards: Code of Conduct, Contributing guide, Security policy, issue/PR templates (community standards, #95)
- `scripts/check.py` modernization verification harness (#86)
- Media delivered as Discord file attachments instead of expiring URLs (#49)
- Error observability helpers and improved auxiliary failure logging (#68)

### Changed

- LLM prompt and orchestration refactor with centralized guidance in `prompt_builder.py` (#88)
- Documentation refresh for the current `src/groksito_discord/` package layout (#77, #84)
- Standardized packaging with the `groksito` console entry point and editable installs (#76)
- Consolidated tool selection; removed low-value legacy tools (#75)
- Response completeness guidance centralized for closer web-Grok parity (#63, #71)
- Version aligned to `0.2.0` with rich PyPI project metadata (#101)

### Fixed

- Video generation Grok web parity: I2V aspect ratio inference, native tool offering, longer delivery TTL; removed bot-side daily quota (video, #87)
- Image edit requests deliver edited images as Discord attachments (#50)
- Test suite stabilization (#58)

### Removed

- MCP and skills system in favor of maximum nativeness (#69)
- Thin media compatibility shims (#74)
- Legacy empty `integrations/` directory (#73)
- Bot-side daily video quota unrelated to SuperGrok/xAI limits (#87)
