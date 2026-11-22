#!/usr/bin/env python3
"""seed_seal.py - validate and SEAL the seed set before any search string exists (F-02).

  seed_seal.py check
  seed_seal.py seal --independence-es "<how the seeds were found, not from the tested string>" --laura-ok "aprobado por Laura"

Rules: >= seed_min seed (10), >= held_out_min (5) marked held_out, origin in existing_sr_included | supervisor | laura_manual
(NEVER the output of the string under test). `seal` refuses if any strings/*_v1.txt already exists or if the same file was sealed.
After `seal`, seed_set.csv is frozen (integrity.py: SEED_CHANGED_AFTER_SEAL). Seeds should already be in references.csv and verified
by the verifier (warning if no verification entry exists).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_lib as L  # noqa: E402
from _common import journal_io, paths  # noqa: E402

SCRIPT = "seed_seal.py"


def check(root):
    rows = L.load_seed(root)
    v = L.validate_seed(root, rows)
    ver = [e for e in journal_io.query(root, type="verification") if e.get("gate") == "pass" and e.get("stage") == "C7"]
    if not ver:
        v["warnings"].append("Aún no hay una verificación de referencias (C7) aprobada: verifica las seed con el verifier antes de sellar.")
    sha = paths.sha256_file(L.seed_path(root)) if L.seed_path(root).is_file() else None
    v["sha256"], v["sealed"] = sha, any(s["seed"]["sha256"] == sha for s in L.seals(root)) if sha else False
    return v


def seal(root, independence_es, laura_ok):
    if not independence_es.strip() or not laura_ok.strip():
        raise L.Refusal("MISSING_STATEMENT", "Hace falta la declaración de independencia de las seed y la aprobación de Laura.")
    v = check(root)
    if not v["ok"]:
        raise L.Refusal("SEED_INVALID", "El seed set no es válido: " + "; ".join(v["errors"]))
    if v["sealed"]:
        raise L.Refusal("ALREADY_SEALED", "Este seed_set.csv ya está sellado.")
    sdir = paths.Paths(root).root / "03_busqueda" / "strings"
    if sdir.is_dir() and any(sdir.glob("*_v1.txt")):
        raise L.Refusal("STRING_EXISTS", "Ya existe una cadena v1: el sello llegaría tarde (F-02).")
    rows = L.load_seed(root)
    held = [L.seed_id(r) for r in rows if r["held_out"]]
    e = journal_io.add(root, {
        "stage": "C3", "type": "seed_seal", "actor": "script", "tool": L.tool(SCRIPT), "human_decision": laura_ok,
        "what_es": "Seed set sellado: %d seed (%d held-out) antes de crear ninguna cadena" % (len(rows), len(held)),
        "why_es": "F-02: el recall solo vale si las seed son independientes de la cadena. " + independence_es.strip(),
        "independence_es": independence_es.strip(), "inputs": [journal_io.file_ref(root, "03_busqueda/seed_set.csv")],
        "seed": {"sha256": v["sha256"], "n": len(rows), "held_out": held, "origins": v["origins"]},
        "refs": [L.seed_id(r) for r in rows if r["pmid"] or r.get("doi")]})
    return {"ok": True, "journal_id": e["id"], "sha256": v["sha256"], "n": len(rows), "held_out": held, "warnings": v["warnings"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    s = sub.add_parser("seal")
    s.add_argument("--independence-es", default="")
    s.add_argument("--laura-ok", default="")
    a = ap.parse_args(argv)

    def go():
        root = L.open_project(a.root)
        if a.cmd == "check":
            r = check(root)
            return r, (0 if r["ok"] else 1)
        return seal(root, a.independence_es, a.laura_ok), 0
    return L.finish(go)


if __name__ == "__main__":
    sys.exit(main())
