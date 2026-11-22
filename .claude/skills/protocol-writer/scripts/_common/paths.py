"""Project root discovery, path helpers, hashing, UTF-8 IO (pathlib only, NFR-07)."""
from __future__ import annotations

import datetime as _dt
import hashlib
import os
import pathlib
import re
import tempfile

PROJECT_DIRNAME = "TFM_Laura"
STATE_FILE = "state.md"
JOURNAL_REL = "journal/journal.jsonl"
PROJECT_YAML_REL = "config/project.yaml"
DATABASES_YAML_REL = "config/databases.yaml"
HASHES_REL = "raw/_hashes.json"
SMOKE_REL = "_smoke/smoke_report.json"


class ProjectNotFound(RuntimeError):
    pass


def utc_now() -> str:
    """UTC timestamp, second precision, e.g. 2026-10-25T22:00:00Z. Tests monkeypatch this."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    return utc_now()[:10]


def is_project_root(p: pathlib.Path) -> bool:
    return (p / STATE_FILE).is_file() and (p / "config" / "project.yaml").is_file()


def find_root(explicit=None, start=None) -> pathlib.Path:
    """Locate the TFM_Laura folder. Order: explicit arg, $TFM_ROOT, cwd and parents,
    cwd/TFM_Laura, /mnt/*/TFM_Laura and /mnt/* (Cowork mounts), script location parents."""
    cands = []
    if explicit:
        cands.append(pathlib.Path(explicit))
    elif os.environ.get("TFM_ROOT"):
        cands.append(pathlib.Path(os.environ["TFM_ROOT"]))
    else:
        base = pathlib.Path(start) if start else pathlib.Path.cwd()
        cands += [base] + list(base.parents)
        cands.append(base / PROJECT_DIRNAME)
        mnt = pathlib.Path("/mnt")
        if mnt.is_dir():
            try:
                for d in sorted(mnt.iterdir()):
                    cands += [d / PROJECT_DIRNAME, d]
            except OSError:
                pass
    for c in cands:
        try:
            c = c.resolve()
        except OSError:
            continue
        if is_project_root(c):
            return c
    raise ProjectNotFound("No encuentro la carpeta TFM_Laura (state.md + config/project.yaml). "
                          "Use --root <ruta> o la variable TFM_ROOT.")


class Paths:
    def __init__(self, root):
        self.root = pathlib.Path(root).resolve()
        r = self.root
        self.state = r / STATE_FILE
        self.journal = r / JOURNAL_REL
        self.project_yaml = r / PROJECT_YAML_REL
        self.databases_yaml = r / DATABASES_YAML_REL
        self.raw = r / "raw"
        self.raw_exports = r / "raw" / "exports"
        self.raw_api = r / "raw" / "api"
        self.raw_chasing = r / "raw" / "chasing"
        self.hashes = r / HASHES_REL
        self.smoke_dir = r / "_smoke"
        self.smoke_report = r / SMOKE_REL
        self.declaration = r / "declaracion" / "declaracion_IA_es.md"


def rel(root, path) -> str:
    """POSIX path of `path` relative to root (raises ValueError if outside)."""
    return pathlib.Path(path).resolve().relative_to(pathlib.Path(root).resolve()).as_posix()


def safe_join(root, rel_path: str) -> pathlib.Path:
    """Join a project-relative POSIX path; reject absolute paths and '..'."""
    if not isinstance(rel_path, str) or rel_path == "":
        raise ValueError("empty path")
    p = pathlib.PurePosixPath(rel_path)
    if p.is_absolute() or ".." in p.parts or re.match(r"^[A-Za-z]:", rel_path) or "\\" in rel_path:
        raise ValueError("path must be project-relative POSIX without '..': %s" % rel_path)
    return pathlib.Path(root).resolve().joinpath(*p.parts)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path) -> str:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return f.read().replace("\r\n", "\n")


def write_text_atomic(path, text: str) -> None:
    """UTF-8, LF, atomic replace. Never use for raw/ files (use rawstore) or journal."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
