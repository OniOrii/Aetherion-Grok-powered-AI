"""
Centralized configuration for the Groksito Discord Bot.

This module provides a single source of truth for all environment variables,
with validation and sensible defaults.

Usage:
    from . import settings
    # or after install: from groksito_discord.config import settings

    token = settings.discord_bot_token
    data_dir = settings.data_dir
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GroksitoSettings(BaseSettings):
    """Validated settings for the Groksito Discord Bot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Discord
    # -------------------------------------------------------------------------
    discord_bot_token: str | None = Field(
        default=None,
        description="Discord bot token (required to actually run the bot)"
    )

    allowed_guild_ids: list[int] = Field(
        default_factory=list,
        description="Guild IDs where the bot is allowed to operate (empty = all guilds)",
    )

    # -------------------------------------------------------------------------
    # xAI / Grok
    # -------------------------------------------------------------------------
    xai_api_key: str | None = Field(
        default=None,
        description="xAI API key for Grok + image/video generation (required for 'api_key' auth mode)"
    )

    grok_model: str = Field(
        default="grok-4.3",
        description="Model name for the Responses API",
    )

    # -------------------------------------------------------------------------
    # API Resilience (lightweight retries + timeouts for Responses + image/video)
    # Pragmatic: only transient errors (rate, server, net) are retried. Policy/auth/4xx fail fast.
    # Defaults match previous behavior for backward compatibility on happy paths.
    # -------------------------------------------------------------------------
    api_max_retries: int = Field(
        default=3,
        description="Max attempts (1 + retries) for transient errors on Grok API calls (Responses, image, video)",
    )
    api_retry_base_delay_seconds: float = Field(
        default=0.5,
        description="Base delay for exponential backoff + jitter on retries (doubles each time)",
    )
    api_timeout_seconds: float = Field(
        default=60.0,
        description="Default timeout (total) for API calls to xAI (Responses client + httpx for image/video). Higher values for video gen.",
    )
    video_poll_max_wait_seconds: int = Field(
        default=600,
        description=(
            "Max seconds to poll xAI video generation before giving up. "
            "xAI SDK default is 10 minutes; 720p/15s jobs often exceed 5 minutes."
        ),
    )
    discord_max_upload_bytes: int = Field(
        default=25 * 1024 * 1024,
        description=(
            "Max Discord bot attachment size in bytes (API hard cap is 25 MB). "
            "Oversized videos fall back to a direct xAI CDN link."
        ),
    )

    # -------------------------------------------------------------------------
    # Experimental: Grok auth via SuperGrok / X Premium+ OAuth (no API key)
    # Modeled after Hermes Agent browser OAuth flow (PKCE loopback to accounts.x.ai)
    # WARNING: Experimental / use at your own risk. May have tier restrictions (403s),
    # different rate limits/quotas than paid API keys, and token storage security considerations.
    # API key mode remains the stable default.
    # -------------------------------------------------------------------------
    grok_auth_mode: str = Field(
        default="api_key",
        description="Authentication mode: 'api_key' (default, uses XAI_API_KEY) or 'oauth' (SuperGrok/X Premium+ browser login, experimental)",
    )

    grok_oauth_port: int = Field(
        default=56121,
        description="Local loopback port for OAuth PKCE callback (must match what xAI allows; same as Hermes Agent)",
    )

    grok_oauth_token_file: Path | None = Field(
        default=None,
        description="Optional explicit path for storing OAuth tokens (defaults to ./oauth/xai_oauth_tokens.json for separation from data/)",
    )

    # -------------------------------------------------------------------------
    # Twitch (Helix API — powers /versus viewer counts)
    # -------------------------------------------------------------------------
    twitch_client_id: str | None = Field(
        default=None,
        description="Twitch application Client ID for Helix API (optional; /versus works without Twitch data if unset)",
    )
    twitch_client_secret: str | None = Field(
        default=None,
        description="Twitch application Client Secret for app access token (optional)",
    )

    # -------------------------------------------------------------------------
    # Feature Flags
    # -------------------------------------------------------------------------
    enable_video_generation: bool = Field(
        default=True,
        description="Master switch for the generate_video tool (both T2V and I2V)",
    )

    # -------------------------------------------------------------------------
    # TTS / Audio configuration (exposed in web dashboard, read by audio_handler)
    # These feed the xAI /v1/tts endpoint (text, voice_id, language required).
    # -------------------------------------------------------------------------
    tts_default_voice: str = Field(
        default="eve",
        description="Default voice_id for TTS generation (eve, ara, rex, sal, leo). Configurable from web dashboard. eve is energetic/upbeat default.",
    )
    tts_default_language: str = Field(
        default="es",
        description="Default language code (BCP-47) for TTS (e.g. 'es', 'es-ES', 'es-MX', 'en', 'auto'). Language is REQUIRED by the xAI TTS API. 'es' works well for Spanish; use 'auto' for mixed or detection.",
    )
    
    welcome_enabled: bool = Field(default=False, description="Post when a member joins.")
    welcome_channel_id: int = Field(default=0, description="Welcome channel ID. 0 = use name.")
    welcome_channel_name: str = Field(default="welcome", description="Channel name if no ID.")
    welcome_message: str = Field(
        default="Welcome {{User.Mention}} to **{{Guild.Name}}**.",
        description="Welcome text.",
    )
    
    # -------------------------------------------------------------------------
    # Context & Conversation (tuned for maximum Grok nativeness)
    # -------------------------------------------------------------------------
    # Dynamic context tiering: lighter (almost zero) for simple queries, richer only when needed.
    # This is a key enabler of "let Grok be Grok" — the base model needs very little injected history.
    context_smart_mode: bool = Field(
        default=True,
        description="Enable dynamic context: lighter (less history) for simple factual queries, richer for complex conversations. Supports extreme nativeness by defaulting to minimal injection.",
    )

    # Proactive summarization is DISABLED by default. Grok's large context window handles long conversations natively.
    # Only enable if you observe excessive token usage on extremely long threads and want automatic compaction.
    summarization_enabled: bool = Field(
        default=False,
        description="Enable automatic proactive summarization of older conversation history (disabled by default for maximum nativeness).",
    )

    summarization_threshold_tokens: int = Field(
        default=6000,
        description="Approximate token threshold for channel history that triggers proactive summarization (only used when summarization_enabled=true).",
    )

    # -------------------------------------------------------------------------
    # Recent Conversation Context (on-demand via get_recent_context tool only)
    # Pre-injection of summaries removed (#19). The summarizer (and these limits) are now used
    # exclusively when the model explicitly calls the get_recent_context custom tool on addressed turns
    # (light decision tools surface it for native reasoning). This reduces latency on simple @mentions.
    # Separate from the (disabled-by-default) proactive long-history summarization.
    # -------------------------------------------------------------------------
    enable_recent_context_summary: bool = Field(
        default=True,
        description="Enable recent conversation context capability. The dedicated summarizer is invoked on-demand only when Grok calls the get_recent_context tool (offered on addressed turns). No automatic pre-injection.",
    )
    enable_recent_context: bool = Field(
        default=True,
        description="Legacy alias for enable_recent_context_summary. Prefer the new flag.",
    )
    recent_context_message_limit: int = Field(
        default=20,
        description="Maximum number of recent messages to consider when the get_recent_context tool builds a summary.",
    )
    recent_context_max_tokens: int = Field(
        default=400,
        description="Target maximum size (in tokens) for summaries produced by the get_recent_context tool.",
    )

    # When true (recommended for token efficiency on tool chains), continuation rounds using previous_response_id send
    # an extremely minimal custom tool list (currently just reply_to_user light).
    aggressive_continuation_tool_minimization: bool = Field(
        default=True,
        description="On tool continuation rounds, send the smallest possible custom tool list (major repeated token saver).",
    )

    # -------------------------------------------------------------------------
    # Persistence (short-term channel context only)
    # -------------------------------------------------------------------------
    data_dir: Path = Field(
        default=Path("./data"),
        description="Base directory for short-term conversation context persistence.",
    )

    pantsu_context_file: Path | None = Field(
        default=None,
        description="Optional override for short-term context JSON path (default: data/pantsu_context.json; see ARCHITECTURE.md)",
    )

    # -------------------------------------------------------------------------
    # Logging & Misc
    # -------------------------------------------------------------------------
    log_level: str = Field(default="INFO", description="Logging level")

    # Structured tool selection logging (very useful after aggressive tool optimizations)
    log_tool_selection: bool = Field(
        default=True,
        description="Log detailed tool schema selection decisions (turn type, custom tools sent, native flags, schema size). Low overhead.",
    )

    log_cache_metrics: bool = Field(
        default=True,
        description="Log structured prompt caching effectiveness metrics (cached_tokens, hit rate, context like turn_type and query_need). Very low overhead.",
    )

    @field_validator("allowed_guild_ids", mode="before")
    @classmethod
    def parse_guild_ids(cls, v: Any) -> list[int]:
        """Parse comma-separated guild IDs from environment."""
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, (list, tuple)):
            return [int(x) for x in v]
        return []

    @field_validator("data_dir", "pantsu_context_file", "grok_oauth_token_file", mode="before")
    @classmethod
    def resolve_path(cls, v: Any) -> Path | None:
        """Resolve paths relative to current working directory.
        Treat empty string (common for optional .env overrides like PANTSU_CONTEXT_FILE=) as None.
        """
        if v is None:
            return None
        if isinstance(v, str) and not v.strip():
            return None
        p = Path(v)
        if not p.is_absolute():
            p = Path.cwd() / p
        return p

    @property
    def context_file(self) -> Path:
        """Path to the short-term conversation context persistence file."""
        if self.pantsu_context_file:
            return self.pantsu_context_file
        return self.data_dir / "pantsu_context.json"

    @property
    def auth_mode(self) -> str:
        """Normalized auth mode: 'api_key' (default), 'oauth', or 'auto'.

        - 'api_key': always use XAI_API_KEY (stable default)
        - 'oauth': require OAuth (SuperGrok/X Premium+ via --login-oauth); no API key needed
        - 'auto': prefer a valid OAuth token (if present and refreshable) for calls, with seamless
          fallback to XAI_API_KEY if no OAuth token. Ideal for "I logged in once, just use it".
        """
        mode = (self.grok_auth_mode or "api_key").strip().lower()
        if mode in ("oauth", "xai-oauth", "grok-oauth", "super-grok", "premium"):
            return "oauth"
        if mode in ("auto", "automatic", "prefer-oauth", "oauth-or-key"):
            return "auto"
        return "api_key"

    @property
    def using_oauth(self) -> bool:
        """True if *strict* OAuth mode (GROK_AUTH_MODE=oauth). For preference logic see get_grok_bearer()."""
        return self.auth_mode == "oauth"

    @property
    def auth_prefers_oauth(self) -> bool:
        """True if we should prefer OAuth tokens when a valid one is available (oauth or auto modes, or token file present)."""
        mode = self.auth_mode
        if mode in ("oauth", "auto"):
            return True
        # Even in api_key mode, if a token file exists we still let the central bearer prefer it (best-effort "use what you have").
        # This makes "login once, it just works" the default UX without forcing users to flip the env var.
        try:
            from ..core.grok_oauth import load_oauth_tokens
            return bool(load_oauth_tokens())
        except Exception:
            return False

    @property
    def oauth_token_file(self) -> Path:
        """Path for persisted OAuth tokens (access/refresh).

        Defaults to ./oauth/xai_oauth_tokens.json (dedicated directory outside
        the data/ folder). This allows better organization, keeps tokens out of
        general data, and makes it easy to mount ./oauth/ as a separate volume
        in Docker (while data/ can have its own volume).

        If GROK_OAUTH_TOKEN_FILE (or grok_oauth_token_file) is set, that explicit
        path is used instead (still resolved to absolute if relative).
        """
        if self.grok_oauth_token_file:
            return self.grok_oauth_token_file
        # Use a dedicated ./oauth/ dir (relative to cwd, will be made absolute
        # consistently with how overrides are handled). Not under data_dir.
        return Path.cwd() / "oauth" / "xai_oauth_tokens.json"

    def ensure_directories(self) -> None:
        """Create required data directories if they do not exist.

        Also ensures the dedicated ./oauth/ directory exists for OAuth token
        storage. This directory lives outside data/ for separation (easier
        Docker volume for just the tokens) and is created at startup for
        consistency (in addition to being ensured on first save/load in
        grok_oauth.py).
        """
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Dedicated ./oauth/ dir (not under data_dir) for xai_oauth_tokens.json
        (Path.cwd() / "oauth").mkdir(parents=True, exist_ok=True)

    def validate_for_run(self) -> None:
        """Raise a clear error if required secrets for running the bot are missing."""
        missing = []
        if not self.discord_bot_token:
            missing.append("DISCORD_BOT_TOKEN")

        mode = self.auth_mode
        if mode == "api_key":
            if not self.xai_api_key:
                missing.append("XAI_API_KEY")
        elif mode == "oauth":
            # Pure OAuth: token obtained via one-time --login-oauth. No XAI_API_KEY required.
            # We do not require the token file here (login can be run separately; --status works without it).
            pass
        elif mode == "auto":
            # Auto: either OAuth token (preferred at runtime) *or* XAI_API_KEY is sufficient.
            # No hard requirement at validate time.
            pass
        else:
            if not self.xai_api_key:
                missing.append("XAI_API_KEY (or set GROK_AUTH_MODE=auto or oauth)")

        if missing:
            raise RuntimeError(
                f"Missing required configuration: {', '.join(missing)}. "
                "Please set them in your .env file before starting the bot. "
                "Tip: Run `python -m groksito_discord --status` for a full health report (works without secrets). "
                "OAuth options: GROK_AUTH_MODE=oauth + `python -m groksito_discord --login-oauth` (no XAI_API_KEY needed), "
                "or GROK_AUTH_MODE=auto to prefer OAuth tokens when present with fallback to key."
            )


# Singleton settings instance (loaded at import time)
settings = GroksitoSettings()

# Ensure directories exist on import (safe and convenient)
settings.ensure_directories()
