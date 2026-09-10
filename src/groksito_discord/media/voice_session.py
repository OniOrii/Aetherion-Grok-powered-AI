from .voice_impl import (
    DaveVoiceReceiver,
    VoiceSession,
    get_recv_cls,
    start_session as _start_session,
    stop_session,
)

DEFAULT_VOICE = "zagan"


async def start_session(guild, voice_client, user_id, voice_name=None):
    return await _start_session(
        guild,
        voice_client,
        user_id,
        voice_name=voice_name or DEFAULT_VOICE,
    )


__all__ = [
    "DEFAULT_VOICE",
    "DaveVoiceReceiver",
    "VoiceSession",
    "get_recv_cls",
    "start_session",
    "stop_session",
]
