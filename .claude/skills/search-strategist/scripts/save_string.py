#!/usr/bin/env python3
"""save_string.py - save a NEW version of a search string (strings/<db>_v<N>.txt) with journal entries.

  save_string.py --db pubmed --from-file <draft.txt> [--why-es "..."] [--approved-by-laura]

* version = highest existing + 1 (older versions are never touched; LREQ-C3-ND);
* v1 is REFUSED unless the seed set is sealed (seed_seal older than the string, F-02);
* writes `change` (integrity.record_change) and an `ai_use` entry (the string is an AI contribution);
* without --approved-by-laura the change is logged as human_decision «pendiente» and a string cannot become final.
Comment lines start with `//`. Numbered-line strings (1. ... / 5. #1 AND #2) are expanded when run.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_lib as L  # noqa: E402
from _common import integrity_core, journal_io, paths  # noqa: E402


def save(root, db, text, why_es="", approved=False):
    if not re.fullmatch(r"[a-z0-9_]+", db):
        raise L.Refusal("BAD_DB", "Nombre de base no válido (usa minúsculas y _): %s" % db)
    sdir = paths.Paths(root).root / "03_busqueda" / "strings"
    sdir.mkdir(parents=True, exist_ok=True)
    nums = [int(m.group(1)) for f in sdir.glob("%s_v*.txt" % db) for m in [re.search(r"_v(\d+)\.txt$", f.name)] if m]
    n = max(nums) + 1 if nums else 1
    if not L.split_comments(text):
        raise L.Refusal("EMPTY_STRING", "La cadena está vacía.")
    if n == 1:
        sp = L.seed_path(root)
        sha = paths.sha256_file(sp) if sp.is_file() else None
        if not sha or not any(s["seed"]["sha256"] == sha for s in L.seals(root)):
            raise L.Refusal("SEED_NOT_SEALED", "No se crea la cadena v1 sin seed set sellado (seed_seal.py seal): F-02.")
    rel = "03_busqueda/strings/%s_v%d.txt" % (db, n)
    full = paths.safe_join(root, rel)
    paths.write_text_atomic(full, text.rstrip("\n") + "\n")
    hd = "aprobado por Laura" if approved else "pendiente"
    e1 = integrity_core.record_change(root, rel, "Nueva versión de la cadena de búsqueda %s v%d" % (db, n), "C3", actor="claude",
                                      why_es=why_es or "propuesta de cadena", human_decision=hd)
    e2 = journal_io.add(root, {"stage": "C3", "type": "ai_use", "actor": "claude", "tool": "Claude (Cowork) + save_string.py v%s" % L.VERSION,
                               "what_es": "Claude redactó la cadena %s v%d" % (db, n),
                               "how_verified": "pendiente: run_search.py (query_check), recall_test.py y PRESS con firma de Laura",
                               "human_decision": hd, "outputs": [journal_io.file_ref(root, rel)]})
    return {"ok": True, "path": rel, "version": n, "change_entry": e1["id"], "ai_use_entry": e2["id"], "human_decision": hd}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("--db", required=True)
    ap.add_argument("--from-file", required=True)
    ap.add_argument("--why-es", default="")
    ap.add_argument("--approved-by-laura", action="store_true")
    a = ap.parse_args(argv)

    def go():
        root = L.open_project(a.root)
        with open(a.from_file, encoding="utf-8-sig") as f:
            text = f.read().replace("\r\n", "\n")
        return save(root, a.db, text, a.why_es, a.approved_by_laura), 0
    return L.finish(go)


if __name__ == "__main__":
    sys.exit(main())
