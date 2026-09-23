"""Tests for /audio Speech Tags help, wrapping parameter, and TTS text preparation."""

from groksito_discord.media.audio_handler import (
    AUDIO_WRAPPING_TAGS,
    XAI_TTS_DOCS_URL,
    _clean_text_for_tts,
    _prepare_text_for_tts,
    apply_wrapping_speech_tag,
    build_audio_speech_tags_embed,
)


def test_audio_wrapping_tags_cover_key_styles():
    values = {tag for _, tag in AUDIO_WRAPPING_TAGS}
    assert "whisper" in values
    assert "soft" in values
    assert "slow" in values
    assert "emphasis" in values
    assert len(AUDIO_WRAPPING_TAGS) <= 25


def test_apply_wrapping_speech_tag_wraps_text():
    assert apply_wrapping_speech_tag("Hola mundo", "whisper") == "<whisper>Hola mundo</whisper>"
    assert apply_wrapping_speech_tag("Hola mundo", None) == "Hola mundo"
    assert apply_wrapping_speech_tag("  ", "soft") == "  "


def test_build_audio_speech_tags_embed_points_to_usage_not_tag_lists():
    embed = build_audio_speech_tags_embed()

    assert embed.title
    assert embed.url == XAI_TTS_DOCS_URL
    assert embed.description
    assert "inline" in embed.description.lower()
    assert "style" in embed.description.lower()
    assert embed.fields == []


def test_clean_text_for_tts_preserves_speech_tags():
    raw = (
        "Entré y [pause] ahí estaba. [laugh] "
        "Tengo que contarte algo. <whisper>Es un secreto.</whisper> "
        "<slow><soft>Buenas noches.</soft></slow>"
    )
    cleaned = _clean_text_for_tts(raw)

    assert "[pause]" in cleaned
    assert "[laugh]" in cleaned
    assert "<whisper>Es un secreto.</whisper>" in cleaned
    assert "<slow><soft>Buenas noches.</soft></slow>" in cleaned


def test_prepare_text_for_tts_preserves_speech_tags():
    raw = "Hola [sigh] <whisper>muy bajito</whisper> adiós."
    prepared = _prepare_text_for_tts(raw)

    assert "[sigh]" in prepared
    assert "<whisper>muy bajito</whisper>" in prepared
