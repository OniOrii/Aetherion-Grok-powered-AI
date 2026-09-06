# Aetherion Web Dashboard

Independent FastAPI + Jinja2 + Tailwind dashboard for Aetherion.

## Running

### Locally (after installing web deps)
```bash
pip install -r requirements.txt
uvicorn web.main:app --reload --port 8010
```

### With Docker Compose
```bash
docker compose up web
```

Access at http://localhost:8010

## Features
- **Dashboard**: Quick status + stats cards.
- **Configuration**: Grouped editor for safe settings. Defensive `.env` writer with automatic backups.
- **Usage & Quotas**: Live data from shared `data/` files.

## Configuration editing
- Only whitelisted safe keys are shown/editable.
- Secrets (`XAI_API_KEY`, `DISCORD_BOT_TOKEN`, OAuth values, `oauth/xai_oauth_tokens.json`) are **never loaded into the form** and **can never be deleted or overwritten** by the web UI.
- After saving `.env`, restart the bot:
  ```bash
  docker compose restart aetherion-discord-bot
  ```

## Architecture notes
- Completely separate from the bot process.
- Reuses the same data volume for quotas/context.
- Uses the shared `.env` for config editing.
- Import path for shared modules remains `groksito_discord` so production deploys do not break.
