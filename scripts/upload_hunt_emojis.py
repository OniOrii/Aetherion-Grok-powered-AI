#!/usr/bin/env python3
"""Bulk-upload Aetherion Hunt HUD + rank PNGs as Discord Application Emojis.

Uploads the fixed 13 Hunt assets (6 HUD stats + 7 rank badges) to the bot's
application emoji set, then prints ready-to-paste ``.env`` lines
(``HUNT_EMOJI_*`` / ``HUNT_RANK_EMOJI_*``). Idempotent: existing emoji names
are reused unless ``--force``.

Usage (from repo root, with DISCORD_TOKEN in ``.env``)::

    python scripts/upload_hunt_emojis.py --dry-run
    python scripts/upload_hunt_emojis.py
    python scripts/upload_hunt_emojis.py --write-env
    python scripts/upload_hunt_emojis.py --env /path/to/.env --force

Requires ``DISCORD_TOKEN`` (or ``BOT_TOKEN``). Application ID from
``DISCORD_APPLICATION_ID`` / ``APPLICATION_ID`` / ``CLIENT_ID``, else resolved
via ``GET /oauth2/applications/@me``.

Animal portrait bulk upload is out of scope (``--animals`` stub only).
Stdlib + urllib only; no new dependencies.
"""

from __future__ import annotations

import argparse
import base64
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
API_BASE = "https://discord.com/api/v10"
USER_AGENT = "AetherionHuntEmojiUpload/1.0 (+https://github.com/OniOrii/Aetherion-Grok-powered-AI)"

# Max Discord application emoji image size (bytes).
MAX_EMOJI_BYTES = 256 * 1024
# Retry budget for HTTP 429.
MAX_RATE_LIMIT_RETRIES = 8


@dataclass(frozen=True)
class EmojiAsset:
    """One PNG → Discord app emoji name → .env key."""

    rel_path: str
    emoji_name: str
    env_key: str


# Fixed mapping (13 assets). phys.png is intentionally skipped (same role as atk).
HUNT_EMOJI_ASSETS: tuple[EmojiAsset, ...] = (
    EmojiAsset("src/groksito_discord/discord/assets/hunt_icons/hp.png", "hunt_hp", "HUNT_EMOJI_HP"),
    EmojiAsset("src/groksito_discord/discord/assets/hunt_icons/wp.png", "hunt_wp", "HUNT_EMOJI_WP"),
    EmojiAsset("src/groksito_discord/discord/assets/hunt_icons/atk.png", "hunt_atk", "HUNT_EMOJI_ATK"),
    EmojiAsset("src/groksito_discord/discord/assets/hunt_icons/mag.png", "hunt_mag", "HUNT_EMOJI_MAG"),
    EmojiAsset("src/groksito_discord/discord/assets/hunt_icons/pr.png", "hunt_pr", "HUNT_EMOJI_PR"),
    EmojiAsset("src/groksito_discord/discord/assets/hunt_icons/mr.png", "hunt_mr", "HUNT_EMOJI_MR"),
    EmojiAsset(
        "src/groksito_discord/discord/assets/hunt_ranks/rank_c.png",
        "aether_c",
        "HUNT_RANK_EMOJI_COMMON",
    ),
    EmojiAsset(
        "src/groksito_discord/discord/assets/hunt_ranks/rank_u.png",
        "aether_u",
        "HUNT_RANK_EMOJI_UNCOMMON",
    ),
    EmojiAsset(
        "src/groksito_discord/discord/assets/hunt_ranks/rank_r.png",
        "aether_r",
        "HUNT_RANK_EMOJI_RARE",
    ),
    EmojiAsset(
        "src/groksito_discord/discord/assets/hunt_ranks/rank_e.png",
        "aether_e",
        "HUNT_RANK_EMOJI_EPIC",
    ),
    EmojiAsset(
        "src/groksito_discord/discord/assets/hunt_ranks/rank_m.png",
        "aether_m",
        "HUNT_RANK_EMOJI_MYTHIC",
    ),
    EmojiAsset(
        "src/groksito_discord/discord/assets/hunt_ranks/rank_a.png",
        "aether_a",
        "HUNT_RANK_EMOJI_ASTRAL",
    ),
    EmojiAsset(
        "src/groksito_discord/discord/assets/hunt_ranks/rank_p.png",
        "aether_p",
        "HUNT_RANK_EMOJI_PRIMORDIAL",
    ),
)


def format_env_line(env_key: str, emoji_name: str, emoji_id: str | int) -> str:
    """Return a single ``KEY=<:name:id>`` line for ``.env``."""
    return f"{env_key}=<:{emoji_name}:{emoji_id}>"


def format_env_block(resolved: list[tuple[EmojiAsset, str]]) -> str:
    """Build a paste-ready ``.env`` block from ``(asset, emoji_id)`` pairs."""
    lines = [format_env_line(a.env_key, a.emoji_name, eid) for a, eid in resolved]
    return "\n".join(lines) + ("\n" if lines else "")


def parse_dotenv(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE parser (no export, strips optional quotes)."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        if key:
            out[key] = val
    return out


def update_env_keys(path: Path, updates: dict[str, str]) -> None:
    """Update or append keys in ``path`` without wiping unrelated lines."""
    if not updates:
        return
    lines: list[str] = []
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    seen: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#") or "=" not in line:
            new_lines.append(line if line.endswith("\n") else line + "\n")
            continue
        key = line.split("=", 1)[0].strip()
        if key in updates:
            if key not in seen:
                new_lines.append(f"{key}={updates[key]}\n")
                seen.add(key)
            # drop duplicate occurrences of keys we are updating
            continue
        new_lines.append(line if line.endswith("\n") else line + "\n")
    for key, val in updates.items():
        if key not in seen:
            new_lines.append(f"{key}={val}\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(new_lines), encoding="utf-8")


def _png_data_uri(png_bytes: bytes) -> str:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


class DiscordApiError(RuntimeError):
    """HTTP error from Discord with status + body snippet."""

    def __init__(self, status: int, body: str, *, retry_after: float | None = None):
        self.status = status
        self.body = body
        self.retry_after = retry_after
        super().__init__(f"Discord API HTTP {status}: {body[:500]}")


class DiscordClient:
    def __init__(self, token: str, *, timeout: float = 30.0):
        self._token = token
        self._timeout = timeout
        self._ctx = ssl.create_default_context()

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{API_BASE}{path}"
        data = None
        headers = {
            "Authorization": f"Bot {self._token}",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=self._timeout, context=self._ctx) as resp:
                    raw = resp.read()
                    if not raw:
                        return None
                    return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                err_body = exc.read().decode("utf-8", errors="replace")
                if exc.code == 429:
                    retry_after = _parse_retry_after(exc, err_body)
                    if attempt >= MAX_RATE_LIMIT_RETRIES:
                        raise DiscordApiError(429, err_body, retry_after=retry_after) from exc
                    wait = max(retry_after or 1.0, 0.5)
                    print(f"Rate limited; sleeping {wait:.1f}s then retrying…", file=sys.stderr)
                    time.sleep(wait)
                    continue
                if exc.code == 401:
                    raise DiscordApiError(
                        401,
                        "Unauthorized — check DISCORD_TOKEN / BOT_TOKEN "
                        f"(body: {err_body[:200]})",
                    ) from exc
                if exc.code == 413 or (
                    exc.code == 400 and "too large" in err_body.lower()
                ):
                    raise DiscordApiError(
                        exc.code,
                        f"Payload too large for Discord emoji upload: {err_body[:300]}",
                    ) from exc
                raise DiscordApiError(exc.code, err_body) from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(f"Network error talking to Discord: {exc}") from exc
        raise RuntimeError("rate-limit retries exhausted")


def _parse_retry_after(exc: urllib.error.HTTPError, body: str) -> float | None:
    hdr = exc.headers.get("Retry-After") if exc.headers else None
    if hdr:
        try:
            return float(hdr)
        except ValueError:
            pass
    try:
        payload = json.loads(body)
        ra = payload.get("retry_after")
        if ra is not None:
            return float(ra)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


def resolve_credentials(env: dict[str, str], client: DiscordClient | None) -> tuple[str, str]:
    """Return ``(token, application_id)``; may call Discord if app id missing."""
    token = (env.get("DISCORD_TOKEN") or env.get("BOT_TOKEN") or "").strip()
    if not token:
        raise SystemExit(
            "Missing bot token. Set DISCORD_TOKEN (or BOT_TOKEN) in .env "
            "or pass --env pointing at a file that has it."
        )
    app_id = (
        env.get("DISCORD_APPLICATION_ID")
        or env.get("APPLICATION_ID")
        or env.get("CLIENT_ID")
        or ""
    ).strip()
    if app_id:
        return token, app_id
    if client is None:
        client = DiscordClient(token)
    me = client.request("GET", "/oauth2/applications/@me")
    if not isinstance(me, dict) or not me.get("id"):
        raise SystemExit(
            "Could not resolve application id from /oauth2/applications/@me. "
            "Set DISCORD_APPLICATION_ID (or APPLICATION_ID / CLIENT_ID) in .env."
        )
    return token, str(me["id"])


def list_app_emojis(client: DiscordClient, app_id: str) -> dict[str, dict[str, Any]]:
    """Return ``{name: emoji_object}`` for existing application emojis."""
    payload = client.request("GET", f"/applications/{app_id}/emojis")
    items: list[Any]
    if isinstance(payload, dict):
        items = list(payload.get("items") or [])
    elif isinstance(payload, list):
        items = payload
    else:
        items = []
    by_name: dict[str, dict[str, Any]] = {}
    for item in items:
        if isinstance(item, dict) and item.get("name"):
            by_name[str(item["name"])] = item
    return by_name


def create_app_emoji(
    client: DiscordClient, app_id: str, name: str, png_bytes: bytes
) -> dict[str, Any]:
    body = {"name": name, "image": _png_data_uri(png_bytes)}
    result = client.request("POST", f"/applications/{app_id}/emojis", body=body)
    if not isinstance(result, dict) or not result.get("id"):
        raise RuntimeError(f"Unexpected create response for {name!r}: {result!r}")
    return result


def delete_app_emoji(client: DiscordClient, app_id: str, emoji_id: str) -> None:
    client.request("DELETE", f"/applications/{app_id}/emojis/{emoji_id}")


def load_png(repo_root: Path, asset: EmojiAsset) -> bytes:
    path = repo_root / asset.rel_path
    if not path.is_file():
        raise FileNotFoundError(f"Missing asset file: {path}")
    data = path.read_bytes()
    if len(data) > MAX_EMOJI_BYTES:
        raise SystemExit(
            f"Payload too big: {path} is {len(data)} bytes "
            f"(Discord app emoji limit is {MAX_EMOJI_BYTES})."
        )
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SystemExit(f"Not a PNG: {path}")
    return data


def upload_all(
    *,
    repo_root: Path,
    client: DiscordClient,
    app_id: str,
    force: bool,
    dry_run: bool,
) -> list[tuple[EmojiAsset, str]]:
    existing = {} if dry_run else list_app_emojis(client, app_id)
    resolved: list[tuple[EmojiAsset, str]] = []

    for asset in HUNT_EMOJI_ASSETS:
        png = load_png(repo_root, asset)
        prior = existing.get(asset.emoji_name)
        if dry_run:
            action = "re-upload" if (force and prior) else ("reuse" if prior else "upload")
            print(
                f"[dry-run] {action:8} {asset.emoji_name:12} "
                f"← {asset.rel_path} → {asset.env_key}"
            )
            eid = str(prior["id"]) if prior else "DRY_RUN_ID"
            resolved.append((asset, eid))
            continue

        if prior and not force:
            eid = str(prior["id"])
            print(f"reuse  {asset.emoji_name} id={eid}")
            resolved.append((asset, eid))
            continue

        if prior and force:
            print(f"force  deleting {asset.emoji_name} id={prior['id']} then re-upload")
            delete_app_emoji(client, app_id, str(prior["id"]))
            # Refresh local map so a mid-run name collision is less likely.
            existing.pop(asset.emoji_name, None)

        created = create_app_emoji(client, app_id, asset.emoji_name, png)
        eid = str(created["id"])
        existing[asset.emoji_name] = created
        print(f"upload {asset.emoji_name} id={eid}")
        resolved.append((asset, eid))

    return resolved


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Upload Hunt HUD + rank PNGs as Discord Application Emojis."
    )
    p.add_argument(
        "--env",
        type=Path,
        default=None,
        help="Path to .env (default: <repo>/.env)",
    )
    p.add_argument(
        "--write-env",
        action="store_true",
        help="Update/create HUNT_* emoji keys in the .env file (keeps other keys).",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Delete+recreate when an emoji name already exists (image refresh).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned uploads only; no Discord writes.",
    )
    p.add_argument(
        "--animals",
        action="store_true",
        help="Stub: animal portrait bulk upload is not implemented yet.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.animals:
        print(
            "--animals is a stub (animal portrait bulk upload not implemented yet). "
            "Continuing with the fixed 13 HUD+rank assets only.",
            file=sys.stderr,
        )

    env_path = (args.env or (REPO_ROOT / ".env")).resolve()
    env = parse_dotenv(env_path)

    if args.dry_run:
        # Token optional for dry-run planning of file paths; still warn if missing.
        token = (env.get("DISCORD_TOKEN") or env.get("BOT_TOKEN") or "").strip()
        if not token:
            print(
                "Note: no DISCORD_TOKEN/BOT_TOKEN in env (ok for --dry-run path listing).",
                file=sys.stderr,
            )
        client = DiscordClient(token or "dry-run-placeholder") if token else None
        app_id = (
            env.get("DISCORD_APPLICATION_ID")
            or env.get("APPLICATION_ID")
            or env.get("CLIENT_ID")
            or "DRY_APP"
        ).strip()
        # Skip Discord list in dry-run; just plan from files.
        resolved = upload_all(
            repo_root=REPO_ROOT,
            client=client or DiscordClient("dry-run"),
            app_id=app_id,
            force=args.force,
            dry_run=True,
        )
    else:
        token, app_id = resolve_credentials(env, None)
        client = DiscordClient(token)
        # Re-resolve app id via API if it came from env-less path already done;
        # resolve_credentials already handled @me when needed.
        resolved = upload_all(
            repo_root=REPO_ROOT,
            client=client,
            app_id=app_id,
            force=args.force,
            dry_run=False,
        )

    block = format_env_block(resolved)
    print("\n# Paste into .env (or re-run with --write-env):\n")
    print(block.rstrip("\n"))
    print()

    if args.write_env and not args.dry_run:
        updates = {
            asset.env_key: f"<:{asset.emoji_name}:{eid}>" for asset, eid in resolved
        }
        update_env_keys(env_path, updates)
        print(f"Updated {len(updates)} keys in {env_path}")
    elif args.write_env and args.dry_run:
        print("--write-env ignored with --dry-run (no file changes).", file=sys.stderr)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DiscordApiError as err:
        print(f"Error: {err}", file=sys.stderr)
        raise SystemExit(1) from err
    except FileNotFoundError as err:
        print(f"Error: {err}", file=sys.stderr)
        raise SystemExit(1) from err
