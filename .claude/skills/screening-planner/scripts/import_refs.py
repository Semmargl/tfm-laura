#!/usr/bin/env python3
"""import_refs.py - import RIS / nbib (MEDLINE) / CSV exports from raw/exports/ into one normalised table (Q4-1, W2-3).

  import_refs.py [--root R] [--file raw/exports/x.ris ...]

Only exports that Laura registered (integrity.py register-export, actor laura, real database export shape, hash intact) are read;
others are LISTED as skipped with the reason - never silently ignored. The result is 04_seleccion/dedup/records_v<N>.csv (derived; raw/ is
never touched). rec_id = <file stem>#<index> (stable). Counts per database go to the journal (input of the PRISMA flow, PRELIMINAR until
the real screening). Formats of Cochrane CENTRAL / PEDro / LILACS exports are «pendiente de verificar» (R-10): if a database has no usable
export, copy its results by hand into templates/plantilla_pedro_manual.csv (title,authors,year,journal,doi,pmid,url,abstract) and register that CSV.
"""
import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import screen_lib as S  # noqa: E402
from _common import journal_io, paths  # noqa: E402

SCRIPT = "import_refs.py"


def run(root, files=None, journal=True):
    S.need_scripts(root)
    exp = paths.Paths(root).raw_exports
    cand = sorted(files or [paths.rel(root, p) for p in exp.glob("*") if p.is_file() and not p.name.startswith(".") and p.name not in S.integrity_core.IGNORED])
    used, skipped, records, per_db, per_file = [], [], [], {}, {}
    for rel in cand:
        ext = os.path.splitext(rel)[1].lower()
        if ext not in S.PARSERS:
            skipped.append({"file": rel, "reason": "formato no importable (%s); solo RIS/nbib/CSV" % (ext or "sin extensión")})
            continue
        ok, why = S.export_ok(root, rel)
        if not ok:
            skipped.append({"file": rel, "reason": why})
            continue
        full = paths.safe_join(root, rel)
        sha = paths.sha256_file(full)
        db = S.db_of(os.path.basename(rel))
        raw = S.PARSERS[ext](S._text(full))
        n0 = len(records)
        for i, r in enumerate(raw, 1):
            records.append(S.build_record(rel, sha, db, i, r))
        per_file[rel] = len(records) - n0
        per_db[db] = per_db.get(db, 0) + len(records) - n0
        used.append({"path": rel, "sha256": sha})
    if not records:
        raise S.Refusal("NOTHING_TO_IMPORT", "No hay exports válidos que importar. Omitidos: %s" % ("; ".join("%s (%s)" % (s["file"], s["reason"]) for s in skipped) or "ninguno"))
    key = hashlib.sha256("|".join("%s:%s" % (u["path"], u["sha256"]) for u in used).encode()).hexdigest()
    prev = [e for e in journal_io.query(root, type="change", stage="C4") if e.get("kind") == "import_refs" and e.get("inputs_key") == key]
    if prev:
        return {"ok": True, "unchanged": True, "records_file": prev[-1]["outputs"][0]["path"], "message_es": "Sin cambios: los mismos exports ya estaban importados."}
    d = paths.Paths(root).root / "04_seleccion" / "dedup"
    n = 1
    while (d / ("records_v%d.csv" % n)).exists():
        n += 1
    rel_out = "04_seleccion/dedup/records_v%d.csv" % n
    S.write_csv(root, rel_out, S.REC_COLS, records)
    no_id = sum(1 for r in records if not r["pmid"] and not r["doi"])
    no_title = sum(1 for r in records if not r["title"])
    res = {"ok": True, "records_file": rel_out, "identified": len(records), "per_db": per_db, "per_file": per_file, "skipped": skipped,
           "records_without_id": no_id, "records_without_title": no_title,
           "message_es": "Importados %d registros de %d archivos (%s)%s" % (len(records), len(used), ", ".join("%s: %d" % kv for kv in sorted(per_db.items())),
                                                                            "; omitidos: %d" % len(skipped) if skipped else "")}
    if journal:
        e = journal_io.add(root, {
            "stage": "C4", "type": "change", "actor": "script", "kind": "import_refs", "tool": S.tool(SCRIPT), "human_decision": "n/a",
            "what_es": res["message_es"], "why_es": "Q4-1: tabla normalizada de los exports registrados por Laura",
            "how_verified": "solo exports registrados (actor laura) con forma válida", "inputs": used, "inputs_key": key,
            "outputs": [journal_io.file_ref(root, rel_out)], "counts": {"identified": len(records), "per_db": per_db}, "skipped": skipped})
        res["journal_id"] = e["id"]
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("--file", action="append")
    a = ap.parse_args(argv)

    def go():
        root = S.open_project(a.root)
        res = run(root, a.file)
        return res, 0
    return S.finish(go)


if __name__ == "__main__":
    sys.exit(main())
