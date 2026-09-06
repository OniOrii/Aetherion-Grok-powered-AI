"""Slash wrappers for Aetherion music on the existing VoiceClient."""
from __future__ import annotations

import logging

import discord

from ..media.voice_music import resolve_track, start_playback
from ..media.voice_session import get_recv_cls, start_session

logger = logging.getLogger("aetherion.slash_music")


def _member_channel(interaction: discord.Interaction):
    member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None
    voice_state = getattr(member or interaction.user, "voice", None)
    return getattr(voice_state, "channel", None)


async def ensure_voice(interaction: discord.Interaction):
    if interaction.guild is None:
        return None, "Use this in a server."
    channel = _member_channel(interaction)
    if channel is None:
        return None, "Join a voice channel first."
    vc = interaction.guild.voice_client
    if vc and vc.is_connected():
        if getattr(vc, "channel", None) != channel:
            try:
                await vc.move_to(channel)
            except Exception as e:
                return None, f"Could not move to your channel: {e}"
        return vc, None
    try:
        recv_cls = get_recv_cls()
        vc = await channel.connect(cls=recv_cls or discord.VoiceClient)
        await start_session(interaction.guild, vc, interaction.user.id)
        return vc, None
    except Exception as e:
        logger.exception("ensure_voice failed")
        return None, f"Could not join voice: {e}"


def register_music(tree, is_guild_allowed) -> None:
    @tree.command(name="play", description="Play a song in your voice channel")
    @discord.app_commands.describe(query="Song name or artist, e.g. Astronaut in the Ocean Masked Wolf")
    async def play_slash(interaction: discord.Interaction, query: str):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message("Aetherion is not available in this server.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        q = (query or "").strip()
        if not q:
            await interaction.followup.send("Tell me what to play.", ephemeral=True)
            return
        vc, err = await ensure_voice(interaction)
        if err:
            await interaction.followup.send(err, ephemeral=True)
            return
        track = await resolve_track(q)
        if not track:
            await interaction.followup.send("I could not find that song.", ephemeral=True)
            return
        try:
            start_playback(vc, track["url"])
        except Exception as e:
            await interaction.followup.send(f"Found it but could not play it: {e}", ephemeral=True)
            return
        await interaction.followup.send(f"Playing **{track['title']}**.", ephemeral=True)

    @tree.command(name="pause", description="Pause or resume the current song")
    async def pause_slash(interaction: discord.Interaction):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message("Aetherion is not available in this server.", ephemeral=True)
            return
        vc = interaction.guild.voice_client if interaction.guild else None
        if not vc or not vc.is_connected():
            await interaction.response.send_message("I am not in a voice channel.", ephemeral=True)
            return
        if vc.is_paused():
            vc.resume()
            await interaction.response.send_message("Resumed.", ephemeral=True)
            return
        if vc.is_playing():
            vc.pause()
            await interaction.response.send_message("Paused.", ephemeral=True)
            return
        await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @tree.command(name="stop", description="Stop the current song")
    async def stop_slash(interaction: discord.Interaction):
        if interaction.guild and not is_guild_allowed(interaction.guild.id):
            await interaction.response.send_message("Aetherion is not available in this server.", ephemeral=True)
            return
        vc = interaction.guild.voice_client if interaction.guild else None
        if not vc or not vc.is_connected():
            await interaction.response.send_message("I am not in a voice channel.", ephemeral=True)
            return
        if vc.is_playing() or vc.is_paused():
            vc.stop()
            await interaction.response.send_message("Stopped.", ephemeral=True)
            return
        await interaction.response.send_message("Nothing is playing.", ephemeral=True)
