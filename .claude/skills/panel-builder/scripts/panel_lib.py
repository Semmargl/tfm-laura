"""panel-builder shared helpers (journal lookups, dotted paths, constants). stdlib + _common only."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if not os.path.isdir(os.path.join(HERE, "_common")):
    sys.path.append(os.path.dirname(os.path.dirname(HERE)))
from _common import config, journal_io, miniyaml, paths  # noqa: E402,F401

VERSION = "1.0"
WATERMARK = "PRELIMINAR — piloto, no forma parte del protocolo"       # W-1
SIGNATURE = "Sugerencia; decide Laura"
PANELS_NOW = ("viabilidad", "flow")                                     # implemented in phase 1
PANELS_LATER = ("busqueda", "mapa", "prisma_p")                          # phase 2-3
WATERMARKED = ("flow", "mapa")
FLOW_METRICS = [("flow_identificados", "Registros identificados"), ("flow_duplicados", "Duplicados marcados"),
                ("flow_cribados", "Registros cribados"), ("flow_excluidos", "Excluidos"), ("flow_incluidos", "Incluidos")]


def getpath(obj, dotted):
    """Dotted lookup; 'by_year.2020' works on dict keys; raises KeyError if absent."""
    cur = obj
    for part in str(dotted).split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise KeyError(dotted)
    return cur


def value_text(v, agg=None):
    if agg == "len":
        v = len(v)
    return str(v)


def by_id(entries):
    return {e["id"]: e for e in entries}


def topic_ids(root, entries):
    p = paths.Paths(root).root / "config" / "topics.yaml"
    ids = []
    if p.is_file():
        data = miniyaml.loads(paths.read_text(p)) or {}
        for t in data.get("topics") or []:
            if isinstance(t, dict) and t.get("id") is not None:
                ids.append((str(t["id"]), str(t.get("title_es", ""))))
    known = {i for i, _ in ids}
    for e in entries:
        tid = e.get("topic_id")
        if tid and tid not in known:
            known.add(tid)
            ids.append((str(tid), ""))
    return ids


def latest(entries, topic_id, metric=None, type_=None, **eq):
    hit = None
    for e in entries:
        if e.get("topic_id") != topic_id:
            continue
        if metric is not None and e.get("metric") != metric:
            continue
        if type_ is not None and e.get("type") != type_:
            continue
        if any(e.get(k) != v for k, v in eq.items()):
            continue
        hit = e
    return hit


def project_config(root):
    return config.load_config(root)


def unique_rel(root, rel):
    """Report files are evidence referenced by sha256 in the journal: never overwrite one (same-second runs get _r2, _r3)."""
    base, ext = os.path.splitext(rel)
    n, cand = 1, rel
    while (paths.Paths(root).root / cand).exists():
        n += 1
        cand = "%s_r%d%s" % (base, n, ext)
    return cand
