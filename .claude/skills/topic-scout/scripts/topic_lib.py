"""topic-scout shared helpers: topics.yaml, PubMed esearch parsing, MeSH validation (F-05), mode guard.

Only stdlib + skills/_common. Every network call goes through http_client.HttpClient (cap, cache, envelope).
"""
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if not os.path.isdir(os.path.join(HERE, "_common")):      # dev layout: skills/_common is the canonical copy
    sys.path.append(os.path.dirname(os.path.dirname(HERE)))
from _common import config, journal_io, miniyaml, modes, paths  # noqa: E402,F401
from _common import http_client as hc  # noqa: E402

VERSION = "1.0"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
MESH_TAGS = r"(?:mh|mesh|mesh terms|majr|mesh major topic|mh:noexp|mesh:noexp|mesh terms:noexp)"
_Q_MESH = re.compile(r'"([^"]+)"\s*\[\s*' + MESH_TAGS + r'\s*\]', re.I)
_U_MESH = re.compile(r'(?<![\w"\]])([A-Za-z][\w\-]*)\s*\[\s*' + MESH_TAGS + r'\s*\]', re.I)
_UNQ_MULTI = re.compile(r'(?<!")\b([A-Za-z][\w\-]*(?:,? [A-Za-z][\w\-]*)+)\s*\[\s*' + MESH_TAGS + r'\s*\]', re.I)

EXIT_OK, EXIT_BLOCK, EXIT_USAGE, EXIT_CONFIRM, EXIT_NET = 0, 1, 2, 3, 4


def out(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")


# ---- topics ---------------------------------------------------------------------------------------
def load_topics(root):
    p = paths.Paths(root).root / "config" / "topics.yaml"
    data = miniyaml.loads(paths.read_text(p)) if p.is_file() else {}
    return list((data or {}).get("topics") or [])


def get_topic(root, topic_id):
    for t in load_topics(root):
        if isinstance(t, dict) and str(t.get("id")) == str(topic_id):
            return t
    raise KeyError("tema %s no esta en config/topics.yaml" % topic_id)


def guard_network(root):
    """None if network scripts may run, else a Spanish message (modes.can_run)."""
    mode = config.get_mode(root)
    if modes.can_run(mode, needs_network=True):
        return None
    return ("Modo actual: %s. Este conteo necesita internet (modo FULL). Usa el conector PubMed o copia el numero "
            "de pubmed.gov y registralo con record_manual.py." % mode)


def degrade(root, exc):
    try:
        modes.degrade_to_lite_a(root, "error de red en topic-scout: %s" % exc)
    except Exception:  # never mask the original error
        pass


# ---- MeSH extraction -------------------------------------------------------------------------------
def extract_mesh_terms(query):
    """Return (terms, style_warnings). Terms are descriptor names (subheading after '/' removed)."""
    terms, warns = [], []
    for m in _Q_MESH.finditer(query):
        terms.append(m.group(1))
    for m in _U_MESH.finditer(query):
        terms.append(m.group(1))
    for m in _UNQ_MULTI.finditer(query):
        warns.append("termino MeSH sin comillas: %s (usa \"termino\"[mh])" % m.group(1))
    clean, seen = [], set()
    for t in terms:
        d = t.split("/")[0].strip()
        if d and d.lower() not in seen:
            seen.add(d.lower())
            clean.append(d)
    return clean, warns


# ---- PubMed esearch --------------------------------------------------------------------------------
def parse_esearch(text):
    """Parse esearch JSON -> {count, translation, errors[], warnings[], idlist}. Never raises on bad shape."""
    try:
        data = json.loads(text)
    except ValueError:
        return {"count": None, "translation": "", "errors": ["respuesta no es JSON"], "warnings": [], "idlist": []}
    res = data.get("esearchresult") if isinstance(data, dict) else None
    if not isinstance(res, dict):
        return {"count": None, "translation": "", "errors": ["respuesta sin esearchresult"], "warnings": [], "idlist": []}
    errors, warnings = [], []
    if res.get("ERROR"):
        errors.append("ERROR: %s" % res["ERROR"])
    el = res.get("errorlist") or {}
    for p in el.get("phrasesnotfound") or []:
        errors.append("PhraseNotFound: %s" % p)
    for p in el.get("fieldsnotfound") or []:
        errors.append("FieldNotFound: %s" % p)
    wl = res.get("warninglist") or {}
    for key, label in (("phrasesignored", "PhraseIgnored"), ("quotedphrasesnotfound", "QuotedPhraseNotFound"),
                       ("outputmessages", "OutputMessage")):
        for p in wl.get(key) or []:
            warnings.append("%s: %s" % (label, p))
    try:
        count = int(res.get("count"))
    except (TypeError, ValueError):
        count = None
        errors.append("sin contador (count) en la respuesta")
    return {"count": count, "translation": res.get("querytranslation", ""), "errors": errors, "warnings": warnings,
            "idlist": list(res.get("idlist") or [])}


def pubmed_search(client, term, retmax=0, cache="day", max_age_s=None):
    r = client.get(EUTILS + "esearch.fcgi", {"db": "pubmed", "term": term, "retmode": "json", "retmax": str(retmax)},
                   cache=cache, max_age_s=max_age_s)
    d = parse_esearch(r.text)
    d["resp"] = r
    d["term"] = term
    return d


def mesh_check(client, term):
    """Exact-descriptor validation through esearch db=mesh + esummary db=mesh (F-05). No guessing:
    an unexpected response shape is an ERROR, never a silent pass."""
    q = '"%s"[MeSH Terms]' % term
    r1 = client.get(EUTILS + "esearch.fcgi", {"db": "mesh", "term": q, "retmode": "json", "retmax": "5"})
    d1 = parse_esearch(r1.text)
    res = {"term": term, "valid": False, "descriptor": None, "ui": None, "message": "", "inputs": [r1.rel_path]}
    ids = d1["idlist"]
    if d1["count"] is None:
        res["message"] = "respuesta inesperada de MeSH: " + "; ".join(d1["errors"])
        return res
    if not ids:
        res["message"] = "'%s' no existe en MeSH (ni como descriptor ni como sinonimo)" % term
        return res
    r2 = client.get(EUTILS + "esummary.fcgi", {"db": "mesh", "id": ",".join(ids), "retmode": "json"})
    res["inputs"].append(r2.rel_path)
    try:
        result = json.loads(r2.text)["result"]
    except (ValueError, KeyError, TypeError):
        res["message"] = "esummary de MeSH con formato inesperado: no se puede validar '%s'" % term
        return res
    names = []
    for uid in result.get("uids", ids):
        rec = result.get(str(uid)) or {}
        mt = rec.get("ds_meshterms")
        if not mt:
            continue
        names.append(mt[0])
        if str(mt[0]).strip().lower() == term.strip().lower():
            res.update(valid=True, descriptor=mt[0], ui=rec.get("ds_meshui"), message="descriptor exacto")
            return res
    if names:
        res["message"] = "'%s' no es un descriptor exacto; el descriptor MeSH es: %s" % (term, " | ".join(names))
        res["descriptor"] = names[0]
    else:
        res["message"] = "esummary de MeSH sin ds_meshterms: no se puede validar '%s'" % term
    return res


def refs_for(root, rel_paths):
    out_ = []
    for rp in rel_paths:
        if rp and (paths.Paths(root).root / rp).is_file():
            ref = journal_io.file_ref(root, rp)
            if ref not in out_:
                out_.append(ref)
    return out_


def year_now():
    return int(paths.today()[:4])


def pubmed_link(term):
    import urllib.parse
    return "https://pubmed.ncbi.nlm.nih.gov/?" + urllib.parse.urlencode({"term": term})


def unique_rel(root, rel):
    """rel path that does not exist yet (adds _r2, _r3 ...): outputs referenced by the journal are never overwritten."""
    base, ext = os.path.splitext(rel)
    n, cand = 1, rel
    while (paths.Paths(root).root / cand).exists():
        n += 1
        cand = "%s_r%d%s" % (base, n, ext)
    return cand


def write_json(root, rel, obj):
    paths.write_text_atomic(paths.safe_join(root, rel), json.dumps(obj, ensure_ascii=False, indent=1) + "\n")
