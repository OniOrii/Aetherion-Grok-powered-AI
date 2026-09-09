# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Last-10 per-user conversation memory for text chat and voice (used only when Aetherion needs to recall something)
- Name-address: saying Aetherion / Ethereon / Aetheron / Groksito counts as talking to the bot, same as a ping
- Live Discord voice session: `/join` / `/leave`, DAVE decrypt, wake word, Ara TTS, Agent Tools web search
- Voice wake-word aliases (Atherion, Aetherian, A Theory on, Athena, Theorion, Atheorion, and others)
- Music on the same voice connection (no Lavalink): say **Aetherion play …** or use slash commands
- `/play`, `/pause` (toggles resume), `/stop` for YouTube audio / podcast-style videos
- Optional YouTube cookies for `/play` on Railway (`YOUTUBE_COOKIES`, `YOUTUBE_COOKIES_B64`, or `YOUTUBE_COOKIES_FILE`)
- `/datechannel` Eastern-midnight date dock and `/welcome` banners
- `aetherion` console script (Railway still accepts `groksito`)
- `yt-dlp` dependency for resolving play queries

### Changed
- Live VC replies use light reasoning (`VOICE_REASONING_EFFORT=low`) and a short answer cap so spoken answers start sooner; text chat still uses full `GROK_MODEL`
- System prompt identity so Aetherion answers as itself and stays on the current thread in text chat
- Project metadata, dashboard, and user-facing strings rebranded from Groksito to Aetherion
- Package import path remains `groksito_discord` so existing deploys keep starting
- Date dock sleeps until 12:00 AM Eastern instead of polling every 10 minutes
- Voice decrypt falls back to the member who ran `/join` when Discord has not mapped their SSRC yet

### Fixed
- `/join` from a second member could connect the bot but never transcribe their voice
- Play requests that started with extra STT noise (`Atherion - Play …`) skipped the music handler

### Removed
- Upstream `CONTRIBUTING.md`
- Slash commands `/stmchr`, `/versus`, `/topkorea`, `/topgames`, `/steamchart`, `/mislimites`

## [0.2.0] - 2026-06-17

First pre-release baseline. Seeded from merged work on `main` through the modernization
roadmap, native-behavior improvements, and release automation.
