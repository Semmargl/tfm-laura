#!/usr/bin/env python3
"""ref_style.py - format the VERIFIED references in the chosen style (Q7-8): vancouver (default, provisional until the guía docente) | apa | harvard.

  ref_style.py format [--style vancouver|apa|harvard]

Metadata comes ONLY from legitimate saved API responses (raw/api: PubMed efetch XML / Crossref JSON) of references whose latest verify_refs
status is VALID; nothing is typed from memory. Output: 07_verificacion/reports/referencias_<style>_<ts>_es.md. Changing the style = changing
the parameter (config/project.yaml: citation_style). Fields missing in the source are shown as «[falta ...]», never invented.
"""
import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_lib as V  # noqa: E402
from _common import config, journal_io, paths  # noqa: E402

SCRIPT = "ref_style.py"


def _t(el):
    return "".join(el.itertext()).strip() if el is not None else ""


def meta_from_pubmed(art):
    mc = art.find("MedlineCitation")
    a = mc.find("Article")
    authors = []
    for au in a.findall("AuthorList/Author"):
        authors.append({"family": _t(au.find("LastName")) or _t(au.find("CollectiveName")), "initials": _t(au.find("Initials")), "given": _t(au.find("ForeName"))})
    ji = a.find("Journal/JournalIssue")
    doi = ""
    for el in art.findall("PubmedData/ArticleIdList/ArticleId"):   # B6: not the ReferenceList DOIs
        if el.get("IdType") == "doi":
            doi = _t(el)
            break
    if not doi:
        for el in a.iter("ELocationID"):
            if el.get("EIdType") == "doi":
                doi = _t(el)
                break
    return {"authors": authors, "title": _t(a.find("ArticleTitle")).rstrip("."), "journal": _t(mc.find("MedlineJournalInfo/MedlineTA")) or _t(a.find("Journal/Title")),
            "journal_full": _t(a.find("Journal/Title")), "year": _t(ji.find("PubDate/Year")) or _t(ji.find("PubDate/MedlineDate"))[:4], "volume": _t(ji.find("Volume")),
            "issue": _t(ji.find("Issue")), "pages": _t(a.find("Pagination/MedlinePgn")), "doi": doi}


def meta_from_crossref(msg):
    au = [{"family": x.get("family") or x.get("name", ""), "initials": "".join(p[0] for p in (x.get("given") or "").replace("-", " ").split() if p), "given": x.get("given", "")}
          for x in msg.get("author") or []]
    dp = ((msg.get("issued") or {}).get("date-parts") or [[""]])[0]
    return {"authors": au, "title": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", (msg.get("title") or [""])[0])).rstrip("."),
            "journal": (msg.get("short-container-title") or msg.get("container-title") or [""])[0], "journal_full": (msg.get("container-title") or [""])[0],
            "year": str(dp[0]) if dp and dp[0] else "", "volume": msg.get("volume", ""), "issue": msg.get("issue", ""), "pages": msg.get("page", ""), "doi": msg.get("DOI", "")}


def find_meta(root, row, ctx):
    for rel in sorted(ctx["reg"]):
        if not rel.startswith("raw/api/"):
            continue
        ok, _ = V.source_legit(root, rel, ctx["reg"])
        if not ok:
            continue
        body = json.loads(paths.read_text(paths.safe_join(root, rel)))["body"]
        if body.lstrip().startswith("<") and row["pmid"]:
            try:
                for art in ET.fromstring(body).iter("PubmedArticle"):
                    if _t(art.find("MedlineCitation/PMID")) == row["pmid"]:
                        return meta_from_pubmed(art)
            except ET.ParseError:
                continue
        elif body.lstrip().startswith("{") and row["doi"] and ("/works/" + row["doi"]) in json.loads(paths.read_text(paths.safe_join(root, rel)))["_meta"]["url"].lower():
            try:
                return meta_from_crossref(json.loads(body).get("message") or {})
            except ValueError:
                continue
    return None


def _miss(v, what):
    return v if v else "[falta %s]" % what


def fmt(style, m):
    au = m["authors"]
    if style == "vancouver":
        names = ["%s %s" % (a["family"], a["initials"]) for a in au[:6]]
        s = ", ".join(names) + (", et al" if len(au) > 6 else "")
        vol = m["volume"] + (("(%s)" % m["issue"]) if m["issue"] else "")
        tail = ";".join(x for x in (_miss(m["year"], "año") + (";" + vol if vol else ""),) if x) + (":" + m["pages"] if m["pages"] else "")
        return "%s. %s. %s. %s.%s" % (_miss(s, "autores"), _miss(m["title"], "título"), _miss(m["journal"], "revista"), tail, (" doi:" + m["doi"]) if m["doi"] else "")
    if style == "apa":
        names = ["%s, %s" % (a["family"], ". ".join(list(a["initials"])) + ".") if a["initials"] else a["family"] for a in au[:20]]
        s = (", ".join(names[:-1]) + ", & " + names[-1]) if len(names) > 1 else (names[0] if names else "")
        vol = m["volume"] + (("(%s)" % m["issue"]) if m["issue"] else "")
        return "%s (%s). %s. %s%s%s.%s" % (_miss(s, "autores"), _miss(m["year"], "año"), _miss(m["title"], "título"), _miss(m["journal_full"], "revista"),
                                         (", " + vol) if vol else "", (", " + m["pages"]) if m["pages"] else "", (" https://doi.org/" + m["doi"]) if m["doi"] else "")
    if style == "harvard":
        names = ["%s, %s" % (a["family"], ".".join(list(a["initials"])) + ".") if a["initials"] else a["family"] for a in au[:3]]
        s = " and ".join([", ".join(names[:-1]), names[-1]]) if len(names) > 1 else (names[0] if names else "")
        s += " et al." if len(au) > 3 else ""
        return "%s (%s) '%s', %s%s%s.%s" % (_miss(s, "autores"), _miss(m["year"], "año"), _miss(m["title"], "título"), _miss(m["journal_full"], "revista"),
                                           (", " + m["volume"] + (("(%s)" % m["issue"]) if m["issue"] else "")) if m["volume"] else "",
                                           (", pp. " + m["pages"]) if m["pages"] else "", (" doi:" + m["doi"]) if m["doi"] else "")
    raise V.Refusal("BAD_STYLE", "Estilo no soportado: %s (vancouver | apa | harvard)." % style)


def run(root, style=None, journal=True):
    V.need_mode(root, network=False)
    style = (style or config.load_config(root).get("citation_style") or "vancouver").lower()
    ver = [e for e in journal_io.query(root, type="verification") if e.get("gate_name") == "G-C7-refs"]
    if not ver:
        raise V.Refusal("NOT_VERIFIED", "Aún no hay verify_refs.py completo (modo FULL): solo se formatean referencias VALID.")
    rep = json.loads(paths.read_text(paths.safe_join(root, ver[-1]["script_report"]["path"])))
    valid = {i["ref_id"] for i in rep["details"]["items"] if i["status"] == "VALID"}
    rows = [r for r in V.load_refs(root) if r["ref_id"] in valid]
    ctx = V.context(root)
    lines, missing = [], []
    for r in rows:
        m = find_meta(root, r, ctx)
        if not m:
            missing.append(r["ref_id"])
            continue
        lines.append((r["ref_id"], fmt(style, m)))
    out = ["# Referencias (%s) - %s" % (style, "provisional hasta recibir la guía docente" if config.load_config(root).get("citation_style_status") == "provisional" else "estilo confirmado"), ""]
    out += ["%d. %s  _(%s)_" % (i, t, rid) for i, (rid, t) in enumerate(lines, 1)]
    if missing:
        out += ["", "Sin metadatos legibles en raw/api (no se inventan): " + ", ".join(missing)]
    rel = V.unique_rel(root, "%s/referencias_%s_%s_es.md" % (V.REPORTS, style, V.stamp()))
    paths.write_text_atomic(paths.safe_join(root, rel), "\n".join(out) + "\n")
    res = {"ok": not missing, "style": style, "formatted": len(lines), "missing_metadata": missing, "path": rel}
    if journal:
        e = journal_io.add(root, {"stage": "C7", "type": "change", "actor": "script", "kind": "ref_style", "tool": V.tool(SCRIPT), "human_decision": "n/a",
                                  "what_es": "Referencias en estilo %s: %d formateadas, %d sin metadatos" % (style, len(lines), len(missing)),
                                  "outputs": [journal_io.file_ref(root, rel)]})
        res["journal_id"] = e["id"]
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("cmd", nargs="?", default="format", choices=["format"])
    ap.add_argument("--style")
    a = ap.parse_args(argv)

    def go():
        r = run(V.open_project(a.root), a.style)
        return r, (0 if r["ok"] else 1)
    return V.finish(go)


if __name__ == "__main__":
    sys.exit(main())
