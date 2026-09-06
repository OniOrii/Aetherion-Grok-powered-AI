"""
Centralized configuration for the Aetherion Discord Bot.

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


class AetherionSettings(BaseSettings):
    """Validated settings for the Aetherion Discord Bot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    discord_bot_token: str | None = Field(
        default=None,
        description="Discord bot token (required to actually run the bot)"
    )

    allowed_guild_ids: list[int] = Field(
        default_factory=list,
        description="Guild IDs where the bot is allowed to operate (empty = all guilds)",
    )

    xai_api_key: str | None = Field(
        default=None,
        description="xAI API key for Grok + image/video generation (required for 'api_key' auth mode)"
    )

    grok_model: str = Field(
        default="grok-4.3",
        description="Model name for the Responses API",
    )

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

    twitch_client_id: str | None = Field(
        default=None,
        description="Twitch application Client ID for Helix API (optional; /versus works without Twitch data if unset)",
    )
    twitch_client_secret: str | None = Field(
        default=None,
        description="Twitch application Client Secret for app access token (optional)",
    )

    enable_video_generation: bool = Field(
        default=True,
        description="Master switch for the generate_video tool (both T2V and I2V)",
    )

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
    welcome_background_url: str | None = Field(default=None, description="Image URL for the welcome banner background.")
    
    context_smart_mode: bool = Field(
        default=True,
        description="Enable dynamic context: lighter (less history) for simple factual queries, richer for complex conversations. Supports extreme nativeness by defaulting to minimal injection.",
    )

    summarization_enabled: bool = Field(
        default=False,
        description="Enable automatic proactive summarization of older conversation history (disabled by default for maximum nativeness).",
    )

    summarization_threshold_tokens: int = Field(
        default=6000,
        description="Approximate token threshold for channel history that triggers proactive summarization (only used when summarization_enabled=true).",
    )

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

    aggressive_continuation_tool_minimization: bool = Field(
        default=True,
        description="On tool continuation rounds, send the smallest possible custom tool list (major repeated token saver).",
    )

    data_dir: Path = Field(
        default=Path("./data"),
        description="Base directory for short-term conversation context persistence.",
    )

    pantsu_context_file: Path | None = Field(
        default=None,
        description="Optional override for short-term context JSON path (default: data/pantsu_context.json; see ARCHITECTURE.md)",
    )

    log_level: str = Field(default="INFO", description="Logging level")

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
        if self.pantsu_context_file:
            return self.pantsu_context_file
        return self.data_dir / "pantsu_context.json"

    @property
    def auth_mode(self) -> str:
        mode = (self.grok_auth_mode or "api_key").strip().lower()
        if mode in ("oauth", "xai-oauth", "grok-oauth", "super-grok", "premium"):
            return "oauth"
        if mode in ("auto", "automatic", "prefer-oauth", "oauth-or-key"):
            return "auto"
        return "api_key"

    @property
    def using_oauth(self) -> bool:
        return self.auth_mode == "oauth"

    @property
    def auth_prefers_oauth(self) -> bool:
        mode = self.auth_mode
        if mode in ("oauth", "auto"):
            return True
        try:
            from ..core.grok_oauth import load_oauth_tokens
            return bool(load_oauth_tokens())
        except Exception:
            return False

    @property
    def oauth_token_file(self) -> Path:
        if self.grok_oauth_token_file:
            return self.grok_oauth_token_file
        return Path.cwd() / "oauth" / "xai_oauth_tokens.json"

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (Path.cwd() / "oauth").mkdir(parents=True, exist_ok=True)

    def validate_for_run(self) -> None:
        missing = []
        if not self.discord_bot_token:
            missing.append("DISCORD_BOT_TOKEN")

        mode = self.auth_mode
        if mode == "api_key":
            if not self.xai_api_key:
                missing.append("XAI_API_KEY")
        elif mode == "oauth":
            pass
        elif mode == "auto":
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


# Keep the old class name so existing imports do not break.
GroksitoSettings = AetherionSettings

settings = AetherionSettings()
settings.ensure_directories()
