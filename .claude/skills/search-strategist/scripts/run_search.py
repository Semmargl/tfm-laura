#!/usr/bin/env python3
"""run_search.py - run a search string against a database and LOG how the database parsed it (F-05, W-3).

  run_search.py run --db pubmed --string-file 03_busqueda/strings/pubmed_v1.txt [--limits "..."] [--refresh] [--lint-only] [--confirmed]
  run_search.py record-details --db pubmed --string-file ... --count N --translation "..." [--error "..."] [--warning "..."]
                  (LITE: Laura copies «Search details» from pubmed.gov; entry actor = laura)

pubmed: esearch -> QueryTranslation / ErrorList / WarningList, every [mh] term checked against db=mesh. ANY Error = blocker
(gate fail). Repeat within 1 hour (or same day) is served from raw/api cache; a fresh repeat is compared with the cached
count and the daily difference goes into the journal (W-3). Supplementary DBs (europepmc, openalex) and clinicaltrials_gov
only log a count. Manual DBs (CENTRAL, PEDro, LILACS, WHO ICTRP): use prisma_s_log.py record.
Journal: type query_check (+ type count when there is no Error). gate=pass only through a tfm-report/v1 script report.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_lib as L  # noqa: E402
from _common import config, http_client, journal_io, paths  # noqa: E402

SCRIPT = "run_search.py"
SUPPLEMENTARY = {"europepmc": "Europe PMC (REST)", "openalex": "OpenAlex (API)", "clinicaltrials_gov": "ClinicalTrials.gov (API v2)"}


def _count_other(client, db, query, cache="day", max_age_s=3600):
    if db == "europepmc":
        r = client.get(L.EPMC, {"query": query, "format": "json", "pageSize": 1, "resultType": "lite"}, cache=cache, max_age_s=max_age_s)
        return int(r.json().get("hitCount")), r
    if db == "openalex":
        r = client.get(L.OPENALEX, {"search": query, "per-page": 1}, cache=cache, max_age_s=max_age_s)
        return int(r.json()["meta"]["count"]), r
    r = client.get(L.CTGOV, {"query.term": query, "pageSize": 1, "countTotal": "true"}, cache=cache, max_age_s=max_age_s)
    return int(r.json()["totalCount"]), r


def _entry_inputs(root, rel):
    return [journal_io.file_ref(root, rel)]


def run(root, db, string_rel, limits="", refresh=False, lint_only=False, client=None, journal=True, confirmed=False):
    if db not in ("pubmed",) + tuple(SUPPLEMENTARY):
        raise L.Refusal("DB_MANUAL", "«%s» se busca a mano: ejecútala tú, exporta a raw/exports/ y registra con prisma_s_log.py record." % db)
    L.string_guard(root, string_rel)
    text = L.read_string_file(root, string_rel)
    query, problems = L.build_query(text)
    local = L.syntax_issues(query) if db == "pubmed" else []
    errors = [i["msg_es"] for i in local if i["level"] == "error"] + problems
    warnings = [i["msg_es"] for i in local if i["level"] == "warning"]
    res = {"db": db, "string_file": string_rel, "executed_query": query, "mesh": [], "translation": "", "count": None,
           "repeat": None, "evidence": [], "offline": False}
    gate_ok_possible = True
    api_ref = None
    if lint_only:
        L.need_mode(root, network=False)
        res["offline"] = True
        warnings.append("Sin conexión: la base de datos no analizó la consulta (solo se revisó la sintaxis).")
        gate_ok_possible = False
    elif errors:
        warnings.append("No se consultó la base: corrige primero los errores de sintaxis.")
    else:
        L.need_mode(root, network=True)
        client = client or http_client.HttpClient(root, confirmed=confirmed)
        if db == "pubmed":
            params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": 0}
            qk = http_client.query_key(L.ESEARCH, params)
            prev = client.cached_entries(qk)
            e = L.esearch_pubmed(client, query, 0, cache="refresh" if refresh else "day", max_age_s=None if refresh else 3600)
            res.update(translation=e["translation"], count=e["count"])
            errors += e["errors"]
            warnings += e["warnings"]
            res["evidence"].append({"path": e["rel_path"], "sha256": e["sha256"]})
            api_ref = {"path": e["rel_path"], "sha256": e["sha256"]}
            if prev:
                last = prev[-1]
                try:
                    pc = int(last.json()["esearchresult"]["count"])
                except (ValueError, KeyError, TypeError):
                    pc = None
                if e["from_cache"]:
                    res["repeat"] = {"source": "cache", "same": True, "previous_ts": last.ts, "count": e["count"]}
                else:
                    res["repeat"] = {"source": "fresh", "previous_ts": last.ts, "previous_count": pc, "count": e["count"],
                                     "same": pc == e["count"], "delta": None if pc is None else e["count"] - pc}
                    if res["repeat"]["same"] is False:
                        warnings.append("El resultado cambió desde %s: %+d (PubMed se actualiza a diario). Queda en el diario." % (last.ts, res["repeat"]["delta"]))
            if not errors:
                for term, tag in L.mesh_terms(query):
                    m = L.validate_mesh(client, term)
                    res["mesh"].append(m)
                    if m["status"] == "not_found":
                        errors.append("MeSH «%s» no existe en db=mesh (etiqueta %s): PubMed lo reescribiría en silencio." % (term, tag))
                    elif m["status"] == "entry_term":
                        warnings.append("«%s» es un término de entrada, no el descriptor «%s»." % (term, m.get("descriptor", "?")))
                    elif m["status"] == "found_unchecked":
                        warnings.append("«%s» existe en db=mesh pero no se pudo confirmar que sea el descriptor exacto." % term)
        else:
            n, r = _count_other(client, db, query, "refresh" if refresh else "day", None if refresh else 3600)
            res["count"] = n
            res["evidence"].append({"path": r.rel_path, "sha256": r.sha256})
            api_ref = {"path": r.rel_path, "sha256": r.sha256}
            warnings.append("Base complementaria: no cuenta para el mínimo de bases (F-07) y no analiza la sintaxis como PubMed.")
    res["errors"], res["warnings"] = errors, warnings
    res["gate"] = "fail" if errors else ("pass" if gate_ok_possible and db == "pubmed" else "pending")
    res["ok"] = not errors
    if journal:
        _log(root, res, query, text, limits)
    return res


def _log(root, res, query, text, limits):
    db, rel = res["db"], res["string_file"]
    ver = L.string_version(rel)
    ref = journal_io.make_script_report(
        root, SCRIPT, L.unique_rel(root, "03_busqueda/reports/query_check_%s_v%d_%s.json" % (db, ver, L.stamp())),
        "fail" if res["errors"] else "pass",
        details={"db": db, "string_file": rel, "errors": res["errors"], "warnings": res["warnings"], "mesh": res["mesh"],
                 "translation": res["translation"], "count": res["count"], "repeat": res["repeat"], "offline": res["offline"]},
        version=L.VERSION)
    qc = {"db": db, "query": L.verbatim(text), "translation": res["translation"], "errors": res["errors"], "warnings": res["warnings"], "mesh": res["mesh"]}
    entry = {"stage": "C3", "type": "query_check", "actor": "script", "tool": L.tool(SCRIPT), "gate_name": "G-C3-query_check",
             "what_es": "Revisión de la consulta %s (%s): %d error(es), %d aviso(s)" % (rel, db, len(res["errors"]), len(res["warnings"])),
             "why_es": "F-05: comprobar cómo interpretó la base la cadena y si los MeSH existen",
             "how_verified": "esearch (QueryTranslation/ErrorList/WarningList) + db=mesh" if not res["offline"] else "solo sintaxis local (sin red)",
             "human_decision": "n/a", "gate": res["gate"], "query_check": qc, "inputs": _entry_inputs(root, rel),
             "script_report": ref}
    if res["gate"] == "pending":
        entry.pop("script_report")
    if res["evidence"]:
        entry["outputs"] = res["evidence"][:1]
    res["query_check_entry"] = journal_io.add(root, entry)["id"]
    if not res["errors"] and res["count"] is not None:
        rep = res["repeat"] or {}
        what = "Cadena %s ejecutada en %s: %d resultados" % (rel, db, res["count"])
        if rep.get("same") is False:
            what += " (diferencia diaria respecto a la ejecución anterior: %+d)" % rep["delta"]
        c = {"stage": "C3", "type": "count", "actor": "script", "tool": L.tool(SCRIPT), "what_es": what,
             "how_verified": "esearch; repetición dentro de 1 h o igual a la caché" if db == "pubmed" else "API pública",
             "human_decision": "n/a", "inputs": _entry_inputs(root, rel),
             "query": {"db": db, "platform": "PubMed (NCBI E-utilities)" if db == "pubmed" else SUPPLEMENTARY.get(db, db),
                       "string": L.verbatim(text), "date": paths.today(), "limits": limits or "sin límites", "count": res["count"]}}
        if rep:
            c["repeat"] = rep
        if res["evidence"]:
            c["outputs"] = res["evidence"][:1]
        res["count_entry"] = journal_io.add(root, c)["id"]
    res["script_report"] = ref


def record_details(root, db, string_rel, count, translation, errors, warnings, limits=""):
    """LITE: Laura pasted pubmed.gov «Search details». Entry actor = laura; a pass needs her decision."""
    L.string_guard(root, string_rel)
    text = L.read_string_file(root, string_rel)
    gate = "fail" if errors else "pass"
    qc = {"db": db, "query": L.verbatim(text), "translation": translation, "errors": list(errors), "warnings": list(warnings)}
    e1 = journal_io.add(root, {
        "stage": "C3", "type": "query_check", "actor": "laura", "gate_name": "G-C3-query_check", "gate": gate,
        "what_es": "Laura copió los «Search details» de %s para %s" % (db, string_rel),
        "how_verified": "copiado a mano de pubmed.gov (Search details)", "human_decision": "aprobado por Laura",
        "query_check": qc, "inputs": _entry_inputs(root, string_rel)})
    e2 = None
    if not errors:
        e2 = journal_io.add(root, {
            "stage": "C3", "type": "count", "actor": "laura", "what_es": "Laura ejecutó %s en %s: %d resultados" % (string_rel, db, count),
            "how_verified": "contador de pubmed.gov anotado por Laura", "human_decision": "aprobado por Laura",
            "inputs": _entry_inputs(root, string_rel),
            "query": {"db": db, "platform": "PubMed (web)", "string": L.verbatim(text), "date": paths.today(),
                      "limits": limits or "sin límites", "count": int(count)}})
    return {"ok": not errors, "gate": gate, "query_check_entry": e1["id"], "count_entry": e2["id"] if e2 else None}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--db", required=True)
    r.add_argument("--string-file", required=True)
    r.add_argument("--limits", default="")
    r.add_argument("--refresh", action="store_true")
    r.add_argument("--lint-only", action="store_true")
    r.add_argument("--confirmed", action="store_true")
    r.add_argument("--email")
    d = sub.add_parser("record-details")
    d.add_argument("--db", default="pubmed")
    d.add_argument("--string-file", required=True)
    d.add_argument("--count", type=int, required=True)
    d.add_argument("--translation", default="")
    d.add_argument("--error", action="append", default=[])
    d.add_argument("--warning", action="append", default=[])
    d.add_argument("--limits", default="")
    a = ap.parse_args(argv)

    def go():
        root = L.open_project(a.root)
        if a.cmd == "run":
            c = http_client.HttpClient(root, email=a.email, confirmed=a.confirmed) if not a.lint_only else None
            res = run(root, a.db, a.string_file, a.limits, a.refresh, a.lint_only, client=c, confirmed=a.confirmed)
            return res, (0 if res["ok"] else 1)
        res = record_details(root, a.db, a.string_file, a.count, a.translation, a.error, a.warning, a.limits)
        return res, (0 if res["ok"] else 1)
    return L.finish(go)


if __name__ == "__main__":
    sys.exit(main())
