
# Aetherion Discord Bot

![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)
![Discord](https://img.shields.io/badge/Discord-Bot-7289da.svg)
![xAI](https://img.shields.io/badge/xAI-Grok-ff6b6b.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
[![Release](https://img.shields.io/github/v/release/lupintic/groksito-discord-bot?include_prereleases&sort=semver)](https://github.com/lupintic/groksito-discord-bot/releases)
[![GHCR](https://img.shields.io/badge/GHCR-ghcr.io%2Flupintic%2Fgroksito--discord--bot-blue?logo=docker)](https://github.com/lupintic/groksito-discord-bot/pkgs/container/groksito-discord-bot)

**Aetherion** is a standalone Discord bot that brings Grok (xAI) natively into Discord servers. It is a fully conversational experience powered directly by Grok models, with vision, tool use, and direct image/video/audio generation.

The bot is designed around "maximum nativeness": minimal custom memory or context injection, trusting Grok's long context window, native web_search / x_search, vision, and reasoning. It adds just enough Discord integration to be useful in real servers.

## ✨ Features

- **Conversational Grok in Discord**
  - Activates on direct mentions, replies to the bot, or strong directed signals in reply chains.
  - Native vision: processes images from attachments, embeds, and recent referenced messages/URLs.
  - On-demand recent conversation summaries via tool (no automatic heavy context stuffing).
  - Prompt construction optimized for cache efficiency: stable `SYSTEM_PROMPT` prefix + minimal gated dynamic context only on addressed turns.

- **Direct Media Generation (Grok-native)**
  - Image generation (`generate_image`) with Grok Imagine — supports stylized and suggestive content per Grok's model policy.
  - Image editing (`edit_image`).
  - Video generation (`generate_video`): text-to-video and image-to-video (toggleable). Offered natively on addressed turns (same pattern as images); limits come from your xAI/SuperGrok subscription, not a bot-side daily cap. Image-to-video infers aspect ratio from the reference image to avoid stretched output.
  - TTS audio (`generate_audio`): multiple voices (eve, ara, rex, sal, leo) with language control. Dedicated `/audio` slash command and context menu "🔊 Leer en voz alta".

- **Discord Interaction Tools**
  - The model controls response style via tools: `reply_to_user`, `react_to_message`, `create_thread`.
  - On-demand Discord asset tools: `get_user_avatar` (profile picture CDN URL for @mentioned users) and `get_top_server_emoji` (most-used server emote) — usable as references for image edit / image-to-video.
  - Full support for referenced messages, reply chains, and image harvesting.

- **Steam Integration**
  - Slash commands: `/stmchr` (fixed popular list), `/steamchart` (custom games), `/topgames` (live top from Steam Charts).
- **Korea rankings**
  - `/topkorea` — live top 10 from TheLog (게임순위 전체, PC bang actual data). Added 2026-06-22.
  - Rich embeds with current players, game-themed colors, thumbnails (robust CDN + fallback resolution), and direct links to Steam store.

- **xAI Authentication Options**
  - Classic `XAI_API_KEY` (stable default).
  - Experimental browser OAuth for SuperGrok / X Premium+ users (`--login-oauth`).
  - `auto` mode prefers fresh OAuth tokens with seamless fallback to API key.
  - Same bearer token used for Responses API + all image/video/TTS endpoints.
  - Docker-friendly flows (`--no-browser`, `--print-url-only` + SSH tunnel).

- **Independent Web Dashboard**
  - Separate FastAPI + Jinja2 application (run via `docker compose up web` or standalone uvicorn).
  - Status & health (live heartbeats from the bot process), guilds list, usage/quotas, configuration editor (safe keys only — secrets never exposed or overwritten).
  - Shares `data/` and `.env` via volumes in Docker. Bot and web are intentionally decoupled processes.

- **Security & Operations**
  - Guild whitelist (`ALLOWED_GUILD_IDS`) — bot ignores everything else.
  - Per-user rate limiting (6 requests / 60s sliding window) enforced before LLM calls.
  - Strict activation policy prevents replying to random user-to-user conversations.
  - All secrets via environment variables only. OAuth tokens in dedicated `./oauth/` (gitignored, Docker volume friendly).
  - Rich structured logging (cyberpunk neon banner at startup) + correlation IDs.
  - Health snapshots and heartbeats feed the dashboard even during startup/reconnects.

- **Docker & Self-hosting**
  - Multi-stage Dockerfile (full "bot" image + slim "web" dashboard image).
  - `docker-compose.yml` with separate services, recommended volume mounts for `data/` and `oauth/`.
  - `--check`, `--status`, `--auth-status`, `--test-auth` CLI commands for safe validation.

## 🚀 Installation & Running

### Prerequisites
- Python 3.11+
- Discord Bot token (https://discord.com/developers/applications)
- xAI authentication: either an `XAI_API_KEY` (console.x.ai) **or** a SuperGrok / X Premium+ account for OAuth login
- (Optional but recommended) Docker for easy deployment
- (For full video gen) ffmpeg is included in the Docker image

### Quick Start (Local)

```bash
# 1. Clone
git clone https://github.com/OniOrii/Aetherion-Grok-powered-AI.git
cd Aetherion-Grok-powered-AI

# 2. Create .env (or use scripts/configure_env.py for guided setup)
cp .env.example .env
# Edit .env — at minimum: DISCORD_BOT_TOKEN and XAI_API_KEY (or plan to use --login-oauth)

# 3. (Recommended) Editable install + validate
python -m pip install -e .
groksito --check
# or: python -m groksito_discord --check

# 4. (Optional but powerful) Login with OAuth instead of / in addition to API key
groksito --login-oauth
# or for Docker/VPS: --login-oauth --print-url-only  (then SSH tunnel from laptop)

# 5. Run the bot
groksito
# or: python -m groksito_discord
```

Useful CLI flags:
- `--check` / `--status` — validate config and show health without connecting
- `--auth-status`, `--test-auth` — verify xAI credentials (OAuth or key)
- `--login-oauth`, `--logout-oauth`

### Docker (Recommended for 24/7)

```bash
# Full stack (bot + web dashboard on :8010)
docker compose up -d

# Web dashboard only
docker compose up web

# Login OAuth from the container (no browser inside)
docker compose run --rm groksito-discord-bot --login-oauth --print-url-only
```

> **Using pre-built images?** The examples above build locally. For pre-built GHCR images (including the latest pre-release), see the **Pre-built images (GHCR)** section below and enable the `image:` lines in `docker-compose.yml`.

Access the dashboard at http://localhost:8010 (or the port you mapped).

#### Pre-built images (GHCR)

Released versions (including pre-releases) are published automatically to [GitHub Container Registry](https://github.com/lupintic/groksito-discord-bot/pkgs/container/groksito-discord-bot).

**Latest pre-release:**

```bash
docker pull ghcr.io/lupintic/groksito-discord-bot:0.2.0-pre.1
docker pull ghcr.io/lupintic/groksito-discord-bot-web:0.2.0-pre.1
```

**Stable releases** also get a `:latest` tag (bot only):

```bash
docker pull ghcr.io/lupintic/groksito-discord-bot:latest
```

Pin to a specific commit with `sha-<short>` tags (for example `sha-d645292`). Pre-release tags publish version tags but **not** `:latest`.

To run pre-built images with compose, uncomment the `image:` lines in `docker-compose.yml` and comment out the matching `build:` blocks.

## 📖 Usage

- Mention `@Aetherion` or reply directly to the bot → it activates.
- Strong signals (e.g. "qué es eso de arriba", "genera una imagen de...", "lee esto en voz alta") in replies to other users can also wake it (conservative policy).
- Use `/audio` or right-click message → Apps → "🔊 Leer en voz alta" for TTS.
- Steam: `/stmchr`, `/steamchart`, `/topgames`.
- Korea: `/topkorea` (TheLog PC bang top 10)
- The web dashboard (`/config`, `/usage`, `/guilds`, etc.) lets you tweak safe settings without touching secrets.

Example interactions are natural Spanish/English conversation. The bot is intentionally low-ceremony.

## 🏗️ Architecture & Internals

See [ARCHITECTURE.md](./ARCHITECTURE.md) for component breakdown, data flow, the hybrid tool system, media stack, OAuth handling, and extension points.

High-level pieces live under `src/groksito_discord/`:
- `main.py` — CLI entry (`groksito` console script).
- `discord/client.py` — Gateway connection, slash commands, heartbeats, rate limits.
- `core/conversation.py` — activation policy, vision harvest, referenced-message context.
- `llm/client.py` + `llm/llm_input.py` — Responses API orchestration and input building. `llm_input.py` is the single source of truth: always one stable `SYSTEM_PROMPT` system message; dynamic referent/emoji context (when present) is folded into the user message for prompt cache efficiency.
- `llm/tools.py` + `llm/media_tools.py` — tiered custom tools and media intent gates.
- `media/*_handler.py` + `media/delivery.py` — image/video/audio generation and direct delivery.
- `discord/integrations/steam.py` — Steam player counts and embed data for slash commands.
- `core/grok_oauth.py` — OAuth PKCE + token management.
- `context/` — short-term per-channel history (persisted as `data/pantsu_context.json`; legacy filename, see ARCHITECTURE.md).
- `web/` — independent FastAPI dashboard (reuses `utils/env_utils` + `config`).

## 🛠️ Development & Configuration

- All runtime configuration is in `.env` (Pydantic `GroksitoSettings`).
- Key flags: `GROK_AUTH_MODE`, `ALLOWED_GUILD_IDS`, `ENABLE_VIDEO_GENERATION`, TTS voice/language, etc.
- The web `/config` page edits only whitelisted safe keys and creates timestamped backups on every save.
- Add new custom tools by extending the schemas/handlers in `llm/tools.py` and registering them in the tiered selection logic.
- Tests live in `tests/`. Run with `pytest`.
- Full modernization verification: `python scripts/check.py` (pytest + `--check` + `--status`; add `--skip-docker` to skip image builds).

Never commit `.env` or `oauth/xai_oauth_tokens.json`.

### Repository layout

Committed project roots: `src/`, `tests/`, `web/`, `data/.gitkeep`, Docker files, and root docs (`README.md`, `ARCHITECTURE.md`, `GROK_OAUTH.md`).

- `data/` — runtime state written by the bot (heartbeats, context, Steam app-list cache). Contents are gitignored except the empty `data/.gitkeep` placeholder.
- `oauth/` — OAuth tokens from `--login-oauth` (gitignored).
- `docs/`, `AGENTS.md`, `.grok/`, `mcps/`, `agent-tools/`, `terminals/` — local agent/workflow artifacts when developing with AI tooling. Not part of the Discord bot runtime; never commit them.

## 📄 License

MIT License — see [LICENSE](./LICENSE).

## 🤝 Contributing

Contributions, bug reports, and feature ideas are welcome.

See the full [CONTRIBUTING.md](./CONTRIBUTING.md) guide (development setup, philosophy, process, what not to do).

Maintainers: see [RELEASE.md](./RELEASE.md) for the pre-release and stable release process (version bumps, tagging, GHCR publishing).

We also maintain a [Code of Conduct](./CODE_OF_CONDUCT.md) and [Security Policy](./SECURITY.md).

Quick summary:
1. Fork the repo
2. Create a feature branch
3. Make focused changes + add tests when reasonable
4. Run verification (`python scripts/check.py --skip-docker`)
5. Open a Pull Request (use the template)

Keep changes focused and respect the "maximum nativeness" philosophy.

## 🙏 Credits

- Built with heavy iteration using Grok models and tooling.
- Thanks to the xAI team for the Grok models and APIs.
- Steam data via public Steam Charts + store APIs (no affiliation).

---

**Status**: Active. Self-hostable with Docker. Focused on a clean, powerful, and natural Grok-in-Discord experience.

**Recent addition (2026-06-22):** New `/topkorea` command for Korean PC bang game rankings (TheLog). Implementation notes + design in `docs/superpowers/`. Updated by Grok following superpowers workflow (brainstorm → design spec → plan → execute).

Made with ❤️ by [@lupintic](https://github.com/lupintic).
Maintained and rebranded by [@OniOrii](https://github.com/OniOrii). as Aetherion.
