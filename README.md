# Aetherion Discord Bot

![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)
![Discord](https://img.shields.io/badge/Discord-Bot-7289da.svg)
![xAI](https://img.shields.io/badge/xAI-Grok-ff6b6b.svg)

**Aetherion** is a standalone Discord bot that brings Grok (xAI) into a real server: text chat, vision, image/video/audio generation, live voice, SoundCloud music on the same voice connection, and play-money games with **Aether Coins**.

Forked from [lupintic/groksito-discord-bot](https://github.com/lupintic/groksito-discord-bot) and rebuilt as Aetherion by [@OniOrii](https://github.com/OniOrii).

See [CHANGELOG.md](./CHANGELOG.md) for dated history. Every shipped change is logged there.

## What it can do

### Chat with Grok
- Activates on a mention, a reply to Aetherion, or a clearly directed message.
- Reads images from attachments, embeds, and recent reply-chain pictures.
- Can search the web, generate or edit images, generate video (when enabled), and speak text out loud.
- Default spoken voice is **Zagan**. Other Grok voices: Ara, Eve, Rex, Sal, Leo.
- `/help` explains commands with topic pages.

### Live voice
- `/join` while you are already in a voice channel. `/leave` to disconnect.
- Listens to the member who last ran `/join`.
- Wake word: say **Aetherion**, then the question, then pause.
- Replies play back in the same channel. New speech is ignored until the current reply finishes.

### Music (SoundCloud only)
- Slash: `/play query:...`, `/pause`, `/stop`.
- Voice: **Aetherion play …**, **Aetherion pause**, **Aetherion stop**.
- Resolves a SoundCloud title or a `soundcloud.com` link and streams it with ffmpeg.
- YouTube, YouTube Music, Mixcloud, and Audiomack links are rejected on purpose.

### Aether Coins
Play-money wallet in `data/ai_coins.json`. New players start with **500**. Bets and grants move in **tens**.

- `/balance` — your wallet.
- `/daily` — **500** Aether Coins once per Eastern day.
- `/leaderboard` — top wallets on this server.
- `/givecoins` — Ori only, 10–10,000 coins to a member.

### Games
- `/blackjack` — fair dealer, Hit / Stand / Double, table art, Play Again.
  - Bet **10–1,000**.
- `/slots` — Cosmos Wheel, Nebula, Event Horizon.
  - Bet **100–10,000**. Corner cabinet thumbnail. Spin Again / Change Bet.
- `/cointoss` — Heads or Tails, falling coin animation.
  - Odds **48% / 48% / 2% side**. Side pays **2.5x**. Bet **10–10,000**.

### Server tools
- `/reactionrole post|add|remove|list|colors` — exclusive color roles (Administrators).
- `/welcome` — welcome-banner channel (Administrators).
- `/datechannel` — voice channel renamed at midnight Eastern (Administrators).
- `/purge` — delete up to 100 recent messages (Administrators).
- `/edit` — Ori only, rewrite text Aetherion already posted.
- `/status` — Ori only, set Aetherion's status bubble.
- `/audio` — TTS in the current text channel. Right-click a message → Apps → **Leer en voz alta**.
- `/ping` — alive check.
- `/help` — command guide with a topic dropdown.

## Slash command list

| Command | Who | What |
| --- | --- | --- |
| `/help` | anyone | How the bot works |
| `/join` `/leave` | anyone | Voice session |
| `/play` `/pause` `/stop` | anyone | SoundCloud on that session |
| `/blackjack` | anyone | Cards vs Aetherion |
| `/slots` | anyone | Three machines |
| `/cointoss` | anyone | Coin flip |
| `/balance` `/daily` `/leaderboard` | anyone | Wallet |
| `/givecoins` | Ori | Grant coins |
| `/audio` | anyone | Speak text in-channel |
| `/ping` | anyone | Awake check |
| `/welcome` `/datechannel` `/purge` `/reactionrole` | Administrators | Server setup |
| `/edit` `/status` | Ori | Bot text and presence |

## Install and run

### Need
- Python 3.11+
- Discord bot token
- `XAI_API_KEY` (or SuperGrok / X Premium+ OAuth)
- `davey` for encrypted voice
- `yt-dlp` + ffmpeg for SoundCloud playback (yt-dlp is the downloader; it does **not** play YouTube here)

### Local

```bash
git clone https://github.com/OniOrii/Aetherion-Grok-powered-AI.git
cd Aetherion-Grok-powered-AI
cp .env.example .env
# Set DISCORD_BOT_TOKEN and XAI_API_KEY
python -m pip install -e .
groksito --check
groksito
```

Useful flags: `--check`, `--status`, `--auth-status`, `--test-auth`, `--login-oauth`, `--logout-oauth`.

### Docker

```bash
docker compose up -d
```

Dashboard: http://localhost:8010

### Railway

Point the service at this repo. Set `DISCORD_BOT_TOKEN` and `XAI_API_KEY`. After a GitHub push, wait until the deployment is **Active** before testing commands.

## Usage

- Mention `@Aetherion` or reply to it in text.
- Voice: join a VC, `/join`, say **Aetherion** then the question.
- Music: `/play query: song or soundcloud url`. Do not paste a YouTube link.
- Games: `/blackjack`, `/slots`, `/cointoss`. Claim `/daily` once a day.
- Admins: `/welcome`, `/datechannel`, `/reactionrole colors`, `/purge`.
- `/help` for the in-Discord command guide.

## Layout

High-level pieces under `src/groksito_discord/`:

- `discord/slash_commands.py` — wires every slash module.
- `discord/slash_help.py` — `/help` pages.
- `discord/slash_blackjack.py`, `slash_slots.py`, `slash_cointoss.py` — games.
- `discord/ai_coins.py` — wallets, daily drip, grants.
- `discord/slash_music.py` + `media/voice_music.py` — SoundCloud only.
- `media/voice_session.py` — DAVE decrypt, wake word, STT, TTS.
- `discord/reaction_roles.py`, `welcome.py`, `date_dock.py` — server utilities.
- `core/conversation.py` — when Grok answers in text.
- `web/` — optional FastAPI dashboard.

Runtime files live in `data/` (wallets, date dock, welcome channel, context). OAuth tokens live in `oauth/`. Neither folder is committed except `data/.gitkeep`.

More internals: [ARCHITECTURE.md](./ARCHITECTURE.md). OAuth: [GROK_OAUTH.md](./GROK_OAUTH.md).

## Credits

- Built and maintained by [@OniOrii](https://github.com/OniOrii) as **Aetherion**.
- Started from [lupintic/groksito-discord-bot](https://github.com/lupintic/groksito-discord-bot).
- Grok models and APIs by xAI.

**Status:** Active. Self-hostable with Docker or Railway. Talks in voice, plays SoundCloud on that same connection, and runs blackjack / slots / coin toss on Aether Coins.
