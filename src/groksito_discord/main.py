"""
Aetherion Discord Bot — Main Entry Point (Standalone)

Fully wired conversational entrypoint.

Usage:
    groksito
    python -m groksito_discord
    groksito --check   # Validate config only
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from .config import settings

# =============================================================================
# Colored logging via rich (configured at import time for early coverage)
# Replaces basicConfig. Works locally + inside `docker compose up` (via FORCE_COLOR).
# Tags like [LLM], [TOOLS], [Activation], [TOKENS], [CONTEXT] remain literal (markup=False).
# =============================================================================
try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.theme import Theme

    _LOG_LEVEL = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Support forcing colors in non-tty environments (docker compose, CI, redirected logs).
    # Set FORCE_COLOR=1 or RICH_FORCE_TERMINAL=1 in env or docker-compose.
    _force_terminal = (
        os.getenv("FORCE_COLOR") == "1"
        or os.getenv("RICH_FORCE_TERMINAL") == "1"
        or os.getenv("PY_COLORS") == "1"
    )

    _theme = Theme(
        {
            "logging.level.debug": "dim",
            "logging.level.info": "cyan",
            "logging.level.warning": "yellow",
            "logging.level.error": "bold red",
            "logging.level.critical": "bold red",
        }
    )

    _console = Console(
        theme=_theme,
        force_terminal=True if _force_terminal else None,  # None = rich auto-detect (tty)
        no_color=False,
    )

    _rich_handler = RichHandler(
        console=_console,
        rich_tracebacks=True,
        tracebacks_show_locals=False,
        markup=False,  # [LLM] [TOOLS] etc must appear as plain text, not rich markup
        show_time=True,
        show_level=True,
        show_path=False,
        log_time_format="[%Y-%m-%d %H:%M:%S]",
    )

    logging.basicConfig(
        level=_LOG_LEVEL,
        format="%(message)s",  # RichHandler owns the visual prefix (time + colored level + name)
        datefmt="[%Y-%m-%d %H:%M:%S]",
        handlers=[_rich_handler],
        force=True,  # override any previous root config
    )
except Exception as rich_setup_err:
    # Very defensive: if rich import/setup fails (e.g. partial install), fall back to stdlib.
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("groksito.bot").warning(
        f"Rich logging setup failed, using stdlib fallback: {rich_setup_err}"
    )

logger = logging.getLogger("groksito.bot")


def _is_running_in_docker() -> bool:
    """Best-effort detection of running inside a Docker (or similar) container.

    Used to automatically improve the UX of --login-oauth for the common
    "bot runs in Docker on a server, user logs in from their laptop" case.
    """
    try:
        if os.path.exists("/.dockerenv"):
            return True
        # cgroup based detection (works in many container runtimes)
        if os.path.exists("/proc/1/cgroup"):
            with open("/proc/1/cgroup", "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if "docker" in content or "kubepods" in content or "containerd" in content:
                    return True
        # env var sometimes set by compose / custom entrypoints
        if os.getenv("DOCKER_CONTAINER") or os.getenv("container"):
            return True
    except OSError as docker_probe_err:
        logger.debug(f"Docker detection probe failed (non-fatal): {docker_probe_err}")
    return False

# Optional import for OAuth (lazy so api_key users don't pay import cost)
try:
    from .core.grok_oauth import (
        login_oauth_interactive,
        logout_oauth,
        print_auth_status,
        get_grok_bearer,
    )
except Exception as oauth_import_err:
    login_oauth_interactive = None  # type: ignore
    logout_oauth = None  # type: ignore
    print_auth_status = None  # type: ignore
    get_grok_bearer = None  # type: ignore
    logger.warning(f"[Auth] OAuth module import failed (OAuth CLI disabled): {oauth_import_err}")

# (rich logging already configured at module top; no duplicate basicConfig here)


def _print_config_summary() -> None:
    """Print a safe summary of the current configuration."""
    logger.info("=== Aetherion Configuration ===")
    logger.info(f"Data directory: {settings.data_dir}")
    logger.info(f"Video generation: {'ENABLED' if settings.enable_video_generation else 'DISABLED'}")
    logger.info(f"Allowed guilds: {settings.allowed_guild_ids or 'ALL (no whitelist)'}")
    logger.info(f"Model: {getattr(settings, 'grok_model', 'default')}")
    logger.info("==============================")


def _print_startup_banner() -> None:
    """
    Print a single cyberpunk/neon-styled ASCII banner for Aetherion at startup.

    - Uses the block "AETHERION" art (futuristic terminal aesthetic).
    - Framed with rules and a tagline for strong cyberpunk vibe (neon, matrix, holo).
    - Printed with rich colors (cyan/magenta) for local + docker (FORCE_COLOR).
    - Called only from the real startup path (main), never for --status/--check.
    - Guarded by process lifetime: prints once per `python -m ...` invocation.
    """
    try:
        from rich.console import Console

        # Dedicated console for banner (separate from logging handler console).
        # Respects the same FORCE_COLOR logic because rich detects or we set in env.
        banner_console = Console()

        # The core block art — professional yet strong cyberpunk block letters.
        # (Improved framing + subtitle give the "glitch / neon terminal / matrix" feel.)
        aetherion_art = (
            " █████╗ ███████╗████████╗██╗  ██╗███████╗██████╗ ██╗ ██████╗ ███╗   ██╗\n"
            "██╔══██╗██╔═════╝╚══██╔══╝██║  ██║██╔═════╝██╔══██╗██║██╔═══██╗████╗  ██║\n"
            "███████║█████╗     ██║   ███████║█████╗  ██████╔╝██║██║   ██║██╔██╗ ██║\n"
            "██╔══██║██╔══╝     ██║   ██╔══██║██╔══╝  ██╔══██╗██║██║   ██║██║╚██╗██║\n"
            "██║  ██║███████╗   ██║   ██║  ██║███████╗██║  ██║██║╚██████╔╝██║ ╚████║\n"
            "╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝"
        )

        banner_console.print()
        banner_console.rule(
            "[bold cyan]▌ NEURAL INTERFACE // xAI :: AETHERION v0.2 // MAX NATIVENESS ▐[/]",
            style="cyan",
        )
        banner_console.print(aetherion_art, style="bold bright_magenta", highlight=False)
        banner_console.print(
            "[dim cyan]>>> EXTREME LAZINESS ENABLED :: LET GROK DECIDE :: TOKEN EFFICIENT <<<[/]",
            justify="center",
        )
        banner_console.rule(style="cyan")
        banner_console.print()
    except Exception:
        # Fallback: never break startup because of banner art
        print("\n" + "=" * 64)
        print("AETHERION — NEURAL INTERFACE // xAI")
        print("=" * 64 + "\n")


async def main() -> None:
    _print_config_summary()
    _print_startup_banner()

    # Lightweight early auth probe (prefers OAuth token if present; does not force login)
    try:
        from .core.grok_oauth import get_grok_bearer
        b = get_grok_bearer() if get_grok_bearer else None
        if b:
            src = "OAuth token (SuperGrok)" if settings.auth_prefers_oauth or settings.using_oauth else "API key (or OAuth fallback)"
            logger.info(f"[Auth] Effective credential ready ({src}).")
        else:
            logger.info("[Auth] No credential yet — use --login-oauth or XAI_API_KEY.")
    except Exception as auth_probe_err:
        logger.warning(f"[Auth] Early credential probe failed (non-fatal): {auth_probe_err}")

    # Validate required secrets before attempting to connect
    try:
        settings.validate_for_run()
    except RuntimeError as e:
        logger.error(str(e))
        logger.error("Run with --check to validate configuration without connecting.")
        sys.exit(1)

    logger.info("🚀 Starting Aetherion Discord Bot")

    # Write an early "process is alive, connecting" heartbeat so the web
    # dashboard doesn't show "down" during the normal ~10-30s startup window.
    try:
        from .core.health import write_bot_heartbeat
        write_bot_heartbeat(connected=False, user="starting...")
    except Exception as hb_err:
        logger.warning(f"[Health] Early heartbeat write failed (non-fatal, degraded): {hb_err}")

    try:
        from .discord.client import ensure_discord_connected

        # This process is the CONVERSATIONAL OWNER
        client = await ensure_discord_connected(conversational=True)

        logger.info("✅ Aetherion fully wired and connected.")
        logger.info("   (LLM + tools + media generation stack is active)")
        logger.info("   The bot is now ready to handle mentions and replies.")

        await asyncio.Future()

    except Exception as exc:
        logger.exception(f"Fatal error starting Aetherion: {exc}")
        await asyncio.sleep(10)
        raise


def run() -> None:
    # Simple argument handling
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd in ("--check", "-c"):
            _print_config_summary()
            try:
                settings.validate_for_run()
                logger.info("✅ Configuration looks good. Secrets are present.")
                sys.exit(0)
            except RuntimeError as e:
                logger.error(str(e))
                sys.exit(1)

        if cmd in ("--status", "-s"):
            _print_config_summary()
            try:
                from .core.health import print_health_status
                print_health_status()
            except Exception as e:
                logger.error(f"Health check failed: {e}")
            sys.exit(0)

        # =====================================================================
        # Experimental OAuth commands (SuperGrok / X Premium+)
        #
        # Docker-friendly login:
        #   - The container does not need a browser. Use --no-browser (auto-selected
        #     when we detect /.dockerenv or container cgroups).
        #   - New --print-url-only (or --url-only) is great for CI / scripts / when
        #     you want to copy the URL to your laptop.
        #   - See docker-compose.yml for the recommended ./oauth volume.
        #   - Full guide is also in the function docstring of login_oauth_interactive
        #     inside grok_oauth.py.
        # =====================================================================
        if cmd in ("--login-oauth", "--auth-login", "--oauth-login"):
            _print_config_summary()
            if not login_oauth_interactive:
                logger.error("OAuth support not available (import failed).")
                sys.exit(1)
            # Allow login even if full validate would fail (for pure oauth setup)
            no_browser = "--no-browser" in sys.argv or "-nb" in sys.argv
            manual = "--manual-paste" in sys.argv or "--paste" in sys.argv
            print_url_only = "--print-url-only" in sys.argv or "--url-only" in sys.argv or "--print-url" in sys.argv

            # Docker / remote server friendliness:
            # If we detect we are inside a container and the user didn't explicitly
            # ask for browser open, force no-browser mode and give better guidance.
            if not no_browser and not print_url_only and _is_running_in_docker():
                print("[Docker detected] Forcing --no-browser mode for --login-oauth.")
                print("                (Browsers can't be opened from inside most containers.)")
                print("                Add --no-browser explicitly if you are testing locally.")
                no_browser = True

            success = login_oauth_interactive(
                no_browser=no_browser,
                manual_paste=manual,
                print_url_only=print_url_only,
            )
            sys.exit(0 if success else 1)

        if cmd in ("--logout-oauth", "--auth-logout", "--oauth-logout"):
            if not logout_oauth:
                logger.error("OAuth support not available.")
                sys.exit(1)
            logout_oauth()
            sys.exit(0)

        if cmd in ("--auth-status", "--oauth-status"):
            _print_config_summary()
            if print_auth_status:
                print_auth_status()
            else:
                print("OAuth support module not loaded.")
            # Also show basic health if possible
            try:
                from .core.health import print_health_status
                print_health_status()
            except Exception as health_err:
                logger.warning(f"Health status unavailable during --auth-status: {health_err}")
            sys.exit(0)

        # ---------------------------------------------------------------------
        # --test-auth / --verify-auth: quick non-Discord verification that the
        # current credential (OAuth preferred or API key) can actually call xAI.
        # Exercises the exact same get_grok_bearer() path used by llm + media.
        # ---------------------------------------------------------------------
        if cmd in ("--test-auth", "--verify-auth", "--test-oauth", "--auth-test", "--verify-oauth"):
            _print_config_summary()
            if print_auth_status:
                print_auth_status()
            bearer = None
            if get_grok_bearer:
                bearer = get_grok_bearer()
            if not bearer:
                print("\n❌ No usable credential. Run one of:")
                print("   groksito --login-oauth")
                print("   # or set XAI_API_KEY in .env")
                sys.exit(1)

            src = "OAuth (SuperGrok)" if (settings.auth_mode in ("oauth", "auto") or (bearer and len(str(bearer)) > 50) ) else "API key"
            print(f"\n[Auth Test] Using {src} credential (len={len(str(bearer))}). Making minimal verification call...")

            try:
                import httpx
                model = getattr(settings, "grok_model", None) or "grok-4.3"
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(
                        "https://api.x.ai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {bearer}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": "Reply with exactly the word: OK"}],
                            "max_tokens": 3,
                            "temperature": 0,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    content = ""
                    try:
                        content = data["choices"][0]["message"]["content"]
                    except Exception:
                        content = str(data)[:120]
                    print(f"✅ Verification call succeeded via {src}.")
                    print(f"   Model: {model}")
                    print(f"   Grok replied: {content.strip()[:80]!r}")
                    print("   The same bearer is used for Responses API, image generations, edits, and video.")
                    print("   You are ready to run the bot.")
            except Exception as e:
                print(f"⚠️  Verification call failed: {e}")
                print("   The token/key may be valid but hitting a temporary issue, quota, or tier gate.")
                print("   Try --auth-status again, or fall back to a classic XAI_API_KEY + GROK_AUTH_MODE=api_key.")
            sys.exit(0)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down Aetherion...")
    except Exception:
        logger.exception("Unhandled error")
        sys.exit(1)


if __name__ == "__main__":
    run()
