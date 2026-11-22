#!/usr/bin/env python3
"""recall_test.py - does the search string find the sealed seed set? (Q3-2, F-02, F-03)

  recall_test.py --db pubmed --string-file 03_busqueda/strings/pubmed_v1.txt            (FULL: runs the string via E-utilities)
  recall_test.py --db pubmed --string-file ... --offline --results-file raw/exports/pubmed_2026-12-01_v1.nbib
                                                              (LITE-a / FULL: Laura ran the string on pubmed.gov and exported)

REFUSES (exit 5) unless the journal seed_seal that matches today's seed_set.csv is strictly OLDER than the first journal
entry of every strings/*_v1.txt (the seed set cannot be tuned to the string). Thresholds: 10 seed -> 10/10 and held-out 5 -> 5/5;
with more seed >= ratio_seed (95%) / ratio_held_out (90%). Seeds without PMID cannot be tested -> fail (Laura decides).
Result: tfm-report/v1 + journal `verification` (gate_name G-C3-recall). A miss is never "explained away" by this script:
the reason + string edit or Laura+supervisor decision go into the journal separately.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_lib as L  # noqa: E402
from _common import config, http_client, journal_io, paths  # noqa: E402

SCRIPT = "recall_test.py"


def thresholds(n_seed, n_held, rc):
    """-> (required ratio seed, required ratio held-out) per W-2."""
    return (1.0 if n_seed <= rc["seed_min"] else rc["ratio_seed"],
            1.0 if n_held <= rc["held_out_min"] else rc["ratio_held_out"])


def evaluate(rows, found, rc):
    per = []
    for r in rows:
        per.append({"id": L.seed_id(r), "pmid": r["pmid"], "doi": r.get("doi", ""), "title": r.get("title", ""), "origin": r.get("origin", ""),
                    "held_out": r["held_out"], "testable": bool(r["pmid"]),
                    "found": bool(r["pmid"]) and r["pmid"] in found})
    held = [p for p in per if p["held_out"]]
    nf, hf = sum(p["found"] for p in per), sum(p["found"] for p in held)
    need_s, need_h = thresholds(len(per), len(held), rc)
    sr = nf / float(len(per)) if per else 0.0
    hr = hf / float(len(held)) if held else 0.0
    reasons = []
    if len(per) < rc["seed_min"]:
        reasons.append("seed insuficiente: %d < %d" % (len(per), rc["seed_min"]))
    if len(held) < rc["held_out_min"]:
        reasons.append("held-out insuficiente: %d < %d" % (len(held), rc["held_out_min"]))
    if sr + 1e-9 < need_s:
        reasons.append("recall seed %d/%d < %.0f%%" % (nf, len(per), need_s * 100))
    if hr + 1e-9 < need_h:
        reasons.append("recall held-out %d/%d < %.0f%%" % (hf, len(held), need_h * 100))
    unt = [p["id"] for p in per if not p["testable"]]
    if unt:
        reasons.append("seed sin PMID no probables: %s" % ", ".join(unt))
    return {"per_seed": per, "n_seed": len(per), "found_seed": nf, "n_held_out": len(held), "found_held_out": hf,
            "required_seed_ratio": need_s, "required_held_out_ratio": need_h, "misses": [p["id"] for p in per if not p["found"]],
            "reasons": reasons, "pass": not reasons}


def find_online(root, client, query, rows):
    found, evidence = set(), []
    base = L.esearch_pubmed(client, query, 0)
    evidence.append({"what": "string", "path": base["rel_path"], "sha256": base["sha256"], "count": base["count"]})
    if base["errors"]:
        raise L.Refusal("QUERY_ERRORS", "PubMed devolvió Error en la cadena (%s): corrige y vuelve a pasar run_search.py." % "; ".join(base["errors"]), 5)
    for r in rows:
        if not r["pmid"]:
            continue
        e = L.esearch_pubmed(client, "(%s) AND %s[uid]" % (query, r["pmid"]), 0)
        evidence.append({"what": "PMID:" + r["pmid"], "path": e["rel_path"], "sha256": e["sha256"], "count": e["count"]})
        if e["count"] == 1 and not e["errors"]:
            found.add(r["pmid"])
    return found, evidence


def run(root, db, string_rel, offline=False, results_rel=None, client=None, confirmed=False, journal=True):
    if db != "pubmed" and not offline:
        raise L.Refusal("DB_ONLINE_UNSUPPORTED", "El recall automático en línea solo existe para PubMed; en las demás bases usa --offline con tu export.")
    L.need_mode(root, network=not offline)
    seal = L.check_seal_order(root)                       # F-02: refuse when the order is wrong
    L.string_guard(root, string_rel)
    text = L.read_string_file(root, string_rel)
    query, problems = L.build_query(text)
    local = [i for i in L.syntax_issues(query) if i["level"] == "error"] if db == "pubmed" else []
    if problems or local:
        raise L.Refusal("QUERY_SYNTAX", "La cadena tiene errores de sintaxis: " + "; ".join(problems + [i["msg_es"] for i in local]))
    rows = L.load_seed(root)
    sv = L.validate_seed(root, rows)
    cfg = config.load_config(root)["recall"]
    inputs = [journal_io.file_ref(root, string_rel), journal_io.file_ref(root, "03_busqueda/seed_set.csv")]
    if offline:
        if not results_rel:
            raise L.Refusal("RESULTS_FILE_REQUIRED", "Falta --results-file (el export de la búsqueda que ejecutaste tú).")
        L.source_ok(root, results_rel)
        found = L.pmids_from_export(paths.safe_join(root, results_rel))
        evidence = [{"what": "export de Laura", "path": results_rel, "sha256": paths.sha256_file(paths.safe_join(root, results_rel)),
                     "pmids_in_file": len(found)}]
        inputs.append(journal_io.file_ref(root, results_rel))
        how = "export de Laura (%s) leído por script; la cadena la ejecutó Laura" % results_rel
    else:
        client = client or http_client.HttpClient(root, confirmed=confirmed)
        found, evidence = find_online(root, client, query, rows)
        how = "esearch PubMed: (cadena) AND PMID[uid] por cada seed"
    ev = evaluate(rows, found, cfg)
    ev["seed_validation"] = {k: sv[k] for k in ("errors", "warnings", "origins")}
    if not sv["ok"]:
        ev["pass"] = False
        ev["reasons"] += ["seed set no válido: " + "; ".join(sv["errors"])]
    ev.update(db=db, string_file=rel_s(string_rel), seal=seal["id"], seal_ts=seal["ts"], evidence=evidence, offline=offline)
    res = {"ok": ev["pass"], "gate": "pass" if ev["pass"] else "fail", "summary": {k: ev[k] for k in (
        "n_seed", "found_seed", "n_held_out", "found_held_out", "misses", "reasons")}, "seal": seal["id"]}
    if journal:
        ver = L.string_version(string_rel)
        ref = journal_io.make_script_report(root, SCRIPT, L.unique_rel(root, "03_busqueda/recall/recall_%s_v%d_%s.json" % (db, ver, L.stamp())),
                                            "pass" if ev["pass"] else "fail", details=ev, version=L.VERSION)
        entry = {
            "stage": "C3", "type": "verification", "actor": "script", "tool": L.tool(SCRIPT), "gate_name": "G-C3-recall",
            "gate": res["gate"], "script_report": ref, "human_decision": "n/a", "how_verified": how,
            "what_es": "Recall de %s (%s): seed %d/%d, held-out %d/%d%s" % (
                string_rel, db, ev["found_seed"], ev["n_seed"], ev["found_held_out"], ev["n_held_out"],
                "" if ev["pass"] else " - NO alcanza el umbral: " + "; ".join(ev["reasons"])),
            "why_es": "Q3-2: la cadena debe encontrar las seed independientes (sello %s anterior a la cadena v1)" % seal["id"],
            "inputs": inputs, "recall": {"seed": "%d/%d" % (ev["found_seed"], ev["n_seed"]), "held_out": "%d/%d" % (ev["found_held_out"], ev["n_held_out"])}}
        miss_refs = [m for m in ev["misses"] if m.startswith("PMID:")]
        if miss_refs:
            entry["refs"] = miss_refs
        e = journal_io.add(root, entry)
        res["journal_id"], res["script_report"] = e["id"], ref
    return res


def rel_s(x):
    return x


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("--db", default="pubmed")
    ap.add_argument("--string-file", required=True)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--results-file")
    ap.add_argument("--confirmed", action="store_true")
    ap.add_argument("--email")
    a = ap.parse_args(argv)

    def go():
        root = L.open_project(a.root)
        c = None if a.offline else http_client.HttpClient(root, email=a.email, confirmed=a.confirmed)
        res = run(root, a.db, a.string_file, a.offline, a.results_file, client=c)
        return res, (0 if res["ok"] else 1)
    return L.finish(go)


if __name__ == "__main__":
    sys.exit(main())
