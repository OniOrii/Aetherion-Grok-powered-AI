# Aetherion Discord Bot

![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)
![Discord](https://img.shields.io/badge/Discord-Bot-7289da.svg)
![xAI](https://img.shields.io/badge/xAI-Grok-ff6b6b.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

**Aetherion** is a standalone Discord bot that brings Grok (xAI) natively into Discord servers — text, media, and live voice. It is a fully conversational experience powered directly by Grok models, with vision, tool use, direct image/video/audio generation, and a voice-channel listener that talks back.

The bot is designed around "maximum nativeness": minimal custom memory or context injection, trusting Grok's long context window, native web search, vision, and reasoning. It adds just enough Discord integration to be useful in a real server: slash commands, a date dock, welcome banners, and a DAVE-aware voice session.

Forked from [lupintic/groksito-discord-bot](https://github.com/lupintic/groksito-discord-bot) and rebuilt as Aetherion by [@OniOrii](https://github.com/OniOrii).

## ✨ Features

- **Conversational Grok in Discord**
  - Activates on direct mentions, replies to the bot, or strong directed signals in reply chains.
  - Native vision: processes images from attachments, embeds, and recent referenced messages/URLs.
  - On-demand recent conversation summaries via tool (no automatic heavy context stuffing).
  - Prompt construction optimized for cache efficiency: stable `SYSTEM_PROMPT` prefix + minimal gated dynamic context only on addressed turns.

- **Live voice in a Discord VC**
  - `/join` while you are already in a voice channel. `/leave` to disconnect.
  - Joins with stock `discord.VoiceClient` so discord.py can finish the DAVE handshake, then decrypts inbound Opus with `davey`.
  - Listens only to the member who ran `/join`.
  - Wake word required: say **Aetherion** (STT aliases like Atherion, A Theory on, Athena, Thea, Iryan still count).
  - Pipeline: silence-gated PCM → xAI STT → Grok (`/v1/responses` + `web_search`) → Ara TTS back into the channel.
  - Ignores new speech until the current reply finishes playing.
  - Strips URLs and `[[1]](...)` citations so it does not read links out loud.
  - Clock is injected as America/Detroit so "what time is it" is not a guess.

- **Date dock**
  - `/datechannel` (Manage Server) pins a locked voice channel that shows today's date.
  - Renames it every night at 12:00 AM Eastern to `📅️ | Saturday, Sep 6th` (example).
  - Re-checks every 10 minutes so a restart cannot leave yesterday sitting all day.
  - Saved per guild in `data/date_channels.json`.

- **Welcome banners**
  - `/welcome` (Manage Server) sets the text channel for new-member banners.
  - Posts when someone joins; stored per guild.

- **Direct Media Generation (Grok-native)**
  - Image generation (`generate_image`) with Grok Imagine — supports stylized and suggestive content per Grok's model policy.
  - Image editing (`edit_image`).
  - Video generation (`generate_video`): text-to-video and image-to-video (toggleable).
  - TTS audio (`generate_audio`): voices include ara, eve, rex, sal, leo. Dedicated `/audio` slash command and context menu "🔊 Leer en voz alta". Voice-channel replies use **Ara** by default.

- **Discord Interaction Tools**
  - The model controls response style via tools: `reply_to_user`, `react_to_message`, `create_thread`.
  - On-demand Discord asset tools: `get_user_avatar` and `get_top_server_emoji`.
  - Full support for referenced messages, reply chains, and image harvesting.

- **Games & live data**
  - `/stmchr`, `/steamchart`, `/topgames` — Steam player counts and store embeds.
  - `/versus` — two games head-to-head on Steam players vs Twitch viewers.
  - `/topkorea` — TheLog PC bang top 10.
  - `/korea50` — Gamemeca weekly top 50 (English names, cached daily).
  - `/ping` — alive check. `/mislimites` — remaining rate-limit tokens.

- **xAI Authentication Options**
  - Classic `XAI_API_KEY` (stable default).
  - Experimental browser OAuth for SuperGrok / X Premium+ users (`--login-oauth`).
  - `auto` mode prefers fresh OAuth tokens with seamless fallback to API key.
  - Same bearer token used for Responses API + image/video/TTS/STT.

- **Independent Web Dashboard**
  - Separate FastAPI + Jinja2 application (`docker compose up web` or uvicorn).
  - Status & health, guilds, usage/quotas, configuration editor (safe keys only).
  - Shares `data/` and `.env` via volumes in Docker.

- **Security & Operations**
  - Guild whitelist (`ALLOWED_GUILD_IDS`) — bot ignores everything else.
  - Per-user rate limiting (6 requests / 60s) before LLM calls.
  - Strict activation policy in text; wake word in voice.
  - All secrets via environment variables. OAuth tokens in `./oauth/` (gitignored).
  - Structured logging + correlation IDs. Health snapshots feed the dashboard.

- **Docker, Railway & self-hosting**
  - Multi-stage Dockerfile (bot image + slim web dashboard image).
  - `docker-compose.yml` with separate services and volume mounts for `data/` and `oauth/`.
  - Railway-friendly: one service, env vars, `davey` in requirements so DAVE decrypt works in production.
  - `--check`, `--status`, `--auth-status`, `--test-auth` CLI commands for safe validation.

## 🚀 Installation & Running

### Prerequisites
- Python 3.11+
- Discord Bot token (https://discord.com/developers/applications)
- xAI authentication: an `XAI_API_KEY` (console.x.ai) **or** a SuperGrok / X Premium+ account for OAuth
- `davey` for encrypted voice (`pip install davey` — already in project requirements)
- ffmpeg for VC playback and video (bundled in the Docker image)
- (Optional) Docker or Railway for 24/7

### Quick Start (Local)

```bash
# 1. Clone
git clone https://github.com/OniOrii/Aetherion-Grok-powered-AI.git
cd Aetherion-Grok-powered-AI

# 2. Create .env
cp .env.example .env
# Edit .env — at minimum: DISCORD_BOT_TOKEN and XAI_API_KEY

# 3. Editable install + validate
python -m pip install -e .
groksito --check
# or: python -m groksito_discord --check

# 4. (Optional) OAuth instead of / in addition to API key
groksito --login-oauth

# 5. Run
groksito
# or: python -m groksito_discord
```

Useful CLI flags:
- `--check` / `--status` — validate config without connecting
- `--auth-status`, `--test-auth` — verify xAI credentials
- `--login-oauth`, `--logout-oauth`

### Docker

```bash
docker compose up -d
```

Dashboard: http://localhost:8010

### Railway

Point the service at this repo, set `DISCORD_BOT_TOKEN` and `XAI_API_KEY`, keep `davey` in the install. After each GitHub push, wait until the deployment is **Active** before testing `/join` — an old build will not have the latest voice code.

## 📖 Usage

- Mention `@Aetherion` or reply directly to the bot → it activates in text.
- Voice: join a VC, run `/join`, say **Aetherion** then the question, pause. `/leave` when done.
- `/datechannel` on a voice channel → that channel becomes the daily date dock (Eastern midnight).
- `/welcome` on a text channel → new-member banners land there.
- `/audio` or right-click a message → Apps → "🔊 Leer en voz alta" for TTS in-channel.
- Steam / Twitch: `/stmchr`, `/steamchart`, `/topgames`, `/versus`.
- Korea: `/topkorea`, `/korea50`.
- `/ping`, `/mislimites`.

Example interactions are natural English/Spanish conversation. The bot is intentionally low-ceremony.

## 🏗️ Architecture & Internals

See [ARCHITECTURE.md](./ARCHITECTURE.md) for component breakdown, data flow, the hybrid tool system, media stack, OAuth handling, and extension points.

High-level pieces live under `src/groksito_discord/`:
- `main.py` — CLI entry (`groksito` console script).
- `discord/client.py` — Gateway connection, slash commands (`/join`, `/leave`, `/datechannel`, `/welcome`, Steam, Korea), heartbeats, rate limits.
- `discord/date_dock.py` — Eastern-midnight voice-channel rename loop.
- `discord/welcome.py` — new-member banners.
- `core/conversation.py` — activation policy, vision harvest, referenced-message context.
- `llm/client.py` + `llm/llm_input.py` — Responses API orchestration and input building.
- `llm/tools.py` + `llm/media_tools.py` — tiered custom tools and media intent gates.
- `media/voice_session.py` — DAVE decrypt, wake word, STT, web search, Ara TTS, playback lock.
- `media/*_handler.py` + `media/delivery.py` — image/video/audio generation and direct delivery.
- `discord/integrations/steam.py` / `twitch.py` / `thelog.py` / `gamemeca.py` — live game data.
- `core/grok_oauth.py` — OAuth PKCE + token management.
- `context/` — short-term per-channel history (`data/pantsu_context.json`; legacy filename).
- `web/` — independent FastAPI dashboard.

## 🛠️ Development & Configuration

- All runtime configuration is in `.env` (Pydantic settings).
- Key flags: `GROK_AUTH_MODE`, `ALLOWED_GUILD_IDS`, `ENABLE_VIDEO_GENERATION`, TTS voice/language.
- Voice needs `davey` installed in the running environment or DAVE decrypt never starts.
- The web `/config` page edits only whitelisted safe keys and creates timestamped backups on every save.
- Add new custom tools by extending the schemas/handlers in `llm/tools.py`.
- Tests live in `tests/`. Run with `pytest`.
- Full verification: `python scripts/check.py` (add `--skip-docker` to skip image builds).

Never commit `.env` or `oauth/xai_oauth_tokens.json`.

### Repository layout

Committed project roots: `src/`, `tests/`, `web/`, `data/.gitkeep`, Docker files, and root docs (`README.md`, `ARCHITECTURE.md`, `GROK_OAUTH.md`).

- `data/` — runtime state (heartbeats, context, Steam cache, `date_channels.json`, welcome channel ids). Gitignored except `data/.gitkeep`.
- `oauth/` — OAuth tokens from `--login-oauth` (gitignored).

## 📄 License

MIT License — see [LICENSE](./LICENSE).

## 🤝 Contributing

Contributions, bug reports, and feature ideas are welcome.

See [CONTRIBUTING.md](./CONTRIBUTING.md) if present. Keep changes focused and respect the "maximum nativeness" philosophy.

## 🙏 Credits

- Built and maintained by [@OniOrii](https://github.com/OniOrii) as **Aetherion**.
- Started from [lupintic/groksito-discord-bot](https://github.com/lupintic/groksito-discord-bot).
- Grok models and APIs by xAI.
- Steam / Twitch / TheLog / Gamemeca data via public sources (no affiliation).

---

**Status**: Active. Self-hostable with Docker or Railway. Focused on a clean Grok-in-Discord experience that also talks in voice.
