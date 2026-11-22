#!/usr/bin/env python3
"""pilot_sample.py - optional screening PILOT + supervisor spot-check sample (Q4-2, PRISMA-P 11b, W-1).

  pilot_sample.py record-go --by laura|supervisor --says "..." [--no]    the pilot is OPTIONAL: it needs this decision first
  pilot_sample.py sample [--n 50] [--seed 20261025]                       deterministic sample of UNIQUE records, decision columns EMPTY
  pilot_sample.py show --file <pilot csv> [--page 1]                      20 records per page (never load more into the chat)
  pilot_sample.py check --file <pilot csv>                                every row decided by laura, closed-list reasons (gate G-C4-pilot)
  pilot_sample.py supervisor-sample [--pct 20]                            records the supervisor re-checks (single reviewer + spot check)

Screening decisions are LAURA'S. This script never proposes include/exclude. Claude is NOT a second reviewer (PRISMA-P 11b = one reviewer
+ supervisor spot check). Every pilot file carries the watermark «PRELIMINAR — piloto, no forma parte del protocolo» (W-1).
"""
import argparse
import csv
import io
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import screen_lib as S  # noqa: E402
from _common import config, journal_io, paths  # noqa: E402

SCRIPT = "pilot_sample.py"
PILOT_COLS = ["rec_id", "title", "year", "journal", "abstract", "decision", "reason", "decided_by", "decided_date", "marca"]
SUP_COLS = ["rec_id", "title", "year", "supervisor_decision", "agrees_with_laura", "note"]
PER_PAGE = 20


def go_status(root):
    ents = [e for e in journal_io.query(root, type="decision") if e.get("kind") in ("pilot_go", "pilot_no")]
    return ents[-1] if ents else None


def record_go(root, by, says, no=False):
    if by not in ("laura", "supervisor"):
        raise S.Refusal("BAD_ACTOR", "La decisión del piloto es de Laura o del tutor.")
    if not says.strip():
        raise S.Refusal("MISSING_STATEMENT", "Hace falta lo que dijo (--says): el piloto es opcional y lo decide el tutor/Laura (W-1).")
    e = journal_io.add(root, {"stage": "C4", "type": "decision", "actor": by, "kind": "pilot_no" if no else "pilot_go", "human_decision": "aprobado por " + ("Laura" if by == "laura" else "el tutor"),
                              "what_es": "Piloto de selección: " + ("NO se hace" if no else "SÍ se hace (preliminar, no forma parte del protocolo)"), "why_es": says.strip()})
    return {"ok": True, "journal_id": e["id"]}


def unique_records(root):
    rel = S.latest(root, "dedup")
    if not rel:
        raise S.Refusal("NO_DEDUP", "Primero ejecuta dedup.py: el piloto se saca de los registros únicos.")
    rows = [r for r in S.read_csv(root, rel) if not r["duplicate_of"]]
    return rel, sorted(rows, key=lambda r: r["rec_id"])


def sample(root, n=None, seed=20261025, journal=True):
    S.need_scripts(root)
    g = go_status(root)
    if not g or g["kind"] != "pilot_go":
        raise S.Refusal("PILOT_NOT_DECIDED", "El piloto es opcional y aún no hay decisión del tutor/Laura (record-go). No se crea la muestra.")
    n = n or int(config.load_config(root)["pilot_n"])
    rel, uniq = unique_records(root)
    warn = []
    if len(uniq) < n:
        warn.append("Solo hay %d registros únicos (< %d): el piloto usa todos." % (len(uniq), n))
        n = len(uniq)
    picked = sorted(random.Random(seed).sample(uniq, n), key=lambda r: r["rec_id"])
    rows = [{"rec_id": r["rec_id"], "title": r["title"], "year": r["year"], "journal": r["journal"], "abstract": r["abstract"], "decision": "", "reason": "",
             "decided_by": "", "decided_date": "", "marca": S.WATERMARK} for r in picked]
    out = S.unique_rel(root, "04_seleccion/pilot/pilot_sample_%s.csv" % S.stamp())
    S.write_csv(root, out, PILOT_COLS, rows)
    res = {"ok": True, "file": out, "n": n, "seed": seed, "from": rel, "warnings": warn, "watermark": S.WATERMARK,
           "message_es": "Muestra de piloto de %d registros (%s). Las decisiones las toma Laura; razones de exclusión: %s." % (n, S.WATERMARK, ", ".join(S.EXCLUSION_REASONS))}
    if journal:
        e = journal_io.add(root, {"stage": "C4", "type": "change", "actor": "script", "kind": "pilot_sample", "tool": S.tool(SCRIPT), "human_decision": "n/a",
                                  "what_es": res["message_es"], "how_verified": "muestra determinista (semilla %d) de registros únicos" % seed,
                                  "inputs": [journal_io.file_ref(root, rel)], "outputs": [journal_io.file_ref(root, out)], "watermark": S.WATERMARK, "seed": seed})
        res["journal_id"] = e["id"]
    return res


def show(root, rel, page=1):
    rows = S.read_csv(root, rel)
    chunk = rows[(page - 1) * PER_PAGE: page * PER_PAGE]
    return {"ok": True, "page": page, "pages": (len(rows) + PER_PAGE - 1) // PER_PAGE, "records": [
        {k: r[k] for k in ("rec_id", "title", "year", "journal", "abstract", "decision", "reason")} for r in chunk]}


def check(root, rel, journal=True):
    rows = S.read_csv(root, rel)
    n_cfg = int(config.load_config(root)["pilot_n"])
    problems = []
    for r in rows:
        d, why, by = r["decision"].strip().lower(), r["reason"].strip().lower(), r["decided_by"].strip().lower()
        if d not in S.DECISIONS:
            problems.append("%s: decisión vacía o no válida (%s)" % (r["rec_id"], "/".join(S.DECISIONS)))
        if d == "excluir" and why not in S.EXCLUSION_REASONS:
            problems.append("%s: la exclusión necesita una razón de la lista cerrada (%s)" % (r["rec_id"], ", ".join(S.EXCLUSION_REASONS)))
        if by != "laura":
            problems.append("%s: decided_by debe ser «laura» (hay «%s»)" % (r["rec_id"], by))
        if S.WATERMARK not in r.get("marca", ""):
            problems.append("%s: falta la marca PRELIMINAR" % r["rec_id"])
    short = len(rows) < n_cfg
    uniq_n = len(unique_records(root)[1]) if S.latest(root, "dedup") else None
    if short and (uniq_n is None or uniq_n >= n_cfg):
        problems.append("el piloto tiene %d registros (< %d)" % (len(rows), n_cfg))
    ok = not problems
    res = {"ok": ok, "rows": len(rows), "problems": problems[:50], "n_problems": len(problems), "pilot_n": n_cfg,
           "message_es": "Piloto: %d registros, %d problema(s)" % (len(rows), len(problems))}
    if journal:
        ref = journal_io.make_script_report(root, SCRIPT, S.unique_rel(root, "04_seleccion/pilot/check_%s.json" % S.stamp()), "pass" if ok else "fail",
                                            details={"file": rel, "problems": problems[:200], "rows": len(rows)}, version=S.VERSION)
        e = journal_io.add(root, {"stage": "C4", "type": "verification", "actor": "script", "kind": "pilot_check", "gate_name": "G-C4-pilot",
                                  "gate": "pass" if ok else "fail", "script_report": ref, "tool": S.tool(SCRIPT), "human_decision": "n/a",
                                  "how_verified": "100% decided_by laura + razones de lista cerrada", "what_es": res["message_es"],
                                  "inputs": [journal_io.file_ref(root, rel)], "watermark": S.WATERMARK})
        res["journal_id"], res["script_report"] = e["id"], ref
    return res


def supervisor_sample(root, pct=None, seed=20261026, journal=True):
    S.need_scripts(root)
    pct = float(pct if pct is not None else config.load_config(root)["supervisor_check_pct"])
    rel, uniq = unique_records(root)
    k = max(1, int(round(len(uniq) * pct / 100.0))) if uniq else 0
    picked = sorted(random.Random(seed).sample(uniq, k), key=lambda r: r["rec_id"])
    rows = [{"rec_id": r["rec_id"], "title": r["title"], "year": r["year"], "supervisor_decision": "", "agrees_with_laura": "", "note": ""} for r in picked]
    out = S.unique_rel(root, "04_seleccion/supervisor_check_sample.csv")
    S.write_csv(root, out, SUP_COLS, rows)
    res = {"ok": True, "file": out, "pct": pct, "n": k, "of": len(uniq), "status": "porcentaje pendiente de acordar con el tutor",
           "message_es": "Muestra de verificación del tutor: %d de %d registros únicos (%.0f%%, pendiente de acordar con el tutor)." % (k, len(uniq), pct)}
    if journal:
        e = journal_io.add(root, {"stage": "C4", "type": "change", "actor": "script", "kind": "supervisor_sample", "tool": S.tool(SCRIPT), "human_decision": "pendiente",
                                  "what_es": res["message_es"], "inputs": [journal_io.file_ref(root, rel)], "outputs": [journal_io.file_ref(root, out)], "seed": seed})
        res["journal_id"] = e["id"]
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("record-go")
    g.add_argument("--by", required=True)
    g.add_argument("--says", default="")
    g.add_argument("--no", action="store_true")
    s = sub.add_parser("sample")
    s.add_argument("--n", type=int)
    s.add_argument("--seed", type=int, default=20261025)
    w = sub.add_parser("show")
    w.add_argument("--file", required=True)
    w.add_argument("--page", type=int, default=1)
    c = sub.add_parser("check")
    c.add_argument("--file", required=True)
    v = sub.add_parser("supervisor-sample")
    v.add_argument("--pct", type=float)
    a = ap.parse_args(argv)

    def go():
        root = S.open_project(a.root)
        if a.cmd == "record-go":
            r = record_go(root, a.by, a.says, a.no)
        elif a.cmd == "sample":
            r = sample(root, a.n, a.seed)
        elif a.cmd == "show":
            r = show(root, a.file, a.page)
        elif a.cmd == "check":
            r = check(root, a.file)
        else:
            r = supervisor_sample(root, a.pct)
        return r, (0 if r["ok"] else 1)
    return S.finish(go)


if __name__ == "__main__":
    sys.exit(main())
