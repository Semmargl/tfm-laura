"""verifier shared helpers (C7): plumbing, normalisers, provenance (F-01), source legitimacy (F-04), PubMed/Crossref parsing."""
from __future__ import annotations

import csv
import difflib
import io
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import config, http_client, integrity_core, journal_io, modes, paths, rawstore  # noqa: E402

VERSION = "1.0"
STAGE = "C7"
REFS_REL = "07_verificacion/references.csv"
REPORTS = "07_verificacion/reports"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
CROSSREF = "https://api.crossref.org/works"
HANDLES = "https://doi.org/api/handles/"
PROV_TYPES = ("search", "count", "verification", "reference_add", "change")
BLOCKING = {"NO_PROVENANCE", "UNVERIFIABLE", "NOT_FOUND", "MISMATCH", "RETRACTED", "EOC", "DUPLICATE", "METADATA_NOT_COMPARED"}
UNVERIFIED = {"UNVERIFIABLE", "METADATA_NOT_COMPARED"}
RETRACT_TYPES = {"retraction", "withdrawal", "removal"}
EOC_TYPES = {"expression_of_concern", "expression-of-concern"}
TITLE_SIM = 0.90
EXTRA_COLS = ["claimed_title", "claimed_first_author", "claimed_year", "claimed_journal", "claimed_issn"]
BASE_COLS = ["ref_id", "doi", "pmid", "source_journal_id", "provenance_status"]


class Refusal(Exception):
    def __init__(self, code, msg_es, exit_code=5):
        self.code, self.msg_es, self.exit_code = code, msg_es, exit_code
        Exception.__init__(self, "%s: %s" % (code, msg_es))


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")


def tool(script):
    return journal_io.tool_string(script, VERSION)


def stamp():
    return paths.utc_now().replace("-", "").replace(":", "")


_ROOT = []


def open_project(root_arg):
    r = paths.find_root(root_arg)
    _ROOT[:] = [r]
    return r


def finish(fn):
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
        msg = "No hay conexión con la API (%s)." % e
        if _ROOT:
            try:
                modes.degrade_to_lite_a(_ROOT[0], str(e)[:120])
                msg += " El modo pasa a LITE-a (queda en el diario): usa --offline y el checklist LITE."
            except Exception:
                pass
        emit({"ok": False, "network_error": True, "message_es": msg})
        return 4
    except journal_io.JournalError as e:
        emit({"ok": False, "journal_errors": e.errors})
        return 1
    emit(obj)
    return code


def need_mode(root, network):
    mode = config.get_mode(root)
    if not modes.can_run(mode, needs_network=network):
        raise Refusal("MODE_NOT_ALLOWED", "Modo actual %s: %s. Usa el camino LITE (checklist_refs_LITE.md)." % (
            mode, "este paso necesita conexión (FULL); con --offline solo se comprueba la procedencia" if network else "no hay scripts en este modo"), 4)
    return mode


def unique_rel(root, rel):
    base, ext = os.path.splitext(rel)
    cand, n = rel, 1
    while paths.safe_join(root, cand).exists():
        n += 1
        cand = "%s_%d%s" % (base, n, ext)
    return cand


# ------------------------------------------------------------------------------------------------ normalisers
def norm_doi(d):
    d = (d or "").strip().lower()
    d = re.sub(r"^(doi:\s*|https?://(dx\.)?doi\.org/)", "", d)
    return d.rstrip(".;, ")


def norm_pmid(p):
    p = re.sub(r"\D", "", p or "")
    return p.lstrip("0") if p else ""


def norm_text(t):
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def sim(a, b):
    a, b = norm_text(a), norm_text(b)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def surname_norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    return re.sub(r"[^a-z]", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


def claimed_surname(a):
    a = (a or "").strip()
    if not a:
        return ""
    if "," in a:
        a = a.split(",")[0]
    elif re.match(r"^[^\W\d_][\w'\-]* [A-Z]{1,3}$", a, re.U):
        a = a.split(" ")[0]
    elif " " in a:
        a = a.split(" ")[-1]
    return surname_norm(a)


# ------------------------------------------------------------------------------------------------ references.csv
def load_refs(root):
    p = paths.safe_join(root, REFS_REL)
    if not p.is_file():
        raise Refusal("NO_REFS", "No existe %s." % REFS_REL)
    rows = list(csv.DictReader(io.StringIO(paths.read_text(p))))
    out = []
    for r in rows:
        r = {(k or "").strip(): (v or "").strip() for k, v in r.items() if k}
        r["doi"], r["pmid"] = norm_doi(r.get("doi")), norm_pmid(r.get("pmid"))
        out.append(r)
    return out


def write_refs(root, rows):
    cols = list(BASE_COLS)
    for c in EXTRA_COLS:
        if any(r.get(c) for r in rows) or c in (rows[0] if rows else {}):
            cols.append(c)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    paths.write_text_atomic(paths.safe_join(root, REFS_REL), buf.getvalue())


# ------------------------------------------------------------------------------------------------ provenance (F-01) and sources (F-04)
def _body_text(full, rel):
    if rel.startswith("raw/api/"):
        return json.loads(paths.read_text(full))["body"]
    b = full.read_bytes()
    if rel.lower().endswith(".pdf"):
        return b.decode("latin-1", errors="replace")
    return integrity_core._text(str(full))


def has_doi(text, doi):
    return bool(doi) and re.search(re.escape(doi) + r"(?![A-Za-z0-9])", text.lower()) is not None


def has_pmid(text, pmid):
    if not pmid:
        return False
    p = re.escape(pmid)
    pats = [r"(?m)^PMID- *%s\b" % p, r"<PMID[^>]*>\s*%s\s*</PMID>" % p, r"pubmed\.ncbi\.nlm\.nih\.gov/%s(?!\d)" % p,
            r"\"(?:pmid|uid)\"\s*:\s*\"?%s(?!\d)" % p, r"\"idlist\"\s*:\s*\[[^\]]*\"%s\"" % p, r"(?m)^(?:AN|ID|PM|PMID)\s*-\s*%s\s*$" % p,
            r"(?m)(?:^|[,;\t])\"?%s\"?(?:[,;\t]|$)" % p, r"PMID[:\s]+%s(?!\d)" % p]
    return any(re.search(x, text, re.I) for x in pats)


def source_legit(root, rel, reg_files=None):
    """(ok, reason) - raw/api envelope written by a script, or raw/exports file registered by Laura with a valid shape. No integrity blocker."""
    try:
        full = paths.safe_join(root, rel)
    except ValueError:
        return False, "ruta no válida"
    if not full.is_file():
        return False, "el archivo no existe"
    reg = (reg_files if reg_files is not None else rawstore.load(root)["files"]).get(rel)
    if not reg:
        return False, "no está registrado en raw/_hashes.json"
    if reg["sha256"] != paths.sha256_file(full):
        return False, "el hash no coincide con el registro"
    if rel.startswith("raw/api/"):
        ok, why = http_client.verify_envelope(full)
        if not ok:
            return False, "no es una respuesta de http_client: " + why
        if reg.get("actor") != "script":
            return False, "registrado con actor %s (debe ser script)" % reg.get("actor")
    elif rel.startswith("raw/exports/") or rel.startswith("raw/chasing/"):
        ok, kind, why = integrity_core.shape_check_export(full)
        if not ok:
            return False, "no parece un export válido: " + why
        if reg.get("actor") != "laura":
            return False, "registrado con actor %s (debe ser laura)" % reg.get("actor")
    else:
        return False, "solo raw/api o raw/exports pueden ser fuente"
    return True, "ok"


def check_provenance(root, row, ctx):
    """F-01 first step. -> {status: OK|NO_PROVENANCE, kind, detail}. ctx = {entries{id:entry}, reg, blockers_by_path}."""
    sj = row.get("source_journal_id", "")
    if not sj:
        return {"status": "NO_PROVENANCE", "detail": "sin source_journal_id"}
    e = ctx["entries"].get(sj)
    if not e:
        return {"status": "NO_PROVENANCE", "detail": "%s no existe en el diario" % sj}
    if e.get("type") not in PROV_TYPES:
        return {"status": "NO_PROVENANCE", "detail": "%s es de tipo %s (se esperaba search/count/verification/reference_add/change)" % (sj, e.get("type"))}
    doi, pmid, rid = row.get("doi", ""), row.get("pmid", ""), row.get("ref_id", "")
    refs = [str(x).lower() for x in (e.get("refs") or [])]
    declared = ("doi:" + doi in refs if doi else False) or ("pmid:" + pmid in refs if pmid else False) or ("refid:" + rid.lower() in refs)
    files = [o["path"] for o in (e.get("outputs") or []) + (e.get("inputs") or []) if str(o.get("path", "")).startswith(("raw/api/", "raw/exports/", "raw/chasing/"))]
    if e["type"] == "reference_add":
        if e.get("actor") != "laura" or not str(e.get("origin_es", "")).strip():
            return {"status": "NO_PROVENANCE", "detail": "reference_add sin actor laura / origin_es"}
        if not declared:
            return {"status": "NO_PROVENANCE", "detail": "%s no declara esta referencia en refs[]" % sj}
        for f in files:
            ok, _ = source_legit(root, f, ctx["reg"])
            if ok and not ctx["blockers"].get(f) and (has_doi(_body_text(paths.safe_join(root, f), f), doi) or has_pmid(_body_text(paths.safe_join(root, f), f), pmid)):
                return {"status": "OK", "kind": "laura_reference_add+file", "detail": "%s + %s" % (sj, f)}
        return {"status": "OK", "kind": "laura_declared", "detail": "%s: añadida a mano por Laura (%s)" % (sj, e.get("origin_es"))}
    if not (doi or pmid):
        return {"status": "NO_PROVENANCE", "detail": "sin DOI ni PMID solo vale una entrada reference_add de Laura"}
    why = []
    for f in files:
        ok, r = source_legit(root, f, ctx["reg"])
        if not ok:
            why.append("%s: %s" % (f, r))
            continue
        if ctx["blockers"].get(f):
            why.append("%s: bloqueo de integridad %s" % (f, ctx["blockers"][f]))
            continue
        body = _body_text(paths.safe_join(root, f), f)
        if has_doi(body, doi) or has_pmid(body, pmid):
            return {"status": "OK", "kind": "file", "detail": "%s en %s" % (sj, f)}
        why.append("%s: no contiene el DOI/PMID" % f)
    return {"status": "NO_PROVENANCE", "detail": "ningún archivo válido de %s contiene este DOI/PMID (%s)" % (sj, "; ".join(why) or "la entrada no enlaza archivos de raw/")}


def context(root):
    ents = {e["id"]: e for e in journal_io.read_all(root)}
    blk = {}
    for b in integrity_core.check(root)["blockers"]:
        blk[b["path"]] = b["code"]
    return {"entries": ents, "reg": rawstore.load(root)["files"], "blockers": blk}


# ------------------------------------------------------------------------------------------------ PubMed XML / Crossref JSON
def _txt(el):
    return "".join(el.itertext()).strip() if el is not None else ""


def parse_pubmed_xml(text):
    """-> {pmid: {title, journal, issn, years(set), first_author, doi, pubtypes[], corrections[(reftype, pmid)]}}"""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return None
    out = {}
    for art in root.iter("PubmedArticle"):
        mc = art.find("MedlineCitation")
        if mc is None:
            continue
        pmid = _txt(mc.find("PMID"))
        a = mc.find("Article")
        years = set()
        for path_ in ("Journal/JournalIssue/PubDate/Year", "ArticleDate/Year"):
            y = _txt(a.find(path_)) if a is not None else ""
            if y:
                years.add(y)
        md = _txt(a.find("Journal/JournalIssue/PubDate/MedlineDate")) if a is not None else ""
        if md[:4].isdigit():
            years.add(md[:4])
        fa = ""
        if a is not None:
            au = a.find("AuthorList/Author")
            if au is not None:
                fa = _txt(au.find("LastName")) or _txt(au.find("CollectiveName"))
        doi = ""
        # B6 fix: only the article's OWN ArticleIdList. art.iter("ArticleId") also walks PubmedData/ReferenceList and returned
        # the DOI of the last cited reference (false MISMATCH on any article with referenced DOIs).
        for el in art.findall("PubmedData/ArticleIdList/ArticleId"):
            if el.get("IdType") == "doi":
                doi = _txt(el)
                break
        if not doi and a is not None:
            for el in a.iter("ELocationID"):
                if el.get("EIdType") == "doi":
                    doi = _txt(el)
        out[pmid] = {"title": _txt(a.find("ArticleTitle")) if a is not None else "", "journal": _txt(a.find("Journal/Title")) if a is not None else "",
                     "issn": _txt(a.find("Journal/ISSN")) if a is not None else "", "years": years, "first_author": fa, "doi": norm_doi(doi),
                     "pubtypes": [_txt(x) for x in mc.iter("PublicationType")],
                     "corrections": [(c.get("RefType", ""), _txt(c.find("PMID"))) for c in mc.iter("CommentsCorrections")]}
    return out


def pubmed_flags(rec):
    """-> (status or None, [notes]). Retracted / EoC from PubMed publication types and CommentsCorrections (F-06)."""
    types = [t.lower() for t in rec["pubtypes"]]
    cc = [c[0] for c in rec["corrections"]]
    notes = []
    if "retracted publication" in types or "RetractionIn" in cc:
        return "RETRACTED", ["PubMed: Retracted Publication / RetractionIn"]
    if "expression of concern" in types or "ExpressionOfConcernIn" in cc:
        return "EOC", ["PubMed: Expression of Concern / ExpressionOfConcernIn"]
    if "retraction of publication" in types:
        return "RETRACTED", ["PubMed: este PMID es el AVISO de retractación (Retraction of Publication), no un artículo citable"]
    if "ErratumIn" in cc:
        notes.append("PubMed: existe una fe de erratas (ErratumIn); revisar si afecta a lo citado")
    return None, notes


def parse_crossref(msg):
    years = set()
    for k in ("issued", "published-print", "published-online", "published"):
        dp = (msg.get(k) or {}).get("date-parts") or [[None]]
        if dp and dp[0] and dp[0][0]:
            years.add(str(dp[0][0]))
    au = (msg.get("author") or [{}])[0]
    return {"title": (msg.get("title") or [""])[0], "journal": (msg.get("container-title") or [""])[0],
            "issn": [str(x).replace("-", "").upper() for x in (msg.get("ISSN") or [])], "years": years,
            "first_author": au.get("family") or au.get("name") or "", "type": msg.get("type", ""),
            "updated_by": [(u.get("type") or "").lower() for u in (msg.get("updated-by") or [])],
            "update_to": [(u.get("type") or "").lower() for u in (msg.get("update-to") or [])]}


def crossref_flags(info, updating_types):
    """info from parse_crossref; updating_types = types found via filter=updates:<doi>. -> (status|None, notes)"""
    kinds = set(info["updated_by"]) | set(updating_types)
    if kinds & RETRACT_TYPES:
        return "RETRACTED", ["Crossref/Retraction Watch: %s" % ", ".join(sorted(kinds & RETRACT_TYPES))]
    if kinds & EOC_TYPES:
        return "EOC", ["Crossref: expression of concern"]
    if set(info["update_to"]) & RETRACT_TYPES:
        return "RETRACTED", ["Crossref: este DOI es el AVISO de retractación, no un artículo citable"]
    other = sorted(k for k in kinds if k)
    return None, (["Crossref: actualizaciones registradas (%s)" % ", ".join(other)] if other else [])


def surname_matches(claimed, api_surname):
    """B6: tolerant to compound surnames («Bayramoglu Demirdogen», «Ozdemir Ayla»): equal after normalisation, or the claimed
    surname is one whole word of the API surname (>= 3 letters). A different surname still mismatches."""
    n_api = surname_norm(api_surname)
    cl = surname_norm(claimed_surname(claimed))
    if n_api and n_api in {cl, surname_norm(claimed)}:
        return True
    words = [surname_norm(w) for w in re.split(r"[\s\-]+", api_surname or "") if w]
    return len(cl) >= 3 and cl in words


def combine_source_problems(per_source):
    """B6: PubMed and Crossref sometimes disagree between themselves (author «Ll» in PubMed vs «Chen» in Crossref, title subtitles).
    A metadata problem is reported only if EVERY source that was compared shows it; one source alone -> returned as a note.
    per_source: [list of problem strings, ...] (one list per compared source). -> (problems, notes)"""
    per_source = [p for p in per_source if p is not None]
    if not per_source:
        return [], []
    cat = lambda s: s.split(" ")[0]
    common = set(cat(p) for p in per_source[0])
    for p in per_source[1:]:
        common &= set(cat(x) for x in p)
    probs, notes, seen = [], [], set()
    for lst in per_source:
        for p in lst:
            if p in seen:
                continue
            seen.add(p)
            (probs if cat(p) in common else notes).append(p if cat(p) in common else "solo una fuente discrepa: " + p)
    return probs, notes


def compare_meta(row, api):
    """-> (compared: bool, problems[], notes[]). row has claimed_*; api = {title, first_author, years, issn[], journal}."""
    probs, notes, compared = [], [], False
    ct, ca, cy = row.get("claimed_title", ""), row.get("claimed_first_author", ""), row.get("claimed_year", "")
    if ct:
        compared = True
        s = sim(ct, api["title"])
        if s < TITLE_SIM:
            probs.append("título no coincide (similitud %.2f < %.2f)" % (s, TITLE_SIM))
    if ca:
        compared = True
        if not surname_matches(ca, api["first_author"]):
            probs.append("primer autor no coincide («%s» vs «%s»)" % (ca, api["first_author"]))
    if cy:
        compared = True
        yy = re.sub(r"\D", "", cy)[:4]
        if yy not in api["years"]:
            near = [y for y in api["years"] if y.isdigit() and yy.isdigit() and abs(int(y) - int(yy)) == 1]
            if near:   # B6: online-first vs issue year (PubMed 2024 / Crossref 2025 for the same article) is not a wrong citation
                notes.append("año citado %s; la fuente da %s (±1: publicación online vs número impreso)" % (yy, "/".join(sorted(api["years"]))))
            else:
                probs.append("año no coincide («%s» vs %s)" % (cy, "/".join(sorted(api["years"])) or "?"))
    ci = (row.get("claimed_issn") or "").replace("-", "").upper()
    if ci:
        issns = api["issn"] if isinstance(api["issn"], list) else [str(api["issn"]).replace("-", "").upper()]
        if issns and ci not in issns:
            probs.append("ISSN no coincide")
    cj = row.get("claimed_journal", "")
    if cj and api.get("journal") and sim(cj, api["journal"]) < 0.5 and not ci:
        notes.append("la revista citada («%s») se parece poco a «%s» (¿abreviatura?)" % (cj, api["journal"]))
    return compared, probs, notes


def make_report_md(title, rows, extra_lines=None):
    """Spanish red/yellow/green report. rows: [{ref_id,status,detail,notes[]}]"""
    red = [r for r in rows if r["status"] in BLOCKING]
    green = [r for r in rows if r["status"] in ("VALID",)]
    yellow = [r for r in rows if r not in red and r not in green]
    L_ = ["# " + title, ""]
    L_ += extra_lines or []
    for name, grp, desc in (("ROJO - bloquea la entrega", red, "Hay que decidir/corregir cada una"),
                            ("AMARILLO - revisar", yellow, "No bloquea, pero Laura debe mirarlo"),
                            ("VERDE - verificadas por script", green, "Existen, metadatos coinciden, sin retractación")):
        L_ += ["## %s (%d)" % (name, len(grp)), "_%s_" % desc, ""]
        for r in grp:
            L_.append("- **%s** - %s: %s%s" % (r["ref_id"], r["status"], r.get("detail", ""), ("  [" + "; ".join(r["notes"]) + "]") if r.get("notes") else ""))
        L_.append("")
    L_ += ["El verificador solo informa: no corrige la lista. Cada decisión es de Laura (`verify_refs.py resolve` / `add-ref`).", ""]
    return "\n".join(L_)
