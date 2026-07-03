from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from multilevel import __version__
from multilevel.gitinfo import git_commit, git_dirty


def dependency_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in ("numpy", "scipy", "torch"):
        try:
            module = __import__(name)
        except Exception:
            continue
        versions[name] = str(getattr(module, "__version__", "unknown"))
    return versions


def runtime_provenance(cwd: str | Path | None = None) -> dict[str, Any]:
    root = Path(cwd) if cwd is not None else Path.cwd()
    return {
        "tool_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "hardware": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
        },
        "dependency_versions": dependency_versions(),
        "git_commit": git_commit(root),
        "git_dirty": git_dirty(root),
    }


def attach_runtime_provenance(cert: dict[str, Any], cwd: str | Path | None = None) -> dict[str, Any]:
    out = dict(cert)
    out.update(runtime_provenance(cwd))
    return out
