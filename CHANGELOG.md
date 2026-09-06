# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Live Discord voice session: `/join` / `/leave`, DAVE decrypt, wake word, Ara TTS, Agent Tools web search
- `/datechannel` Eastern-midnight date dock and `/welcome` banners
- `aetherion` console script (Railway still accepts `groksito`)

### Changed
- Project metadata, dashboard, and user-facing strings rebranded from Groksito to Aetherion
- Package import path remains `groksito_discord` so existing deploys keep starting

### Fixed

### Removed
- Upstream `CONTRIBUTING.md`

## [0.2.0] - 2026-06-17

First pre-release baseline. Seeded from merged work on `main` through the modernization
roadmap, native-behavior improvements, and release automation.

### Added

- Long Discord responses split across multiple messages instead of truncating (message splitting, #92)
- Proactive native `web_search` + `x_search` for time-sensitive and live topics (native search, #91)
- Prompt caching improvements: stable single system-message prefix and folded dynamic context (prompt caching, #93)
- `/versus` slash command comparing games on Steam and Twitch (#54)
- `/audio` TTS help embed documenting xAI Speech Tags (#56)
- GitHub Actions CI workflow: pytest matrix, packaging validation, Docker builds (#67, #101)
- GitHub Actions release workflow: GitHub Releases, Python sdist/wheel artifacts, GHCR Docker images (release, #96, #101)
- GitHub community standards: Code of Conduct, Contributing guide, Security policy, issue/PR templates (community standards, #95)
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
