#!/usr/bin/env python3
"""prisma_s_log.py - PRISMA-S search log + database coverage gate (Q3-5, Q3-6, F-07).

  prisma_s_log.py record --db cochrane_central --platform "Cochrane Library (Wiley)" --string-file 03_busqueda/strings/cochrane_central_v1.txt
                         --count 87 --limits "sin límites" [--date 2026-12-03] [--export raw/exports/central_2026-12-03_v1.ris] --laura-says "..."
        (manual databases and registries: the number is dictated by Laura; entry actor = laura)
  prisma_s_log.py build        write 03_busqueda/prisma_s_log.md + gate report (G-C3-prisma-s)

The 6 PRISMA-S fields per search: database, platform, date, full string verbatim, limits, number of results.
Coverage: required databases (config/databases.yaml: PubMed + Cochrane CENTRAL + PEDro) + ClinicalTrials.gov + WHO ICTRP + >= 1 review
registry (PROSPERO/Epistemonikos). Europe PMC and OpenAlex are supplementary and NEVER count toward the minimum (F-07).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_lib as L  # noqa: E402
from _common import config, journal_io, paths  # noqa: E402

SCRIPT = "prisma_s_log.py"
FIELDS = ("db", "platform", "date", "string", "limits", "count")
LOG_REL = "03_busqueda/prisma_s_log.md"
REGISTRIES = ("clinicaltrials_gov", "who_ictrp")
REVIEW_REGISTRIES = ("prospero", "epistemonikos")
SUPPLEMENTARY = ("europepmc", "openalex")


def record(root, db, platform, string_rel, string_inline, count, limits, date, export_rel, said):
    if not said.strip():
        raise L.Refusal("MISSING_STATEMENT", "Hace falta lo que Laura dijo (--laura-says): el número lo da ella desde la base.")
    if string_rel:
        L.string_guard(root, string_rel)
        text = L.verbatim(L.read_string_file(root, string_rel))
    else:
        text = (string_inline or "").strip()
    if not text or not platform.strip() or not (limits or "").strip():
        raise L.Refusal("INCOMPLETE", "Faltan campos PRISMA-S (cadena, plataforma o límites).")
    inputs = []
    if string_rel:
        inputs.append(journal_io.file_ref(root, string_rel))
    if export_rel:
        L.source_ok(root, export_rel)
        inputs.append(journal_io.file_ref(root, export_rel))
    entry = {
        "stage": "C3", "type": "count", "actor": "laura", "human_decision": "aprobado por Laura", "why_es": said.strip(),
        "what_es": "Laura ejecutó la búsqueda en %s (%s): %d resultados" % (db, platform, count),
        "how_verified": "cifra anotada por Laura desde la propia base" + (" + export registrado" if export_rel else ""),
        "query": {"db": db, "platform": platform.strip(), "string": text, "date": date or paths.today(), "limits": limits.strip(), "count": int(count)}}
    if inputs:
        entry["inputs"] = inputs
    e = journal_io.add(root, entry)
    return {"ok": True, "journal_id": e["id"]}


def collect(root):
    out = []
    for e in journal_io.query(root, type="count", stage="C3"):
        q = e.get("query") or {}
        out.append({"id": e["id"], "actor": e["actor"], "ts": e["ts"], **{f: q.get(f) for f in FIELDS}})
    return out


def build(root, journal=True):
    runs = collect(root)
    incomplete = []
    for r in runs:
        miss = [f for f in FIELDS if r.get(f) in (None, "")]
        if miss:
            incomplete.append({"id": r["id"], "missing": miss})
    dbs = config.load_databases(root)
    required = list(dbs.get("required") or ["pubmed", "cochrane_central", "pedro"])
    have = {r["db"] for r in runs}
    missing_required = [d for d in required if d not in have]
    missing_reg = [d for d in REGISTRIES if d not in have]
    review_reg = [d for d in REVIEW_REGISTRIES if d in have]
    ok = bool(runs) and not incomplete and not missing_required and not missing_reg and bool(review_reg)
    lines = ["# Registro de búsquedas (PRISMA-S)", "", "Generado por `prisma_s_log.py build` a partir del diario. No editar a mano.", "",
             "| Base | Plataforma | Fecha | Límites | Resultados | Diario | Cadena |", "|---|---|---|---|---|---|---|"]
    for r in runs:
        s = (r["string"] or "").replace("\n", " ").replace("|", "\\|")
        tag = " (complementaria)" if r["db"] in SUPPLEMENTARY else ""
        lines.append("| %s%s | %s | %s | %s | %s | %s | `%s` |" % (r["db"], tag, r["platform"] or "", r["date"] or "", r["limits"] or "", r["count"] if r["count"] is not None else "", r["id"], s))
    lines += ["", "## Cobertura", "",
              "- Bases obligatorias que faltan: %s" % (", ".join(missing_required) or "ninguna"),
              "- Registros de ensayos que faltan: %s" % (", ".join(missing_reg) or "ninguno"),
              "- Registro de revisiones (PROSPERO/Epistemonikos): %s" % (", ".join(review_reg) or "FALTA"),
              "- Búsquedas con campos PRISMA-S incompletos: %d" % len(incomplete),
              "- Europe PMC y OpenAlex son complementarias: no cuentan para el mínimo de bases.", ""]
    paths.write_text_atomic(paths.safe_join(root, LOG_REL), "\n".join(lines))
    res = {"ok": ok, "searches": len(runs), "incomplete": incomplete, "missing_required": missing_required, "missing_registries": missing_reg,
           "review_registry": review_reg, "path": LOG_REL,
           "message_es": "PRISMA-S: %d búsquedas; bases obligatorias que faltan: %s; registros que faltan: %s" % (
               len(runs), ",".join(missing_required) or "ninguna", ",".join(missing_reg + ([] if review_reg else ["registro de revisiones"])) or "ninguno")}
    if journal:
        ref = journal_io.make_script_report(root, SCRIPT, L.unique_rel(root, "03_busqueda/reports/prisma_s_%s.json" % L.stamp()),
                                            "pass" if ok else "fail", details={k: res[k] for k in ("searches", "incomplete", "missing_required", "missing_registries", "review_registry")},
                                            version=L.VERSION)
        e = journal_io.add(root, {"stage": "C3", "type": "verification", "actor": "script", "tool": L.tool(SCRIPT), "gate_name": "G-C3-prisma-s",
                                  "gate": "pass" if ok else "fail", "script_report": ref, "human_decision": "n/a",
                                  "how_verified": "recuento determinista de entradas count del diario",
                                  "what_es": "Registro PRISMA-S y cobertura de bases: " + res["message_es"],
                                  "outputs": [journal_io.file_ref(root, LOG_REL)]})
        res["journal_id"], res["script_report"] = e["id"], ref
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--db", required=True)
    r.add_argument("--platform", required=True)
    r.add_argument("--string-file")
    r.add_argument("--string")
    r.add_argument("--count", type=int, required=True)
    r.add_argument("--limits", required=True)
    r.add_argument("--date")
    r.add_argument("--export")
    r.add_argument("--laura-says", default="")
    sub.add_parser("build")
    a = ap.parse_args(argv)

    def go():
        root = L.open_project(a.root)
        if a.cmd == "record":
            res = record(root, a.db, a.platform, a.string_file, a.string, a.count, a.limits, a.date, a.export, a.laura_says)
        else:
            res = build(root)
        return res, (0 if res["ok"] else 1)
    return L.finish(go)


if __name__ == "__main__":
    sys.exit(main())
