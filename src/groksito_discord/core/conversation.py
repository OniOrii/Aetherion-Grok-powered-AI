"""
Conversation handling, activation detection, vision harvesting, and Groksito invocation.

Key responsibilities:
- Activation decision (mentions, replies, explicit visual intent + X-link support)
- Rich referenced context building (including reply chain traversal)
- Vision image harvesting (attachments + text-extracted URLs + chain fallback)
- Invocation of the LLM stack (llm + tools)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..utils.correlation import cid_prefix

from .. import context
from .safety import safe_reply
from ..media.delivery import DIRECT_DELIVERY_PERFORMED
from ..core.intent import is_image_edit_request
from ..llm.llm_utils import _detect_image_creation_intent

from ..utils.text import (
    extract_urls_from_text as _extract_urls_from_text,
    extract_x_links as _extract_x_links,
    extract_image_urls_from_text as _extract_image_urls_from_text,
)

from .intent import (
    STRONG_DIRECTED_KEYWORDS,
    GENERAL_REPLY_INQUIRY_KEYWORDS,
    _has_strong_directed_reply_intent,
    _has_recent_referent_intent,
    referenced_has_media_attachments,
    is_supported_vision_image,
    is_text_attachment,
    get_attachment_meta,
    _TEXT_INLINE_MAX_BYTES,
)

logger = logging.getLogger("groksito.conversation")

_RECENT_VISION_MAX_AGE_SECONDS: int = 15 * 60

async def _resolve_referenced_and_activation(
    message: Any,
    client_user: Any,
    author_display: str,
) -> tuple[Any | None, bool, bool, bool, bool, bool]:
    cid_p = cid_prefix()
    is_reply_to_bot = False
    explicit_visual_reply_intent = False
    is_reply_continuation = False
    has_x_link_intent = False
    referenced = None

    current_text = message.content or ""
    current_text_lower = current_text.lower()
    has_recent_referent = _has_recent_referent_intent(current_text)
    has_general_reply_inquiry = any(kw in current_text_lower for kw in GENERAL_REPLY_INQUIRY_KEYWORDS)

    is_mentioned_now = client_user in getattr(message, "mentions", [])

    if message.reference and message.reference.message_id:
        is_reply_continuation = True
        logger.debug(f"{cid_p}[Reply] Reply detected to message_id={message.reference.message_id} from {author_display}")

        try:
            referenced = await message.channel.fetch_message(message.reference.message_id)
            if getattr(referenced, "author", None) and referenced.author.id == client_user.id:
                is_reply_to_bot = True
                logger.info(f"{cid_p}[Reply] Direct reply to bot's previous message")
            else:
                logger.info(f"{cid_p}[Reply] Reply to another user's message (bot mentioned or activated)")

            ref_atts = getattr(referenced, "attachments", []) or []
            if ref_atts:
                image_count = sum(1 for a in ref_atts if getattr(a, "content_type", "").startswith("image/"))
                logger.info(f"{cid_p}[Reply] Referenced message has {len(ref_atts)} attachments ({image_count} images)")

        except Exception as fetch_err:
            logger.warning(f"{cid_p}[Reply] Could not fetch referenced message: {fetch_err}")

        text_lower = current_text_lower
        has_specific_x = any(kw in text_lower for kw in STRONG_DIRECTED_KEYWORDS)
        has_x_link_intent = has_specific_x or has_general_reply_inquiry

        if referenced_has_media_attachments(referenced) and (is_mentioned_now or is_reply_to_bot):
            explicit_visual_reply_intent = True
            logger.info(f"{cid_p}[Reply] Media referent on addressed turn (image/video attachment)")

        if has_x_link_intent:
            logger.info(f"{cid_p}[Reply] Reply inquiry intent detected (user appears to be asking about the referenced message content)")

    if is_mentioned_now and (has_general_reply_inquiry or has_recent_referent):
        has_x_link_intent = True
        if not (message.reference and message.reference.message_id):
            logger.info(f"{cid_p}[Mention] Recent referent / inquiry language on direct mention (ensuring recent context + possible vision for referent)")

    if is_mentioned_now:
        should_activate = True
        logger.info(f"{cid_p}[Activation] Direct @mention in message from {author_display}")
    elif is_reply_continuation and is_reply_to_bot:
        should_activate = True
        logger.info(f"{cid_p}[Activation] Direct reply to bot's own previous message from {author_display}")
    else:
        should_activate = False
        if is_reply_continuation:
            logger.info(
                f"{cid_p}[Groksito] Ignoring reply from {author_display} to another user "
                f"(no @mention, not a reply to bot)"
            )
        elif not is_mentioned_now:
            logger.info(f"{cid_p}[Groksito] Ignoring non-reply message from {author_display} (no mention)")

    user_text = getattr(message, "content", "") or ""
    has_current_image_attachment = referenced_has_media_attachments(message)
    has_image_creation_intent = _detect_image_creation_intent(
        user_text,
        has_reference_image=has_current_image_attachment
        or (referenced is not None and referenced_has_media_attachments(referenced)),
    )
    if has_image_creation_intent:
        logger.info(f"{cid_p}[Intent] Image creation/edit intent detected (will offer gen/edit tools)")

    if has_current_image_attachment and (is_mentioned_now or is_reply_to_bot):
        if is_image_edit_request(user_text, has_reference_image=True):
            explicit_visual_reply_intent = True
            logger.info(f"{cid_p}[Mention] Image edit/transform on attached image (addressed turn)")

    return referenced, is_reply_to_bot, explicit_visual_reply_intent, is_reply_continuation, has_x_link_intent, has_image_creation_intent


async def _build_referenced_context(referenced: Any) -> dict[str, Any]:
    cid_p = cid_prefix()
    if not referenced:
        return {}

    try:
        raw_content = (getattr(referenced, "content", "") or "").strip()
        if len(raw_content) > 700:
            ref_content = raw_content[:450] + " ... " + raw_content[-150:]
        else:
            ref_content = raw_content
        ref_author_obj = getattr(referenced, "author", None)
        ref_author = getattr(ref_author_obj, "display_name", "unknown")
        is_bot = bool(getattr(ref_author_obj, "bot", False))

        attachments = []
        image_urls = []
        for att in getattr(referenced, "attachments", []) or []:
            att_info = {
                "url": getattr(att, "url", ""),
                "filename": getattr(att, "filename", ""),
                "content_type": getattr(att, "content_type", ""),
            }
            attachments.append(att_info)
            if getattr(att, "content_type", "").startswith("image/"):
                image_urls.append(att.url)

        ref_text_for_extract = getattr(referenced, "content", "") or ""
        image_urls_from_text = _extract_image_urls_from_text(ref_text_for_extract)
        for u in image_urls_from_text:
            if u not in image_urls:
                image_urls.append(u)

        all_links = _extract_urls_from_text(ref_text_for_extract)
        x_links = _extract_x_links(ref_text_for_extract)

        context = {
            "author": ref_author,
            "is_bot": is_bot,
            "content": ref_content,
            "attachments": attachments,
            "has_attachments": len(attachments) > 0,
            "image_urls": image_urls,
            "external_links": all_links,
            "x_links": x_links,
            "has_x_links": len(x_links) > 0,
        }

        if image_urls:
            logger.info(f"{cid_p}[Reply] High-priority: {len(image_urls)} image(s) found in referenced message")
        if image_urls_from_text:
            logger.info(f"{cid_p}[Reply] Enriched referenced context with {len(image_urls_from_text)} text-extracted image URL(s) (no attachments)")
        if x_links:
            logger.info(f"{cid_p}[Reply] Detected {len(x_links)} X/Twitter link(s) in referenced message content")
        if all_links and not x_links:
            logger.info(f"{cid_p}[Reply] Enriched referenced context with {len(all_links)} external link(s)")

        return context
    except Exception as e:
        logger.warning(f"{cid_p}Failed to build referenced context: {e}")
        return {}


async def _fetch_reply_chain_context(
    message: Any,
    max_depth: int = 3,
    require_images: bool = False,
) -> list[dict]:
    cid_p = cid_prefix()
    contexts = []
    current_ref_id = getattr(message.reference, "message_id", None) if message.reference else None
    depth = 0

    while current_ref_id and depth < max_depth:
        try:
            ref_msg = await message.channel.fetch_message(current_ref_id)
            ctx = await _build_referenced_context(ref_msg)
            if ctx:
                contexts.append(ctx)
                logger.info(f"{cid_p}[ReplyChain] Fetched chain level {depth+1}: has_images={bool(ctx.get('image_urls'))}")

            if require_images and ctx.get("image_urls"):
                break
            if ctx.get("content") and len(ctx.get("content", "")) > 100:
                break

            parent_ref = getattr(ref_msg, "reference", None)
            current_ref_id = getattr(parent_ref, "message_id", None) if parent_ref else None
            depth += 1
        except Exception as e:
            logger.warning(f"{cid_p}[ReplyChain] Failed to fetch chain level {depth}: {e}")
            break

    if contexts:
        logger.info(f"{cid_p}[ReplyChain] Collected {len(contexts)} messages from reply chain (depth traversed: {depth})")

    return contexts


async def _maybe_fetch_text_content(att: Any, cid_p: str) -> str | None:
    try:
        size = getattr(att, "size", 0) or 0
        if size > _TEXT_INLINE_MAX_BYTES or size <= 0:
            return None
        url = getattr(att, "url", None)
        if not url:
            return None
        import httpx
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text[:4000]
            if len(text) < 10:
                return None
            return text
    except Exception as fetch_err:
        logger.debug(f"{cid_p}[Vision] text inline fetch skipped: {fetch_err}")
        return None


async def _extract_gif_frames_as_vision_urls(attachment_url: str, cid_p: str, num_frames: int = 3, max_bytes: int = 15 * 1024 * 1024) -> list[str]:
    if num_frames < 1:
        return []
    import tempfile
    import os
    tmp_path = None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(attachment_url, follow_redirects=True)
            resp.raise_for_status()
            if len(resp.content) > max_bytes:
                logger.debug(f"{cid_p}[Vision] attachment too large for frame extraction")
                return []
            media_bytes = resp.content

        import subprocess
        import base64

        with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as tmp:
            tmp.write(media_bytes)
            tmp_path = tmp.name

        duration = 2.0
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", tmp_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            if probe.returncode == 0 and probe.stdout.strip():
                duration = max(0.1, float(probe.stdout.strip()))
        except Exception:
            pass

        positions = [0.0]
        if num_frames >= 2:
            positions.append(duration / 2.0)
        if num_frames >= 3:
            positions.append(max(0.05, duration - 0.2))
        positions = sorted(set(positions))[:num_frames]

        frames: list[str] = []
        for t in positions:
            cmd = [
                "ffmpeg", "-ss", str(t), "-i", tmp_path,
                "-frames:v", "1",
                "-f", "image2pipe",
                "-vcodec", "png",
                "-y", "pipe:1"
            ]
            proc = subprocess.run(cmd, capture_output=True, timeout=10)
            if proc.returncode == 0 and proc.stdout:
                b64 = base64.b64encode(proc.stdout).decode("ascii")
                frames.append(f"data:image/png;base64,{b64}")

        if frames:
            logger.info(f"{cid_p}[Vision] Extracted {len(frames)} frames from GIF for vision (better than single black frame)")
        else:
            logger.debug(f"{cid_p}[Vision] No frames extracted from GIF")
        return frames
    except Exception as conv_err:
        logger.debug(f"{cid_p}[Vision] GIF frame extraction skipped: {conv_err}")
        return []
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


async def _harvest_vision_images(
    message: Any,
    referenced: Any | None,
    explicit_visual_reply_intent: bool,
    is_reply_continuation: bool = False,
    has_x_link_intent: bool = False,
    is_mentioned: bool = False,
    user_text: str = "",
) -> tuple[list[str], list[dict[str, Any]]]:
    cid_p = cid_prefix()
    image_urls: list[str] = []
    attachments: list[dict[str, Any]] = []

    for att in getattr(message, "attachments", []) or []:
        meta = get_attachment_meta(att)
        if is_text_attachment(att):
            text = await _maybe_fetch_text_content(att, cid_p)
            if text:
                meta = dict(meta)
                meta["text_content"] = text
                logger.debug(f"{cid_p}[Vision] Inlined text content for current attachment: {meta.get('filename')}")
        attachments.append(meta)
        if is_supported_vision_image(att):
            u = getattr(att, "url", None) or meta.get("url")
            if u and u not in image_urls:
                image_urls.append(u)
                logger.debug(f"{cid_p}[Vision] Image URL from attachment (current msg, supported): {u[:70]}...")
        else:
            ct = (getattr(att, "content_type", "") or "").lower()
            fn = (getattr(att, "filename", "") or "").lower()
            if "gif" in ct or fn.endswith(".gif") or "webp" in ct or fn.endswith(".webp"):
                for vurl in await _extract_gif_frames_as_vision_urls(getattr(att, "url", ""), cid_p, num_frames=3):
                    if vurl and vurl not in image_urls:
                        image_urls.append(vurl)
                logger.debug(f"{cid_p}[Vision] Added up to 3 GIF frames as PNG data URIs for vision")

    if referenced and is_reply_continuation:
        for att in getattr(referenced, "attachments", []) or []:
            meta = get_attachment_meta(att)
            attachments.append(meta)
            if is_supported_vision_image(att):
                u = getattr(att, "url", None) or meta.get("url")
                if u and u not in image_urls:
                    image_urls.append(u)
                    logger.debug(f"{cid_p}[Vision] Image URL from attachment (referenced, supported): {u[:70]}...")
            else:
                ct = (getattr(att, "content_type", "") or "").lower()
                fn = (getattr(att, "filename", "") or "").lower()
                if "gif" in ct or fn.endswith(".gif") or "webp" in ct or fn.endswith(".webp"):
                    for vurl in await _extract_gif_frames_as_vision_urls(getattr(att, "url", ""), cid_p, num_frames=3):
                        if vurl and vurl not in image_urls:
                            image_urls.append(vurl)

        if is_reply_continuation and (explicit_visual_reply_intent or has_x_link_intent):
            ref_text = getattr(referenced, "content", "") or ""
            text_urls = _extract_image_urls_from_text(ref_text)
            if text_urls:
                logger.info(f"{cid_p}[Reply] Extracted {len(text_urls)} image URL(s) from referenced_text")
            for u in text_urls:
                if u not in image_urls:
                    image_urls.append(u)

    if is_reply_continuation and (explicit_visual_reply_intent or has_x_link_intent) and not image_urls:
        logger.info(f"{cid_p}[Reply] No images in direct referenced message — traversing reply chain for visual context")
        try:
            chain_contexts = await _fetch_reply_chain_context(
                message, max_depth=3, require_images=True
            )
            for ctx in chain_contexts:
                for url in ctx.get("image_urls", []):
                    if url not in image_urls:
                        image_urls.append(url)
        except Exception as chain_err:
            logger.warning(f"{cid_p}[Reply] Chain traversal for images failed: {chain_err}")

    if not image_urls and is_mentioned and user_text:
        if _has_recent_referent_intent(user_text):
            try:
                ch = getattr(getattr(message, "channel", None), "id", None)
                if ch:
                    from ..context import get_recent_channel_messages
                    recent_msgs = get_recent_channel_messages(ch, limit=8)
                    added = 0
                    now = time.time()
                    for m in reversed(recent_msgs):
                        msg_ts = m.get("ts") or 0
                        age_ok = (now - msg_ts) <= _RECENT_VISION_MAX_AGE_SECONDS if msg_ts else False
                        if age_ok:
                            for u in (m.get("image_urls") or []):
                                if u and u not in image_urls:
                                    image_urls.append(u)
                                    added += 1
                                if added >= 2:
                                    break
                        else:
                            if (m.get("image_urls") or []) and msg_ts:
                                logger.debug(f"{cid_p}[Vision] Skipped stale image(s) from recent msg (age >15m) to avoid 404 on xAI vision fetch")
                        if added >= 2:
                            break
                        if added < 2 and age_ok:
                            content = m.get("content") or ""
                            for u in _extract_image_urls_from_text(content):
                                if u and u not in image_urls:
                                    image_urls.append(u)
                                    added += 1
                                if added >= 2:
                                    break
                        if added >= 2:
                            break
                    if added:
                        logger.info(f"{cid_p}[Vision] Added {added} recent channel image(s) for direct mention + recent visual reference (lightweight)")
            except Exception as recent_vision_err:
                logger.debug(f"{cid_p}[Vision] Recent channel image pull skipped: {recent_vision_err}")

    raw_count = len(image_urls)
    from ..utils.text import filter_unreliable_vision_urls
    image_urls = filter_unreliable_vision_urls(image_urls)
    if len(image_urls) < raw_count:
        logger.info(f"{cid_p}[Vision] Filtered {raw_count - len(image_urls)} unreliable image URL(s) (X/Twitter previews or Discord link-embed proxies) to prevent 404 on vision; using text + x_search fallback")

    def _is_vision_compatible(u: str) -> bool:
        if not u:
            return False
        if u.startswith("data:image/"):
            return True
        try:
            p = u.lower().split("?", 1)[0].split("#", 1)[0]
            return p.endswith((".jpg", ".jpeg", ".png"))
        except Exception:
            return False
    image_urls = [u for u in image_urls if _is_vision_compatible(u)]

    if image_urls:
        logger.info(f"{cid_p}[Vision] Total image URLs harvested for this turn: {len(image_urls)} (reply_continuation={is_reply_continuation}, mentioned={is_mentioned})")

    if attachments:
        n_text = sum(1 for a in attachments if "text_content" in a)
        n_vision = sum(
            1 for a in attachments
            if (str(a.get("content_type", "")).lower().startswith(("image/jpeg", "image/png")))
            or str(a.get("filename", "")).lower().endswith((".jpg", ".jpeg", ".png"))
        )
        logger.info(f"{cid_p}{len(attachments)} attachments harvested ({n_vision} vision, {n_text} text inlined)")

    return image_urls[:5], attachments


async def _invoke_groksito(
    message: Any,
    referenced: Any | None,
    referenced_context: dict | None,
    author_display: str,
    is_meta_convo: bool,
    explicit_visual_reply_intent: bool,
    is_reply_continuation: bool = False,
    has_x_link_intent: bool = False,
    is_reply_to_bot: bool = False,
    has_image_creation_intent: bool = False,
    is_mentioned: bool = False,
) -> None:
    cid_p = cid_prefix()
    try:
        from ..llm import call_grok_with_tools
    except Exception as import_err:
        logger.error(f"{cid_p}Failed to import Groksito LLM modules: {import_err}")
        await safe_reply(message, "Sorry, I am having trouble initializing right now.", mention_author=False)
        return

    user_message = message.content or ""

    image_urls, attachments = await _harvest_vision_images(
        message, referenced, explicit_visual_reply_intent,
        is_reply_continuation=is_reply_continuation,
        has_x_link_intent=has_x_link_intent,
        is_mentioned=is_mentioned,
        user_text=user_message,
    )

    chain_contexts: list[dict] = []
    if (is_reply_continuation or is_mentioned) and (has_x_link_intent or _has_recent_referent_intent(user_message) or explicit_visual_reply_intent):
        try:
            chain_contexts = await _fetch_reply_chain_context(
                message, max_depth=3, require_images=False
            )
            if chain_contexts:
                logger.info(f"{cid_p}[ReplyChain] Fetched text chain (levels={len(chain_contexts)}) for referent / link / visual intent")
        except Exception as chain_err:
            logger.warning(f"{cid_p}[Reply] Text chain fetch failed: {chain_err}")

    try:
        response_text = await call_grok_with_tools(
            user_message=user_message,
            author_name=author_display,
            channel_id=message.channel.id,
            original_message=message,
            image_urls=image_urls,
            attachments=attachments,
            referenced_context=referenced_context,
            reply_chain_contexts=chain_contexts,
            has_visual_intent=has_image_creation_intent,
            is_reply_continuation=is_reply_continuation,
            has_x_link_intent=has_x_link_intent,
            is_reply_to_bot=is_reply_to_bot,
            is_mentioned=is_mentioned,
        )

        if response_text is not DIRECT_DELIVERY_PERFORMED and response_text:
            try:
                from ..utils import emoji_registry
                gid = getattr(message.guild, "id", None) if getattr(message, "guild", None) else None
                guild_obj = getattr(message, "guild", None)
                response_text = emoji_registry.normalize_bot_emoji_output(response_text, gid, guild_obj=guild_obj)
            except Exception as emoji_norm_err:
                logger.debug(f"{cid_p}[Emoji] normalize_bot_emoji_output failed (non-fatal): {emoji_norm_err}")

            await safe_reply(message, response_text, mention_author=False)
    except Exception as e:
        logger.exception(f"{cid_p}Error invoking Groksito: {e}")
        await safe_reply(message, "Something went wrong processing your message. Please try again.", mention_author=False)


_resolve_referenced_and_activation = _resolve_referenced_and_activation
_build_referenced_context = _build_referenced_context
_harvest_vision_images = _harvest_vision_images
_invoke_groksito = _invoke_groksito
