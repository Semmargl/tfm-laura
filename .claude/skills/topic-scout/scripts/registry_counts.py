#!/usr/bin/env python3
"""registry_counts.py --topic T1 [--cond "diastasis recti"] [--confirmed]

ClinicalTrials.gov API v2: number of registered studies for a condition (query.cond). Journal `count`
(db clinicaltrials_gov, metric ctgov_records). FULL mode only. WHO ICTRP / PROSPERO / Epistemonikos are manual
(record_manual.py count).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import topic_lib as tl  # noqa: E402
from topic_lib import hc, journal_io, paths  # noqa: E402

SCRIPT = "registry_counts.py"
CTGOV = "https://clinicaltrials.gov/api/v2/studies"


def run(root, topic, client, cond=None):
    tid = str(topic["id"])
    cond = cond or topic.get("ctgov_cond")
    if not cond:
        raise ValueError("falta 'ctgov_cond' en el tema %s (o usa --cond)" % tid)
    r = client.get(CTGOV, {"query.cond": cond, "countTotal": "true", "pageSize": "1", "format": "json"})
    data = json.loads(r.text)
    if "totalCount" not in data:
        raise ValueError("respuesta de ClinicalTrials.gov sin totalCount")
    n = int(data["totalCount"])
    e = journal_io.add(root, {
        "stage": "C1", "type": "count", "actor": "script", "topic_id": tid, "metric": "ctgov_records",
        "what_es": "Registros en ClinicalTrials.gov para '%s': %d" % (cond, n),
        "tool": journal_io.tool_string(SCRIPT, tl.VERSION), "how_verified": "API v2 /studies countTotal; respuesta en raw/api",
        "human_decision": "n/a",
        "query": {"db": "clinicaltrials_gov", "string": "query.cond=%s" % cond, "date": paths.today(), "count": n},
        "inputs": tl.refs_for(root, [r.rel_path]), "url": "https://clinicaltrials.gov/search?cond=" + cond.replace(" ", "+")})
    return {"ok": True, "topic": tid, "count": n, "journal_id": e["id"],
            "message_es": "ClinicalTrials.gov: %d registros para «%s»." % (n, cond)}


def main(argv=None, client=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("--topic", required=True)
    ap.add_argument("--cond")
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
        r = run(root, topic, c, a.cond)
    except hc.NetworkError as e:
        tl.degrade(root, e)
        tl.out({"ok": False, "network_error": True, "error_es": "Sin conexion (%s). Paso a LITE-a." % e})
        return tl.EXIT_NET
    except (ValueError, hc.HttpError, hc.NeedsConfirmation, journal_io.JournalError) as e:
        tl.out({"ok": False, "error_es": str(e)})
        return tl.EXIT_BLOCK
    tl.out(r)
    return tl.EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
