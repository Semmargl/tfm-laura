"""Integrity checks (invariants 1,2,3,5; W2-3). Detective, not cryptographic.

check(root) -> {"ok", "blockers":[{code,path,msg}], "warnings":[...], "stats":{...}}
Codes (blockers): JOURNAL_INVALID STATE_INVALID RAW_MISSING RAW_HASH_MISMATCH RAW_UNREGISTERED
RAW_NO_JOURNAL RAW_ACTOR_CLAUDE RAW_BAD_SHAPE RAW_BAD_API_META TRACKED_UNJOURNALED TRACKED_DRIFT
SEED_CHANGED_AFTER_SEAL.  Warnings: STATE_LAST_ID, RAW_KIND_ACTOR.
"""
from __future__ import annotations

import csv
import io
import json
import pathlib
import re

from . import http_client, journal_io, paths, rawstore, state_io

IGNORED = {".gitkeep", "_hashes.json", ".DS_Store", "Thumbs.db"}
# (directory, glob) of files whose edits must be journaled (inv. 2). Empty files are skipped.
TRACKED = [("06_protocolo/drafts", "*.md"), ("02_pico", "*.md"), ("03_busqueda/strings", "*.txt")]
CSV_KNOWN_COLS = {"title", "doi", "pmid", "authors", "author", "year", "abstract", "journal", "source", "id",
                  "titulo", "título", "autores", "año", "resumen", "pubmed id", "key", "record id"}


# ---- export shape checks (W2-3) -------------------------------------------------------------
def _text(path):
    b = pathlib.Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


def shape_check_export(path) -> tuple:
    """(ok, kind, reason). RIS / nbib(MEDLINE) / CSV exports must look like database exports."""
    p = pathlib.Path(path)
    ext = p.suffix.lower()
    if p.stat().st_size == 0:
        return False, "empty", "archivo vacio"
    if ext == ".ris":
        t = _text(p)
        ty, er = len(re.findall(r"(?m)^TY  - ", t)), len(re.findall(r"(?m)^ER  -", t))
        if ty == 0 or er == 0:
            return False, "ris", "no tiene registros RIS (TY  - ... ER  - )"
        return True, "ris", "%d registros" % ty
    if ext in (".nbib", ".medline"):
        t = _text(p)
        n = len(re.findall(r"(?m)^PMID- ", t))
        if n == 0 or not re.search(r"(?m)^TI  - ", t):
            return False, "nbib", "no tiene registros MEDLINE (PMID- / TI  - )"
        return True, "nbib", "%d registros" % n
    if ext == ".csv":
        t = _text(p)
        try:
            rows = list(csv.reader(io.StringIO(t)))
        except csv.Error as e:
            return False, "csv", "CSV ilegible: %s" % e
        if len(rows) < 2:
            return False, "csv", "CSV sin filas de datos"
        cols = {c.strip().lower() for c in rows[0]}
        if not (cols & CSV_KNOWN_COLS):
            return False, "csv", "cabecera sin columnas bibliograficas (title/doi/pmid...)"
        return True, "csv", "%d filas" % (len(rows) - 1)
    if ext == ".pdf":
        with open(p, "rb") as f:
            return (True, "pdf", "pdf") if f.read(5) == b"%PDF-" else (False, "pdf", "no empieza con %PDF-")
    if ext in (".txt", ".md"):
        return (True, "text", "texto") if _text(p).strip() else (False, "text", "texto vacio")
    return False, "unknown", "extension no admitida en raw/exports (%s)" % ext


# ---- main check -------------------------------------------------------------------------------
def _walk(d):
    if not d.is_dir():
        return []
    return sorted(p for p in d.rglob("*") if p.is_file() and p.name not in IGNORED)


def check(root) -> dict:
    root = paths.Paths(root).root
    P = paths.Paths(root)
    B, W = [], []

    def blk(code, path, msg):
        B.append({"code": code, "path": path, "msg": msg})

    jv = journal_io.validate_file(root)
    for e in jv["errors"]:
        blk("JOURNAL_INVALID", "journal/journal.jsonl", e)
    entries = []
    try:
        entries = journal_io.read_all(root)
    except journal_io.JournalError:
        pass
    sv = state_io.validate_state(root, journal_io.last_id(root) if jv["ok"] else None) if P.state.is_file() else \
        {"ok": False, "errors": ["state.md missing"], "warnings": [], "tokens": 0}
    for e in sv["errors"]:
        blk("STATE_INVALID", "state.md", e)
    for w in sv["warnings"]:
        W.append({"code": "STATE_LAST_ID" if "last_journal_id" in w else "STATE_SIZE", "path": "state.md", "msg": w})

    reg = rawstore.load(root)["files"]
    seen = set()
    for p in _walk(P.raw):
        r = paths.rel(root, p)
        seen.add(r)
        sha = paths.sha256_file(p)
        ent = reg.get(r)
        in_api = r.startswith("raw/api/") or (r.startswith("raw/chasing/") and p.suffix.lower() == ".json")
        if ent is None:
            blk("RAW_UNREGISTERED", r, "archivo en raw/ sin registro en _hashes.json (usar integrity.py register-export)")
        elif ent["sha256"] != sha:
            blk("RAW_HASH_MISMATCH", r, "raw/ es inmutable pero el hash cambio")
        if in_api:
            ok, why = http_client.verify_envelope(p)
            if not ok:
                blk("RAW_BAD_API_META", r, "no es una respuesta de API valida de http_client: " + why)
            elif ent is not None and ent.get("actor") != "script":
                W.append({"code": "RAW_KIND_ACTOR", "path": r, "msg": "respuesta de API registrada con actor %s" % ent.get("actor")})
        else:
            ok, kind, why = shape_check_export(p)
            if not ok:
                blk("RAW_BAD_SHAPE", r, "no parece un export valido (%s): %s" % (kind, why))
            outs = [e for e in entries if any(o.get("path") == r and o.get("sha256") == sha for o in (e.get("outputs") or []))]
            if not outs:
                blk("RAW_NO_JOURNAL", r, "sin entrada de diario (actor laura) que lo declare con este sha256")
            elif not any(e.get("actor") in ("laura", "script") for e in outs):
                blk("RAW_ACTOR_CLAUDE", r, "solo Claude figura como autor: Claude no puede escribir en raw/")
            if ent is not None and ent.get("actor") != "laura":
                W.append({"code": "RAW_KIND_ACTOR", "path": r, "msg": "export registrado con actor %s" % ent.get("actor")})
    for r in reg:
        if r not in seen:
            blk("RAW_MISSING", r, "registrado en _hashes.json pero ya no existe (raw/ no se borra)")

    for d, pat in TRACKED:
        for p in _walk(P.root / d):
            if not fnmatch_name(p.name, pat) or p.stat().st_size == 0:
                continue
            r = paths.rel(root, p)
            sha = paths.sha256_file(p)
            outs = journal_io.find_for_path(root, r)
            if not outs:
                blk("TRACKED_UNJOURNALED", r, "archivo con contenido sin ninguna entrada de diario (inv. 2)")
            elif [o for o in outs[-1]["outputs"] if o["path"] == r][-1]["sha256"] != sha:
                blk("TRACKED_DRIFT", r, "cambio sin registrar: el hash no coincide con la ultima entrada %s" % outs[-1]["id"])
    seed = P.root / "03_busqueda" / "seed_set.csv"
    seals = [e for e in entries if e.get("type") == "seed_seal"]
    if seals and seed.is_file() and paths.sha256_file(seed) != seals[-1]["seed"]["sha256"]:
        blk("SEED_CHANGED_AFTER_SEAL", "03_busqueda/seed_set.csv", "seed_set.csv cambio despues de seed_seal %s" % seals[-1]["id"])
    return {"ok": not B, "blockers": B, "warnings": W,
            "stats": {"journal_entries": len(entries), "raw_files": len(seen), "registered": len(reg)}}


def fnmatch_name(name, pat):
    import fnmatch
    return fnmatch.fnmatch(name, pat)


# ---- actions ------------------------------------------------------------------------------------
def register_export(root, rel_path: str, what_es: str, stage: str, db: str = "") -> dict:
    """Laura dropped a file in raw/exports/: shape-check, hash, register (actor laura), journal it.
    Refuses files that fail the shape check (W2-3): they are not a source for F-01/F-04."""
    full = paths.safe_join(root, rel_path)
    if not rel_path.startswith("raw/exports/") and not rel_path.startswith("raw/chasing/"):
        raise ValueError("solo raw/exports/ o raw/chasing/")
    ok, kind, why = shape_check_export(full)
    if not ok:
        raise ValueError("export rechazado (%s): %s" % (kind, why))
    sha = paths.sha256_file(full)
    e = journal_io.add(root, {"stage": stage, "type": "change", "actor": "laura", "what_es": what_es,
                              "tool": "integrity.py register-export", "db": db, "kind": kind, "shape": why,
                              "outputs": [{"path": rel_path, "sha256": sha}], "human_decision": "aprobado por Laura"})
    rawstore.register(root, rel_path, "laura", "export", e["id"])
    return e


def record_change(root, rel_path: str, what_es: str, stage: str, actor: str = "claude", why_es: str = "",
                  human_decision: str = "pendiente") -> dict:
    """Journal a legitimate edit of a tracked file (drafts/pico/strings) with its new sha256."""
    full = paths.safe_join(root, rel_path)
    return journal_io.add(root, {"stage": stage, "type": "change", "actor": actor, "what_es": what_es,
                                 "why_es": why_es, "tool": "integrity.py record-change", "human_decision": human_decision,
                                 "outputs": [{"path": rel_path, "sha256": paths.sha256_file(full)}]})
