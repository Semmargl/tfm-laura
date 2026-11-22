#!/usr/bin/env python3
"""dedup.py - flag duplicates (NEVER delete) in the imported table (Q4-1, LREQ-C4-ND).

  dedup.py run [--records 04_seleccion/dedup/records_v1.csv]      -> 04_seleccion/dedup/dedup_v<N>.csv (+ journal numbers before/after)
  dedup.py selftest --fixture eval/dedup_planted/fixture.json      planted-duplicates evaluation: recall >= 95%, false merges <= 1

Rules (in order): same DOI | same PMID | same normalised title (+ year +-1, same first-author surname when both known) |
fuzzy title (ratio >= 0.93, year +-1, same surname). A merge is NEVER made when both records carry different DOIs or different PMIDs
(listed as `possible_duplicates` for Laura instead). `duplicate_of` points to the kept record (richest: PMID, DOI, abstract); every row
stays in the file. The numbers (identified / duplicates / unique, per database) are logged for the PRISMA flow (PRELIMINAR until real screening).
"""
import argparse
import difflib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import screen_lib as S  # noqa: E402
from _common import journal_io, paths  # noqa: E402

SCRIPT = "dedup.py"
FUZZY = 0.93


class UF(object):
    def __init__(self, items):
        self.p = {i: i for i in items}

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def _yd(a, b):
    if not a or not b:
        return None
    return abs(int(a) - int(b))


def _conflict(a, b):
    return (a["doi"] and b["doi"] and a["doi"] != b["doi"]) or (a["pmid"] and b["pmid"] and a["pmid"] != b["pmid"])


def match(a, b):
    """-> reason string or None. a, b are normalised records."""
    if a["doi"] and a["doi"] == b["doi"]:
        return "doi"
    if a["pmid"] and a["pmid"] == b["pmid"]:
        return "pmid"
    ta, tb = a["norm_title"], b["norm_title"]
    if not ta or not tb or len(ta) < 15:
        return None
    sa, sb = S.surname(a["first_author"]), S.surname(b["first_author"])
    yd = _yd(a["year"], b["year"])
    surname_ok = (not sa or not sb or sa == sb)
    if ta == tb and (yd is None or yd <= 1) and surname_ok:
        return "titulo_exacto"
    if yd is not None and yd <= 1 and sa and sb and sa == sb:
        sm = difflib.SequenceMatcher(None, ta, tb)
        if sm.real_quick_ratio() >= FUZZY and sm.quick_ratio() >= FUZZY and sm.ratio() >= FUZZY:
            return "titulo_aprox"
    return None


def cluster(records):
    """-> (duplicate_of {rec_id: kept}, reason {rec_id: why}, possible [(a, b, why)])"""
    recs = {r["rec_id"]: r for r in records}
    ids = sorted(recs)
    uf = UF(ids)
    blocks = {}
    for i in ids:
        r = recs[i]
        keys = []
        if r["doi"]:
            keys.append(("d", r["doi"]))
        if r["pmid"]:
            keys.append(("p", r["pmid"]))
        if r["norm_title"]:
            keys.append(("t", r["norm_title"][:14]))
            keys.append(("t2", r["norm_title"][-14:]))
            sn = S.surname(r["first_author"])
            if sn:
                keys.append(("a", sn, r["year"][:3] if r["year"] else ""))
        for k in keys:
            blocks.setdefault(k, []).append(i)
    why, possible, seen = {}, [], set()
    for bl in blocks.values():
        for x in range(len(bl)):
            for y in range(x + 1, len(bl)):
                a, b = bl[x], bl[y]
                if (a, b) in seen:
                    continue
                seen.add((a, b))
                ra, rb = recs[a], recs[b]
                m = match(ra, rb)
                if not m:
                    continue
                if m not in ("doi", "pmid") and _conflict(ra, rb):
                    possible.append((a, b, "mismo título pero identificadores distintos (%s)" % ("DOI" if ra["doi"] and rb["doi"] and ra["doi"] != rb["doi"] else "PMID")))
                    continue
                uf.union(a, b)
                why[(a, b)] = m
    groups = {}
    for i in ids:
        groups.setdefault(uf.find(i), []).append(i)
    dup_of, reason = {}, {}
    for members in groups.values():
        if len(members) == 1:
            continue
        keep = max(members, key=lambda i: (bool(recs[i]["pmid"]), bool(recs[i]["doi"]), len(recs[i]["abstract"]), [-ord(c) for c in i]))
        for i in members:
            if i != keep:
                dup_of[i] = keep
                rs = [v for (a, b), v in why.items() if i in (a, b)]
                reason[i] = sorted(set(rs), key=["doi", "pmid", "titulo_exacto", "titulo_aprox"].index)[0] if rs else "transitivo"
    return dup_of, reason, possible


def run(root, records_rel=None, journal=True):
    S.need_scripts(root)
    records_rel = records_rel or S.latest(root, "records")
    if not records_rel:
        raise S.Refusal("NO_RECORDS", "Primero importa los exports con import_refs.py.")
    recs = S.read_csv(root, records_rel)
    dup_of, reason, possible = cluster(recs)
    for r in recs:
        r["duplicate_of"] = dup_of.get(r["rec_id"], "")
        r["dup_reason"] = reason.get(r["rec_id"], "")
    ver = records_rel.rsplit("_v", 1)[-1].split(".")[0]
    out_rel = S.unique_rel(root, "04_seleccion/dedup/dedup_v%s.csv" % ver)
    S.write_csv(root, out_rel, S.DEDUP_COLS, recs)
    per_db, dup_db = {}, {}
    for r in recs:
        per_db[r["db"]] = per_db.get(r["db"], 0) + 1
        if r["duplicate_of"]:
            dup_db[r["db"]] = dup_db.get(r["db"], 0) + 1
    by_reason = {}
    for v in reason.values():
        by_reason[v] = by_reason.get(v, 0) + 1
    counts = {"identified": len(recs), "duplicates_marked": len(dup_of), "unique": len(recs) - len(dup_of), "per_db": per_db,
              "duplicates_per_db": dup_db, "by_reason": by_reason, "deleted": 0}
    res = {"ok": True, "dedup_file": out_rel, "counts": counts,
           "possible_duplicates": [{"a": a, "b": b, "why": w} for a, b, w in possible],
           "message_es": "Registros: %d; duplicados marcados: %d (no se borra nada); únicos: %d; posibles duplicados para que Laura mire: %d" % (
               len(recs), len(dup_of), len(recs) - len(dup_of), len(possible))}
    if journal:
        ref = journal_io.make_script_report(root, SCRIPT, S.unique_rel(root, "04_seleccion/dedup/report_%s.json" % S.stamp()), "pass",
                                            details={"records": records_rel, "dedup_file": out_rel, "counts": counts, "possible_duplicates": res["possible_duplicates"]},
                                            version=S.VERSION)
        e = journal_io.add(root, {
            "stage": "C4", "type": "verification", "actor": "script", "kind": "dedup", "gate_name": "G-C4-dedup", "gate": "pass", "script_report": ref,
            "tool": S.tool(SCRIPT), "human_decision": "n/a", "how_verified": "reglas DOI/PMID/título normalizado/difuso; nada se elimina",
            "what_es": res["message_es"], "inputs": [journal_io.file_ref(root, records_rel)], "outputs": [journal_io.file_ref(root, out_rel)],
            "counts": counts})
        res["journal_id"], res["script_report"] = e["id"], ref
    return res


def evaluate_planted(records, truth):
    """truth: {rec_id: cluster_label}. Returns recall of true duplicate pairs and number of false merges."""
    dup_of, _, _ = cluster(records)
    labels = {}
    for rid, lab in truth.items():
        labels.setdefault(lab, []).append(rid)
    true_dups = sum(len(v) - 1 for v in labels.values())
    caught, false_merges = 0, 0
    kept_of = lambda r: dup_of.get(r, r)       # noqa: E731
    for lab, members in labels.items():
        reps = {kept_of(m) for m in members}
        caught += len(members) - len(reps)
    for d, k in dup_of.items():
        if truth.get(d) != truth.get(k):
            false_merges += 1
    return {"true_duplicates": true_dups, "caught": caught, "recall": caught / float(true_dups) if true_dups else 1.0, "false_merges": false_merges}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--records")
    t = sub.add_parser("selftest")
    t.add_argument("--fixture", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        with open(a.fixture, encoding="utf-8") as f:
            fx = json.load(f)
        recs = [S.build_record("fixture", "0" * 64, r.get("db", "fixture"), i, r) for i, r in enumerate(fx["records"], 1)]
        for r, raw in zip(recs, fx["records"]):
            r["rec_id"] = raw["rec_id"]
        ev = evaluate_planted(recs, fx["truth"])
        ev["ok"] = ev["recall"] >= 0.95 and ev["false_merges"] <= 1 and ev["true_duplicates"] >= 30
        S.emit(ev)
        return 0 if ev["ok"] else 1

    def go():
        root = S.open_project(a.root)
        return run(root, a.records), 0
    return S.finish(go)


if __name__ == "__main__":
    sys.exit(main())
