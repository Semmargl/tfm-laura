#!/usr/bin/env python3
"""verify_refs.py - deterministic verification of 07_verificacion/references.csv (Q7-1, Q7-2, Q7-3, F-01, F-06, W2-1, W2-2, W2-4).

  verify_refs.py run [--offline] [--confirmed]
  verify_refs.py resolve --ref-id R5 --via 1|2|3 [--url ...] [--new-id ...] --laura-says "..."      (UNVERIFIABLE path, W2-4)
  verify_refs.py add-ref --ref-id R9 [--doi ..] [--pmid ..] --origin-es "..." --laura-says "..." [claimed_* fields]   (manual add, F-01)

STEP 1 (always, offline-capable): PROVENANCE. A reference needs `source_journal_id` -> a journal entry (search|count|verification|
reference_add|change) that links a file in raw/api (http_client envelope, actor script) or raw/exports (shape-checked, actor laura)
which CONTAINS its DOI/PMID; or a reference_add by Laura. Otherwise NO_PROVENANCE (release blocker). A real DOI recalled from memory
therefore never passes.  --offline stops here (LITE-a): gate_name G-C7-provenance, release_allowed=false.
STEP 2 (FULL): PubMed efetch by PMID (metadata + PublicationType + CommentsCorrections) and Crossref by DOI (metadata + updated-by +
filter=updates:<doi>); retracted/EoC by Crossref OR PubMed (F-06). Metadata vs the CLAIMED fields (claimed_title, claimed_first_author,
claimed_year, claimed_journal, claimed_issn in references.csv): title similarity >= 0.90, first-author surname, year, ISSN.
No DOI and no PMID => UNVERIFIABLE (never VALID) until Laura resolves it: 1 official URL/ISSN/handle, 2 find a PMID/DOI, 3 replace.
Statuses: VALID | NO_PROVENANCE | NOT_FOUND | MISMATCH | RETRACTED | EOC | DUPLICATE | UNVERIFIABLE | METADATA_NOT_COMPARED |
UNVERIFIABLE_RESOLVED | REPLACED.  The script writes reports and never edits the reference list.
"""
import argparse
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_lib as V  # noqa: E402
from _common import config, http_client, journal_io, paths  # noqa: E402

SCRIPT = "verify_refs.py"


def resolutions(root):
    out = {}
    for e in journal_io.query(root, type="decision"):
        if e.get("kind") == "unverifiable_resolution" and e.get("actor") == "laura":
            out[e["ref_id"]] = e
    return out


def efetch_all(client, pmids):
    """-> ({pmid: rec}, error_or_None, [evidence])"""
    recs, ev = {}, []
    ids = sorted(set(pmids))
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        r = client.get(V.EFETCH, {"db": "pubmed", "id": ",".join(chunk), "retmode": "xml"})
        ev.append({"path": r.rel_path, "sha256": r.sha256})
        parsed = V.parse_pubmed_xml(r.text)
        if parsed is None:
            return recs, "respuesta de PubMed ilegible", ev
        recs.update(parsed)
    return recs, None, ev


def crossref_one(client, doi):
    """-> (info|None, status_text, updating_types, evidence[])"""
    ev = []
    r = client.get("%s/%s" % (V.CROSSREF, urllib.parse.quote(doi, safe="/()")), accept=(200, 404))
    ev.append({"path": r.rel_path, "sha256": r.sha256})
    if r.status == 404:
        h = client.get(V.HANDLES + urllib.parse.quote(doi, safe="/()"), accept=(200, 404))
        ev.append({"path": h.rel_path, "sha256": h.sha256})
        try:
            exists = h.status == 200 and h.json().get("responseCode") == 1
        except ValueError:
            exists = False
        return None, ("other_registry" if exists else "not_found"), [], ev
    info = V.parse_crossref(r.json().get("message") or {})
    q = client.get(V.CROSSREF, {"filter": "updates:" + doi, "rows": 20, "select": "DOI,type,update-to"})
    ev.append({"path": q.rel_path, "sha256": q.sha256})
    upd = []
    for it in (q.json().get("message") or {}).get("items", []):
        for u in it.get("update-to") or []:
            if norm(u.get("DOI")) == doi:
                upd.append((u.get("type") or "").lower())
    return info, "ok", upd, ev


def norm(x):
    return V.norm_doi(x or "")


def run(root, offline=False, client=None, confirmed=False, journal=True):
    V.need_mode(root, network=not offline)
    rows = V.load_refs(root)
    if not rows:
        raise V.Refusal("EMPTY_REFS", "references.csv está vacío: no hay nada que verificar.")
    ctx = V.context(root)
    res_map = resolutions(root)
    out = {r["ref_id"]: {"ref_id": r["ref_id"], "doi": r["doi"], "pmid": r["pmid"], "status": None, "detail": "", "notes": [], "evidence": [],
                         "provenance": None} for r in rows}
    # ---- step 1: provenance
    pending = []
    for r in rows:
        o = out[r["ref_id"]]
        p = V.check_provenance(root, r, ctx)
        o["provenance"] = p
        if p["status"] != "OK":
            o["status"], o["detail"] = "NO_PROVENANCE", p["detail"]
        else:
            o["notes"].append("procedencia: %s (%s)" % (p.get("kind"), p["detail"]))
            pending.append(r)
    # ---- duplicates (offline) among all rows
    seen = {}
    for r in rows:
        for key in [("doi", r["doi"]), ("pmid", r["pmid"]), ("title", V.norm_text(r.get("claimed_title", "")))]:
            if not key[1]:
                continue
            if key in seen and seen[key] != r["ref_id"]:
                o = out[r["ref_id"]]
                if o["status"] is None:
                    o["status"], o["detail"] = "DUPLICATE", "duplicada de %s (%s)" % (seen[key], key[0])
                break
            seen.setdefault(key, r["ref_id"])
    # ---- step 2: existence / metadata / retractions (FULL only)
    client = client or (None if offline else http_client.HttpClient(root, confirmed=confirmed))
    todo = [r for r in pending if out[r["ref_id"]]["status"] is None]
    if not offline:
        pm_recs, pm_err, pm_ev = {}, None, []
        pmids = [r["pmid"] for r in todo if r["pmid"]]
        if pmids:
            pm_recs, pm_err, pm_ev = efetch_all(client, pmids)
        for r in todo:
            o = out[r["ref_id"]]
            if not r["pmid"] and not r["doi"]:
                rs = res_map.get(r["ref_id"])
                if rs:
                    o["status"] = "REPLACED" if str(rs.get("via")) == "3" else "UNVERIFIABLE_RESOLVED"
                    o["detail"] = "sin DOI/PMID; decisión de Laura %s (vía %s)%s" % (rs["id"], rs.get("via"), (": " + rs["url"]) if rs.get("url") else "")
                else:
                    o["status"], o["detail"] = "UNVERIFIABLE", "sin DOI ni PMID: no se puede verificar; Laura elige una vía (resolve --via 1|2|3)"
                continue
            flags, probs, compared, notes, apis = [], [], False, [], []
            src_probs = []
            not_found, checked = [], False
            if r["pmid"]:
                rec = pm_recs.get(r["pmid"])
                o["evidence"] += pm_ev[:1]
                if pm_err:
                    o["status"], o["detail"] = "UNVERIFIABLE", pm_err
                    continue
                if rec is None:
                    not_found.append("PMID %s no existe en PubMed" % r["pmid"])
                else:
                    checked = True
                    st, nn = V.pubmed_flags(rec)
                    notes += nn
                    if st:
                        flags.append(st)
                    if r["doi"] and rec["doi"] and rec["doi"] != r["doi"]:
                        probs.append("el DOI del CSV (%s) no es el que PubMed asocia a ese PMID (%s)" % (r["doi"], rec["doi"]))
                    c, p_, n_ = V.compare_meta(r, rec)
                    meta_p = [x for x in p_]
                    compared, notes = compared or c, notes + n_
                    if c:
                        src_probs.append(meta_p)
            if r["doi"]:
                info, st_txt, upd, ev = crossref_one(client, r["doi"])
                o["evidence"] += ev
                if st_txt == "not_found":
                    not_found.append("DOI %s no existe (Crossref 404 y doi.org sin registro)" % r["doi"])
                elif st_txt == "other_registry":
                    notes.append("el DOI existe pero no en Crossref (¿DataCite?): metadatos no comparables por esta vía")
                else:
                    checked = True
                    st, nn = V.crossref_flags(info, upd)
                    notes += nn
                    if st:
                        flags.append(st)
                    c, p_, n_ = V.compare_meta(r, info)
                    compared, notes = compared or c, notes + n_
                    if c:
                        src_probs.append(list(p_))
            mp, mn = V.combine_source_problems(src_probs)
            probs, notes = probs + mp, notes + mn
            if "RETRACTED" in flags:
                o["status"], o["detail"] = "RETRACTED", "retractada o aviso de retractación (Crossref/PubMed)"
            elif "EOC" in flags:
                o["status"], o["detail"] = "EOC", "expresión de preocupación (Crossref/PubMed)"
            elif not_found:
                o["status"], o["detail"] = "NOT_FOUND", "; ".join(not_found)
            elif probs:
                o["status"], o["detail"] = "MISMATCH", "; ".join(probs)
            elif not checked:
                o["status"], o["detail"] = "UNVERIFIABLE", "existe pero no se pudieron comparar metadatos"
            elif not compared:
                o["status"], o["detail"] = "METADATA_NOT_COMPARED", "existe, pero references.csv no trae claimed_title / claimed_first_author / claimed_year: no hay nada que comparar"
            else:
                o["status"], o["detail"] = "VALID", "existe, metadatos coinciden, sin retractación ni expresión de preocupación"
            o["notes"] += notes
    else:
        for r in todo:
            if not r["pmid"] and not r["doi"]:
                rs = res_map.get(r["ref_id"])
                o = out[r["ref_id"]]
                o["status"] = ("REPLACED" if str(rs.get("via")) == "3" else "UNVERIFIABLE_RESOLVED") if rs else "UNVERIFIABLE"
                o["detail"] = "sin DOI ni PMID" + ("; decisión de Laura %s" % rs["id"] if rs else "")
            else:
                out[r["ref_id"]]["status"], out[r["ref_id"]]["detail"] = "PROVENANCE_OK_OFFLINE", "procedencia correcta; existencia/retractación pendientes (checklist LITE o modo FULL)"
    for o in out.values():
        if o["status"] is None:
            o["status"] = "UNVERIFIABLE"
    items = [out[r["ref_id"]] for r in rows]
    counts = {}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    no_prov = counts.get("NO_PROVENANCE", 0)
    unverified = sum(counts.get(s, 0) for s in V.UNVERIFIED)
    blockers = [it for it in items if it["status"] in V.BLOCKING]
    ok = not blockers
    release = ok and not offline
    summary = {"total": len(items), "counts": counts, "no_provenance_count": no_prov, "unverified_count": unverified,
               "blocking": len(blockers), "release_allowed": release and no_prov + unverified == 0, "scope": "provenance_only" if offline else "full"}
    res = {"ok": ok, "summary": summary, "items": items,
           "message_es": "%d referencias: %s. %s" % (len(items), ", ".join("%s=%d" % kv for kv in sorted(counts.items())),
                                                    "Release permitido." if summary["release_allowed"] else "Release NO permitido (bloqueos: %d)." % len(blockers) if blockers else
                                                    "Solo procedencia comprobada (offline): falta existencia/retractación." if offline else "")}
    if journal:
        ts = V.stamp()
        md = V.make_report_md("Verificación de referencias (%s)" % ("solo procedencia, sin red" if offline else "completa"),
                              [dict(it, status=it["status"]) for it in items],
                              ["Resultado: " + res["message_es"], "release_allowed: %s" % summary["release_allowed"], ""])
        md_rel = V.unique_rel(root, "%s/verificacion_%s_es.md" % (V.REPORTS, ts))
        paths.write_text_atomic(paths.safe_join(root, md_rel), md)
        ref = journal_io.make_script_report(root, SCRIPT, V.unique_rel(root, "%s/verify_%s.json" % (V.REPORTS, ts)), "pass" if ok else "fail",
                                            details={"summary": summary, "items": items, "report_es": md_rel}, version=V.VERSION)
        gname = "G-C7-provenance" if offline else "G-C7-refs"
        e = journal_io.add(root, {
            "stage": "C7", "type": "verification", "actor": "script", "tool": V.tool(SCRIPT), "gate_name": gname, "gate": "pass" if ok else "fail",
            "script_report": ref, "human_decision": "n/a", "how_verified": "procedencia en raw/ + " + ("(sin red)" if offline else "PubMed efetch + Crossref"),
            "what_es": res["message_es"], "inputs": [journal_io.file_ref(root, V.REFS_REL)], "outputs": [journal_io.file_ref(root, md_rel)],
            "counts": {"no_provenance": no_prov, "unverified": unverified}, "release_allowed": summary["release_allowed"]})
        res["journal_id"], res["script_report"], res["report_es"] = e["id"], ref, md_rel
    return res


def resolve(root, ref_id, via, url, new_id, said):
    if not said.strip():
        raise V.Refusal("MISSING_STATEMENT", "Hace falta lo que Laura dijo (--laura-says): la decisión es suya.")
    rows = V.load_refs(root)
    if ref_id not in {r["ref_id"] for r in rows}:
        raise V.Refusal("UNKNOWN_REF", "No existe la referencia %s." % ref_id)
    if via not in ("1", "2", "3"):
        raise V.Refusal("BAD_VIA", "Vía 1 (URL/ISSN/handle), 2 (buscar PMID/DOI) o 3 (sustituir).")
    if via == "1" and not url.strip():
        raise V.Refusal("URL_REQUIRED", "La vía 1 necesita la URL oficial / ISSN / handle.")
    if via == "2" and not new_id.strip():
        raise V.Refusal("NEW_ID_REQUIRED", "La vía 2 necesita el PMID/DOI encontrado (después hay que actualizar references.csv y registrar su procedencia con add-ref).")
    e = journal_io.add(root, {"stage": "C7", "type": "decision", "actor": "laura", "kind": "unverifiable_resolution", "ref_id": ref_id, "via": via,
                              "url": url.strip(), "new_id": new_id.strip(), "human_decision": "aprobado por Laura", "why_es": said.strip(),
                              "what_es": "Laura resuelve la referencia sin DOI/PMID %s por la vía %s" % (ref_id, via)})
    note = "Sigue UNVERIFIABLE hasta que references.csv tenga el id nuevo con su procedencia." if via == "2" else "Queda como no bloqueante, pero NO como «verificada»."
    return {"ok": True, "journal_id": e["id"], "message_es": note}


def add_ref(root, ref_id, doi, pmid, origin_es, said, claimed):
    if not said.strip() or not origin_es.strip():
        raise V.Refusal("MISSING_STATEMENT", "Hace falta origin_es (de dónde la sacó Laura) y su palabra (--laura-says).")
    rows = V.load_refs(root) if paths.safe_join(root, V.REFS_REL).is_file() else []
    if ref_id in {r["ref_id"] for r in rows}:
        raise V.Refusal("REF_EXISTS", "%s ya existe." % ref_id)
    refs = ["REFID:" + ref_id] + (["DOI:" + V.norm_doi(doi)] if doi else []) + (["PMID:" + V.norm_pmid(pmid)] if pmid else [])
    e = journal_io.add(root, {"stage": "C7", "type": "reference_add", "actor": "laura", "origin_es": origin_es.strip(), "refs": refs,
                              "human_decision": "aprobado por Laura", "why_es": said.strip(), "what_es": "Laura añade a mano la referencia %s" % ref_id})
    row = {"ref_id": ref_id, "doi": V.norm_doi(doi), "pmid": V.norm_pmid(pmid), "source_journal_id": e["id"], "provenance_status": "laura_declared"}
    row.update({k: v for k, v in claimed.items() if v})
    rows.append(row)
    V.write_refs(root, rows)
    return {"ok": True, "journal_id": e["id"], "ref_id": ref_id}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--offline", action="store_true")
    r.add_argument("--confirmed", action="store_true")
    r.add_argument("--email")
    s = sub.add_parser("resolve")
    s.add_argument("--ref-id", required=True)
    s.add_argument("--via", required=True)
    s.add_argument("--url", default="")
    s.add_argument("--new-id", default="")
    s.add_argument("--laura-says", default="")
    d = sub.add_parser("add-ref")
    d.add_argument("--ref-id", required=True)
    d.add_argument("--doi", default="")
    d.add_argument("--pmid", default="")
    d.add_argument("--origin-es", default="")
    d.add_argument("--laura-says", default="")
    for c in V.EXTRA_COLS:
        d.add_argument("--" + c.replace("_", "-"), default="")
    a = ap.parse_args(argv)

    def go():
        root = V.open_project(a.root)
        if a.cmd == "run":
            c = None if a.offline else http_client.HttpClient(root, email=a.email, confirmed=a.confirmed)
            res = run(root, a.offline, client=c)
            return res, (0 if res["ok"] else 1)
        if a.cmd == "resolve":
            return resolve(root, a.ref_id, a.via, a.url, a.new_id, a.laura_says), 0
        return add_ref(root, a.ref_id, a.doi, a.pmid, a.origin_es, a.laura_says, {c: getattr(a, c) for c in V.EXTRA_COLS}), 0
    return V.finish(go)


if __name__ == "__main__":
    sys.exit(main())
