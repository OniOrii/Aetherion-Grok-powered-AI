"""Aetherion slash commands. Game chart commands are not registered."""
from __future__ import annotations

from typing import Optional
import logging

import discord

from ..config import settings
from ..media.delivery import register_image_request
from ..media.audio_handler import (
    AUDIO_WRAPPING_TAGS,
    _tool_generate_audio,
    apply_wrapping_speech_tag,
    build_audio_speech_tags_embed,
    prepare_text_from_interaction,
)
from ..media.voice_session import get_recv_cls, start_session, stop_session

logger = logging.getLogger("aetherion.slash")

_ALLOWED_GUILD_IDS = set(settings.allowed_guild_ids)


def is_guild_allowed(guild_id):
    if not _ALLOWED_GUILD_IDS:
        return True
    if guild_id is None:
        return False
    return guild_id in _ALLOWED_GUILD_IDS


def register(tree, client) -> None:
    from .client import rate_limiter

    @tree.command(name="ping", description="Check if Aetherion is awake")
    async def ping(interaction: discord.Interaction):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        await interaction.response.send_message("Still here.", ephemeral=True)

    @tree.command(
        name="welcome",
        description="Set the channel for welcome banners (Manage Server required)",
    )
    @discord.app_commands.describe(channel="Channel where new-member welcomes should post")
    async def welcome_slash(interaction: discord.Interaction, channel: discord.TextChannel):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        if interaction.guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return
        member = interaction.user
        perms = getattr(member, "guild_permissions", None)
        if not perms or not (perms.manage_guild or perms.administrator):
            await interaction.response.send_message(
                "You need **Manage Server** to set the welcome channel.", ephemeral=True
            )
            return
        from .welcome import set_guild_welcome_channel
        set_guild_welcome_channel(interaction.guild.id, channel.id)
        await interaction.response.send_message(
            f"Welcome banners will now post in {channel.mention}.", ephemeral=True
        )

    @tree.command(
        name="datechannel",
        description="Set the voice channel that shows today's date (Manage Server required)",
    )
    @discord.app_commands.describe(channel="Voice channel to rename each night at midnight Eastern")
    async def datechannel_slash(interaction: discord.Interaction, channel: discord.VoiceChannel):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        if interaction.guild is None:
            await interaction.response.send_message("Use this command in a server.", ephemeral=True)
            return
        member = interaction.user
        perms = getattr(member, "guild_permissions", None)
        if not perms or not (perms.manage_guild or perms.administrator):
            await interaction.response.send_message(
                "You need **Manage Server** to set the date channel.", ephemeral=True
            )
            return
        from .date_dock import set_guild_date_channel, format_date_channel_name
        set_guild_date_channel(interaction.guild.id, channel.id)
        preview = format_date_channel_name()
        await interaction.response.send_message(
            f"Date dock set to {channel.mention}. It will show `{preview}` and update at 12:00 AM Eastern.",
            ephemeral=True,
        )
        try:
            if channel.name != preview:
                await channel.edit(name=preview, reason="Aetherion date dock setup")
        except discord.Forbidden:
            await interaction.followup.send(
                "Saved, but I could not rename it. Give me **Manage Channels** on that voice channel.",
                ephemeral=True,
            )
        except Exception:
            logger.exception("date dock immediate rename failed")

    @tree.command(
        name="audio",
        description="Generate TTS audio. Inline: [pause][laugh][sigh]. Optional wrapping style. Reply to a message.",
    )
    @discord.app_commands.describe(
        text="Text to speak. Inline: [pause], [laugh], [sigh], [breath], [chuckle], [long-pause], etc.",
        voice="Grok voice for the audio.",
        estilo="Optional wrapping style.",
    )
    @discord.app_commands.choices(
        voice=[
            discord.app_commands.Choice(name="Eve (energetic, recommended)", value="eve"),
            discord.app_commands.Choice(name="Ara (warm)", value="ara"),
            discord.app_commands.Choice(name="Rex (professional)", value="rex"),
            discord.app_commands.Choice(name="Sal (balanced)", value="sal"),
            discord.app_commands.Choice(name="Leo (authoritative)", value="leo"),
        ],
        estilo=[discord.app_commands.Choice(name=label, value=tag) for label, tag in AUDIO_WRAPPING_TAGS],
    )
    async def audio_slash(
        interaction: discord.Interaction,
        text: Optional[str] = None,
        voice: Optional[discord.app_commands.Choice[str]] = None,
        estilo: Optional[discord.app_commands.Choice[str]] = None,
    ):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        rl = getattr(client, "rate_limiter", rate_limiter)
        can_use, _ = rl.check(interaction.user.id)
        if not can_use:
            await interaction.response.send_message(
                "Tranquilo campeon, ya usaste tus 6 requests este minuto.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        provided = (text or "").strip()
        final_text = await prepare_text_from_interaction(interaction, provided)
        if not final_text:
            await interaction.followup.send(embed=build_audio_speech_tags_embed(), ephemeral=True)
            return
        selected_style = estilo.value if estilo else None
        final_text = apply_wrapping_speech_tag(final_text, selected_style)
        selected_voice = voice.value if voice else getattr(settings, "tts_default_voice", "eve") or "eve"
        selected_lang = getattr(settings, "tts_default_language", "es") or "es"
        request_id = None
        try:
            ch = getattr(interaction, "channel", None)
            request_id = await register_image_request(
                user_id=interaction.user.id,
                channel_id=getattr(ch, "id", 0) or 0,
                message_id=getattr(interaction, "id", 0),
                operation_type="audio",
                original_message=interaction,
            )
        except Exception as reg_err:
            logger.warning(f"[AudioSlash] Failed to register audio request: {reg_err}")
        result = await _tool_generate_audio(
            text=final_text, voice=selected_voice, language=selected_lang, request_id=request_id
        )
        if result and "SUCCESS" in result:
            style_note = f" · estilo **{selected_style}**" if selected_style else ""
            await interaction.followup.send(
                f"Audio generado con la voz **{selected_voice}**{style_note} y enviado al canal.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(result or "No se pudo generar el audio.", ephemeral=True)

    @tree.command(name="join", description="Join your current voice channel.")
    async def join_slash(interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.followup.send("Aetherion is not available in this server.", ephemeral=True)
            return
        member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
        voice_state = getattr(member or interaction.user, "voice", None)
        channel = getattr(voice_state, "channel", None)
        if channel is None:
            await interaction.followup.send("Join a voice channel first, then run /join.", ephemeral=True)
            return
        try:
            recv_cls = get_recv_cls()
            vc = interaction.guild.voice_client if interaction.guild else None
            if vc and vc.is_connected():
                await vc.disconnect()
            if recv_cls is None:
                await channel.connect()
                await interaction.followup.send(
                    f"Joined **{channel.name}**, but listening is not installed.", ephemeral=True
                )
                return
            vc = await channel.connect(cls=recv_cls)
            note = await start_session(interaction.guild, vc, interaction.user.id)
            await interaction.followup.send(f"Joined **{channel.name}**. {note}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Could not join voice: {e}", ephemeral=True)

    @tree.command(name="leave", description="Leave the voice channel.")
    async def leave_slash(interaction: discord.Interaction):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available in this server.", ephemeral=True
            )
            return
        vc = interaction.guild.voice_client if interaction.guild else None
        if not vc or not vc.is_connected():
            await interaction.response.send_message("I am not in a voice channel.", ephemeral=True)
            return
        name = getattr(vc.channel, "name", "voice")
        if interaction.guild:
            stop_session(interaction.guild.id)
        await vc.disconnect()
        await interaction.response.send_message(f"Left **{name}**.", ephemeral=True)

    @tree.context_menu(name="Leer en voz alta")
    async def read_aloud_context(interaction: discord.Interaction, message: discord.Message):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message(
                "Aetherion is not available on this server.", ephemeral=True
            )
            return
        rl = getattr(client, "rate_limiter", rate_limiter)
        can_use, _ = rl.check(interaction.user.id)
        if not can_use:
            await interaction.response.send_message(
                "Tranquilo campeon, ya usaste tus 6 requests este minuto.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        final_text = (getattr(message, "content", "") or "").strip()
        if not final_text:
            await interaction.followup.send("El mensaje no contiene texto para leer en voz alta.", ephemeral=True)
            return
        selected_voice = getattr(settings, "tts_default_voice", "eve") or "eve"
        selected_lang = getattr(settings, "tts_default_language", "es") or "es"
        request_id = None
        try:
            ch = getattr(interaction, "channel", None)
            request_id = await register_image_request(
                user_id=interaction.user.id,
                channel_id=getattr(ch, "id", 0) or 0,
                message_id=getattr(message, "id", 0) or getattr(interaction, "id", 0),
                operation_type="audio",
                original_message=message,
            )
        except Exception as reg_err:
            logger.warning(f"[ReadAloudContext] Failed to register audio request: {reg_err}")
        result = await _tool_generate_audio(
            text=final_text, voice=selected_voice, language=selected_lang, request_id=request_id
        )
        if result and "SUCCESS" in str(result).upper():
            await interaction.followup.send(
                f"Audio generado con la voz **{selected_voice}** y enviado al canal.", ephemeral=True
            )
        else:
            await interaction.followup.send(result or "No se pudo generar el audio.", ephemeral=True)
