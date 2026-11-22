#!/usr/bin/env python3
"""panel_check.py check|checklist  --file 08_paneles/panel_viabilidad.html [--journal]

Q8-1 / Q8-2: parses the panel HTML and compares EVERY traced number with journal/journal.jsonl (mismatch must be 0):
  * element with data-journal-id + data-field (+ data-agg=len) -> journal value must equal data-value;
    elements with class "num" must also DISPLAY exactly data-value;
  * class "num" without data-journal-id/data-config -> NUM_UNTRACED; data-config -> compared with config/project.yaml;
  * single file, offline: no <script src>, <link>, <iframe>, <img src=http>, @import, url(http...);
  * <html lang="es">; viabilidad panel carries «Sugerencia; decide Laura»; flow/mapa carry «PRELIMINAR — piloto, no forma parte del protocolo»;
  * warning (not error) when the journal has newer entries than the panel's «hasta J-xxxx» marker (stale panel).
--journal writes a tfm-report/v1 under 08_paneles/reports/ and a `verification` entry (actor script, gate G-C8).
`checklist` prints the numbers as a Spanish table for Laura's manual check in LITE-b (<= 20 numbers in viabilidad).
Exit 0 ok · 1 mismatch/error · 2 usage.
"""
import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_lib as pl  # noqa: E402
from panel_lib import journal_io, paths  # noqa: E402

SCRIPT = "panel_check.py"
MAX_BYTES = 2 * 1024 * 1024
VOID = {"meta", "br", "hr", "img", "input", "link", "source", "wbr", "col", "area", "base", "embed", "param", "track"}


class _P(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.stack, self.items, self.lang, self.ext, self.tags, self.text_all = [], [], None, [], set(), []
        self.panel = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.add(tag)
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "body":
            self.panel = a.get("data-panel")
        if tag in ("script", "link", "iframe", "object", "embed") and (tag != "script" or a.get("src")) or \
                (tag == "link"):
            self.ext.append("<%s>" % tag)
        for k in ("src", "href"):
            v = a.get(k, "")
            if tag in ("img", "source", "video", "audio") and v.startswith(("http", "//")):
                self.ext.append("%s %s=%s" % (tag, k, v))
        if tag == "form" and a.get("action"):
            self.ext.append("<form action>")
        cls = (a.get("class") or "").split()
        if tag not in VOID and ("data-journal-id" in a or "data-config" in a or "num" in cls):
            it = {"tag": tag, "attrs": a, "class": cls, "text": ""}
            self.items.append(it)
            self.stack.append(it)
        elif tag not in VOID:
            self.stack.append(None)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if self.stack:
            self.stack.pop()

    def handle_data(self, data):
        self.text_all.append(data)
        for it in self.stack:
            if it is not None:
                it["text"] += data


def check_file(root, rel):
    full = paths.safe_join(root, rel)
    raw = paths.read_text(full)
    entries = journal_io.read_all(root)
    ix = pl.by_id(entries)
    cfg = pl.project_config(root)
    p = _P()
    p.feed(raw)
    errors, warns, numbers = [], [], []

    def err(code, msg, **kw):
        errors.append(dict({"code": code, "msg_es": msg}, **kw))

    if len(raw.encode("utf-8")) > MAX_BYTES:
        err("TOO_BIG", "el archivo pesa mas de 2 MB")
    if (p.lang or "").lower() != "es":
        err("NOT_SPANISH", "falta <html lang=\"es\">")
    if p.ext or re.search(r"@import|url\(\s*['\"]?https?:|<script[^>]+src=", raw, re.I):
        err("EXTERNAL_RESOURCE", "el panel pide recursos externos: debe ser un unico HTML sin internet", found=p.ext[:5])
    text_all = "".join(p.text_all)
    panel = p.panel or ""
    if panel == "viabilidad" and pl.SIGNATURE not in text_all:
        err("NO_SIGNATURE", "falta la firma «%s»" % pl.SIGNATURE)
    if (panel in pl.WATERMARKED or "data-watermark" in raw) and pl.WATERMARK not in text_all:
        err("NO_WATERMARK", "falta la marca «%s»" % pl.WATERMARK)
    for it in p.items:
        a, tag = it["attrs"], it["tag"]
        is_num = "num" in it["class"]
        shown = it["text"].strip()
        if "data-journal-id" in a:
            jid, fld, val = a["data-journal-id"], a.get("data-field", ""), a.get("data-value")
            rec = {"id": jid, "field": fld, "panel_value": val, "shown": shown if is_num else None, "journal_value": None, "ok": False}
            e = ix.get(jid)
            if e is None:
                err("JOURNAL_ID_MISSING", "el diario no tiene %s" % jid, id=jid)
            elif not fld or val is None:
                err("BAD_BINDING", "%s: faltan data-field/data-value" % jid, id=jid)
            else:
                try:
                    jv = pl.value_text(pl.getpath(e, fld), a.get("data-agg"))
                    rec["journal_value"] = jv
                    if jv != val:
                        err("VALUE_MISMATCH", "%s %s: panel=%s diario=%s" % (jid, fld, val, jv), id=jid, field=fld)
                    elif is_num and shown != val:
                        err("TEXT_MISMATCH", "%s %s: se muestra «%s» pero el valor es %s" % (jid, fld, shown, val), id=jid)
                    else:
                        rec["ok"] = True
                except (KeyError, TypeError):
                    err("FIELD_MISSING", "%s no tiene el campo %s" % (jid, fld), id=jid, field=fld)
            if is_num or tag in ("rect", "text"):
                numbers.append(rec)
        elif "data-config" in a:
            try:
                cv = str(pl.getpath(cfg, a["data-config"]))
            except KeyError:
                cv = None
            ok = cv == a.get("data-value") and (shown == cv)
            if not ok:
                err("CONFIG_MISMATCH", "%s: panel=%s config=%s" % (a["data-config"], a.get("data-value"), cv))
            numbers.append({"id": "config", "field": a["data-config"], "panel_value": a.get("data-value"), "shown": shown,
                            "journal_value": cv, "ok": ok})
        elif is_num:
            err("NUM_UNTRACED", "numero sin data-journal-id: «%s»" % shown, shown=shown)
    last = journal_io.last_id(root)
    m = re.search(r"hasta (J-\d{4,})", text_all)
    if m and last and m.group(1) != last:
        warns.append({"code": "STALE_PANEL", "msg_es": "el diario ya llega a %s y el panel a %s: regenera el panel" % (last, m.group(1))})
    mism = sum(1 for e in errors if e["code"] in ("VALUE_MISMATCH", "TEXT_MISMATCH", "JOURNAL_ID_MISSING", "FIELD_MISSING",
                                                  "NUM_UNTRACED", "CONFIG_MISMATCH", "BAD_BINDING"))
    return {"ok": not errors, "file": rel, "panel": panel, "errors": errors, "warnings": warns, "mismatches": mism,
            "numbers_checked": len(numbers), "numbers": numbers, "sha256": paths.sha256_file(full)}


def checklist(res):
    nums = [n for n in res["numbers"] if n["id"] != "config"]
    L = ["# Comprobacion manual de cifras — %s" % res["file"], "",
         "Abre `journal/journal.jsonl`, busca el identificador y confirma que la cifra coincide. Firma al final (%d cifras)." % len(nums), "",
         "| # | Cifra en el panel | Identificador | Campo | Valor en el diario | ✔ Laura |", "|---|---|---|---|---|---|"]
    for i, n in enumerate(nums, 1):
        L.append("| %d | %s | %s | %s | %s | ☐ |" % (i, n["panel_value"], n["id"], n["field"], n["journal_value"]))
    L += ["", "Firma de Laura: ____________  Fecha: ____________", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd")
    for n in ("check", "checklist"):
        s = sub.add_parser(n)
        s.add_argument("--file", default="08_paneles/panel_viabilidad.html")
        if n == "check":
            s.add_argument("--journal", action="store_true")
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 2
    try:
        root = paths.find_root(a.root)
        res = check_file(root, a.file)
    except (paths.ProjectNotFound, OSError, ValueError, journal_io.JournalError) as e:
        sys.stdout.write(json.dumps({"ok": False, "error_es": str(e)}, ensure_ascii=False) + "\n")
        return 2
    if a.cmd == "checklist":
        sys.stdout.write(checklist(res))
        return 0 if res["ok"] else 1
    if getattr(a, "journal", False):
        ts = paths.utc_now().replace(":", "").replace("-", "")
        base = os.path.splitext(os.path.basename(a.file))[0]
        rep = journal_io.make_script_report(root, SCRIPT, pl.unique_rel(root, "08_paneles/reports/%s_check_%s.json" % (base, ts)), "pass" if res["ok"] else "fail",
                                            details={"file": res["file"], "sha256": res["sha256"], "numbers_checked": res["numbers_checked"],
                                                     "mismatches": res["mismatches"]}, version=pl.VERSION)
        e = journal_io.add(root, {"stage": "C8", "type": "verification", "actor": "script", "gate_name": "G-C8",
                                  "gate": "pass" if res["ok"] else "fail",
                                  "what_es": "Comprobacion del panel %s: %d cifras, %d discrepancias" % (res["file"], res["numbers_checked"], res["mismatches"]),
                                  "tool": journal_io.tool_string(SCRIPT, pl.VERSION), "how_verified": "cada data-journal-id comparado con journal.jsonl",
                                  "human_decision": "n/a", "script_report": rep, "inputs": [journal_io.file_ref(root, res["file"])]})
        res["journal_id"] = e["id"]
    brief = {k: res[k] for k in ("ok", "file", "panel", "numbers_checked", "mismatches", "errors", "warnings")}
    if "journal_id" in res:
        brief["journal_id"] = res["journal_id"]
    sys.stdout.write(json.dumps(brief, ensure_ascii=False) + "\n")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
