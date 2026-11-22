"""journal/journal.jsonl: append-only, validated (D-05, rev.1 F-01..F-08).

Rules enforced here:
 * ids J-0001.. strictly sequential, ts assigned by us (no back-dating), file only appended;
 * ai_use needs the 5 Euneiz 2.4 fields; decision needs actor laura|supervisor;
 * LLM never closes a gate (sec 2.4): gate=pass with actor claude/script needs a valid
   script report (tfm-report/v1, result=pass, sha256 matches); advisory entries never pass;
 * seed_seal / query_check / reference_add have mandatory sub-fields.
"""
from __future__ import annotations

import json
import os
import pathlib
import re

from . import paths

TYPES = ("count", "search", "decision", "ai_use", "verification", "change", "setup",
         "seed_seal", "query_check", "reference_add")
ACTORS = ("laura", "claude", "supervisor", "script")
SEED_ORIGINS = ("existing_sr_included", "supervisor", "laura_manual")
REPORT_SCHEMA = "tfm-report/v1"
AI_USE_FIELDS = ("tool", "stage", "what_es", "how_verified", "human_decision")
_ID = re.compile(r"^J-\d{4,}$")
_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_STAGE = re.compile(r"^(C[0-9]|setup)$")
_SHA = re.compile(r"^[0-9a-f]{64}$")


class JournalError(ValueError):
    def __init__(self, errors):
        self.errors = list(errors)
        ValueError.__init__(self, "; ".join(self.errors))


def _nonempty(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


def file_ref(root, rel_path: str) -> dict:
    """{'path','sha256'} for inputs/outputs of an entry."""
    return {"path": rel_path, "sha256": paths.sha256_file(paths.safe_join(root, rel_path))}


def tool_string(script: str, version: str, base: str = "Claude (Cowork)") -> str:
    return "%s + %s v%s" % (base, script, version)


def make_script_report(root, script: str, rel_path: str, result: str, details=None, version: str = "1.0") -> dict:
    """Write a tfm-report/v1 JSON file (called by scripts) and return the `script_report` ref
    to put into a journal entry: {'script','path','sha256'}."""
    if result not in ("pass", "fail"):
        raise ValueError("result must be pass|fail")
    payload = {"schema": REPORT_SCHEMA, "script": script, "version": version, "ts": paths.utc_now(),
               "result": result, "details": details or {}}
    paths.write_text_atomic(paths.safe_join(root, rel_path), json.dumps(payload, ensure_ascii=False, indent=1) + "\n")
    return {"script": script, "path": rel_path, "sha256": paths.sha256_file(paths.safe_join(root, rel_path))}


def _check_refs(entry, key, errs):
    v = entry.get(key)
    if v is None:
        return
    if not isinstance(v, list):
        errs.append("%s must be a list" % key)
        return
    for it in v:
        if not isinstance(it, dict) or not _nonempty(it.get("path")) or not _SHA.match(str(it.get("sha256", ""))):
            errs.append("%s items need path + sha256(64 hex)" % key)
            return
        try:
            paths.safe_join(".", it["path"])
        except ValueError:
            errs.append("%s path not project-relative: %s" % (key, it["path"]))


def _check_report(entry, root, errs):
    rep = entry.get("script_report")
    if not isinstance(rep, dict) or not _nonempty(rep.get("script")) or not _nonempty(rep.get("path")) \
            or not _SHA.match(str(rep.get("sha256", ""))):
        errs.append("gate=pass by %s needs script_report {script,path,sha256}" % entry.get("actor"))
        return
    if root is None:
        return
    try:
        full = paths.safe_join(root, rep["path"])
    except ValueError:
        errs.append("script_report.path invalid")
        return
    if not full.is_file():
        errs.append("script_report file missing: %s" % rep["path"])
        return
    if paths.sha256_file(full) != rep["sha256"]:
        errs.append("script_report sha256 mismatch: %s" % rep["path"])
        return
    try:
        data = json.loads(paths.read_text(full))
    except ValueError:
        errs.append("script_report is not JSON")
        return
    if data.get("schema") != REPORT_SCHEMA or data.get("script") != rep["script"]:
        errs.append("script_report has wrong schema/script")
    elif data.get("result") != "pass":
        errs.append("script_report result is not pass")


def validate_entry(entry: dict, root=None) -> list:
    """Return a list of error strings (empty = valid). `root` enables file checks."""
    errs = []
    if not isinstance(entry, dict):
        return ["entry must be an object"]
    if not _ID.match(str(entry.get("id", ""))):
        errs.append("id must look like J-0001")
    if not _TS.match(str(entry.get("ts", ""))):
        errs.append("ts must be UTC like 2026-10-25T22:00:00Z")
    t, actor = entry.get("type"), entry.get("actor")
    if t not in TYPES:
        errs.append("type must be one of %s" % (TYPES,))
    if actor not in ACTORS:
        errs.append("actor must be one of %s" % (ACTORS,))
    if not _STAGE.match(str(entry.get("stage", ""))):
        errs.append("stage must be C0..C9 or setup")
    if not _nonempty(entry.get("what_es")):
        errs.append("what_es (Spanish description) is required")
    _check_refs(entry, "inputs", errs)
    _check_refs(entry, "outputs", errs)
    if "refs" in entry and not (isinstance(entry["refs"], list) and all(isinstance(x, str) for x in entry["refs"])):
        errs.append("refs must be a list of strings like PMID:123 / DOI:10.x")

    if t == "ai_use":
        for f in AI_USE_FIELDS:
            if not _nonempty(entry.get(f)):
                errs.append("ai_use requires non-empty '%s' (Normativa Euneiz 2.4)" % f)
    elif t in ("count", "search"):
        q = entry.get("query")
        if not isinstance(q, dict) or not all(_nonempty(q.get(k)) for k in ("db", "string", "date")):
            errs.append("%s requires query{db,string,date}" % t)
        elif t == "count" and not isinstance(q.get("count"), int):
            errs.append("count requires query.count (int)")
    elif t == "decision":
        if actor not in ("laura", "supervisor"):
            errs.append("decision must have actor laura|supervisor (Claude never decides)")
        if not _nonempty(entry.get("human_decision")):
            errs.append("decision requires human_decision")
    elif t == "query_check":
        qc = entry.get("query_check")
        if not isinstance(qc, dict) or not _nonempty(qc.get("db")) or not _nonempty(qc.get("query")) \
                or not isinstance(qc.get("errors"), list) or not isinstance(qc.get("warnings"), list) \
                or "translation" not in qc:
            errs.append("query_check requires {db,query,translation,errors[],warnings[]}")
        elif qc["errors"] and entry.get("gate") == "pass":
            errs.append("query_check with ErrorList cannot pass (Error = blocker)")
    elif t == "seed_seal":
        s = entry.get("seed")
        if not isinstance(s, dict) or not _SHA.match(str(s.get("sha256", ""))) or not isinstance(s.get("n"), int) \
                or not isinstance(s.get("held_out"), list) or not isinstance(s.get("origins"), dict):
            errs.append("seed_seal requires seed{sha256,n,held_out[],origins{}}")
        else:
            bad = [o for o in s["origins"] if o not in SEED_ORIGINS]
            if bad:
                errs.append("seed origins not allowed: %s" % bad)
    elif t == "reference_add":
        if actor != "laura":
            errs.append("reference_add must have actor laura")
        if not _nonempty(entry.get("origin_es")):
            errs.append("reference_add requires origin_es")
        if not entry.get("refs"):
            errs.append("reference_add requires refs[]")

    gate = entry.get("gate")
    if gate is not None and gate not in ("pass", "fail", "pending"):
        errs.append("gate must be pass|fail|pending")
    if gate == "pass":
        if entry.get("advisory") is True:
            errs.append("advisory judgment can never close a gate")
        if actor in ("claude", "script"):
            _check_report(entry, root, errs)
        elif not _nonempty(entry.get("human_decision")):
            errs.append("gate=pass by a human requires human_decision")
    return errs


def _lines(root):
    p = paths.Paths(root).journal
    if not p.is_file():
        return []
    return paths.read_text(p).split("\n")


def read_all(root) -> list:
    out = []
    for n, ln in enumerate(_lines(root), 1):
        if ln.strip():
            try:
                out.append(json.loads(ln))
            except ValueError:
                raise JournalError(["line %d: not valid JSON" % n])
    return out


def last_id(root):
    e = read_all(root)
    return e[-1]["id"] if e else None


def next_id(root) -> str:
    e = read_all(root)
    n = int(e[-1]["id"][2:]) + 1 if e else 1
    return "J-%04d" % n


def tail(root, n: int = 20) -> list:
    return read_all(root)[-n:]


def query(root, **filters) -> list:
    """Filter by equality on top-level keys (type=, stage=, actor=, gate=)."""
    return [e for e in read_all(root) if all(e.get(k) == v for k, v in filters.items() if v is not None)]


def find_for_path(root, rel_path: str, key: str = "outputs") -> list:
    return [e for e in read_all(root) if any(o.get("path") == rel_path for o in (e.get(key) or []))]


def add(root, entry: dict) -> dict:
    """Validate and append one entry. id/ts are assigned here (caller values ignored)."""
    p = paths.Paths(root).journal
    p.parent.mkdir(parents=True, exist_ok=True)
    e = dict(entry)
    e["id"], e["ts"] = next_id(root), paths.utc_now()
    existing = read_all(root)
    if existing and e["ts"] < existing[-1]["ts"]:
        raise JournalError(["clock went backwards: refusing to write a back-dated entry"])
    errs = validate_entry(e, root)
    if errs:
        raise JournalError(errs)
    ordered = {k: e[k] for k in ("id", "ts", "stage", "type", "actor", "what_es") if k in e}
    ordered.update({k: v for k, v in e.items() if k not in ordered})
    line = json.dumps(ordered, ensure_ascii=False, separators=(",", ":")) + "\n"
    data = line.encode("utf-8")
    prefix = b""
    if p.is_file() and p.stat().st_size > 0:
        with open(p, "rb") as f:
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                prefix = b"\n"
    fd = os.open(str(p), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, prefix + data)
        os.fsync(fd)
    finally:
        os.close(fd)
    return ordered


def validate_file(root) -> dict:
    """Whole-file validation: JSON per line, sequential ids, ts non-decreasing, every entry valid."""
    errors, prev_n, prev_ts = [], 0, ""
    try:
        entries = read_all(root)
    except JournalError as e:
        return {"ok": False, "errors": e.errors, "count": 0}
    for e in entries:
        eid = e.get("id", "?")
        for er in validate_entry(e, root):
            errors.append("%s: %s" % (eid, er))
        try:
            n = int(str(eid)[2:])
        except ValueError:
            continue
        if n != prev_n + 1:
            errors.append("%s: id not sequential (expected J-%04d)" % (eid, prev_n + 1))
        prev_n = n
        if e.get("ts", "") < prev_ts:
            errors.append("%s: ts earlier than previous entry" % eid)
        prev_ts = e.get("ts", prev_ts)
    return {"ok": not errors, "errors": errors, "count": len(entries)}
