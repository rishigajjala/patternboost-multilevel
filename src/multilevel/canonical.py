from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_obj(obj: Any) -> str:
    return hashlib.sha256(canonical_dumps(obj).encode("utf-8")).hexdigest()


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str | Path, obj: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(obj, indent=2, sort_keys=True))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(tmp), str(target))


def attach_certificate_hash(cert: dict[str, Any]) -> dict[str, Any]:
    out = dict(cert)
    out.pop("certificate_hash", None)
    out["certificate_hash"] = sha256_obj(out)
    return out
