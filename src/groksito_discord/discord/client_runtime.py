"""Runtime Discord client for Aetherion."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Any, Deque, Optional

from ..utils.correlation import cid_prefix, generate_correlation_id, set_correlation_id
from ..utils.errors import log_auxiliary_failure
import discord

try:
    from discord.voice_client import VoiceClient as _DiscordVoiceClient
    _DiscordVoiceClient.warn_nacl = False
    _DiscordVoiceClient.warn_dave = False
except Exception:
    pass

from ..config import settings
from ..core.safety import safe_reply as _safe_reply
from .integrations import gamemeca
from ..utils.text import extract_urls_from_text
from ..media.delivery import register_image_request
from ..media.audio_handler import (
    AUDIO_WRAPPING_TAGS,
    _tool_generate_audio,
    apply_wrapping_speech_tag,
    build_audio_speech_tags_embed,
    prepare_text_from_interaction,
)
from ..media.voice_session import get_recv_cls, start_session, stop_session
from .slash_commands import register as register_slash_commands

logger = logging.getLogger("aetherion.client")

_ALLOWED_GUILD_IDS: set[int] = set(settings.allowed_guild_ids)
_discord_client: "discord.Client | None" = None
_discord_ready = asyncio.Event()
_discord_task: asyncio.Task | None = None
rate_limiter: Any = None
tree: Any = None


async def _periodic_gamemeca_ranking_update(gamemeca_module):
    try:
        await gamemeca_module.refresh_ranking()
    except Exception as e:
        logger.debug(f"[Gamemeca] initial refresh failed (non-fatal): {e}")
    while True:
        await asyncio.sleep(24 * 3600)
        try:
            await gamemeca_module.refresh_ranking()
        except Exception as e:
            logger.warning(f"[Gamemeca] background refresh failed: {e}")


def is_guild_allowed(guild_id: int | None) -> bool:
    if not _ALLOWED_GUILD_IDS:
        return True
    if guild_id is None:
        return False
    return guild_id in _ALLOWED_GUILD_IDS


class RateLimiter:
    def __init__(self, max_requests: int = 6, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.records: dict[int, Deque[float]] = defaultdict(deque)

    def check(self, user_id: int) -> tuple[bool, int]:
        now = time.time()
        user_records = self.records[user_id]
        while user_records and now - user_records[0] > self.window:
            user_records.popleft()
        used = len(user_records)
        if used >= self.max_requests:
            return False, 0
        user_records.append(now)
        return True, self.max_requests - used

    def get_remaining(self, user_id: int) -> int:
        now = time.time()
        user_records = self.records[user_id]
        while user_records and now - user_records[0] > self.window:
            user_records.popleft()
        return max(0, self.max_requests - len(user_records))


async def ensure_discord_connected(conversational: bool = True) -> "discord.Client":
    global _discord_client, _discord_task, rate_limiter, tree
    if _discord_client is not None:
        await _discord_ready.wait()
        return _discord_client
    if not settings.discord_bot_token:
        raise RuntimeError("DISCORD_BOT_TOKEN is not configured in .env")

    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True
    intents.message_content = True
    intents.voice_states = True
    _discord_client = discord.Client(intents=intents)
    rate_limiter = RateLimiter()
    tree = discord.app_commands.CommandTree(_discord_client)
    _discord_client.rate_limiter = rate_limiter
    _discord_client.command_tree = tree
    register_slash_commands(tree, _discord_client)

    from .. import context
    from ..core.conversation import (
        _resolve_referenced_and_activation,
        _build_referenced_context,
        _invoke_groksito,
    )

    @_discord_client.event
    async def on_ready():
        logger.info(f"Aetherion connected as {_discord_client.user}")
        try:
            await _discord_client.change_presence(
                activity=discord.Activity(type=discord.ActivityType.watching, name="Interstellar")
            )
            await tree.sync()
            logger.info("Slash commands synchronized")
        except Exception as e:
            logger.error(f"Error syncing slash commands: {e}")
        _discord_ready.set()
        try:
            from ..utils import emoji_registry
            asyncio.create_task(emoji_registry.scan_all_accessible_emojis(_discord_client))
        except Exception:
            pass
        try:
            asyncio.create_task(_periodic_gamemeca_ranking_update(gamemeca))
        except Exception:
            pass
        try:
            from .date_dock import date_dock_loop
            asyncio.create_task(date_dock_loop(_discord_client))
        except Exception:
            pass
        try:
            from ..core.health import (
                write_bot_heartbeat,
                write_bot_guilds_snapshot,
                write_bot_stats,
                write_bot_health_snapshot,
            )
            guilds_list = getattr(_discord_client, "guilds", []) or []
            write_bot_heartbeat(
                connected=True,
                user=str(_discord_client.user),
                user_id=_discord_client.user.id if _discord_client.user else None,
                guilds=len(guilds_list),
                latency=getattr(_discord_client, "latency", None),
            )
            write_bot_guilds_snapshot(guilds_list)
            write_bot_stats()
            write_bot_health_snapshot()
        except Exception as health_err:
            log_auxiliary_failure(logger, "initial health snapshot write", health_err, feature="Health")

    @_discord_client.event
    async def on_disconnect():
        try:
            from ..core.health import write_bot_heartbeat
            write_bot_heartbeat(connected=False)
        except Exception:
            pass

    @_discord_client.event
    async def on_resumed():
        try:
            from ..core.health import write_bot_heartbeat, write_bot_guilds_snapshot, write_bot_stats, write_bot_health_snapshot
            guilds_list = getattr(_discord_client, "guilds", []) or []
            write_bot_heartbeat(
                connected=True,
                user=str(getattr(_discord_client, "user", None)),
                user_id=getattr(getattr(_discord_client, "user", None), "id", None),
                guilds=len(guilds_list),
                latency=getattr(_discord_client, "latency", None),
            )
            write_bot_guilds_snapshot(guilds_list)
            write_bot_stats()
            write_bot_health_snapshot()
        except Exception:
            pass

    @_discord_client.event
    async def on_guild_join(guild):
        try:
            from ..utils import emoji_registry
            asyncio.create_task(emoji_registry.ensure_guild_emojis_registered(guild))
        except Exception:
            pass

    @_discord_client.event
    async def on_member_join(member):
        from .welcome import on_member_join as _welcome_join
        await _welcome_join(member)

    @_discord_client.event
    async def on_member_update(before, after):
        from .welcome import on_member_update as _welcome_update
        await _welcome_update(before, after)

    @_discord_client.event
    async def on_message(message: discord.Message):
        cid_p = ""
        try:
            if message.author.id == _discord_client.user.id:
                return
            author_display = getattr(message.author, "display_name", None) or getattr(message.author, "name", "Usuario")
            if message.author.id == 1022200760018161684:
                author_display = "Ori (creator of Aetherion)"
            cid = generate_correlation_id()
            set_correlation_id(cid)
            cid_p = cid_prefix()
            if message.guild and not is_guild_allowed(message.guild.id):
                return
            from ..media.voice_reply import maybe_handle_voice_note
            if await maybe_handle_voice_note(message):
                return
            try:
                from ..utils import emoji_registry
                asyncio.create_task(emoji_registry.ensure_guild_emojis_registered(message.guild))
                emoji_registry.record_emojis_from_message(message)
            except Exception:
                pass
            image_urls: list[str] = []
            links: list[str] = []
            try:
                for att in getattr(message, "attachments", []) or []:
                    ct = getattr(att, "content_type", "") or ""
                    if "image" in ct.lower() and getattr(att, "url", None):
                        image_urls.append(att.url)
                for emb in getattr(message, "embeds", []) or []:
                    for key in ("image", "thumbnail"):
                        obj = getattr(emb, key, None)
                        if obj and getattr(obj, "url", None):
                            image_urls.append(obj.url)
                if message.content:
                    for clean in extract_urls_from_text(message.content):
                        if clean and clean not in links:
                            links.append(clean)
            except Exception:
                pass
            context.update_from_message(
                channel_id=message.channel.id,
                user_id=message.author.id,
                author_name=author_display,
                content=message.content or "",
                is_bot=False,
                image_urls=image_urls,
                links=links,
            )
            result = await _resolve_referenced_and_activation(
                message=message,
                client_user=_discord_client.user,
                author_display=author_display,
            )
            if len(result) >= 6:
                referenced, is_reply_to_bot, explicit_visual, is_reply_cont, has_x_link_intent, has_image_creation = result
            else:
                referenced, is_reply_to_bot, explicit_visual, is_reply_cont, has_x_link_intent = result if len(result) == 5 else (*result, False)
                has_image_creation = False
            is_mentioned = _discord_client.user in getattr(message, "mentions", [])
            if not is_mentioned and not is_reply_to_bot:
                return
            rl = getattr(_discord_client, "rate_limiter", rate_limiter)
            can_use, _ = rl.check(message.author.id)
            if not can_use:
                await _safe_reply(message, "Tranquilo campeon, ya usaste tus 6 requests este minuto.", mention_author=False)
                return
            if message.reference and message.reference.message_id and referenced is None:
                try:
                    referenced = await message.channel.fetch_message(message.reference.message_id)
                except Exception:
                    pass
            referenced_context = await _build_referenced_context(referenced) if referenced else None
            is_meta = False
            try:
                is_meta = context.is_conversation_meta_question(message.content or "")
            except Exception:
                pass
            async with message.channel.typing():
                await _invoke_groksito(
                    message=message,
                    referenced=referenced,
                    referenced_context=referenced_context,
                    author_display=author_display,
                    is_meta_convo=is_meta,
                    explicit_visual_reply_intent=explicit_visual,
                    is_reply_continuation=is_reply_cont,
                    has_x_link_intent=has_x_link_intent,
                    is_reply_to_bot=is_reply_to_bot,
                    has_image_creation_intent=has_image_creation,
                    is_mentioned=is_mentioned,
                )
        except Exception as e:
            logger.exception(f"{cid_p}Unhandled error in on_message: {e}")

    async def _runner():
        try:
            await _discord_client.start(settings.discord_bot_token)
        except Exception as exc:
            logger.error(f"Discord connection failed: {exc}", exc_info=True)
            _discord_ready.clear()

    _discord_task = asyncio.create_task(_runner())
    try:
        await asyncio.wait_for(_discord_ready.wait(), timeout=30.0)
    except asyncio.TimeoutError:
        raise RuntimeError("Timeout waiting for Discord connection. Check token and network.")

    async def _heartbeat_updater() -> None:
        while True:
            try:
                await asyncio.sleep(35)
                if _discord_client and getattr(_discord_client, "is_ready", lambda: False)():
                    try:
                        from ..core.health import write_bot_heartbeat, write_bot_guilds_snapshot, write_bot_stats, write_bot_health_snapshot
                        guilds_list = getattr(_discord_client, "guilds", []) or []
                        write_bot_heartbeat(
                            connected=True,
                            user=str(getattr(_discord_client, "user", None)),
                            user_id=getattr(getattr(_discord_client, "user", None), "id", None),
                            guilds=len(guilds_list),
                            latency=getattr(_discord_client, "latency", None),
                        )
                        write_bot_guilds_snapshot(guilds_list)
                        write_bot_stats()
                        write_bot_health_snapshot()
                    except Exception:
                        pass
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(10)

    asyncio.create_task(_heartbeat_updater())
    return _discord_client
