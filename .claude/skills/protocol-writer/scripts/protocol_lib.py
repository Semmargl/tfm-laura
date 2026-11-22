"""Shared logic of protocol-writer (C6): section table, draft markers, review state, digest, declaration loader."""
import hashlib
import math
import os
import re
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
if not os.path.isdir(os.path.join(_here, "_common")):      # dev layout
    sys.path.insert(1, os.path.dirname(os.path.dirname(_here)))
from _common import journal_io, paths  # noqa: E402

VERSION = "1.0"
DRAFTS = "06_protocolo/drafts"
VERSIONS = "06_protocolo/versions"
EXPORT = "06_protocolo/export"
MARKERS = ("draft-ai", "author-reviewed", "final")
PLACEHOLDER = "[PENDIENTE"
RESUMEN_MAX_LINES = 15
RESUMEN_CHARS_PER_LINE = 95        # heuristic for Times New Roman 12 pt on A4
DECL_TITLE = "Declaración de uso de inteligencia artificial"

# (id, title, heading level, PRISMA-P 2015 items covered, parent group)
SECTIONS = [
    ("resumen", "Resumen", 1, [], None),
    ("administrativo", "Información administrativa", 1, ["1a", "1b", "2", "3a", "3b", "4", "5a", "5b", "5c"], None),
    ("introduccion", "Introducción", 1, ["6"], None),
    ("objetivos", "Objetivos", 2, ["7"], "objmet"),
    ("met_elegibilidad", "Criterios de elegibilidad", 3, ["8"], "met"),
    ("met_fuentes", "Fuentes de información", 3, ["9"], "met"),
    ("met_busqueda", "Estrategia de búsqueda", 3, ["10"], "met"),
    ("met_seleccion", "Gestión de datos y selección de estudios", 3, ["11a", "11b"], "met"),
    ("met_extraccion", "Extracción de datos, variables y desenlaces", 3, ["11c", "12", "13"], "met"),
    ("met_sesgo", "Riesgo de sesgo", 3, ["14", "16"], "met"),
    ("met_sintesis", "Síntesis y certeza de la evidencia", 3, ["15a", "15b", "15c", "15d", "17"], "met"),
    ("resultados", "Resultados esperados", 1, [], None),
    ("conclusiones", "Conclusiones", 1, [], None),
    ("bibliografia", "Bibliografía", 1, [], None),
    ("anexo_a_busqueda", "Anexo A. Estrategias de búsqueda completas", 2, [], "anexos"),
]
SECTION_IDS = [s[0] for s in SECTIONS]
TITLES = {s[0]: s[1] for s in SECTIONS}
PRISMA_P_ITEMS = ["1a", "1b", "2", "3a", "3b", "4", "5a", "5b", "5c", "6", "7", "8", "9", "10", "11a", "11b", "11c", "12", "13",
                  "14", "15a", "15b", "15c", "15d", "16", "17"]
STYLES = ("vancouver", "apa", "harvard")
_MARK_RE = re.compile(r"^\[(draft-ai|author-reviewed|final)\]\s*\n", re.I)


def draft_rel(sid):
    return "%s/%s.md" % (DRAFTS, sid)


def split_marker(text):
    """-> (marker or None, body)."""
    m = _MARK_RE.match(text)
    if not m:
        return None, text.strip("\n")
    return m.group(1).lower(), text[m.end():].strip("\n")


def join_marker(marker, body):
    return "[%s]\n\n%s\n" % (marker, body.strip("\n"))


def body_sha(body):
    return hashlib.sha256(body.strip("\n").encode("utf-8")).hexdigest()


def read_draft(root, sid):
    p = paths.safe_join(root, draft_rel(sid))
    if not p.is_file():
        return None, None
    return split_marker(paths.read_text(p))


def drafts_digest(root):
    """sha256 over 'id:sha256(file)' of all SECTION_IDS drafts that exist (same algorithm in registration-finalizer)."""
    parts = []
    for sid in sorted(SECTION_IDS):
        p = paths.safe_join(root, draft_rel(sid))
        if p.is_file():
            parts.append("%s:%s" % (sid, paths.sha256_file(p)))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _kinds(root, rel):
    return [e for e in journal_io.find_for_path(root, rel)]


def review_state(root, sid):
    """-> {'marker','valid','reason'}; valid means the marker is backed by Laura's decision on the current text."""
    marker, body = read_draft(root, sid)
    if body is None:
        return {"marker": None, "valid": False, "reason": "falta"}
    if marker is None:
        return {"marker": None, "valid": False, "reason": "sin etiqueta [draft-ai]/[author-reviewed]/[final]"}
    if marker == "draft-ai":
        return {"marker": marker, "valid": True, "reason": ""}
    rel = draft_rel(sid)
    es = _kinds(root, rel)
    sha = body_sha(body)
    ok_rev = [e for e in es if e.get("kind") == "author_reviewed" and e.get("actor") == "laura" and e.get("body_sha256") == sha]
    if marker == "author-reviewed":
        last = es[-1] if es else {}
        if ok_rev and last.get("kind") in ("author_reviewed", "section_final") and last.get("body_sha256") == sha:
            return {"marker": marker, "valid": True, "reason": ""}
        return {"marker": marker, "valid": False, "reason": "etiqueta sin decisión de Laura sobre el texto actual"}
    ok_fin = [e for e in es if e.get("kind") == "section_final" and e.get("actor") == "laura" and e.get("body_sha256") == sha]
    if ok_rev and ok_fin:
        return {"marker": marker, "valid": True, "reason": ""}
    return {"marker": marker, "valid": False, "reason": "[final] sin revisión de la autora y decisión de Laura sobre el texto actual"}


def resumen_lines(body):
    return sum(max(1, math.ceil(len(p.strip()) / float(RESUMEN_CHARS_PER_LINE))) for p in body.split("\n") if p.strip())


def load_declaration():
    """declaration.py belongs to tfm-orchestrator (sibling skill). Returns the module or None."""
    try:
        import declaration  # noqa
        return declaration
    except ImportError:
        pass
    sib = os.path.join(os.path.dirname(os.path.dirname(_here)), "tfm-orchestrator", "scripts")
    if os.path.isdir(sib):
        sys.path.append(sib)
        try:
            import declaration  # noqa
            return declaration
        except ImportError:
            return None
    return None


def template_blocks():
    p = os.path.join(os.path.dirname(_here), "templates", "protocol_skeleton_es.md")
    with open(p, encoding="utf-8") as f:
        text = f.read().replace("\r\n", "\n")
    blocks, cur, buf = {}, None, []
    for line in text.split("\n"):
        m = re.match(r"^<!-- section: (\w+) -->$", line.strip())
        if m:
            if cur:
                blocks[cur] = "\n".join(buf).strip("\n")
            cur, buf = m.group(1), []
        elif cur:
            buf.append(line)
    if cur:
        blocks[cur] = "\n".join(buf).strip("\n")
    return blocks
