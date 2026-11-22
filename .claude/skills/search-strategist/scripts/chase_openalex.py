#!/usr/bin/env python3
"""chase_openalex.py - citation chasing (backward + forward) of every seed via OpenAlex (Q3-4, F-03).

  chase_openalex.py run [--max-forward 400] [--confirmed]      chase 100% of seeds -> 03_busqueda/chasing/triage.csv (+ raw/api cache)
  chase_openalex.py record-triage --laura-says "..."           journal Laura's relevante/no marks (actor laura)
  chase_openalex.py status                                      coverage of seeds and triage

Claude/the script only SORT (sort_hint = title-word overlap with the seed titles). Whether a candidate is «relevante» or «no» is
decided by Laura: she fills the `triage` column; only record-triage turns it into a journal decision (actor laura).
Candidates are never deleted and existing triage marks are never overwritten by a new run. OpenAlex <= 500 requests/run (client cap).
"""
import argparse
import csv
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_lib as L  # noqa: E402
from _common import http_client, journal_io, paths  # noqa: E402

SCRIPT = "chase_openalex.py"
TRIAGE_REL = "03_busqueda/chasing/triage.csv"
COLS = ["openalex_id", "doi", "pmid", "title", "year", "direction", "seeds", "sort_hint", "triage", "triage_by", "triage_date", "triage_journal_id"]
SELECT = "id,doi,title,publication_year,ids"


def short_id(x):
    return (x or "").rstrip("/").rsplit("/", 1)[-1]


def norm_doi(d):
    d = (d or "").strip().lower()
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", d)


def rec_from_work(w):
    ids = w.get("ids") or {}
    pm = re.sub(r"\D", "", (ids.get("pmid") or "").rsplit("/", 1)[-1])
    return {"openalex_id": short_id(w.get("id")), "doi": norm_doi(w.get("doi") or ids.get("doi")), "pmid": pm,
            "title": (w.get("title") or "").replace("\n", " ").strip(), "year": str(w.get("publication_year") or "")}


def words(s):
    return set(re.findall(r"[a-z]{4,}", (s or "").lower()))


def load_triage(root):
    p = paths.safe_join(root, TRIAGE_REL)
    if not p.is_file():
        return []
    return list(csv.DictReader(io.StringIO(paths.read_text(p))))


def save_triage(root, rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, "") for c in COLS})
    paths.write_text_atomic(paths.safe_join(root, TRIAGE_REL), buf.getvalue())


def chase_seed(client, seed, max_forward, evidence):
    out = {"seed": L.seed_id(seed), "status": "ok", "backward": 0, "forward": 0, "cands": []}
    if seed["pmid"]:
        url = "https://api.openalex.org/works/pmid:%s" % seed["pmid"]
    elif seed.get("doi"):
        url = "https://api.openalex.org/works/doi:%s" % seed["doi"]
    else:
        out["status"] = "no_id"
        return out
    r = client.get(url, accept=(200, 404))
    evidence.append({"path": r.rel_path, "sha256": r.sha256})
    if r.status == 404:
        out["status"] = "not_in_openalex"
        return out
    w = r.json()
    wid = short_id(w.get("id"))
    refs = [short_id(x) for x in (w.get("referenced_works") or [])]
    for i in range(0, len(refs), 50):                                  # backward: resolve referenced works in batches
        chunk = refs[i:i + 50]
        rr = client.get(L.OPENALEX, {"filter": "openalex_id:" + "|".join(chunk), "per-page": 50, "select": SELECT})
        evidence.append({"path": rr.rel_path, "sha256": rr.sha256})
        for x in rr.json().get("results", []):
            out["cands"].append(dict(rec_from_work(x), direction="backward"))
    out["backward"] = len(refs)
    cursor, got = "*", 0
    while cursor and got < max_forward:                                # forward: works citing the seed
        rf = client.get(L.OPENALEX, {"filter": "cites:" + wid, "per-page": 200, "select": SELECT, "cursor": cursor})
        evidence.append({"path": rf.rel_path, "sha256": rf.sha256})
        data = rf.json()
        for x in data.get("results", []):
            out["cands"].append(dict(rec_from_work(x), direction="forward"))
            got += 1
        cursor = (data.get("meta") or {}).get("next_cursor")
        if not data.get("results"):
            break
    out["forward"] = got
    return out


def run(root, max_forward=400, client=None, confirmed=False, journal=True):
    L.need_mode(root, network=True)
    rows = L.load_seed(root)
    if not rows:
        raise L.Refusal("NO_SEED", "No hay seed set: el chasing parte de las seed.")
    client = client or http_client.HttpClient(root, confirmed=confirmed)
    evidence, per_seed, cands = [], {}, []
    for s in rows:
        res = chase_seed(client, s, max_forward, evidence)
        per_seed[res["seed"]] = {k: res[k] for k in ("status", "backward", "forward")}
        for c in res["cands"]:
            c["seed"] = res["seed"]
            cands.append(c)
    seed_ids = {r["pmid"] for r in rows if r["pmid"]}
    seed_dois = {norm_doi(r.get("doi")) for r in rows if r.get("doi")}
    seed_words = set()
    for r in rows:
        seed_words |= words(r.get("title"))
    existing = load_triage(root)
    index = {(x["openalex_id"] or x["doi"] or x["pmid"]): x for x in existing}
    added = 0
    for c in cands:
        if (c["pmid"] and c["pmid"] in seed_ids) or (c["doi"] and c["doi"] in seed_dois):
            continue
        key = c["openalex_id"] or c["doi"] or c["pmid"]
        hint = "%.2f" % (len(words(c["title"]) & seed_words) / float(max(1, len(words(c["title"])))))
        if key in index:
            cur = index[key]
            sset = set(filter(None, cur["seeds"].split(";"))) | {c["seed"]}
            cur["seeds"] = ";".join(sorted(sset))
            if c["direction"] not in cur["direction"].split("+"):
                cur["direction"] += "+" + c["direction"]
        else:
            c2 = dict(c, seeds=c["seed"], sort_hint=hint, triage="", triage_by="", triage_date="", triage_journal_id="")
            index[key] = c2
            existing.append(c2)
            added += 1
    existing.sort(key=lambda r: (-float(r["sort_hint"] or 0), r["openalex_id"]))
    save_triage(root, existing)
    chased = [k for k, v in per_seed.items() if v["status"] == "ok"]
    ok = len(chased) == len(rows)
    out = {"ok": ok, "seeds": len(rows), "chased": len(chased), "per_seed": per_seed, "candidates_total": len(existing), "new_candidates": added,
           "requests": client.stats(), "triage_file": TRIAGE_REL,
           "message_es": "Chasing de %d/%d seed; %d candidatos nuevos para que Laura marque «relevante»/«no» en %s." % (len(chased), len(rows), added, TRIAGE_REL)}
    if not ok:
        out["message_es"] += " Seeds sin chasing: %s (hazlo a mano con SpiderCite o «Cited by» de PubMed)." % ", ".join(k for k in per_seed if k not in chased)
    if journal:
        ref = journal_io.make_script_report(root, SCRIPT, L.unique_rel(root, "03_busqueda/chasing/run_%s.json" % L.stamp()), "pass" if ok else "fail",
                                            details={"per_seed": per_seed, "new_candidates": added, "evidence_n": len(evidence)}, version=L.VERSION)
        e = journal_io.add(root, {
            "stage": "C3", "type": "search", "actor": "script", "tool": L.tool(SCRIPT), "gate_name": "G-C3-chasing", "gate": "pass" if ok else "fail",
            "script_report": ref, "human_decision": "n/a", "how_verified": "OpenAlex works (referenced_works + cites:), respuestas guardadas en raw/api",
            "what_es": "Citation chasing de %d/%d seed: %d candidatos nuevos pendientes de triage de Laura" % (len(chased), len(rows), added),
            "query": {"db": "openalex", "string": "backward+forward chasing of seed set", "date": paths.today(), "limits": "max %d por seed (forward)" % max_forward},
            "outputs": evidence[:1] + [journal_io.file_ref(root, TRIAGE_REL)]})
        out["journal_id"], out["script_report"] = e["id"], ref
    return out


def record_triage(root, said):
    if not said.strip():
        raise L.Refusal("MISSING_STATEMENT", "Hace falta lo que Laura dijo (--laura-says): el triage es suyo.")
    rows = load_triage(root)
    new = [r for r in rows if r["triage"].strip().lower() in ("relevante", "no") and not r["triage_journal_id"]]
    bad = [r for r in rows if r["triage"].strip() and r["triage"].strip().lower() not in ("relevante", "no")]
    if bad:
        raise L.Refusal("BAD_TRIAGE_VALUE", "Valores no válidos en la columna triage (solo «relevante» o «no»): %s" % ", ".join(r["openalex_id"] for r in bad[:5]))
    if not new:
        return {"ok": True, "recorded": 0, "message_es": "No hay marcas nuevas de Laura."}
    nrel = sum(1 for r in new if r["triage"].strip().lower() == "relevante")
    e = journal_io.add(root, {
        "stage": "C3", "type": "decision", "actor": "laura", "kind": "chasing_triage", "human_decision": "aprobado por Laura",
        "what_es": "Laura hizo el triage de %d candidatos del chasing: %d relevantes, %d no" % (len(new), nrel, len(new) - nrel),
        "why_es": said.strip()})
    for r in new:
        r["triage"] = r["triage"].strip().lower()
        r["triage_by"], r["triage_date"], r["triage_journal_id"] = "laura", paths.today(), e["id"]
    save_triage(root, rows)
    return {"ok": True, "recorded": len(new), "relevantes": nrel, "journal_id": e["id"]}


def status(root):
    rows = L.load_seed(root)
    runs = [e for e in journal_io.query(root, type="search") if e.get("gate_name") == "G-C3-chasing"]
    chased = set()
    for e in runs:
        try:
            rep = json.loads(paths.read_text(paths.safe_join(root, e["script_report"]["path"])))
            chased |= {k for k, v in rep["details"]["per_seed"].items() if v["status"] == "ok"}
        except (OSError, ValueError, KeyError):
            continue
    ids = [L.seed_id(r) for r in rows]
    missing = [i for i in ids if i not in chased]
    tri = load_triage(root)
    pend = [r for r in tri if r["triage"].strip().lower() not in ("relevante", "no")]
    unrec = [r for r in tri if r["triage"].strip() and not r["triage_journal_id"]]
    ok = bool(rows) and not missing and not pend and not unrec and bool(runs)
    return {"ok": ok, "seeds": len(ids), "seeds_chased": len(ids) - len(missing), "seeds_missing": missing, "candidates": len(tri),
            "pending_triage": len(pend), "triage_not_journaled": len(unrec),
            "message_es": "Chasing: %d/%d seed; triage pendiente de Laura: %d; sin registrar: %d" % (len(ids) - len(missing), len(ids), len(pend), len(unrec))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--max-forward", type=int, default=400)
    r.add_argument("--confirmed", action="store_true")
    r.add_argument("--email")
    t = sub.add_parser("record-triage")
    t.add_argument("--laura-says", default="")
    sub.add_parser("status")
    a = ap.parse_args(argv)

    def go():
        root = L.open_project(a.root)
        if a.cmd == "run":
            res = run(root, a.max_forward, client=http_client.HttpClient(root, email=a.email, confirmed=a.confirmed))
        elif a.cmd == "record-triage":
            res = record_triage(root, a.laura_says)
        else:
            res = status(root)
        return res, (0 if res["ok"] else 1)
    return L.finish(go)


if __name__ == "__main__":
    sys.exit(main())
