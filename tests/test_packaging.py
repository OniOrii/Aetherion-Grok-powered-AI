"""Packaging and entry-point regression tests."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src" / "groksito_discord"

REQUIRED_CLASSIFIERS = (
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Operating System :: OS Independent",
    "Topic :: Communications :: Chat",
    "Framework :: AsyncIO",
)

DEPRECATED_LICENSE_CLASSIFIER = "License :: OSI Approved :: MIT License"

REQUIRED_KEYWORDS = ("discord", "bot", "grok", "xai", "aetherion", "ai", "llm")

REQUIRED_PROJECT_URLS = {
    "Homepage": "https://github.com/OniOrii/Aetherion-Grok-powered-AI",
    "Repository": "https://github.com/OniOrii/Aetherion-Grok-powered-AI",
    "Issues": "https://github.com/OniOrii/Aetherion-Grok-powered-AI/issues",
    "Documentation": "https://github.com/OniOrii/Aetherion-Grok-powered-AI#readme",
}


def _load_pyproject() -> dict:
    return tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_configure_env_script_replaces_root_setup_py():
    assert (PROJECT_ROOT / "scripts" / "configure_env.py").is_file()
    assert not (PROJECT_ROOT / "setup.py").exists()


def test_dockerfile_uses_canonical_entrypoint():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "src.groksito_discord" not in dockerfile
    assert "groksito" in dockerfile or "groksito_discord" in dockerfile or "aetherion" in dockerfile


def test_no_src_groksito_run_path_in_python_sources():
    offenders: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        if "src.groksito_discord" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(PROJECT_ROOT)))
    assert offenders == []


def test_groksito_main_entry_importable():
    from groksito_discord.main import run

    assert callable(run)


def test_module_main_entrypoint():
    import groksito_discord.__main__ as main_mod

    assert hasattr(main_mod, "run")


def test_pyproject_license_is_mit():
    assert _load_pyproject()["project"]["license"] == "MIT"


def test_pyproject_uses_license_expression_not_classifier():
    classifiers = _load_pyproject()["project"].get("classifiers", [])
    assert DEPRECATED_LICENSE_CLASSIFIER not in classifiers


def test_pyproject_has_pypi_classifiers():
    classifiers = _load_pyproject()["project"].get("classifiers", [])
    for required in REQUIRED_CLASSIFIERS:
        assert required in classifiers, f"Missing classifier: {required}"


def test_pyproject_has_keywords():
    keywords = _load_pyproject()["project"].get("keywords", [])
    for required in REQUIRED_KEYWORDS:
        assert required in keywords, f"Missing keyword: {required}"


def test_pyproject_has_project_urls():
    urls = _load_pyproject()["project"].get("urls", {})
    for name, value in REQUIRED_PROJECT_URLS.items():
        assert urls.get(name) == value, f"Missing or incorrect project URL: {name}"


def test_pyproject_project_name_is_aetherion():
    assert _load_pyproject()["project"]["name"] == "aetherion-discord-bot"
    scripts = _load_pyproject()["project"]["scripts"]
    assert scripts.get("aetherion") == "groksito_discord.main:run"
    assert scripts.get("groksito") == "groksito_discord.main:run"


def test_packaging_build_produces_sdist_and_wheel():
    dist_dir = PROJECT_ROOT / "dist-test-packaging"
    dist_dir.mkdir(exist_ok=True)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "build", "--sdist", "--wheel", "--outdir", str(dist_dir)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        artifacts = (
            list(dist_dir.glob("aetherion_discord_bot-*.tar.gz"))
            + list(dist_dir.glob("aetherion_discord_bot-*.whl"))
            + list(dist_dir.glob("aetherion-discord-bot-*.tar.gz"))
        )
        assert len(artifacts) >= 1, f"Expected sdist or wheel, found: {artifacts}"
    finally:
        for path in dist_dir.glob("*"):
            path.unlink()
        dist_dir.rmdir()
