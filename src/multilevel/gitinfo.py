from __future__ import annotations

import subprocess
from pathlib import Path


def git_commit(cwd: str | Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return ""


def git_dirty(cwd: str | Path) -> bool | None:
    try:
        out = subprocess.check_output(
            ["git", "status", "--short"],
            cwd=str(cwd),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return bool(out.strip())
    except Exception:
        return None

