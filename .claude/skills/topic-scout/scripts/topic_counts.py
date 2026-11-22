#!/usr/bin/env python3
"""topic_counts.py run|check-query|repeat  (C1; FULL mode only, E-utilities, free).

  run --topic T1 [--years 10] [--sr-years 5] [--confirmed]
        1) validates every [mh] term with esearch db=mesh (exact descriptor) and the PubMed QueryTranslation /
           ErrorList / WarningList (F-05) -> journal `query_check`; any Error = BLOCKER, no counts are written;
        2) counts: total, RCT (10 y, per year), clinical trials, systematic reviews (5 y) -> 01_tema/counts/<id>_<date>.json
           + one journal `count` entry per metric (query + date + number + file hash).
  check-query --topic T1      only step 1.
  repeat --topic T1           W-3: repeat the stored queries (cache=refresh); passes if +-0 or equal to a cached answer
                              or the previous answer is older than 1 h (difference is logged).
Exit codes: 0 ok · 1 blocker (query_check Error / repeat fail) · 2 usage/mode · 3 needs Laura's confirmation (>50 requests) · 4 network.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import topic_lib as tl  # noqa: E402
from topic_lib import hc, journal_io, paths  # noqa: E402

SCRIPT = "topic_counts.py"
HOUR = 3600


def build_queries(base, y_now, years=10, sr_years=5):
    """The 14 queries of one topic (default). Fixed order, deterministic strings (NFR-08)."""
    y0 = y_now - years + 1
    qs = [{"key": "total", "metric": "total", "string": base},
          {"key": "rct_window", "metric": "rct_10y",
           "string": "(%s) AND randomized controlled trial[pt] AND (%d:%d[dp])" % (base, y0, y_now)}]
    for y in range(y0, y_now + 1):
        qs.append({"key": "rct_%d" % y, "metric": "rct_year", "year": y,
                   "string": "(%s) AND randomized controlled trial[pt] AND (%d[dp])" % (base, y)})
    qs.append({"key": "ct", "metric": "ct", "string": "(%s) AND clinical trial[pt]" % base})
    qs.append({"key": "sr", "metric": "sr_5y",
               "string": "(%s) AND systematic review[pt] AND (%d:%d[dp])" % (base, y_now - sr_years + 1, y_now)})
    return qs


def _script_report(root, tid, result, details, tag):
    ts = paths.utc_now().replace(":", "").replace("-", "")
    rel = tl.unique_rel(root, "01_tema/counts/report_%s_%s_%s.json" % (tag, tid, ts))
    return journal_io.make_script_report(root, SCRIPT, rel, result, details=details, version=tl.VERSION)


def check_query(root, topic, client):
    """Step 1. Returns dict(ok, mesh[], search, errors, warnings, entry)."""
    tid, base = str(topic["id"]), str(topic.get("query") or "").strip()
    if not base:
        raise ValueError("el tema %s no tiene 'query' en config/topics.yaml" % tid)
    terms, style = tl.extract_mesh_terms(base)
    mesh = [tl.mesh_check(client, t) for t in terms]
    s = tl.pubmed_search(client, base, cache="day")
    errors = list(s["errors"]) + ["MeSH no valido: %s (%s)" % (m["term"], m["message"]) for m in mesh if not m["valid"]]
    warnings = list(s["warnings"]) + style
    inputs = [s["resp"].rel_path] + [p for m in mesh for p in m["inputs"]]
    entry = {"stage": "C1", "type": "query_check", "actor": "script", "topic_id": tid,
             "what_es": "Comprobacion de la ecuacion del tema %s en PubMed (traduccion, errores, MeSH)" % tid,
             "why_es": "F-05: un termino que PubMed no entiende da un conteo falso",
             "tool": journal_io.tool_string(SCRIPT, tl.VERSION),
             "how_verified": "esearch db=pubmed (QueryTranslation/ErrorList/WarningList) + esearch/esummary db=mesh por termino",
             "query_check": {"db": "pubmed", "query": base, "translation": s["translation"], "errors": errors,
                             "warnings": warnings},
             "mesh": [{k: m[k] for k in ("term", "valid", "descriptor", "ui", "message")} for m in mesh],
             "inputs": tl.refs_for(root, inputs), "human_decision": "n/a"}
    if errors:
        entry["gate"] = "fail"
    else:
        entry["gate"] = "pass"
        entry["script_report"] = _script_report(root, tid, "pass", {"mesh_terms": len(mesh), "warnings": len(warnings)}, "qc")
    e = journal_io.add(root, entry)
    return {"ok": not errors, "mesh": mesh, "search": s, "errors": errors, "warnings": warnings, "entry": e,
            "translation": s["translation"]}


def run(root, topic, client, years=10, sr_years=5):
    tid, base = str(topic["id"]), str(topic.get("query") or "").strip()
    qc = check_query(root, topic, client)
    if not qc["ok"]:
        return {"ok": False, "blocked": True, "topic": tid, "query_check_id": qc["entry"]["id"], "errors": qc["errors"],
                "warnings": qc["warnings"], "message_es": "Hay errores en la ecuacion; no se guarda ningun conteo. "
                "Corrigela con Laura y vuelve a ejecutar. Errores: " + " | ".join(qc["errors"])}
    y_now, date = tl.year_now(), paths.today()
    results, files = [], []
    for q in build_queries(base, y_now, years, sr_years):
        s = qc["search"] if q["key"] == "total" else tl.pubmed_search(client, q["string"], cache="day")
        if s["errors"]:
            return {"ok": False, "blocked": True, "topic": tid, "errors": s["errors"], "query_check_id": qc["entry"]["id"],
                    "message_es": "PubMed devolvio un error en una consulta derivada (%s): %s" % (q["key"], "; ".join(s["errors"]))}
        results.append((q, s))
    by_year = {str(q["year"]): s["count"] for q, s in results if q["metric"] == "rct_year"}
    summary = {"schema": "tfm-topic-counts/v1", "topic_id": tid, "title_es": topic.get("title_es", ""), "date": date,
               "db": "pubmed", "base_query": base, "translation": qc["translation"], "year_now": y_now,
               "partial_year": y_now, "queries": [{"key": q["key"], "metric": q["metric"], "string": q["string"],
                                                  "count": s["count"], "response": s["resp"].rel_path} for q, s in results],
               "by_year": by_year}
    rel = tl.unique_rel(root, "01_tema/counts/%s_%s.json" % (tid, date))
    tl.write_json(root, rel, summary)
    out_ref = journal_io.file_ref(root, rel)
    ids = {}
    for q, s in results:
        if q["metric"] == "rct_year":
            continue
        extra = {}
        if q["metric"] == "rct_10y":
            extra = {"by_year": by_year, "partial_year": y_now}
        resp_refs = [s["resp"].rel_path] + ([r["response"] for r in summary["queries"] if r["metric"] == "rct_year"]
                                            if q["metric"] == "rct_10y" else [])
        e = journal_io.add(root, dict({
            "stage": "C1", "type": "count", "actor": "script", "topic_id": tid, "metric": q["metric"],
            "what_es": "Conteo PubMed (%s) del tema %s: %d" % (q["metric"], tid, s["count"]),
            "tool": journal_io.tool_string(SCRIPT, tl.VERSION),
            "how_verified": "esearch db=pubmed, retmax=0; consulta y respuesta guardadas en raw/api",
            "human_decision": "n/a",
            "query": {"db": "pubmed", "string": q["string"], "date": date, "limits": "[dp] anual; sin filtro de idioma",
                      "count": s["count"]},
            "inputs": tl.refs_for(root, resp_refs), "outputs": [out_ref]}, **extra))
        ids[q["metric"]] = e["id"]
    return {"ok": True, "blocked": False, "topic": tid, "file": rel, "journal_ids": ids,
            "counts": {q["metric"]: s["count"] for q, s in results if q["metric"] != "rct_year"}, "by_year": by_year,
            "warnings": qc["warnings"], "query_check_id": qc["entry"]["id"], "requests": client.stats(),
            "message_es": "Conteos guardados en %s. El ano en curso (%d) esta incompleto." % (rel, y_now)}


def repeat(root, topic, client):
    tid = str(topic["id"])
    files = sorted((paths.Paths(root).root / "01_tema" / "counts").glob("%s_*.json" % tid))
    files = [f for f in files if not f.name.startswith("report_")]
    if not files:
        raise ValueError("no hay conteos previos de %s: ejecuta primero 'run'" % tid)
    import json
    prev = json.loads(paths.read_text(files[-1]))
    rows, ok = [], True
    for q in prev["queries"]:
        term = q["string"]
        qk = hc.query_key(tl.EUTILS + "esearch.fcgi", {"db": "pubmed", "term": term, "retmode": "json", "retmax": "0"})
        before = client.cached_entries(qk)
        counts_before = [tl.parse_esearch(r.text)["count"] for r in before]
        s = tl.pubmed_search(client, term, cache="refresh")
        now = s["count"]
        last_ts = before[-1].ts if before else None
        within = bool(last_ts) and hc._age_s(last_ts) <= HOUR
        same = bool(counts_before) and now == counts_before[-1]
        in_cache = now in counts_before
        row_ok = same or in_cache or not within
        ok = ok and row_ok
        rows.append({"key": q["key"], "now": now, "previous": counts_before[-1] if counts_before else None,
                     "within_1h": within, "equal_previous": same, "equal_any_cache": in_cache, "ok": row_ok})
    diffs = [r for r in rows if not r["equal_previous"]]
    rep = _script_report(root, tid, "pass" if ok else "fail", {"rows": rows}, "repeat")
    e = journal_io.add(root, {
        "stage": "C1", "type": "verification", "actor": "script", "topic_id": tid, "gate_name": "G-C1-repeat",
        "gate": "pass" if ok else "fail",
        "what_es": "Repeticion de los conteos de %s: %d consultas, %d con diferencia" % (tid, len(rows), len(diffs)),
        "why_es": "W-3: un repeticion en menos de 1 h debe dar +-0 o coincidir con la cache; PubMed cambia a diario",
        "tool": journal_io.tool_string(SCRIPT, tl.VERSION), "how_verified": "esearch repetido con cache=refresh",
        "human_decision": "n/a", "script_report": rep, "differences": diffs})
    return {"ok": ok, "journal_id": e["id"], "rows": rows,
            "message_es": "Repeticion %s: %d de %d consultas identicas." % ("correcta" if ok else "CON DIFERENCIAS",
                                                                           len(rows) - len(diffs), len(rows))}


def main(argv=None, client=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "check-query", "repeat"):
        p = sub.add_parser(name)
        p.add_argument("--topic", required=True)
        p.add_argument("--confirmed", action="store_true", help="Laura confirmed > warn_after requests")
        if name == "run":
            p.add_argument("--years", type=int, default=10)
            p.add_argument("--sr-years", type=int, default=5)
    args = ap.parse_args(argv)
    try:
        root = paths.find_root(args.root)
        topic = tl.get_topic(root, args.topic)
    except (paths.ProjectNotFound, KeyError) as e:
        tl.out({"ok": False, "error_es": e.args[0] if e.args else str(e)})
        return tl.EXIT_USAGE
    msg = tl.guard_network(root) if client is None else None
    if msg:
        tl.out({"ok": False, "error_es": msg})
        return tl.EXIT_USAGE
    c = client or hc.HttpClient(root, confirmed=args.confirmed)
    try:
        if args.cmd == "run":
            r = run(root, topic, c, args.years, args.sr_years)
        elif args.cmd == "repeat":
            r = repeat(root, topic, c)
        else:
            q = check_query(root, topic, c)
            r = {"ok": q["ok"], "errors": q["errors"], "warnings": q["warnings"], "translation": q["translation"],
                 "mesh": q["mesh"], "journal_id": q["entry"]["id"]}
            for m in r["mesh"]:
                m.pop("inputs", None)
    except hc.NeedsConfirmation as e:
        tl.out({"ok": False, "needs_confirmation": True, "error_es": str(e) + ". Pregunta a Laura y repite con --confirmed."})
        return tl.EXIT_CONFIRM
    except hc.CapExceeded as e:
        tl.out({"ok": False, "error_es": str(e)})
        return tl.EXIT_BLOCK
    except hc.NetworkError as e:
        tl.degrade(root, e)
        tl.out({"ok": False, "network_error": True, "error_es": "No hay conexion con PubMed (%s). Paso a modo LITE-a: "
                "usa el conector PubMed o copia los numeros de pubmed.gov." % e})
        return tl.EXIT_NET
    except (ValueError, journal_io.JournalError) as e:
        tl.out({"ok": False, "error_es": str(e)})
        return tl.EXIT_USAGE
    tl.out(r)
    return tl.EXIT_OK if r.get("ok") else tl.EXIT_BLOCK


if __name__ == "__main__":
    sys.exit(main())
