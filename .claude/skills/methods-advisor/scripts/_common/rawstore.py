"""raw/_hashes.json registry (provenance of raw/ files; invariant 5).

Format: {"schema":"tfm-hashes/v1","files":{"raw/api/x.json":{"sha256":..,"actor":"script|laura",
"kind":"api|export|chasing","journal_id":"J-0001"|null,"registered":ts}}}
raw/ files are write-once: save_new() refuses to overwrite.
"""
from __future__ import annotations

import json
import os
import pathlib

from . import paths

SCHEMA = "tfm-hashes/v1"


def load(root) -> dict:
    p = paths.Paths(root).hashes
    if not p.is_file():
        return {"schema": SCHEMA, "files": {}}
    data = json.loads(paths.read_text(p) or "{}")
    data.setdefault("schema", SCHEMA)
    data.setdefault("files", {})
    return data


def _save(root, data) -> None:
    paths.write_text_atomic(paths.Paths(root).hashes, json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n")


def register(root, rel_path: str, actor: str, kind: str, journal_id=None) -> dict:
    """Record sha256 of an existing raw file. Re-registering a path with a different hash is refused."""
    if actor not in ("script", "laura"):
        raise ValueError("raw/ files may only be registered with actor script|laura")
    full = paths.safe_join(root, rel_path)
    if not full.is_file():
        raise FileNotFoundError(rel_path)
    sha = paths.sha256_file(full)
    data = load(root)
    old = data["files"].get(rel_path)
    if old and old["sha256"] != sha:
        raise ValueError("raw file changed after registration (immutable): %s" % rel_path)
    ent = old or {"sha256": sha, "actor": actor, "kind": kind, "journal_id": journal_id, "registered": paths.utc_now()}
    if journal_id and not ent.get("journal_id"):
        ent["journal_id"] = journal_id
    data["files"][rel_path] = ent
    _save(root, data)
    return ent


def save_new(root, rel_path: str, data: bytes, actor: str, kind: str, journal_id=None) -> dict:
    """Write a NEW raw file (never overwrite) and register it."""
    full = paths.safe_join(root, rel_path)
    if full.exists():
        raise FileExistsError("raw/ is write-once: %s" % rel_path)
    full.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(full), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return register(root, rel_path, actor, kind, journal_id)
