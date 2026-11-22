#!/usr/bin/env python3
"""integrity.py check|register-export|record-change|versions  (session-start integrity, W2-3).

  check                                  raw/ hashes + provenance + export/API shape, tracked files vs journal,
                                         journal + state validity. Exit 1 on any blocker.
  register-export <raw/exports/f.ris> --what-es "..." --stage C3 [--db pubmed]
                                         shape-check, hash, register as uploaded by Laura, journal it
  record-change <path> --what-es "..." --stage C6 [--actor claude] [--why-es ".."]
                                         journal a legitimate edit of drafts/pico/strings with its new sha256
  versions [--skills-dir DIR ...] [--log] compare skill VERSION + _common hash with _update/UPDATE_NOTE.json ('Revisa el sistema')
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common  # noqa: E402
from _common import integrity_core, journal_io, paths  # noqa: E402

VERSION = "1.0"


def read_version_file(p):
    d = {}
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        for ln in lines:
            if ":" in ln:
                k, v = ln.split(":", 1)
                d[k.strip()] = v.strip()
    return d


def versions(root, skills_dirs=None):
    here_skill = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mine = read_version_file(os.path.join(here_skill, "VERSION"))
    local_hash = _common.common_hash()
    cands = list(skills_dirs or [os.path.dirname(here_skill), "/mnt/.skills", "/mnt/skills",
                                  os.path.expanduser("~/.claude/skills")])
    found = {}
    for base in cands:
        if os.path.isdir(base):
            for name in sorted(os.listdir(base)):
                v = read_version_file(os.path.join(base, name, "VERSION"))
                if v:
                    found[name] = v
    found.setdefault(os.path.basename(here_skill), mine)
    note_p = paths.Paths(root).root / "_update" / "UPDATE_NOTE.json"
    note = json.loads(paths.read_text(note_p)) if note_p.is_file() else None
    res, problems = {}, []
    expect_hash = (note or {}).get("common_hash")
    for name, v in sorted(found.items()):
        st = "ok"
        if expect_hash and v.get("common_hash") != expect_hash:
            st = "stale"
        exp = ((note or {}).get("skills") or {}).get(name)
        if exp and exp != v.get("version"):
            st = "stale"
        res[name] = {"version": v.get("version"), "common_hash": (v.get("common_hash") or "")[:12], "status": st}
        if st == "stale":
            problems.append(name)
    hashes = {v.get("common_hash") for v in found.values() if v.get("common_hash")}
    if len(hashes) > 1:
        problems += [n for n, v in found.items() if v.get("common_hash") != local_hash and n not in problems]
    for n in ((note or {}).get("skills") or {}):
        if n not in found:
            res[n] = {"version": None, "common_hash": "", "status": "no_visible"}
    return {"ok": not problems, "release": (note or {}).get("release"), "own_common_hash": local_hash[:12],
            "skills": res, "reupload": sorted(set(problems)),
            "summary_es": ("Todo al día." if not problems else "Vuelve a subir estos zip (primero tfm-orchestrator): " + ", ".join(sorted(set(problems))))}


def human(r):
    if r["ok"]:
        return "Integridad OK (%(raw_files)d archivos en raw/, %(journal_entries)d entradas en el diario)." % r["stats"]
    return "BLOQUEOS:\n" + "\n".join("- [%s] %s: %s" % (b["code"], b["path"], b["msg"]) for b in r["blockers"])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("check")
    r = sub.add_parser("register-export")
    r.add_argument("path")
    r.add_argument("--what-es", required=True)
    r.add_argument("--stage", required=True)
    r.add_argument("--db", default="")
    c = sub.add_parser("record-change")
    c.add_argument("path")
    c.add_argument("--what-es", required=True)
    c.add_argument("--stage", required=True)
    c.add_argument("--actor", default="claude")
    c.add_argument("--why-es", default="")
    v = sub.add_parser("versions")
    v.add_argument("--skills-dir", action="append")
    v.add_argument("--log", action="store_true")
    a = ap.parse_args(argv)
    try:
        root = paths.find_root(a.root)
    except paths.ProjectNotFound as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2
    cmd = a.cmd or "check"
    if cmd == "check":
        rep = integrity_core.check(root)
        rep["summary_es"] = human(rep)
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 0 if rep["ok"] else 1
    try:
        if cmd == "register-export":
            e = integrity_core.register_export(root, a.path, a.what_es, a.stage, a.db)
        elif cmd == "record-change":
            e = integrity_core.record_change(root, a.path, a.what_es, a.stage, a.actor, a.why_es)
        else:
            rep = versions(root, a.skills_dir)
            if a.log:
                journal_io.add(root, {"stage": "setup", "type": "setup", "actor": "script", "tool": "integrity.py v" + VERSION,
                                      "what_es": "Revisión de versiones: " + rep["summary_es"]})
            print(json.dumps(rep, ensure_ascii=False, indent=1))
            return 0 if rep["ok"] else 1
    except (ValueError, FileNotFoundError, journal_io.JournalError) as ex:
        print(json.dumps({"ok": False, "error": str(ex), "errors": getattr(ex, "errors", None)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, "journal_id": e["id"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
