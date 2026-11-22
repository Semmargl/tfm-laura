"""state.md contract (tfm-state/v1): YAML frontmatter (machine) + ES body (human)."""
from __future__ import annotations

import math
import re

from . import miniyaml, paths

SCHEMA = "tfm-state/v1"
MODES = ("PENDING", "FULL", "LITE-a", "LITE-b", "LITE-P")
KEY_ORDER = ["schema", "mode", "phase", "stage", "step", "open_decisions", "next_action_es",
             "pico_version", "last_journal_id", "updated"]
MAX_STATE_TOKENS = 1500
WARN_STATE_TOKENS = 1200
MAX_ALWAYS_LOAD_TOKENS = 2000
MAX_BODY_LINES = 25
_STAGE = re.compile(r"^C[0-9]$")


def estimate_tokens(text: str) -> int:
    return int(math.ceil(len(text) / 4.0))


def split_frontmatter(text: str):
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end < 0:
        return None, text
    meta = miniyaml.loads(text[4:end]) or {}
    body = text[end + 4:].lstrip("\n")
    return meta, body


def render(meta: dict, body: str) -> str:
    ordered = {k: meta[k] for k in KEY_ORDER if k in meta}
    ordered.update({k: v for k, v in meta.items() if k not in ordered})
    return "---\n" + miniyaml.dumps(ordered) + "---\n" + body.rstrip("\n") + "\n"


def initial_state() -> tuple:
    meta = {"schema": SCHEMA, "mode": "PENDING", "phase": 0, "stage": "C0", "step": "C0.0 instalacion",
            "open_decisions": [], "next_action_es": "Ejecutar la prueba del sistema (GATE-0): escribe «Hola, empecemos»",
            "pico_version": None, "last_journal_id": None, "updated": paths.utc_now()}
    body = "# Estado del proyecto\n\nProyecto nuevo. Falta ejecutar la prueba del sistema (GATE-0).\n"
    return meta, body


def load_state(root):
    meta, body = split_frontmatter(paths.read_text(paths.Paths(root).state))
    if meta is None:
        raise ValueError("state.md has no YAML frontmatter")
    return meta, body


def save_state(root, meta: dict, body: str) -> None:
    paths.write_text_atomic(paths.Paths(root).state, render(meta, body))


def set_fields(root, touch=True, **fields) -> dict:
    meta, body = load_state(root)
    meta.update(fields)
    if touch and "updated" not in fields:
        meta["updated"] = paths.utc_now()
    save_state(root, meta, body)
    return meta


def validate_meta(meta: dict) -> list:
    errs = []
    for k in KEY_ORDER:
        if k not in meta:
            errs.append("missing key: %s" % k)
    if meta.get("schema") != SCHEMA:
        errs.append("schema must be %s" % SCHEMA)
    if meta.get("mode") not in MODES:
        errs.append("mode must be one of %s" % (MODES,))
    if not isinstance(meta.get("phase"), int) or not 0 <= meta.get("phase", -1) <= 3:
        errs.append("phase must be int 0..3")
    if not isinstance(meta.get("stage"), str) or not _STAGE.match(meta.get("stage") or ""):
        errs.append("stage must look like C0..C9")
    od = meta.get("open_decisions")
    if not isinstance(od, list) or len(od) > 5:
        errs.append("open_decisions must be a list with <= 5 items")
    lj = meta.get("last_journal_id")
    if lj is not None and not re.match(r"^J-\d{4,}$", str(lj)):
        errs.append("last_journal_id must be null or J-NNNN")
    return errs


def validate_state(root, journal_last_id=None) -> dict:
    p = paths.Paths(root).state
    errors, warnings = [], []
    if not p.is_file():
        return {"ok": False, "errors": ["state.md missing"], "warnings": [], "tokens": 0}
    text = paths.read_text(p)
    tokens = estimate_tokens(text)
    try:
        meta, body = split_frontmatter(text)
    except miniyaml.YamlError as e:
        return {"ok": False, "errors": ["frontmatter unreadable: %s" % e], "warnings": [], "tokens": tokens}
    if meta is None:
        return {"ok": False, "errors": ["no YAML frontmatter"], "warnings": [], "tokens": tokens}
    errors += validate_meta(meta)
    if tokens > MAX_STATE_TOKENS:
        errors.append("state.md ~%d tokens > %d" % (tokens, MAX_STATE_TOKENS))
    elif tokens > WARN_STATE_TOKENS:
        warnings.append("state.md ~%d tokens (limit %d)" % (tokens, MAX_STATE_TOKENS))
    nlines = len([ln for ln in body.split("\n") if ln.strip()])
    if nlines > MAX_BODY_LINES:
        warnings.append("body has %d non-empty lines (> %d)" % (nlines, MAX_BODY_LINES))
    if journal_last_id is not None and meta.get("last_journal_id") != journal_last_id:
        warnings.append("last_journal_id %s != journal %s" % (meta.get("last_journal_id"), journal_last_id))
    return {"ok": not errors, "errors": errors, "warnings": warnings, "tokens": tokens}
