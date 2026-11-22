#!/usr/bin/env python3
"""flow_counts.py - numbers for the PRISMA flow (input of panel-builder), from the journal and the dedup/pilot files.

  flow_counts.py build     -> 04_seleccion/flow_counts.json (+ journal `change`)

Until the real screening is done every figure is PRELIMINAR (W-1: the PRISMA-P protocol needs a screening PLAN, not its execution): the
file carries `scope: preliminar` and the watermark. Numbers come only from journaled script output (import_refs / dedup / pilot check).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import screen_lib as S  # noqa: E402
from _common import journal_io, paths  # noqa: E402

SCRIPT = "flow_counts.py"


def build(root, journal=True):
    S.need_scripts(root)
    dd = [e for e in journal_io.query(root, type="verification", stage="C4") if e.get("kind") == "dedup"]
    if not dd:
        raise S.Refusal("NO_DEDUP", "Aún no hay un dedup en el diario: nada que contar.")
    last = dd[-1]
    pil = [e for e in journal_io.query(root, type="verification", stage="C4") if e.get("kind") == "pilot_check"]
    pilot = None
    if pil:
        pe = pil[-1]
        rel = pe["inputs"][0]["path"]
        rows = S.read_csv(root, rel)
        tally = {}
        for r in rows:
            tally[r["decision"].strip().lower()] = tally.get(r["decision"].strip().lower(), 0) + 1
        pilot = {"file": rel, "n": len(rows), "tally": tally, "check_gate": pe["gate"], "journal_id": pe["id"], "watermark": S.WATERMARK}
    out = {"schema": "tfm-flow/v1", "scope": "preliminar", "watermark": S.WATERMARK, "counts": last["counts"], "dedup_journal_id": last["id"], "pilot": pilot}
    rel_out = "04_seleccion/flow_counts.json"
    paths.write_text_atomic(paths.safe_join(root, rel_out), json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    res = {"ok": True, "path": rel_out, "flow": out}
    if journal:
        e = journal_io.add(root, {"stage": "C4", "type": "change", "actor": "script", "kind": "flow_counts", "tool": S.tool(SCRIPT), "human_decision": "n/a",
                                  "what_es": "Números preliminares para el flujo PRISMA: %d identificados, %d únicos" % (last["counts"]["identified"], last["counts"]["unique"]),
                                  "inputs": [journal_io.file_ref(root, last["outputs"][0]["path"])], "outputs": [journal_io.file_ref(root, rel_out)]})
        res["journal_id"] = e["id"]
        res["count_ids"] = _emit_flow_counts(root, out, rel_out)
    return res


# Contract with panel-builder (panel_lib.FLOW_METRICS): one journal `count` entry per flow_* metric.
def _emit_flow_counts(root, out, rel_out):
    import datetime
    c = out["counts"]
    vals = [("flow_identificados", c.get("identified")), ("flow_duplicados", c.get("duplicates_marked"))]
    p = out.get("pilot")
    if p:
        t = p["tally"]
        vals += [("flow_cribados", p["n"]), ("flow_excluidos", t.get("excluir", 0)), ("flow_incluidos", t.get("incluir", 0))]
    ref = journal_io.file_ref(root, rel_out)
    ids = {}
    for metric, v in vals:
        if not isinstance(v, int):
            continue
        e = journal_io.add(root, {"stage": "C4", "type": "count", "actor": "script", "metric": metric, "tool": S.tool(SCRIPT),
                                  "human_decision": "n/a", "scope": "preliminar",
                                  "what_es": "Flujo PRISMA (%s, PRELIMINAR): %d" % (metric, v),
                                  "how_verified": "derivado de dedup/piloto registrados en el diario",
                                  "query": {"db": "local", "string": "flow_counts:" + metric, "date": datetime.date.today().isoformat(), "count": v},
                                  "inputs": [ref], "outputs": [ref]})
        ids[metric] = e["id"]
    return ids


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("cmd", nargs="?", default="build", choices=["build"])
    a = ap.parse_args(argv)

    def go():
        return build(S.open_project(a.root)), 0
    return S.finish(go)


if __name__ == "__main__":
    sys.exit(main())
