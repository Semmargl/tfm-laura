#!/usr/bin/env python3
"""record_manual.py count|decision  (works offline, LITE-a/LITE-b-with-scripts too)

  count    --topic T1 --metric prospero|epistemonikos|who_ictrp|rct_10y|ct|sr_5y|total|... --db prospero
           --string "diastasis recti" --count 3 [--url URL] [--date YYYY-MM-DD] [--search-details-file f.txt]
           Laura's manual number (PROSPERO/Epistemonikos link + date + count) or a number she copied from pubmed.gov
           in LITE. actor=laura. With --search-details-file (PubMed «Search details» text) also writes a
           `query_check` (F-05, LITE) — Claude only compares the MeSH terms (advisory).
  decision --topic T1 --kind same_pico_sr|topic_choice --text "No hay SR con el mismo PICO" [--by laura|supervisor]
           [--outcome no_same_pico|same_pico]  (for same_pico_sr: the feasibility panel shows the badge from it)
           Records LAURA's (or the supervisor's) decision verbatim. Never call it for a choice Claude made.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import topic_lib as tl  # noqa: E402
from topic_lib import journal_io, paths  # noqa: E402

SCRIPT = "record_manual.py"


def add_count(root, topic_id, metric, db, string, count, url="", date=None, details_text=None, note=""):
    ent = {"stage": "C1", "type": "count", "actor": "laura", "topic_id": topic_id, "metric": metric, "manual": True,
           "what_es": "Conteo manual de Laura (%s) para %s: %d" % (db, topic_id, count),
           "tool": "manual (Laura) + " + journal_io.tool_string(SCRIPT, tl.VERSION, base="Claude (Cowork)"),
           "how_verified": note or "copiado por Laura de la pagina de la base; no reproducible por script",
           "human_decision": "aprobado por Laura",
           "query": {"db": db, "string": string, "date": date or paths.today(), "count": int(count)}}
    if url:
        ent["url"] = url
    e = journal_io.add(root, ent)
    qc = None
    if details_text:
        qc = journal_io.add(root, {
            "stage": "C1", "type": "query_check", "actor": "laura", "topic_id": topic_id, "gate": "pending",
            "what_es": "Laura copio el bloque «Search details» de %s" % db, "human_decision": "pendiente",
            "how_verified": "texto copiado de la pagina; Claude compara los terminos MeSH (advisory)", "advisory": True,
            "query_check": {"db": db, "query": string, "translation": details_text.strip(), "errors": [], "warnings": []}})
    return e, qc


OUTCOMES = ("no_same_pico", "same_pico")


def add_decision(root, topic_id, kind, text, by="laura", outcome=None):
    if by not in ("laura", "supervisor"):
        raise ValueError("by debe ser laura|supervisor")
    if outcome is not None and outcome not in OUTCOMES:
        raise ValueError("outcome debe ser %s" % (OUTCOMES,))
    return journal_io.add(root, dict({
        "stage": "C1", "type": "decision", "actor": by, "topic_id": topic_id, "kind": kind,
        "what_es": "Decision de %s sobre el tema %s (%s): %s" % (by, topic_id, kind, text),
        "human_decision": text}, **({"outcome": outcome} if outcome else {})))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("count")
    for k in ("topic", "metric", "db", "string"):
        c.add_argument("--" + k, required=True)
    c.add_argument("--count", type=int, required=True)
    c.add_argument("--url", default="")
    c.add_argument("--date")
    c.add_argument("--note", default="")
    c.add_argument("--search-details-file")
    d = sub.add_parser("decision")
    d.add_argument("--topic", required=True)
    d.add_argument("--kind", required=True)
    d.add_argument("--text", required=True)
    d.add_argument("--by", default="laura")
    d.add_argument("--outcome", choices=OUTCOMES, help="same_pico_sr: no_same_pico | same_pico (the panel reads it)")
    a = ap.parse_args(argv)
    try:
        root = paths.find_root(a.root)
        if a.cmd == "count":
            det = paths.read_text(a.search_details_file) if a.search_details_file else None
            e, qc = add_count(root, a.topic, a.metric, a.db, a.string, a.count, a.url, a.date, det, a.note)
            tl.out({"ok": True, "journal_id": e["id"], "query_check_id": qc["id"] if qc else None})
        else:
            e = add_decision(root, a.topic, a.kind, a.text, a.by, a.outcome)
            tl.out({"ok": True, "journal_id": e["id"]})
    except (paths.ProjectNotFound, ValueError, OSError, journal_io.JournalError) as e:
        tl.out({"ok": False, "error_es": str(e)})
        return tl.EXIT_USAGE
    return tl.EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
