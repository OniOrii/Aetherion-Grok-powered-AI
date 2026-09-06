# Releasing Aetherion

This document describes how maintainers cut pre-releases and stable releases for **Aetherion**. The automated pipeline lives in [`.github/workflows/release.yml`](./.github/workflows/release.yml).

## Who releases

Release tagging is a **maintainer** responsibility ([@OniOrii](https://github.com/OniOrii)). Contributors land changes on `main`; maintainers cut tags when `main` is ready.

## Versioning policy

This project follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).

**Source of truth:** `version` in [`pyproject.toml`](./pyproject.toml). The installed package exposes the same value via `groksito_discord.__version__` (import path is unchanged so Railway keeps starting).

### Pre-release vs stable

| Kind | When to use | Example tags |
|------|-------------|--------------|
| **Pre-release** | Validate packaging and release notes before calling a version stable. | `v0.3.0-pre.1`, `v0.3.0-rc.1` |
| **Stable** | `main` is green and changelog is finalized. | `v0.3.0`, `v1.0.0` |

**Tag format:** always prefix with `v`. Pushing a `v*` tag triggers the Release workflow.

## Prerequisites (must pass before tagging)

```bash
python scripts/check.py --skip-docker
python scripts/check.py
```

`scripts/check.py` runs pytest, `python -m groksito_discord --check`, `python -m groksito_discord --status`, and optional Docker builds.

Do not tag if `main` CI is failing.

## Release checklist

1. Move `CHANGELOG.md` `[Unreleased]` entries into a dated section.
2. Bump `version` in `pyproject.toml`.
3. Run `python scripts/check.py --skip-docker`.
4. Tag and push:

```bash
git checkout main
git pull origin main
git tag -a v0.3.0 -m "v0.3.0"
git push origin v0.3.0
```

## Production host

Aetherion production runs on Railway from this repo. After each tag or `main` push, wait until the deployment is **Active** before testing `/join`.

The Railway start command remains `pip install -e . && groksito` on purpose. `aetherion` is an alias to the same entry point.

## Related docs

- [CHANGELOG.md](./CHANGELOG.md)
- [SECURITY.md](./SECURITY.md)
- [README.md](./README.md)
