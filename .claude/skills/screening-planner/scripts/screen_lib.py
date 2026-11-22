"""screening-planner shared helpers (C4): parsers for RIS / nbib / CSV exports, normalisers, CLI plumbing. Stdlib only."""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import config, http_client, integrity_core, journal_io, modes, paths, rawstore  # noqa: E402

VERSION = "1.0"
STAGE = "C4"
WATERMARK = "PRELIMINAR — piloto, no forma parte del protocolo"
REC_COLS = ["rec_id", "source_file", "source_sha256", "db", "pmid", "doi", "title", "norm_title", "first_author", "year", "journal", "abstract"]
DEDUP_COLS = REC_COLS + ["duplicate_of", "dup_reason"]
EXCLUSION_REASONS = ["poblacion", "intervencion", "comparador", "resultado", "diseno_estudio", "tipo_publicacion", "idioma", "duplicado", "no_recuperable"]
DECISIONS = ["incluir", "excluir", "dudoso"]


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


def open_project(root_arg):
    return paths.find_root(root_arg)


def finish(fn):
    try:
        obj, code = fn()
    except Refusal as e:
        emit({"ok": False, "refused": e.code, "message_es": e.msg_es})
        return e.exit_code
    except paths.ProjectNotFound as e:
        emit({"ok": False, "error": str(e)})
        return 2
    except journal_io.JournalError as e:
        emit({"ok": False, "journal_errors": e.errors})
        return 1
    emit(obj)
    return code


def need_scripts(root):
    mode = config.get_mode(root)
    if not modes.can_run(mode, needs_network=False):
        raise Refusal("MODE_NOT_ALLOWED", "Modo actual %s: no hay scripts. En LITE-b/LITE-P haz el duplicado en Rayyan/TERA Deduplicator y anota los números a mano." % mode, 4)
    return mode


def unique_rel(root, rel):
    base, ext = os.path.splitext(rel)
    cand, n = rel, 1
    while paths.safe_join(root, cand).exists():
        n += 1
        cand = "%s_%d%s" % (base, n, ext)
    return cand


# ---------------------------------------------------------------------------------------------- normalisers
def norm_doi(d):
    d = (d or "").strip().lower()
    d = re.sub(r"^(doi:\s*|https?://(dx\.)?doi\.org/)", "", d)
    return d.rstrip(".;, ")


def norm_pmid(p):
    p = re.sub(r"\D", "", p or "")
    return p.lstrip("0") if p else ""


def norm_title(t):
    t = unicodedata.normalize("NFKD", t or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return re.sub(r"^(the|a|an|el|la|los|las) ", "", t)


def surname(first_author):
    a = (first_author or "").strip()
    if not a:
        return ""
    had_comma = "," in a
    a = a.split(",")[0].strip()
    if re.match(r"^[^\W\d_][\w'\-]* [A-Z]{1,3}$", a, re.U):          # «Perez A» (PubMed style)
        s = a.split(" ")[0]
    elif had_comma:                                                  # «Perez, Ana» / «van der Berg, J»
        s = a
    else:                                                            # «Ana Perez»
        s = a.split(" ")[-1]
    s = unicodedata.normalize("NFKD", s)
    return re.sub(r"[^a-z]", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


def year_of(s):
    m = re.search(r"(1[89]\d\d|20\d\d)", s or "")
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------------------------- parsers
def _text(path):
    return integrity_core._text(str(path))


def parse_ris(text):
    recs, cur, last = [], None, None
    for ln in text.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^([A-Z][A-Z0-9])  - ?(.*)$", ln)
        if m:
            tag, val = m.group(1), m.group(2).strip()
            if tag == "TY":
                cur, last = {}, None
                recs.append(cur)
                continue
            if tag == "ER":
                cur, last = None, None
                continue
            if cur is None:
                continue
            cur.setdefault(tag, []).append(val)
            last = tag
        elif ln.startswith("PMID- ") and cur is not None:
            cur.setdefault("PMID", []).append(ln[6:].strip())
        elif ln.strip() and cur is not None and last:
            cur[last][-1] += " " + ln.strip()
    out = []
    for r in recs:
        pm = ""
        for tag in ("PMID", "AN", "ID"):
            for v in r.get(tag, []):
                if re.fullmatch(r"\d{5,9}", v):
                    pm = v
                    break
            if pm:
                break
        urls = " ".join(r.get("UR", []) + r.get("L2", []))
        if not pm:
            m = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", urls)
            pm = m.group(1) if m else ""
        doi = ""
        for v in r.get("DO", []) + r.get("M3", []) + r.get("UR", []) + r.get("L2", []):
            m = re.search(r"10\.\d{4,9}/\S+", v)
            if m:
                doi = m.group(0)
                break
        au = (r.get("AU") or r.get("A1") or [""])[0]
        out.append({"pmid": pm, "doi": doi, "title": (r.get("TI") or r.get("T1") or [""])[0], "first_author": au,
                    "year": year_of((r.get("PY") or r.get("Y1") or r.get("DA") or [""])[0]),
                    "journal": (r.get("JO") or r.get("JF") or r.get("T2") or r.get("JA") or [""])[0],
                    "abstract": (r.get("AB") or r.get("N2") or [""])[0]})
    return out


def parse_nbib(text):
    out = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        if not re.search(r"(?m)^PMID- ", block):
            continue
        f, last = {}, None
        for ln in block.split("\n"):
            m = re.match(r"^([A-Z]{2,4})\s*- (.*)$", ln)
            if m:
                last = m.group(1)
                f.setdefault(last, []).append(m.group(2).strip())
            elif ln.startswith("      ") and last:
                f[last][-1] += " " + ln.strip()
        doi = ""
        for v in f.get("LID", []) + f.get("AID", []):
            m = re.match(r"(10\.\S+)\s*\[doi\]", v)
            if m:
                doi = m.group(1)
                break
        out.append({"pmid": (f.get("PMID") or [""])[0], "doi": doi, "title": (f.get("TI") or [""])[0],
                    "first_author": (f.get("AU") or f.get("FAU") or [""])[0], "year": year_of((f.get("DP") or [""])[0]),
                    "journal": (f.get("JT") or f.get("TA") or [""])[0], "abstract": (f.get("AB") or [""])[0]})
    return out


CSV_MAP = {"title": ("title", "titulo", "título", "article title", "ti"), "doi": ("doi", "digital object identifier"),
           "pmid": ("pmid", "pubmed id", "pubmedid", "pubmed_id"), "first_author": ("authors", "author", "autores", "autor", "first author", "au"),
           "year": ("year", "año", "anio", "publication year", "py", "date", "publication date"),
           "journal": ("journal", "source", "revista", "fuente", "journal/book", "source title"), "abstract": ("abstract", "resumen", "ab")}


def parse_csv(text):
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        return []
    hdr = [h.strip().lower() for h in rows[0]]
    idx = {}
    for k, names in CSV_MAP.items():
        for i, h in enumerate(hdr):
            if h in names and k not in idx:
                idx[k] = i
    out = []
    for r in rows[1:]:
        if not any(c.strip() for c in r):
            continue
        g = lambda k: r[idx[k]].strip() if k in idx and idx[k] < len(r) else ""   # noqa: E731
        au = re.split(r";|\s+and\s+", g("first_author"))[0].strip()
        out.append({"pmid": g("pmid"), "doi": g("doi"), "title": g("title"), "first_author": au, "year": year_of(g("year")),
                    "journal": g("journal"), "abstract": g("abstract")})
    return out


PARSERS = {".ris": parse_ris, ".nbib": parse_nbib, ".medline": parse_nbib, ".csv": parse_csv}
KNOWN_DB = re.compile(r"^([a-z0-9]+(?:_[a-z0-9]+)*?)_\d{4}-\d{2}-\d{2}_v\d+")


def db_of(filename):
    m = KNOWN_DB.match(filename.lower())
    return m.group(1) if m else "desconocida"


def export_ok(root, rel):
    """(ok, reason) - source must be registered with actor laura, hash intact, real export shape."""
    full = paths.safe_join(root, rel)
    reg = rawstore.load(root)["files"].get(rel)
    if not reg:
        return False, "no registrado (integrity.py register-export)"
    if reg["sha256"] != paths.sha256_file(full):
        return False, "el hash cambió después del registro"
    if reg.get("actor") != "laura":
        return False, "no fue registrado por Laura"
    ok, kind, why = integrity_core.shape_check_export(full)
    return (True, kind) if ok else (False, "forma inválida: " + why)


def build_record(rel, sha, db, idx, raw):
    t = (raw.get("title") or "").strip()
    return {"rec_id": "%s#%d" % (os.path.splitext(os.path.basename(rel))[0], idx), "source_file": rel, "source_sha256": sha, "db": db,
            "pmid": norm_pmid(raw.get("pmid")), "doi": norm_doi(raw.get("doi")), "title": t, "norm_title": norm_title(t),
            "first_author": (raw.get("first_author") or "").strip(), "year": year_of(raw.get("year")), "journal": (raw.get("journal") or "").strip(),
            "abstract": (raw.get("abstract") or "").strip()}


def write_csv(root, rel, cols, rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    paths.write_text_atomic(paths.safe_join(root, rel), buf.getvalue())


def read_csv(root, rel):
    return list(csv.DictReader(io.StringIO(paths.read_text(paths.safe_join(root, rel)))))


def latest(root, prefix):
    """Latest 04_seleccion/dedup/<prefix>_v<N>*.csv by (N, name)."""
    d = paths.Paths(root).root / "04_seleccion" / "dedup"
    best = None
    for f in d.glob(prefix + "_v*.csv") if d.is_dir() else []:
        m = re.search(r"_v(\d+)(?:_(\d+))?\.csv$", f.name)
        if m:
            k = (int(m.group(1)), int(m.group(2) or 1))
            if best is None or k > best[0]:
                best = (k, f)
    return paths.rel(root, best[1]) if best else None
