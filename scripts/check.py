#!/usr/bin/env python3
"""Run the verification suite.

Usage:
    python scripts/check.py
    python scripts/check.py --skip-docker
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run(label: str, cmd: list[str], *, cwd: Path = PROJECT_ROOT) -> int:
    print(f"\n==> {label}")
    print("    " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=cwd, check=False)
    if result.returncode != 0:
        print(f"FAILED: {label} (exit {result.returncode})")
    else:
        print(f"OK: {label}")
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Aetherion verification")
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip Docker image builds (faster local runs)",
    )
    args = parser.parse_args()

    failures = 0
    py = sys.executable

    failures += _run("pytest", [py, "-m", "pytest", "-q"])
    failures += _run("config check", [py, "-m", "groksito_discord", "--check"])
    failures += _run("status report", [py, "-m", "groksito_discord", "--status"])

    if not args.skip_docker:
        failures += _run(
            "docker build (bot)",
            ["docker", "build", "--target", "bot", "-t", "aetherion-bot:check", "."],
        )
        failures += _run(
            "docker build (web)",
            ["docker", "build", "--target", "web", "-t", "aetherion-web:check", "."],
        )

    if failures:
        print(f"\nVerification finished with {failures} failing step(s).")
        return 1

    print("\nAll verification steps passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
