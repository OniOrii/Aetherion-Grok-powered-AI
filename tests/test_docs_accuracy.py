"""Documentation accuracy regression tests."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def test_readme_maps_to_current_module_layout():
    readme = _read("README.md")
    assert "discord/client.py" in readme
    assert "core/grok_oauth.py" in readme
    assert "llm/client.py" in readme
    assert "bot.py" not in readme


def test_architecture_maps_to_current_module_layout():
    arch = _read("ARCHITECTURE.md")
    assert "discord/client.py" in arch
    assert "core/grok_oauth.py" in arch
    assert "media/delivery.py" in arch
    assert "bot.py" not in arch
    assert "video_generation.py" not in arch


def test_architecture_documents_pantsu_context_compat_once():
    arch = _read("ARCHITECTURE.md")
    assert arch.count("pantsu_context.json") == 1


def test_changelog_follows_keep_a_changelog_format():
    changelog = _read("CHANGELOG.md")
    assert changelog.startswith("# Changelog")
    assert "## [Unreleased]" in changelog
    assert "keepachangelog.com" in changelog.lower()
    assert "## [0.2.0]" in changelog


def test_release_workflow_includes_changelog_excerpt():
    release_workflow = _read(".github/workflows/release.yml")
    assert "extract_changelog" in release_workflow
    assert "CHANGELOG.md" in release_workflow


def test_release_guide_exists():
    release_doc = _read("RELEASE.md")
    assert "pre-release" in release_doc.lower() or "releasing" in release_doc.lower()
    assert "pyproject.toml" in release_doc
