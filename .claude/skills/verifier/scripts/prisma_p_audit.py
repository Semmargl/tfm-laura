#!/usr/bin/env python3
"""prisma_p_audit.py - PRISMA-P 2015 audit: 17 items / 26 sub-items (Q7-5).

  prisma_p_audit.py init                  create 07_verificacion/prisma_p_locators.csv (one row per sub-item; never overwrites)
  prisma_p_audit.py run [--checklist F]   check locators, combine with Laura's decisions, write report, journal G-C7-prisma-p

WHAT THE SCRIPT DOES: for each sub-item, checks that the LOCATOR points to something real in the draft (file exists, heading «file#Heading»
or line «file:L12» exists and is not empty). WHAT IT DOES NOT DO: judge whether the text really satisfies the item. That is the advisory
column (Claude, `advisory`) plus `laura_decision` (cumple | parcial | ausente) - only Laura's column counts.
Final status per sub-item: no valid locator -> ausente | locator ok + Laura «cumple» -> presente | «parcial» -> parcial | empty -> pendiente_laura.
Gate: 26/26 presente (0 ausente, 0 parcial, 0 pendiente) AND the official text loaded in data/prisma_p_2015_checklist.json.
OFFICIAL TEXT: not in this kit (`text_loaded: false`, «pendiente de cargar texto oficial»); source https://www.prisma-statement.org/protocols.
Until it is loaded the audit result is `fail` with that reason: a structure without the official wording cannot approve a protocol.
"""
import argparse
import csv
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_lib as V  # noqa: E402
from _common import journal_io, paths  # noqa: E402

SCRIPT = "prisma_p_audit.py"
LOC_REL = "07_verificacion/prisma_p_locators.csv"
COLS = ["item_id", "label_es", "locator", "advisory_claude", "advisory_note", "laura_decision", "laura_note"]
DEFAULT_CHECKLIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "prisma_p_2015_checklist.json")
LAURA = {"cumple": "presente", "parcial": "parcial", "ausente": "ausente"}


def load_checklist(path=None):
    with open(path or DEFAULT_CHECKLIST, encoding="utf-8") as f:
        data = json.load(f)
    items = data["items"]
    ids = [i["id"] for i in items]
    if len(items) != 26 or len({i["item"] for i in items}) != 17 or len(set(ids)) != 26:
        raise V.Refusal("CHECKLIST_BROKEN", "El checklist PRISMA-P del kit está dañado (no tiene 17 ítems / 26 subítems).")
    data["text_loaded"] = bool(data.get("text_loaded")) and all(i.get("official_text_en") for i in items)
    return data


def init(root, checklist=None):
    data = load_checklist(checklist)
    full = paths.safe_join(root, LOC_REL)
    if full.exists():
        raise V.Refusal("LOCATORS_EXIST", "%s ya existe (no se sobrescribe)." % LOC_REL)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLS, lineterminator="\n")
    w.writeheader()
    for i in data["items"]:
        w.writerow({"item_id": i["id"], "label_es": i["label_es"]})
    paths.write_text_atomic(full, buf.getvalue())
    return {"ok": True, "path": LOC_REL, "rows": len(data["items"]), "official_text_loaded": data["text_loaded"],
            "message_es": "Plantilla creada. Rellena `locator` (p. ej. 06_protocolo/drafts/metodos.md#Criterios de elegibilidad) y, cuando Laura lo decida, `laura_decision`."}


def locator_ok(root, loc):
    """-> (ok, reason). Forms: path | path#Heading text | path:L12"""
    loc = (loc or "").strip()
    if not loc:
        return False, "sin localizador"
    m = re.match(r"^(?P<p>[^#:]+?)(?:#(?P<h>.+)|:L(?P<l>\d+))?$", loc)
    if not m:
        return False, "formato de localizador no válido"
    rel = m.group("p").strip()
    if rel.startswith("raw/"):
        return False, "el localizador no puede apuntar a raw/"
    try:
        full = paths.safe_join(root, rel)
    except ValueError:
        return False, "ruta no válida"
    if not full.is_file():
        return False, "no existe %s" % rel
    text = paths.read_text(full)
    if not text.strip():
        return False, "el archivo está vacío"
    if m.group("h"):
        h = V.norm_text(m.group("h"))
        lines = text.split("\n")
        for k, ln in enumerate(lines):
            if ln.lstrip().startswith("#") and V.norm_text(ln.lstrip("# ")) == h:
                level = len(ln.lstrip()) - len(ln.lstrip().lstrip("#"))
                for x in lines[k + 1:]:
                    xs = x.strip()
                    if not xs:
                        continue
                    if xs.startswith("#"):
                        # B6: a parent heading whose text lives in its sub-headings (## Statistics > ### Data synthesis) is not empty
                        if len(xs) - len(xs.lstrip("#")) <= level:
                            break
                        continue
                    return True, "ok"
                return False, "el apartado «%s» está vacío" % m.group("h")
        return False, "no hay un título «%s» en %s" % (m.group("h"), rel)
    if m.group("l"):
        n = int(m.group("l"))
        lines = text.split("\n")
        if 1 <= n <= len(lines) and lines[n - 1].strip():
            return True, "ok"
        return False, "la línea %d no existe o está vacía" % n
    return True, "ok"


def run(root, checklist=None, journal=True):
    V.need_mode(root, network=False)
    data = load_checklist(checklist)
    full = paths.safe_join(root, LOC_REL)
    if not full.is_file():
        raise V.Refusal("NO_LOCATORS", "Primero crea la plantilla: prisma_p_audit.py init.")
    rows = {r["item_id"].strip(): r for r in csv.DictReader(io.StringIO(paths.read_text(full)))}
    out, counts = [], {}
    for it in data["items"]:
        r = rows.get(it["id"], {})
        ok, why = locator_ok(root, r.get("locator", ""))
        decision = (r.get("laura_decision") or "").strip().lower()
        adv = (r.get("advisory_claude") or "").strip().lower()
        if not ok:
            st = "ausente"
        elif decision in LAURA:
            st = LAURA[decision]
        else:
            st = "pendiente_laura"
        note = []
        if ok and adv and decision in LAURA and ((adv == "cumple") != (decision == "cumple")):
            note.append("Claude (advisory) y Laura no coinciden: manda Laura")
        out.append({"item_id": it["id"], "label_es": it["label_es"], "locator": r.get("locator", ""), "locator_ok": ok, "locator_reason": why,
                    "advisory_claude": adv or None, "laura_decision": decision or None, "status": st, "notes": note})
        counts[st] = counts.get(st, 0) + 1
    reasons = []
    if not data["text_loaded"]:
        reasons.append("texto oficial de PRISMA-P pendiente de cargar (%s)" % data["source_url"])
    bad = len(out) - counts.get("presente", 0)
    if bad:
        reasons.append("%d subítem(s) sin estado «presente»" % bad)
    ok = not reasons
    res = {"ok": ok, "counts": counts, "items": out, "official_text_loaded": data["text_loaded"], "reasons": reasons,
           "message_es": "PRISMA-P: presente %d/26, parcial %d, ausente %d, pendiente de Laura %d%s" % (
               counts.get("presente", 0), counts.get("parcial", 0), counts.get("ausente", 0), counts.get("pendiente_laura", 0),
               "" if data["text_loaded"] else " - texto oficial aún sin cargar" )}
    if journal:
        ts = V.stamp()
        md = ["# Auditoría PRISMA-P 2015 (17 ítems / 26 subítems)", "", res["message_es"], "",
              "Aviso: %s" % data.get("notice_es", ""), "", "| Ítem | Tema | Localizador | Estado | Claude (advisory) | Laura |", "|---|---|---|---|---|---|"]
        for o in out:
            md.append("| %s | %s | %s | %s | %s | %s |" % (o["item_id"], o["label_es"], o["locator"] or "-", o["status"], o["advisory_claude"] or "-", o["laura_decision"] or "-"))
        md += ["", "El script solo comprueba que el localizador exista; la valoración del contenido es de Laura.", ""]
        md_rel = V.unique_rel(root, "%s/prisma_p_%s_es.md" % (V.REPORTS, ts))
        paths.write_text_atomic(paths.safe_join(root, md_rel), "\n".join(md))
        ref = journal_io.make_script_report(root, SCRIPT, V.unique_rel(root, "%s/prisma_p_%s.json" % (V.REPORTS, ts)), "pass" if ok else "fail",
                                            details={"counts": counts, "items": out, "reasons": reasons, "report_es": md_rel}, version=V.VERSION)
        e = journal_io.add(root, {"stage": "C7", "type": "verification", "actor": "script", "tool": V.tool(SCRIPT), "gate_name": "G-C7-prisma-p",
                                  "gate": "pass" if ok else "fail", "script_report": ref, "human_decision": "n/a",
                                  "how_verified": "localizadores verificados por script; contenido valorado por Laura", "what_es": res["message_es"],
                                  "inputs": [journal_io.file_ref(root, LOC_REL)], "outputs": [journal_io.file_ref(root, md_rel)]})
        res["journal_id"], res["script_report"], res["report_es"] = e["id"], ref, md_rel
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("init", "run"):
        s = sub.add_parser(c)
        s.add_argument("--checklist")
    a = ap.parse_args(argv)

    def go():
        root = V.open_project(a.root)
        r = init(root, a.checklist) if a.cmd == "init" else run(root, a.checklist)
        return r, (0 if r["ok"] else 1)
    return V.finish(go)


if __name__ == "__main__":
    sys.exit(main())
