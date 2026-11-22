#!/usr/bin/env python3
"""check_claims.py - literal check of every tagged number / quote against a LEGITIMATE saved source (Q7-4, F-04).

  check_claims.py run [--drafts-dir 06_protocolo/drafts | --file 06_protocolo/drafts/justificacion.md]

Tag syntax in the draft:  «... 45% de las mujeres ...» [ref:R3|abstract]   (R3 = ref_id in references.csv; loc = abstract | fulltext | p.4 |
file:raw/exports/<text of the paper uploaded by Laura>).  Laura's own protocol parameters carry [propio] instead.

SOURCE RULE (F-04): the text compared against comes ONLY from (a) raw/api/*.json written by http_client (envelope valid, actor script) or
(b) a file Laura uploaded to raw/exports/ (registered with sha256, actor laura, valid shape). Anything else - in particular text written by
Claude, drafts, notes - is refused: the claim becomes NO_SOURCE (blocker). Per-record extraction: a batch efetch only counts the article
with the matching PMID.  PDFs are read only if `pdftotext` exists; otherwise upload the text.
Per claim: every number (percentages, decimals, counts; plain years are ignored) and every quoted passage must appear in the source.
A miss = MISMATCH (blocker). Untagged quotes (>= 4 words) and untagged statistics (%, p, n=, CI, OR/RR/HR/MD/SMD, «N participantes/estudios») = blockers.
Whether the source SUPPORTS the sentence is NOT decided here: advisory by Claude (verbatim quotes of both sides, VALID/ADJUST/INVALID/UNVERIFIABLE).
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_lib as V  # noqa: E402
from _common import journal_io, paths  # noqa: E402

SCRIPT = "check_claims.py"
TAG = re.compile(r"\[ref:([^|\]\s]+)\|([^\]]+)\]")
OWN = re.compile(r"\[propio\]", re.I)
QUOTE = re.compile(r"«([^»]+)»|“([^”]+)”|\"([^\"]+)\"")
NUM = re.compile(r"(?<![\w.,])(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)(?![\w])")
STAT = re.compile(r"(\d+(?:[.,]\d+)?\s*%|\bp\s*[<=>≤≥]\s*\d|\bn\s*=\s*\d|\b(?:IC|CI)\s*(?:del\s*)?95|\b(?:OR|RR|HR|MD|SMD|DME)\b\s*[=:]?\s*\d|"
                  r"\b\d[\d.,]*\s+(?:participantes|pacientes|mujeres|hombres|sujetos|estudios|ensayos|ECA|artículos|adultos|niños))", re.I)


def strip_tags(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _walk_json(o, pmid, doi, out):
    if isinstance(o, dict):
        if (pmid and str(o.get("pmid", o.get("uid", ""))) == pmid) or (doi and V.norm_doi(str(o.get("doi", ""))) == doi):
            out.append(" ".join(str(v) for v in _flat(o)))
        for v in o.values():
            _walk_json(v, pmid, doi, out)
    elif isinstance(o, list):
        for v in o:
            _walk_json(v, pmid, doi, out)


def _flat(o):
    if isinstance(o, dict):
        for v in o.values():
            for x in _flat(v):
                yield x
    elif isinstance(o, list):
        for v in o:
            for x in _flat(v):
                yield x
    elif isinstance(o, str):
        yield o


def article_text(body, pmid, doi):
    """Text of ONLY the record for this pmid/doi inside a saved response/export body. None if it is not there."""
    b = body.lstrip()
    if b.startswith("<"):
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            root = None
        if root is not None:
            arts = list(root.iter("PubmedArticle"))
            if arts:
                for a in arts:
                    p = (a.findtext("MedlineCitation/PMID") or "").strip()
                    d = ""
                    for el in a.findall("PubmedData/ArticleIdList/ArticleId"):   # B6: not the ReferenceList DOIs
                        if el.get("IdType") == "doi":
                            d = V.norm_doi("".join(el.itertext()))
                            break
                    if (pmid and p == pmid) or (doi and d == doi):
                        return strip_tags(ET.tostring(a, encoding="unicode"))
                return None
            txt = strip_tags(body)
            return txt if (V.has_pmid(body, pmid) or V.has_doi(body, doi)) else None
    if b[:1] in "{[":
        try:
            data = json.loads(body)
        except ValueError:
            data = None
        if data is not None:
            found = []
            _walk_json(data, pmid, doi, found)
            return strip_tags(" ".join(found)) if found else None
    # plain exports: nbib / RIS / CSV / txt
    blocks = re.split(r"\n\s*\n|(?m:^ER  -.*$)", body)
    for blk in blocks:
        if V.has_pmid(blk, pmid) or V.has_doi(blk, doi):
            return strip_tags(blk)
    return None


def load_source_text(root, rel, pmid, doi, whole=False):
    full = paths.safe_join(root, rel)
    if rel.startswith("raw/api/"):
        body = json.loads(paths.read_text(full))["body"]
    elif rel.lower().endswith(".pdf"):
        exe = shutil.which("pdftotext")
        if not exe:
            return None
        body = subprocess.run([exe, "-q", str(full), "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        return strip_tags(body)
    else:
        body = V.integrity_core._text(str(full))
    return strip_tags(body) if whole else article_text(body, pmid, doi)


def find_sources(root, ref, loc, ctx):
    """-> ([(rel, text)], reasons[]). Only legitimate raw sources; explicit `file:` loc limits the search to that file."""
    cands, reasons, out = [], [], []
    explicit = loc.startswith("file:")
    if explicit:
        cands = [loc[5:].strip()]
    else:
        e = ctx["entries"].get(ref.get("source_journal_id", ""))
        for o in ((e or {}).get("outputs") or []) + ((e or {}).get("inputs") or []):
            if str(o.get("path", "")).startswith(("raw/api/", "raw/exports/")):
                cands.append(o["path"])
        for rel in sorted(ctx["reg"]):
            if rel.startswith(("raw/api/", "raw/exports/")) and rel not in cands:
                cands.append(rel)
    for rel in cands:
        ok, why = V.source_legit(root, rel, ctx["reg"])
        if not ok:
            if explicit or rel in cands[:3]:
                reasons.append("%s: %s" % (rel, why))
            continue
        if ctx["blockers"].get(rel):
            reasons.append("%s: bloqueo de integridad %s" % (rel, ctx["blockers"][rel]))
            continue
        txt = load_source_text(root, rel, ref.get("pmid", ""), ref.get("doi", ""), whole=explicit)
        if txt:
            out.append((rel, txt))
        elif explicit:
            reasons.append("%s: no se pudo leer texto (¿PDF sin pdftotext? sube el texto del artículo)" % rel)
    return out, reasons


def to_floats(token):
    t = token.replace(" ", "")
    vals = set()
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", t):
        vals.add(float(re.sub(r"[.,]", "", t)))               # thousands separators
    try:
        vals.add(float(t.replace(",", ".")))
    except ValueError:
        pass
    return vals


def norm_for_match(s):
    s = html.unescape(s).lower()
    s = re.sub(r"[‘’´`]", "'", s)
    s = re.sub(r"[–—‑−]", "-", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .,;:")


def check_one(claim, source_text):
    """-> (problems[], n_numbers, n_quotes)"""
    probs = []
    src = norm_for_match(source_text)
    src_nums = set()
    for m in NUM.finditer(source_text):
        src_nums |= to_floats(m.group(1))
    quotes = [next(g for g in m.groups() if g) for m in QUOTE.finditer(claim)]
    for q in quotes:
        if norm_for_match(q) not in src:
            probs.append("la cita «%s» no aparece literalmente en la fuente" % q[:80])
    body = QUOTE.sub(" ", claim)
    nums = []
    for m in NUM.finditer(body):
        tok = m.group(1)
        vals = to_floats(tok)
        if re.fullmatch(r"(19|20)\d\d", tok) and not re.search(r"%", body[m.end():m.end() + 2]):
            continue                                             # plain years are not statistics
        nums.append(tok)
        if not (vals & src_nums):
            probs.append("el número %s no aparece en la fuente" % tok)
    return probs, len(nums), len(quotes)


def scan_file(root, rel, refs, ctx):
    text = paths.read_text(paths.safe_join(root, rel))
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        text = text[end + 4:] if end > 0 else text
    items, untagged = [], []
    in_code = False
    for ln_no, ln in enumerate(text.split("\n"), 1):
        if ln.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or ln.lstrip().startswith("#") or not ln.strip():
            continue
        pos = 0
        for m in TAG.finditer(ln):
            seg = ln[pos:m.start()]
            seg = re.split(r"(?<=[.!?])\s+", seg.strip())[-1] if seg.strip() else ""
            pos = m.end()
            items.append({"file": rel, "line": ln_no, "ref_id": m.group(1), "loc": m.group(2).strip(), "claim": seg.strip()})
        rest = ln[pos:] if pos else ln
        for sentence in re.split(r"(?<=[.!?])\s+", rest):
            if TAG.search(sentence) or OWN.search(sentence):
                continue
            for q in QUOTE.finditer(sentence):
                qq = next(g for g in q.groups() if g)
                if len(qq.split()) >= 4:
                    untagged.append({"file": rel, "line": ln_no, "kind": "cita sin etiqueta", "text": qq[:100]})
            if STAT.search(sentence):
                untagged.append({"file": rel, "line": ln_no, "kind": "dato estadístico sin etiqueta [ref:id|loc] ni [propio]", "text": sentence.strip()[:120]})
    return items, untagged


def run(root, files=None, journal=True):
    V.need_mode(root, network=False)
    refs = {r["ref_id"]: r for r in V.load_refs(root)}
    ctx = V.context(root)
    d = paths.Paths(root).root / "06_protocolo" / "drafts"
    targets = list(files) if files else (sorted(paths.rel(root, p) for p in d.glob("*.md")) if d.is_dir() else [])
    all_items, all_untagged = [], []
    for rel in targets:
        it, un = scan_file(root, rel, refs, ctx)
        all_items += it
        all_untagged += un
    results, used = [], {}
    for it in all_items:
        ref = refs.get(it["ref_id"])
        r = dict(it, status=None, problems=[], source=None)
        if not ref:
            r["status"], r["problems"] = "UNKNOWN_REF", ["%s no está en references.csv" % it["ref_id"]]
        else:
            srcs, why = find_sources(root, ref, it["loc"], ctx)
            if not srcs:
                r["status"], r["problems"] = "NO_SOURCE", ["no hay una fuente legítima en raw/ (api de script o archivo de Laura registrado)"] + why[:3]
            else:
                best = None
                for rel, txt in srcs:
                    probs, nn, nq = check_one(it["claim"], txt)
                    if best is None or len(probs) < len(best[0]):
                        best = (probs, nn, nq, rel)
                    if not probs:
                        break
                probs, nn, nq, rel = best
                r["source"] = {"path": rel, "sha256": ctx["reg"][rel]["sha256"]}
                used[rel] = ctx["reg"][rel]["sha256"]
                r["n_numbers"], r["n_quotes"] = nn, nq
                if probs:
                    r["status"], r["problems"] = "MISMATCH", probs
                elif nn + nq == 0:
                    r["status"] = "SEMANTIC_ONLY"
                    r["problems"] = ["sin números ni citas literales: solo se puede valorar el sentido (advisory de Claude)"]
                else:
                    r["status"] = "MATCH"
        results.append(r)
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    bad = [r for r in results if r["status"] in ("MISMATCH", "NO_SOURCE", "UNKNOWN_REF")]
    ok = not bad and not all_untagged
    out = {"ok": ok, "claims": len(results), "counts": counts, "untagged": all_untagged, "blocking": len(bad) + len(all_untagged), "results": results,
           "message_es": "%d afirmaciones etiquetadas: %s; sin etiqueta: %d" % (len(results), ", ".join("%s=%d" % kv for kv in sorted(counts.items())) or "ninguna", len(all_untagged))}
    if journal:
        ts = V.stamp()
        md_rel = V.unique_rel(root, "%s/afirmaciones_%s_es.md" % (V.REPORTS, ts))
        lines = ["# Verificación literal de números y citas", "", out["message_es"], ""]
        for r in results:
            if r["status"] in ("MISMATCH", "NO_SOURCE", "UNKNOWN_REF"):
                lines.append("- ROJO %s:%d [ref:%s|%s] %s - %s" % (r["file"], r["line"], r["ref_id"], r["loc"], r["status"], "; ".join(r["problems"])))
        for u in all_untagged:
            lines.append("- ROJO %s:%d %s: %s" % (u["file"], u["line"], u["kind"], u["text"]))
        for r in results:
            if r["status"] == "SEMANTIC_ONLY":
                lines.append("- AMARILLO %s:%d [ref:%s] solo valoración de sentido (advisory)" % (r["file"], r["line"], r["ref_id"]))
        lines += ["", "Esto no juzga si la fuente respalda la frase: eso es advisory de Claude y decisión de Laura.", ""]
        paths.write_text_atomic(paths.safe_join(root, md_rel), "\n".join(lines))
        ref_ = journal_io.make_script_report(root, SCRIPT, V.unique_rel(root, "%s/claims_%s.json" % (V.REPORTS, ts)), "pass" if ok else "fail",
                                             details={"counts": counts, "untagged": all_untagged, "results": results, "sources": used, "report_es": md_rel}, version=V.VERSION)
        e = journal_io.add(root, {"stage": "C7", "type": "verification", "actor": "script", "tool": V.tool(SCRIPT), "gate_name": "G-C7-claims",
                                  "gate": "pass" if ok else "fail", "script_report": ref_, "human_decision": "n/a",
                                  "how_verified": "coincidencia literal contra fuentes de raw/ (api de script o archivo de Laura)", "what_es": out["message_es"],
                                  "outputs": [journal_io.file_ref(root, md_rel)], "inputs": [{"path": k, "sha256": v} for k, v in sorted(used.items())][:50] or None})
        out["journal_id"], out["script_report"], out["report_es"] = e["id"], ref_, md_rel
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("cmd", nargs="?", default="run", choices=["run"])
    ap.add_argument("--file", action="append")
    a = ap.parse_args(argv)

    def go():
        root = V.open_project(a.root)
        res = run(root, a.file)
        return res, (0 if res["ok"] else 1)
    return V.finish(go)


if __name__ == "__main__":
    sys.exit(main())
