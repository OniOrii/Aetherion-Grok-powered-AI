# Security Policy

## Supported Versions

We release patches for security vulnerabilities on the latest `main` branch. Aetherion is at version 0.2.0 with active development on main.

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| 0.2.0   | :white_check_mark: |
| < 0.1.0 | :x:                |

## Reporting a Vulnerability

**Preferred:** Use GitHub's private vulnerability reporting at  
https://github.com/OniOrii/Aetherion-Grok-powered-AI/security/advisories/new

This is the fastest and most secure channel. You will receive an acknowledgment within 48 hours (usually sooner). We will keep you informed of progress.

**Fallback:** If private reporting is unavailable, contact the maintainer [@OniOrii](https://github.com/OniOrii) or open a private issue and clearly mark it as a security report. Do **not** open a public issue for vulnerabilities.

Please include:
- Description of the issue and potential impact
- Steps to reproduce (if applicable)
- Affected versions / commit
- Any suggested fixes or mitigations

## Scope (Tailored to This Project)

The following areas are in scope for security reports:

- Authentication and secrets handling: `XAI_API_KEY`, `DISCORD_BOT_TOKEN`, OAuth flows and `oauth/xai_oauth_tokens.json` storage (see GROK_OAUTH.md).
- Web dashboard configuration editor: **must never load, display, or overwrite secrets**.
- Media delivery sentinel pattern (`media/delivery.py`): ensures the LLM never receives real asset URLs.
- Rate limiting and activation policy (enforced before any LLM work in `discord/client.py` + `core/conversation.py`).
- Voice session DAVE decrypt path (`media/voice_session.py`).
- Guild whitelist (`ALLOWED_GUILD_IDS`).
- All secrets via environment variables only; `oauth/` directory handling.
- Direct delivery invariants and separation of bot vs. web processes.

Out of scope (example):
- General Discord rate limits or third-party service behavior (Steam, xAI upstream).
- Issues in dependencies unless they have direct impact on the above.

## Security Practices in the Codebase

- All sensitive configuration is in `.env` (never committed) + `oauth/` (gitignored).
- Web dashboard shares `.env` volume for safe keys only; full atomic backup + verification on writes.
- Guild + rate limit gates happen before any LLM invocation.
- Structured logging with correlation IDs (no secrets in logs).

See [ARCHITECTURE.md](./ARCHITECTURE.md) and [GROK_OAUTH.md](./GROK_OAUTH.md) for more.

Thank you for helping keep Aetherion secure.
