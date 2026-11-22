#!/usr/bin/env python3
"""existing_reviews.py --topic T1 [--years 5] [--max 100] [--confirmed]

Lists systematic reviews of the last N years for a topic (PubMed pt + Europe PMC as supplementary) so that LAURA
decides whether one has the same PICO (F-03: Claude never decides). Output: 01_tema/reviews/<id>_<date>.json and .md
(Spanish table), journal `search` entries. FULL mode only.
"""
import argparse
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import topic_lib as tl  # noqa: E402
from topic_lib import hc, journal_io, paths  # noqa: E402

SCRIPT = "existing_reviews.py"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def _doi(rec):
    for a in rec.get("articleids") or []:
        if a.get("idtype") == "doi":
            return a.get("value", "")
    return ""


def fetch_pubmed(client, base, y_now, years, retmax):
    term = "(%s) AND systematic review[pt] AND (%d:%d[dp])" % (base, y_now - years + 1, y_now)
    s = tl.pubmed_search(client, term, retmax=retmax)
    if s["errors"]:
        raise ValueError("PubMed devolvio errores: " + "; ".join(s["errors"]))
    rows, resp = [], [s["resp"].rel_path]
    if s["idlist"]:
        r = client.get(tl.EUTILS + "esummary.fcgi", {"db": "pubmed", "id": ",".join(s["idlist"]), "retmode": "json"})
        resp.append(r.rel_path)
        res = json.loads(r.text).get("result", {})
        for uid in res.get("uids", s["idlist"]):
            rec = res.get(str(uid)) or {}
            rows.append({"pmid": str(uid), "title": rec.get("title", ""), "year": str(rec.get("pubdate", ""))[:4],
                         "journal": rec.get("source", ""), "doi": _doi(rec), "source": "pubmed"})
    return term, s["count"], rows, resp


def fetch_epmc(client, epmc_query, y_now, years, size):
    q = '(%s) AND (PUB_YEAR:[%d TO %d]) AND ("systematic review" OR "meta-analysis")' % (epmc_query, y_now - years + 1, y_now)
    r = client.get(EPMC, {"query": q, "format": "json", "resultType": "lite", "pageSize": str(size)})
    data = json.loads(r.text)
    rows = [{"pmid": str(x.get("pmid", "")), "title": x.get("title", ""), "year": str(x.get("pubYear", "")),
             "journal": x.get("journalTitle", ""), "doi": x.get("doi", ""), "source": "europepmc"}
            for x in (data.get("resultList") or {}).get("result", [])]
    return q, int(data.get("hitCount", len(rows))), rows, [r.rel_path]


def render_md(topic, date, pm_rows, ep_rows, links):
    L = ["# Revisiones sistematicas existentes — tema %s (%s)" % (topic["id"], date), "",
         "Lista generada por script. **Decide Laura** (no Claude) si alguna tiene el mismo PICO que tu tema: "
         "compara la columna «PICO (lo rellena Laura)» con tu PICO.", "",
         "| PMID | Ano | Titulo | Revista | PICO (lo rellena Laura) | ¿Mismo PICO? |", "|---|---|---|---|---|---|"]
    for r in pm_rows:
        L.append("| %s | %s | %s | %s |  |  |" % (r["pmid"], r["year"], r["title"].replace("|", "/"), r["journal"].replace("|", "/")))
    if ep_rows:
        L += ["", "## Europe PMC (complementario; no cuenta como base)", "", "| PMID/DOI | Ano | Titulo |", "|---|---|---|"]
        for r in ep_rows:
            L.append("| %s | %s | %s |" % (r["pmid"] or r["doi"], r["year"], r["title"].replace("|", "/")))
    L += ["", "Abrir busqueda en PubMed: " + links, "", "Registros PROSPERO / Epistemonikos: se buscan a mano; "
          "pega aqui el enlace, la fecha y el numero (record_manual.py count).", ""]
    return "\n".join(L)


def run(root, topic, client, years=5, retmax=100):
    tid, base, date, y_now = str(topic["id"]), str(topic.get("query") or ""), paths.today(), tl.year_now()
    term, n, pm_rows, resp = fetch_pubmed(client, base, y_now, years, retmax)
    ep_rows, ep = [], None
    if topic.get("epmc_query"):
        ep = fetch_epmc(client, str(topic["epmc_query"]), y_now, years, retmax)
        ep_rows = ep[2]
    rel_json = tl.unique_rel(root, "01_tema/reviews/%s_%s.json" % (tid, date))
    rel_md = rel_json[:-5] + ".md"
    obj = {"schema": "tfm-existing-reviews/v1", "topic_id": tid, "date": date, "pubmed": {"query": term, "count": n, "rows": pm_rows},
           "europepmc": ({"query": ep[0], "count": ep[1], "rows": ep_rows} if ep else None),
           "decision_pending_es": "Laura decide si alguna tiene el mismo PICO"}
    tl.write_json(root, rel_json, obj)
    paths.write_text_atomic(paths.safe_join(root, rel_md), render_md(topic, date, pm_rows, ep_rows, tl.pubmed_link(term)))
    refs = ["PMID:%s" % r["pmid"] for r in pm_rows if r["pmid"]]
    ids = []
    e = journal_io.add(root, {
        "stage": "C1", "type": "search", "actor": "script", "topic_id": tid, "metric": "sr_list",
        "what_es": "Lista de revisiones sistematicas (PubMed, %d anos) del tema %s: %d registros" % (years, tid, n),
        "tool": journal_io.tool_string(SCRIPT, tl.VERSION), "how_verified": "esearch+esummary; respuestas en raw/api",
        "human_decision": "pendiente", "query": {"db": "pubmed", "string": term, "date": date, "count": n},
        "refs": refs, "inputs": tl.refs_for(root, resp), "outputs": [journal_io.file_ref(root, rel_json), journal_io.file_ref(root, rel_md)]})
    ids.append(e["id"])
    if ep:
        e2 = journal_io.add(root, {
            "stage": "C1", "type": "search", "actor": "script", "topic_id": tid, "metric": "sr_list_epmc",
            "what_es": "Lista complementaria Europe PMC del tema %s: %d registros" % (tid, ep[1]),
            "tool": journal_io.tool_string(SCRIPT, tl.VERSION), "how_verified": "Europe PMC REST; respuesta en raw/api",
            "human_decision": "pendiente", "query": {"db": "europepmc", "string": ep[0], "date": date, "count": ep[1]},
            "inputs": tl.refs_for(root, ep[3]), "outputs": [journal_io.file_ref(root, rel_json)]})
        ids.append(e2["id"])
    return {"ok": True, "topic": tid, "files": [rel_json, rel_md], "journal_ids": ids, "count_pubmed": n,
            "message_es": "Encontre %d revisiones sistematicas. Revisa la tabla y dime si alguna tiene el mismo PICO: lo decides tu." % n}


def main(argv=None, client=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("--topic", required=True)
    ap.add_argument("--years", type=int, default=5)
    ap.add_argument("--max", type=int, default=100)
    ap.add_argument("--confirmed", action="store_true")
    a = ap.parse_args(argv)
    try:
        root = paths.find_root(a.root)
        topic = tl.get_topic(root, a.topic)
    except (paths.ProjectNotFound, KeyError) as e:
        tl.out({"ok": False, "error_es": e.args[0] if e.args else str(e)})
        return tl.EXIT_USAGE
    msg = tl.guard_network(root) if client is None else None
    if msg:
        tl.out({"ok": False, "error_es": msg})
        return tl.EXIT_USAGE
    c = client or hc.HttpClient(root, confirmed=a.confirmed)
    try:
        r = run(root, topic, c, a.years, a.max)
    except hc.NeedsConfirmation as e:
        tl.out({"ok": False, "needs_confirmation": True, "error_es": str(e)})
        return tl.EXIT_CONFIRM
    except hc.NetworkError as e:
        tl.degrade(root, e)
        tl.out({"ok": False, "network_error": True, "error_es": "Sin conexion (%s). Paso a LITE-a." % e})
        return tl.EXIT_NET
    except (ValueError, hc.HttpError, journal_io.JournalError) as e:
        tl.out({"ok": False, "error_es": str(e)})
        return tl.EXIT_BLOCK
    tl.out(r)
    return tl.EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
