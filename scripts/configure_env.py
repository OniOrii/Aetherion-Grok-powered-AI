#!/usr/bin/env python3
"""Aetherion interactive setup. Safe to run many times."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

try:
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    from rich.panel import Panel
    RICH = True
    console = Console()
except Exception:
    RICH = False
    console = None

ENV_FILE = Path(".env")

src_dir = Path(__file__).resolve().parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from groksito_discord.utils.env_utils import (
    safe_write_env,
    parse_env_file,
    backup_env,
    deduplicate_env_file,
    _format_list_for_display,
    _get_ci,
    create_fresh_env_from_template,
)


def say(msg: str, style: str | None = None) -> None:
    if RICH:
        console.print(msg, style=style)
    else:
        print(msg)


def ask(prompt: str, default: str | None = None) -> str:
    if RICH:
        return Prompt.ask(prompt, default=default, show_default=True) or ""
    p = f"{prompt} [{default}]: " if default else f"{prompt}: "
    val = input(p).strip()
    return val or (default or "")


def confirm(prompt: str, default: bool = False) -> bool:
    if RICH:
        return Confirm.ask(prompt, default=default)
    d = "Y/n" if default else "y/N"
    val = input(f"{prompt} ({d}): ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes")


def show_panel(title: str, content: str) -> None:
    if RICH:
        console.print(Panel(content, title=title, border_style="cyan"))
    else:
        print(f"\n=== {title} ===\n{content}\n" + "=" * (len(title) + 8))


def _try_run_oauth_login() -> bool:
    say("\n--- OAuth login (SuperGrok / X Premium+) ---")
    try:
        from groksito_discord.core.grok_oauth import login_oauth_interactive
    except Exception as e:
        say(f"Could not load the OAuth module: {e}", "red")
        say("Run later: python -m groksito_discord --login-oauth")
        return False
    say("The login flow will open in the browser (or print instructions).")
    say("This is safe and only needed once (tokens are saved under ./oauth/).")
    if not confirm("Start OAuth login now?", default=True):
        say("Skipped. You can run the command above later.")
        return False
    try:
        if login_oauth_interactive(no_browser=False):
            say("OAuth login finished. Tokens were saved.", "bold green")
            return True
        say("OAuth login did not finish (cancelled or an error).", "yellow")
        return False
    except KeyboardInterrupt:
        say("\nLogin interrupted.", "yellow")
        return False
    except Exception as e:
        say(f"Error during OAuth login: {e}", "red")
        return False


def _bootstrap_from_template() -> bool:
    if ENV_FILE.exists():
        return True
    say("No .env found. Creating one from .env.example...", "green")
    try:
        ok, msg, _bak = create_fresh_env_from_template(ENV_FILE)
        if ok:
            say(".env created from the template.", "green")
            return True
        say(f"Could not create from template: {msg}. Trying a direct copy...", "yellow")
    except Exception as e:
        say(f"create_fresh failed: {e}. Trying a direct copy...", "yellow")
    for cand in (Path(".env.example"), Path("env.example")):
        if cand.exists():
            try:
                ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cand, ENV_FILE)
                say(f"Copied {cand} -> .env", "green")
                return True
            except Exception as ex:
                say(f"Direct copy failed: {ex}", "red")
    try:
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        ENV_FILE.write_text(
            "# Aetherion Discord Bot - minimal generated config\n"
            "# Run python scripts/configure_env.py again to finish it.\n\n"
            "DISCORD_BOT_TOKEN=\nXAI_API_KEY=\nGROK_AUTH_MODE=api_key\nALLOWED_GUILD_IDS=\n",
            encoding="utf-8",
        )
        say("Created a minimal .env (no template).", "yellow")
        return True
    except Exception as e:
        say(f"Critical error creating .env: {e}", "red")
        return False


def main() -> None:
    say("Aetherion \u2014 interactive setup", "bold cyan")
    say("This tool is safe to run as many times as you want.")
    say("Uses .env.example when .env is missing, never duplicates keys,\n")

    had_env_before = ENV_FILE.exists()
    if not had_env_before and not _bootstrap_from_template():
        say("Could not create .env. Aborting.", "red")
        return

    existing = parse_env_file(ENV_FILE)
    if existing or ENV_FILE.exists():
        say(f"Found {ENV_FILE} with {len(existing)} keys.", "yellow")
        show_panel(
            "Current values (safe view)",
            "\n".join(f"  {k} = {'<set>' if v else '<empty>'}" for k, v in list(existing.items())[:12])
            + ("\n  ... (more keys)" if len(existing) > 12 else ""),
        )
    else:
        say("No .env found. A new one will be created.", "green")

    choice = "1"
    if had_env_before:
        say("\nOptions (1 \u2014 Safe Update is recommended):")
        say("  1) Safe Update (default): keep everything that already exists.")
        say("     Only asks for missing required keys and lets you change safe settings.")
        say("  2) Clean duplicates only (keeps the last value, backs up, then exits).")
        say("  3) Review and change specific values (one confirmation at a time).")
        say("  4) Start over (backup, write a clean .env from .env.example, then ask again).")
        choice = ask("Choose 1/2/3/4", default="1").strip() or "1"

    updates: dict[str, Any] = {}

    if choice == "2":
        say("\nCleaning duplicate keys (keeps the last occurrence of each key)...")
        changed = deduplicate_env_file(ENV_FILE, keep="last", make_backup=True)
        if changed:
            say("Duplicates removed. Backups written.", "green")
            say("   Run python scripts/configure_env.py again to fill missing values.")
        else:
            say("No duplicate keys found. Your .env is already clean.")
        say("\nDone.")
        return

    if choice == "4":
        if existing or ENV_FILE.exists():
            if not confirm("This will BACK UP your current .env and write a brand-new one from the clean template. Continue?", default=False):
                say("Aborted.", "red")
                return
            if ask("Type RESET in uppercase to confirm a full reset") != "RESET":
                say("Confirmation word did not match. Aborted.", "red")
                return
            bak = backup_env(ENV_FILE)
            say(f"Backup written: {bak}", "green")
        else:
            say("Creating a fresh .env from the clean template...")
        ok, msg, _bak = create_fresh_env_from_template(ENV_FILE, overrides=None)
        if not ok:
            say(f"Could not write the clean template: {msg}", "red")
            return
        say("Clean template written. Reloading...")
        existing = parse_env_file(ENV_FILE)
        choice = "1"

    current_disc = _get_ci(existing, "DISCORD_BOT_TOKEN")
    if current_disc:
        say(f"\nDiscord Bot Token: already set (length ~{len(current_disc)}).")
        if confirm("Change the Discord Bot Token?", default=False):
            new = ask("Paste the new DISCORD_BOT_TOKEN")
            if new:
                updates["DISCORD_BOT_TOKEN"] = new.strip()
    else:
        say("\nDISCORD_BOT_TOKEN is REQUIRED!")
        token = ask("Paste your Discord Bot Token (from https://discord.com/developers/applications)")
        if token:
            updates["DISCORD_BOT_TOKEN"] = token.strip()

    current_mode = _get_ci(existing, "GROK_AUTH_MODE") or "api_key"
    current_xai = _get_ci(existing, "XAI_API_KEY")
    say("\n--- Authentication ---")
    say("You can use a classic XAI_API_KEY (stable) or the experimental OAuth flow (SuperGrok / X Premium+).")
    say("Recommended: set a key, or use GROK_AUTH_MODE=auto and log in once.")
    if current_mode or current_xai:
        say(f"Current mode: {current_mode}")
        if current_xai:
            say("XAI_API_KEY is set.")
        if not confirm("Change authentication settings?", default=False):
            if current_mode and current_mode.lower() not in ("", "none"):
                updates["GROK_AUTH_MODE"] = current_mode

    auth_choice = ask(
        "Auth method: 1=XAI_API_KEY (stable, recommended)  2=OAuth (no key, experimental)  3=auto (prefer OAuth if a token exists)",
        default="1",
    ).strip()
    will_need_oauth = False
    if auth_choice in ("1", ""):
        if not current_xai or confirm("Replace XAI_API_KEY?", default=False):
            key = ask("Paste your XAI_API_KEY (from https://console.x.ai)")
            if key:
                updates["XAI_API_KEY"] = key.strip()
        updates["GROK_AUTH_MODE"] = "api_key"
    elif auth_choice == "2":
        updates["GROK_AUTH_MODE"] = "oauth"
        will_need_oauth = True
        say("OAuth selected. At the end of setup I will offer to start login.")
    else:
        updates["GROK_AUTH_MODE"] = "auto"
        will_need_oauth = True
        if not current_xai or confirm("Also set/update a backup XAI_API_KEY (strongly recommended)?", default=True):
            key = ask("Paste a backup XAI_API_KEY (or leave empty)")
            if key:
                updates["XAI_API_KEY"] = key.strip()
        say("GROK_AUTH_MODE=auto. Run --login-oauth once.")

    current_guilds_raw = _get_ci(existing, "ALLOWED_GUILD_IDS") or _get_ci(existing, "allowed_guild_ids")
    current_guilds = _format_list_for_display(current_guilds_raw)
    say("\n--- Safety ---")
    say("ALLOWED_GUILD_IDS is strongly recommended. Empty = the bot can join any server.")
    guilds = ask("Allowed guild IDs (comma-separated, or empty for all)", default=current_guilds or "")
    if guilds or (current_guilds_raw and confirm("Clear ALLOWED_GUILD_IDS?", default=False)):
        gstr = guilds.strip()
        try:
            if not gstr:
                guild_list: list[int] = []
            elif gstr.startswith("[") and gstr.endswith("]"):
                guild_list = json.loads(gstr)
            else:
                guild_list = [int(x.strip()) for x in gstr.split(",") if x.strip()]
            updates["allowed_guild_ids"] = guild_list
        except Exception as e:
            say(f"Warning: could not parse as a list ({e}). Saving as raw text.")
            updates["allowed_guild_ids"] = gstr

    say("\n--- TTS / Audio ---")
    voices = ["zagan", "eve", "ara", "rex", "sal", "leo"]
    cur_voice = _get_ci(existing, "tts_default_voice") or "eve"
    say(f"Current TTS voice: {cur_voice}")
    if confirm(f"Change default TTS voice? (current: {cur_voice})", default=False):
        say("Available voices: " + ", ".join(voices))
        v = ask("Voice", default=cur_voice)
        if v:
            updates["tts_default_voice"] = v.strip().lower()

    cur_lang = _get_ci(existing, "tts_default_language") or "en"
    say(f"Current TTS language: {cur_lang}")
    if confirm(f"Change default TTS language? (current: {cur_lang})", default=False):
        say("Common: en, en-US, auto")
        lang = ask("Language code", default=cur_lang)
        if lang:
            updates["tts_default_language"] = lang.strip()

    if confirm("Configure extra settings (model, log level, video)?", default=True):
        cur_model = _get_ci(existing, "grok_model") or "grok-4.3"
        m = ask("Grok model", default=cur_model)
        if m:
            updates["grok_model"] = m.strip()
        cur_log = _get_ci(existing, "log_level") or "INFO"
        level = ask("Log level (INFO, DEBUG, WARNING...)", default=cur_log)
        if level:
            updates["log_level"] = level.strip().upper()
        cur_video = _get_ci(existing, "enable_video_generation") or "true"
        updates["enable_video_generation"] = (
            "true" if confirm(f"Enable video generation? (current {cur_video})", default=cur_video.lower() != "false") else "false"
        )

    if not updates:
        say("\nNo changes requested. Nothing to write.")
        if will_need_oauth or (_get_ci(existing, "GROK_AUTH_MODE") or "").lower() in ("oauth", "auto"):
            if confirm("Start OAuth login now?", default=True):
                _try_run_oauth_login()
        say("\nTip: you can run python scripts/configure_env.py again anytime.")
        return

    say(f"\nAbout to safely update {len(updates)} value(s): {', '.join(sorted(updates.keys()))}")
    say("The writer will update in place, collapse old duplicates, keep comments, back up, and verify required keys.")
    if not confirm("Apply these changes to .env now?", default=True):
        say("Aborted by user.")
        return

    ok, msg, bak = safe_write_env(ENV_FILE, updates)
    if ok:
        say("\n.env updated (no duplicates).", "bold green")
        if bak:
            say(f"   Backup saved at: {bak}")
    else:
        say(f"\nUpdate failed: {msg}", "bold red")
        if bak:
            say(f"   A backup exists at: {bak}")
        sys.exit(1)

    say("\n--- Recommended next steps ---")
    say("  1. Validate: python -m groksito_discord --status")
    say("               python -m groksito_discord --check")
    say("  2. If you changed anything from the web dashboard, restart the Discord bot.")
    say("  3. Start:    python -m groksito_discord")

    current_final_mode = _get_ci(parse_env_file(ENV_FILE), "GROK_AUTH_MODE") or updates.get("GROK_AUTH_MODE", "")
    if str(current_final_mode).lower() in ("oauth", "auto") or will_need_oauth:
        say("\n--- OAuth ---")
        if confirm("Run OAuth login now (recommended if you chose oauth/auto)?", default=True):
            _try_run_oauth_login()

    say("\nDone. You can run python scripts/configure_env.py as many times as you want.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        say("\nInterrupted.", "yellow")
        sys.exit(130)
    except Exception as e:
        say(f"\nUnexpected error: {e}", "red")
        if "--debug" in sys.argv:
            import traceback
            traceback.print_exc()
        sys.exit(1)
