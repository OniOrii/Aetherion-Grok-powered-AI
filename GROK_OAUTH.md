# xAI OAuth for Aetherion (SuperGrok / X Premium+)

Aetherion supports authenticating to xAI services using browser-based OAuth 2.0 + PKCE instead of (or in addition to) a classic `XAI_API_KEY`. This allows users with an active SuperGrok or X Premium+ subscription to use their existing quota for:

- Grok chat / Responses API (the main conversational brain)
- Image generation (`/v1/images/generations`)
- Image editing (`/v1/images/edits`)
- Video generation and polling

No `XAI_API_KEY` is required when a valid OAuth access token is present. The same bearer token works across all endpoints.

**Important**: OAuth tokens are stored in `oauth/xai_oauth_tokens.json`. This directory and file are covered by `.gitignore` and must never be committed. See the Security section below and the main [README.md](./README.md).

## Quick Commands

```bash
# One-time login (opens browser by default)
groksito --login-oauth

# Status and verification
groksito --auth-status
groksito --test-auth     # performs a real minimal call with the token

# Variants
groksito --login-oauth --no-browser
groksito --login-oauth --print-url-only
groksito --login-oauth --manual-paste
groksito --logout-oauth
```

After a successful login, set in your `.env` (recommended for clarity):

```env
GROK_AUTH_MODE=auto          # or "oauth" for strict (no API key fallback)
# GROK_MODEL=grok-4.3
```

`auto` (recommended) prefers a fresh OAuth token when present and automatically falls back to `XAI_API_KEY` only if no valid OAuth token is available. You can keep both for redundancy.

## How It Works (High Level)

- Standard OAuth 2.0 + PKCE (S256 code challenge).
- Loopback redirect: `http://127.0.0.1:56121/callback` (configurable via `GROK_OAUTH_PORT`).
- Short-lived local HTTP listener during the login flow only.
- Tokens (access + refresh) stored at `./oauth/xai_oauth_tokens.json`.
- **Proactive refresh**: the client refreshes the access token ~15 minutes before expiry when it is about to be used.
- Reactive refresh on 401 responses during normal operation.
- On `invalid_grant` or revoked refresh token: the local token file is cleared with a clear message instructing you to re-login.
- 403 during login or use often indicates a tier/subscription restriction on the OAuth surface for that account (you can still fall back to a regular `XAI_API_KEY`).

The exact same bearer string is used for the Responses client and raw `Authorization: Bearer ...` headers for Imagine/Video endpoints.

## Local Development (Easiest)

1. `cp .env.example .env`
2. (Optional) Set `GROK_AUTH_MODE=auto` (or `oauth`)
3. `groksito --login-oauth`
4. Browser opens → log in with the X account that has SuperGrok / Premium+.
5. Approve the Aetherion (or "Grok CLI") client.
6. Callback received → tokens saved locally.
7. Run `groksito --auth-status` and `--test-auth` (strongly recommended).
8. Start the bot normally.

You can leave an `XAI_API_KEY` in the file; it will only be used as fallback when no valid OAuth token is available.

## Remote / VPS / Docker / Headless (24/7 Bots)

The running container has no browser. Use one of the following flows.

### Recommended: `--print-url-only` + SSH tunnel

On the server (or via `docker compose run`):

```bash
docker compose run --rm groksito-discord-bot --login-oauth --print-url-only
# or without compose:
groksito --login-oauth --print-url-only
```

Copy the printed authorization URL.

From your laptop (the machine with the browser):

```bash
ssh -L 56121:localhost:56121 user@your-server
```

While the tunnel is open, paste the copied URL into your laptop browser, complete the SuperGrok / X login + approval. The callback travels through the tunnel back to the server process. Tokens are written to the host `./oauth` directory (thanks to the volume mount).

Restart (or let) the main bot container pick up the new tokens.

### Alternative: `--no-browser` + port publish or tunnel

Publish the port temporarily or use the same SSH tunnel technique. Then run with `--no-browser` and open the printed URL from the machine that has browser access.

### Manual paste fallback

```bash
groksito --login-oauth --manual-paste
```

Open the printed URL on any machine with a browser, complete login, then paste the full callback URL (or just the `code=...` value) back into the terminal on the server.

## Configuration Variables

| Variable                  | Purpose                                           | Default                              |
|---------------------------|---------------------------------------------------|--------------------------------------|
| `GROK_AUTH_MODE`          | `api_key`, `oauth`, or `auto`                     | `api_key`                            |
| `GROK_MODEL`              | Model for Responses (and test calls)              | `grok-4.3`                           |
| `GROK_OAUTH_PORT`         | Loopback port for the OAuth callback              | `56121`                              |
| `GROK_OAUTH_TOKEN_FILE`   | Override token storage location                   | `./oauth/xai_oauth_tokens.json`      |

In `auto` mode (or whenever a token file exists), the runtime always prefers a fresh OAuth access token.

## Docker Volume for Token Persistence

The provided `docker-compose.yml` includes:

```yaml
volumes:
  - ./data:/app/data
  - ./oauth:/app/oauth     # tokens survive container restarts
```

Create the host directory if desired:

```bash
mkdir -p ./oauth
```

The image creates `/app/oauth` at build time. The volume ensures tokens written during `docker compose run --login-oauth` are visible to the main bot container.

## Troubleshooting

**"Port 56121 already in use" during login**
- Use `--manual-paste`.
- Or set `GROK_OAUTH_PORT=56122` (and tunnel the new port).
- Kill any previous listener process.

**403 / "tier" / "forbidden" during login or first call**
- Some SuperGrok / Premium+ tiers have different access rules on the `accounts.x.ai` OAuth surface vs the console API key surface.
- Reliable workaround: keep (or obtain) a regular `XAI_API_KEY` from console.x.ai and use `GROK_AUTH_MODE=api_key` (or `auto` with no token file present).

**invalid_grant / "refresh token is invalid"**
- The refresh token was revoked or rotated too many times (long inactivity, account changes, etc.).
- Run `--login-oauth` again. The old local token file is automatically cleared on this error.

**After login, `--auth-status` reports no token**
- Verify the exact path printed during login matches what `--auth-status` reports.
- For Docker: confirm the `./oauth` volume is correctly mounted and the `docker compose run` wrote to the host directory.
- Check `ls -l ./oauth` and permissions (the file should be readable by the bot process).

**Video or image generation fails with auth error but chat works**
- All code paths use the same `get_grok_bearer()`. If one path works, the bearer is good.
- Check for separate quota/tier limits on the Imagine/Video surface (some subscriptions have daily video caps, etc.).

**Force the classic API key even though a token file exists**
- Delete or rename `./oauth/xai_oauth_tokens.json`, or run `--logout-oauth`.
- Or simply do not run `--login-oauth` and keep `GROK_AUTH_MODE=api_key`.

## Quotas, Tiers, and Differences from API Keys

- OAuth consumes your **SuperGrok / X Premium+ subscription quota** (not the pay-per-token developer API key pool).
- Rate limits and media allowances are enforced by xAI/SuperGrok on the API side (Aetherion does not apply a separate bot-side video daily cap).
- Some accounts encounter 403s only on the OAuth client surface.
- The functional experience (models, tools, endpoints) is otherwise identical.

If you hit limits or 403s you cannot accept, the classic `XAI_API_KEY` path remains fully supported and is the stable default for many users.

## Security Notes

- The token file contains a refresh token. Protect the `./oauth` directory (the code attempts restrictive permissions where possible).
- **Never commit** `oauth/xai_oauth_tokens.json` or any `.env` file containing real credentials. These paths are explicitly listed in `.gitignore`.
- The login flow is a one-time owner-only setup step. The Discord bot itself does not perform per-user Discord OAuth for Grok.
- Treat the OAuth tokens with the same care as an `XAI_API_KEY`.

## Updating / Re-login / Logout

- Run `--login-oauth` again at any time. It will overwrite the token file with fresh tokens (including a new refresh token).
- `--logout-oauth` clears only the local file (it does not revoke tokens server-side; use your X account settings if you want to revoke access).

## Testing After Setup (No Discord Required)

```bash
groksito --auth-status
groksito --test-auth
groksito --status
```

`--test-auth` performs a minimal real Grok call using the exact bearer the rest of the bot will use.

## References

- Implementation: `src/groksito_discord/core/grok_oauth.py`
- CLI entry: `src/groksito_discord/main.py` (`groksito` console script)
- Central credential helper: `get_grok_bearer()`
- All LLM and media paths route through the same credential mechanism.
- Related config: `GROK_AUTH_MODE`, related `using_oauth` / `auth_prefers_oauth` logic.

See the main [README.md](./README.md) for overall setup, Docker usage, and the security note about secrets. See [ARCHITECTURE.md](./ARCHITECTURE.md) for how authentication fits into the broader system.
