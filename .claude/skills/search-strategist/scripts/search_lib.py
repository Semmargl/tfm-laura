"""search-strategist shared helpers (C3). Stdlib only; texts for Laura are Spanish, code/comments English.

Exit codes used by all C3 scripts: 0 ok | 1 gate fail / errors found | 2 project folder not found |
3 NeedsConfirmation (>warn_after requests, ask Laura, rerun with --confirmed) | 4 mode does not allow this script |
5 refused (precondition not met: seed seal, source integrity, ...).
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import config, http_client, integrity_core, journal_io, modes, paths, rawstore  # noqa: E402

VERSION = "1.0"
STAGE = "C3"
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
OPENALEX = "https://api.openalex.org/works"
CTGOV = "https://clinicaltrials.gov/api/v2/studies"
MAX_URL_QUERY = 6000          # GET-only client: longer strings must be run by Laura on pubmed.gov (export -> offline)
TRUE = {"1", "true", "yes", "si", "sí", "x", "y", "s"}
SEED_ORIGINS = journal_io.SEED_ORIGINS


class Refusal(Exception):
    """A precondition failed. `code` is machine readable, `msg_es` is for Laura."""

    def __init__(self, code, msg_es, exit_code=5):
        self.code, self.msg_es, self.exit_code = code, msg_es, exit_code
        Exception.__init__(self, "%s: %s" % (code, msg_es))


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")


def tool(script):
    return journal_io.tool_string(script, VERSION)


def stamp():
    return paths.utc_now().replace("-", "").replace(":", "")


def finish(fn):
    """Run fn() -> (obj, exit_code) with the standard error mapping."""
    try:
        obj, code = fn()
    except Refusal as e:
        emit({"ok": False, "refused": e.code, "message_es": e.msg_es})
        return e.exit_code
    except paths.ProjectNotFound as e:
        emit({"ok": False, "error": str(e)})
        return 2
    except http_client.NeedsConfirmation as e:
        emit({"ok": False, "needs_confirmation": True, "message_es": str(e) + " Pregunta a Laura y repite con --confirmed."})
        return 3
    except http_client.CapExceeded as e:
        emit({"ok": False, "cap_exceeded": True, "message_es": str(e)})
        return 5
    except http_client.NetworkError as e:
        return _network_down(e)
    except http_client.HttpError as e:
        emit({"ok": False, "http_error": e.status, "message_es": "La API respondió HTTP %s. No se guardó ningún resultado." % e.status})
        return 1
    except journal_io.JournalError as e:
        emit({"ok": False, "journal_errors": e.errors})
        return 1
    emit(obj)
    return code


_ROOT_FOR_DEGRADE = []


def _network_down(e):
    msg = "No hay conexión con la API (%s)." % e
    if _ROOT_FOR_DEGRADE:
        try:
            modes.degrade_to_lite_a(_ROOT_FOR_DEGRADE[0], str(e)[:120])
            msg += " El modo pasa a LITE-a (queda en el diario). Usa pubmed.gov y pega aquí los «Search details»."
        except Exception:      # degradation must never hide the original error
            pass
    emit({"ok": False, "network_error": True, "message_es": msg})
    return 4


def open_project(root_arg):
    root = paths.find_root(root_arg)
    _ROOT_FOR_DEGRADE[:] = [root]
    return root


def need_mode(root, network):
    mode = config.get_mode(root)
    if not modes.can_run(mode, needs_network=network):
        why = ("requiere conexión (modo FULL)" if network else "requiere modo FULL o LITE-a")
        raise Refusal("MODE_NOT_ALLOWED", "Modo actual %s: este paso %s. Sigue el camino LITE del SKILL.md." % (mode, why), 4)
    return mode


# --------------------------------------------------------------------------------------------- seed set
def seed_path(root):
    return paths.Paths(root).root / "03_busqueda" / "seed_set.csv"


def load_seed(root):
    p = seed_path(root)
    text = paths.read_text(p) if p.is_file() else ""
    rows = []
    for i, r in enumerate(csv.DictReader(io.StringIO(text)), 1):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items() if k}
        r["held_out"] = r.get("held_out", "").lower() in TRUE
        r["pmid"] = re.sub(r"\D", "", r.get("pmid", ""))
        r["_row"] = i
        rows.append(r)
    return rows


def seed_id(r):
    if r.get("pmid"):
        return "PMID:" + r["pmid"]
    if r.get("doi"):
        return "DOI:" + r["doi"]
    return "ROW:%d" % r["_row"]


def validate_seed(root, rows):
    cfg = config.load_config(root)["recall"]
    errors, warnings = [], []
    origins, seen = {}, set()
    for r in rows:
        o = r.get("origin", "")
        if o not in SEED_ORIGINS:
            errors.append("%s: origen «%s» no permitido (%s)" % (seed_id(r), o, ", ".join(SEED_ORIGINS)))
        else:
            origins[o] = origins.get(o, 0) + 1
        if not r["pmid"] and not r.get("doi"):
            errors.append("fila %d: sin PMID ni DOI" % r["_row"])
        elif not r["pmid"]:
            warnings.append("%s: sin PMID, no se puede probar el recall en PubMed (hay que añadir el PMID o decidir con el tutor)" % seed_id(r))
        if seed_id(r) in seen:
            errors.append("%s: seed duplicada" % seed_id(r))
        seen.add(seed_id(r))
    held = [r for r in rows if r["held_out"]]
    if len(rows) < cfg["seed_min"]:
        errors.append("hay %d seed; el mínimo es %d" % (len(rows), cfg["seed_min"]))
    if len(held) < cfg["held_out_min"]:
        errors.append("hay %d seed held-out; el mínimo es %d" % (len(held), cfg["held_out_min"]))
    return {"ok": not errors, "errors": errors, "warnings": warnings, "n": len(rows), "held_out": [seed_id(r) for r in held],
            "origins": origins, "untestable": [seed_id(r) for r in rows if not r["pmid"]]}


def seals(root):
    return journal_io.query(root, type="seed_seal")


def check_seal_order(root):
    """F-02: the seed_seal matching today's seed_set.csv must be strictly OLDER than the first journal
    entry of every strings/*_v1.txt. Raises Refusal otherwise. Returns the seal entry."""
    P = paths.Paths(root)
    sp = seed_path(root)
    if not sp.is_file():
        raise Refusal("SEED_MISSING", "Falta 03_busqueda/seed_set.csv.")
    sha = paths.sha256_file(sp)
    all_seals = seals(root)
    if not all_seals:
        raise Refusal("SEED_NOT_SEALED", "El seed set no está sellado: usa seed_seal.py seal ANTES de crear la cadena v1 (F-02).")
    matching = [s for s in all_seals if s["seed"]["sha256"] == sha]
    if not matching:
        raise Refusal("SEED_CHANGED_AFTER_SEAL", "seed_set.csv cambió después del sello: el recall no es válido (F-02).")
    seal = matching[0]
    sdir = P.root / "03_busqueda" / "strings"
    for f in sorted(sdir.glob("*_v1.txt")) if sdir.is_dir() else []:
        rel = paths.rel(root, f)
        ent = journal_io.find_for_path(root, rel)
        if not ent:
            raise Refusal("ORDER_UNPROVABLE", "%s existe sin entrada de diario: no se puede demostrar que el sello es anterior (F-02)." % rel)
        if not seal["ts"] < ent[0]["ts"]:
            raise Refusal("SEED_SEAL_NOT_BEFORE_STRING",
                          "El sello del seed (%s, %s) no es anterior a %s (%s): recall circular, rechazado (F-02)." % (seal["id"], seal["ts"], rel, ent[0]["ts"]))
    return seal


# --------------------------------------------------------------------------------------------- source files
def source_ok(root, rel, require=None):
    """Return the registry entry if `rel` is a legitimate source (W2-3/F-01/F-04) else raise Refusal."""
    full = paths.safe_join(root, rel)
    if not full.is_file():
        raise Refusal("SOURCE_MISSING", "No existe %s." % rel)
    reg = rawstore.load(root)["files"].get(rel)
    if not reg:
        raise Refusal("SOURCE_UNREGISTERED", "%s no está registrado en raw/_hashes.json (usa integrity.py register-export)." % rel)
    if reg["sha256"] != paths.sha256_file(full):
        raise Refusal("SOURCE_HASH_MISMATCH", "%s cambió después de registrarse." % rel)
    if rel.startswith("raw/api/"):
        ok, why = http_client.verify_envelope(full)
        if not ok or reg.get("actor") != "script":
            raise Refusal("SOURCE_NOT_API", "%s no es una respuesta válida de http_client (%s)." % (rel, why))
    elif rel.startswith("raw/exports/") or rel.startswith("raw/chasing/"):
        ok, kind, why = integrity_core.shape_check_export(full)
        if not ok or reg.get("actor") != "laura":
            raise Refusal("SOURCE_NOT_EXPORT", "%s no es un export de Laura con forma válida (%s)." % (rel, why))
    else:
        raise Refusal("SOURCE_NOT_RAW", "Solo se aceptan fuentes de raw/api o raw/exports (recibido %s)." % rel)
    bl = [b for b in integrity_core.check(root)["blockers"] if b["path"] == rel]
    if bl:
        raise Refusal("SOURCE_INTEGRITY", "%s tiene un bloqueo de integridad: %s" % (rel, bl[0]["code"]))
    return reg


def pmids_from_export(path):
    """PMIDs found in an nbib / RIS / CSV / PMID-list export (formats of CENTRAL/PEDro: 'pendiente de verificar', R-10)."""
    p = str(path)
    text = integrity_core._text(p)       # shared tolerant decoder
    out = set()
    ext = p.lower().rsplit(".", 1)[-1]
    if ext in ("nbib", "medline"):
        out |= set(re.findall(r"(?m)^PMID- *(\d+)", text))
    elif ext == "ris":
        out |= set(re.findall(r"(?m)^(?:AN|ID|PM|PMID)\s*-\s*(\d{4,9})\s*$", text))
        out |= set(re.findall(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", text))
        out |= set(re.findall(r"(?m)^PMID- *(\d+)", text))
    elif ext == "csv":
        rows = list(csv.reader(io.StringIO(text)))
        if rows:
            hdr = [c.strip().lower() for c in rows[0]]
            idx = [i for i, c in enumerate(hdr) if c in ("pmid", "pubmed id", "pubmedid", "pmid/id")]
            for r in rows[1:]:
                for i in idx:
                    if i < len(r) and re.fullmatch(r"\d{1,9}", r[i].strip()):
                        out.add(r[i].strip())
    else:
        out |= set(re.findall(r"(?m)^\s*(\d{4,9})\s*$", text))
    return out


# --------------------------------------------------------------------------------------------- strings / syntax
_TOKEN = re.compile(r'"[^"]*"|\[[^\]]*\]|\(|\)|[^\s()\[\]"]+')
OPS = ("AND", "OR", "NOT")
KNOWN_TAGS = {"tiab", "ti", "ab", "mh", "mesh", "majr", "sh", "tw", "pt", "au", "ad", "la", "dp", "pdat", "sb", "all", "ot", "nm",
              "pmid", "uid", "jour", "ta", "filter", "title/abstract", "title", "abstract", "mesh terms", "mesh major topic",
              "mesh subheadings", "publication type", "language", "date - publication", "journal", "subheading", "text word",
              "all fields", "other term", "supplementary concept", "affiliation", "author", "pubmed id", "dp", "edat", "mhda",
              "crdt", "lang", "tt", "title/abstract:~"}
MESH_TAGS = {"mh", "mesh", "majr", "mesh terms", "mesh major topic"}
_NUM = re.compile(r"^\s*#?(\d+)\s*[.):\-]?\s+(.*\S)\s*$")
_REF = re.compile(r"#(\d+)")


def split_comments(text):
    """Comment lines start with '//'. Returns the useful lines."""
    return [ln.rstrip() for ln in text.replace("\r\n", "\n").split("\n") if ln.strip() and not ln.lstrip().startswith("//")]


def read_string_file(root, rel):
    full = paths.safe_join(root, rel)
    if not full.is_file():
        raise Refusal("STRING_MISSING", "No existe %s." % rel)
    return paths.read_text(full)


def build_query(text):
    """-> (query, problems). Numbered-line strings (1. ... / #1 AND #2) are expanded into the last line."""
    lines = split_comments(text)
    problems = []
    if not lines:
        return "", ["la cadena está vacía"]
    num = [_NUM.match(ln) for ln in lines]
    if len(lines) > 1 and all(num):
        defs = {}
        order = []
        for m in num:
            n = int(m.group(1))
            if n in defs:
                problems.append("línea %d repetida" % n)
            defs[n] = m.group(2)
            order.append(n)
        if order != list(range(1, len(order) + 1)):
            problems.append("la numeración de líneas no es 1..%d consecutiva" % len(order))

        def expand(n, depth=0):
            if depth > 20:
                problems.append("referencias de línea circulares")
                return ""
            def rep(m):
                k = int(m.group(1))
                if k not in defs or k >= n:
                    problems.append("la línea %d cita #%d, que no existe o es posterior" % (n, k))
                    return m.group(0)
                return "(" + expand(k, depth + 1) + ")"
            return _REF.sub(rep, defs[n])
        return expand(order[-1]), problems
    return " ".join(ln.strip() for ln in lines), problems


def tokens(query):
    out = []
    for m in _TOKEN.finditer(query):
        t = m.group(0)
        if t == "(":
            out.append(("lp", t))
        elif t == ")":
            out.append(("rp", t))
        elif t.startswith('"'):
            out.append(("q", t))
        elif t.startswith("["):
            out.append(("tag", t))
        elif t in OPS:
            out.append(("op", t))
        else:
            out.append(("w", t))
    return out


def syntax_issues(query):
    """Deterministic syntax lint of a PubMed-style string. Returns [{level,code,msg_es}] (error = blocker)."""
    iss = []

    def add(level, code, msg):
        iss.append({"level": level, "code": code, "msg_es": msg})

    if not query.strip():
        add("error", "EMPTY", "La cadena está vacía.")
        return iss
    if query.count('"') % 2:
        add("error", "QUOTES_ODD", "Comillas sin cerrar.")
    if query.count("[") != query.count("]"):
        add("error", "BRACKET_UNBALANCED", "Corchetes de campo sin cerrar.")
    toks = tokens(query)
    depth = 0
    for k, t in toks:
        if k == "lp":
            depth += 1
        elif k == "rp":
            depth -= 1
            if depth < 0:
                add("error", "PAREN_UNBALANCED", "Hay un «)» sin su «(».")
                depth = 0
    if depth > 0:
        add("error", "PAREN_UNBALANCED", "Faltan %d paréntesis de cierre." % depth)
    if re.search(r"\(\s*\)", query):
        add("error", "EMPTY_PARENS", "Paréntesis vacíos «()».")
    kinds = [k for k, _ in toks]
    for i, (k, t) in enumerate(toks):
        if k == "w" and t.lower() in ("and", "or", "not") and t not in OPS:
            add("error", "OP_LOWERCASE", "«%s» en minúsculas: PubMed no lo lee como operador booleano; usa %s." % (t, t.upper()))
        if k == "tag":
            name = t[1:-1].strip().lower()
            base = name.split(":")[0].strip()
            if base not in KNOWN_TAGS and name not in KNOWN_TAGS:
                add("error", "TAG_UNKNOWN", "Etiqueta de campo desconocida %s." % t)
        if k == "q" and "*" in t:
            add("warning", "TRUNC_IN_QUOTES", "El truncamiento * dentro de comillas %s no se expande en PubMed." % t)
    # operator placement
    sig = [(k, t) for k, t in toks if k != "tag"]
    if sig:
        if sig[0][0] == "op":
            add("error", "OP_LEADING", "La cadena empieza con el operador %s." % sig[0][1])
        if sig[-1][0] == "op":
            add("error", "OP_TRAILING", "La cadena termina con el operador %s." % sig[-1][1])
    for (k1, t1), (k2, t2) in zip(sig, sig[1:]):
        if k1 == "op" and k2 == "op":
            lvl = "warning" if t2 == "NOT" else "error"
            add(lvl, "OP_DOUBLE", "Dos operadores seguidos: %s %s." % (t1, t2))
        if k1 == "lp" and k2 == "op":
            add("error", "OP_AFTER_PAREN", "Operador %s justo después de «(»." % t2)
        if k1 == "op" and k2 == "rp":
            add("error", "OP_BEFORE_PAREN", "Operador %s justo antes de «)»." % t1)
    # tag after an UNQUOTED multi-word chunk (tag only applies to the last word)
    chunk = []
    for k, t in toks:
        if k == "w":
            chunk.append(t)
        elif k == "tag":
            name = t[1:-1].strip().lower().split(":")[0]
            if len(chunk) > 1 and name in ("tiab", "ti", "ab", "tw", "mh", "mesh", "majr"):
                add("warning", "TAG_ON_UNQUOTED_PHRASE", "«%s%s»: sin comillas la etiqueta solo afecta a la última palabra." % (" ".join(chunk), t))
            chunk = []
        else:
            chunk = []
    return iss


def mesh_terms(query):
    """Terms followed by a MeSH field tag: [(term, tag)]. Subheading suffix '/xxx' is stripped."""
    out, chunk = [], []
    for k, t in tokens(query):
        if k == "q":
            chunk = [t.strip('"')]
        elif k == "w":
            chunk.append(t)
        elif k == "tag":
            name = t[1:-1].strip().lower().split(":")[0].strip()
            if name in MESH_TAGS and chunk:
                term = " ".join(chunk).strip()
                term = term.split("/")[0].strip()
                if term:
                    out.append((term, t))
            chunk = []
        else:
            chunk = []
    seen, uniq = set(), []
    for term, tag in out:
        if term.lower() not in seen:
            seen.add(term.lower())
            uniq.append((term, tag))
    return uniq


# --------------------------------------------------------------------------------------------- PubMed esearch
def parse_esearch(resp):
    """Parse an esearch JSON response -> dict(count, idlist, translation, errors, warnings, ...)."""
    try:
        data = resp.json()
    except ValueError:
        return {"count": None, "idlist": [], "translation": "", "errors": ["Respuesta de PubMed no es JSON (¿HTML de error?)"],
                "warnings": [], "rel_path": resp.rel_path, "sha256": resp.sha256, "ts": resp.ts, "from_cache": resp.from_cache}
    res = data.get("esearchresult") or {}
    errors, warnings = [], []
    if data.get("error"):
        errors.append("ERROR: %s" % data["error"])
    if res.get("ERROR"):
        errors.append("ERROR: %s" % res["ERROR"])
    el = res.get("errorlist") or {}
    for key, label in (("phrasesnotfound", "PhraseNotFound"), ("fieldsnotfound", "FieldNotFound")):
        for x in el.get(key) or []:
            errors.append("%s: %s" % (label, x))
    wl = res.get("warninglist") or {}
    for key, label in (("phrasesignored", "PhraseIgnored"), ("quotedphrasesnotfound", "QuotedPhraseNotFound"), ("outputmessages", "OutputMessage")):
        for x in wl.get(key) or []:
            warnings.append("%s: %s" % (label, x))
    try:
        count = int(res.get("count"))
    except (TypeError, ValueError):
        count = None
        errors.append("PubMed no devolvió un número de resultados")
    return {"count": count, "idlist": list(res.get("idlist") or []), "translation": res.get("querytranslation", ""),
            "errors": errors, "warnings": warnings, "rel_path": resp.rel_path, "sha256": resp.sha256, "ts": resp.ts,
            "from_cache": resp.from_cache}


def esearch_pubmed(client, term, retmax=0, extra=None, cache="day", max_age_s=None):
    params = {"db": "pubmed", "term": term, "retmode": "json", "retmax": retmax}
    params.update(extra or {})
    if len(term) > MAX_URL_QUERY:
        raise Refusal("STRING_TOO_LONG", "La cadena tiene %d caracteres (> %d): ejecútala tú en pubmed.gov, exporta y usa el modo --offline." % (len(term), MAX_URL_QUERY))
    return parse_esearch(client.get(ESEARCH, params, cache=cache, max_age_s=max_age_s))


def validate_mesh(client, term):
    """Check a [mh] term against db=mesh (F-05). status: descriptor | entry_term | not_found | found_unchecked."""
    r = client.get(ESEARCH, {"db": "mesh", "term": '"%s"[MeSH Terms]' % term, "retmode": "json", "retmax": 5})
    try:
        res = r.json().get("esearchresult") or {}
        ids = list(res.get("idlist") or [])
        count = int(res.get("count", 0))
    except (ValueError, TypeError):
        return {"term": term, "status": "not_found", "evidence": r.rel_path, "note": "respuesta ilegible de db=mesh"}
    if count == 0 or not ids:
        return {"term": term, "status": "not_found", "evidence": r.rel_path}
    s = client.get(ESUMMARY, {"db": "mesh", "id": ",".join(ids), "retmode": "json"})
    try:
        result = s.json().get("result") or {}
        for uid in ids:
            names = [str(x) for x in ((result.get(uid) or {}).get("ds_meshterms") or [])]
            if names:
                if names[0].lower() == term.lower():
                    return {"term": term, "status": "descriptor", "evidence": s.rel_path, "ui": (result.get(uid) or {}).get("ds_meshui", "")}
                if term.lower() in [n.lower() for n in names]:
                    return {"term": term, "status": "entry_term", "evidence": s.rel_path, "descriptor": names[0]}
        return {"term": term, "status": "not_found" if any(((result.get(u) or {}).get("ds_meshterms")) for u in ids) else "found_unchecked",
                "evidence": s.rel_path}
    except (ValueError, AttributeError):
        return {"term": term, "status": "found_unchecked", "evidence": s.rel_path}


def make_client(root, args):
    return http_client.HttpClient(root, email=getattr(args, "email", None), confirmed=getattr(args, "confirmed", False))


# --------------------------------------------------------------------------------------------- misc helpers
def unique_rel(root, rel):
    base, ext = os.path.splitext(rel)
    cand, n = rel, 1
    while paths.safe_join(root, cand).exists():
        n += 1
        cand = "%s_%d%s" % (base, n, ext)
    return cand


def string_guard(root, rel):
    """A string file must be journaled and unchanged (inv. 2) before it is used for a gate."""
    bl = [b for b in integrity_core.check(root)["blockers"] if b["path"] == rel]
    if bl:
        raise Refusal("STRING_NOT_CLEAN", "%s: %s. Registra el cambio con integrity.py record-change antes de usarla." % (rel, bl[0]["msg"]))


def string_version(rel):
    m = re.search(r"_v(\d+)\.txt$", rel)
    return int(m.group(1)) if m else 0


def verbatim(text):
    return "\n".join(split_comments(text))
