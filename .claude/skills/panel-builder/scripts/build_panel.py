#!/usr/bin/env python3
"""build_panel.py --panel viabilidad|flow  [--root R] [--out PATH] [--no-check]

One self-contained Spanish HTML (inline CSS/SVG, no CDN, no external requests) built ONLY from journal/journal.jsonl
(+ config for thresholds). Every number is an element with data-journal-id / data-field / data-value; panel_check.py
compares each one with the journal (mismatch must be 0). No number comes from the conversation.

  viabilidad  phase 1: topic feasibility (RCT/year bars, SR 5y, CT, ClinicalTrials.gov, PROSPERO/Epistemonikos manual,
              criteria badges, query, date, journal ids). Signed «Sugerencia; decide Laura».
  flow        PRISMA flow from journal metrics flow_* — ALWAYS watermarked «PRELIMINAR — piloto, no forma parte del
              protocolo» (W-1: the protocol needs a selection PLAN, not results).
  busqueda, mapa, prisma_p: phase 2-3 (not implemented in phase 1).
"""
import argparse
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import panel_lib as pl  # noqa: E402
from panel_lib import journal_io, paths  # noqa: E402

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
esc = html.escape


def num(entry, field, value, cls="num"):
    """A traceable number. `entry` is the journal entry that holds it."""
    return ('<span class="%s" data-journal-id="%s" data-field="%s" data-value="%s" title="%s · %s">%s</span>'
            % (cls, entry["id"], esc(field), esc(str(value)), entry["id"], esc(str(entry.get("ts", ""))[:10]), esc(str(value))))


def cfg_num(path, value):
    return '<span class="num" data-config="%s" data-value="%s">%s</span>' % (esc(path), esc(str(value)), esc(str(value)))


def nodata(txt="sin datos"):
    return '<span class="nd">%s</span>' % esc(txt)


def count_of(e):
    return e["query"]["count"]


def bars_svg(entry, y_now):
    by = entry.get("by_year") or {}
    years = sorted(by, key=int)
    if not years:
        return nodata()
    mx = max([by[y] for y in years] + [1])
    w, h, bw, gap = 360, 120, 26, 6
    parts = ['<svg class="bars" viewBox="0 0 %d %d" role="img" aria-label="ECA por año">' % (w, h + 34)]
    for i, y in enumerate(years):
        v = by[y]
        bh = int(round(h * v / mx))
        x = 4 + i * (bw + gap)
        fld = "by_year.%s" % y
        parts.append('<rect class="bar%s" x="%d" y="%d" width="%d" height="%d" data-journal-id="%s" data-field="%s" data-value="%s"><title>%s: %s</title></rect>'
                     % (" part" if int(y) == int(entry.get("partial_year", -1)) else "", x, h - bh + 14, bw, bh, entry["id"],
                        esc(fld), v, y, v))
        parts.append('<text class="num lbl" x="%d" y="10" text-anchor="middle" data-journal-id="%s" data-field="%s" data-value="%s">%s</text>'
                     % (x + bw // 2, entry["id"], esc(fld), v, v))
        parts.append('<text class="yr" x="%d" y="%d" text-anchor="middle">%s</text>' % (x + bw // 2, h + 28, esc(y[2:])))
    parts.append("</svg>")
    return "".join(parts)


def criteria(cfg_f, rct, ct, decision):
    """-> (crit1 'ok'|'no'|'nd', crit2 'ok'|'no'|'pending')"""
    mn = cfg_f.get("min_rct_ct", 10)
    if rct is None and ct is None:
        c1 = "nd"
    else:
        c1 = "ok" if (rct is not None and count_of(rct) >= mn) or (ct is not None and count_of(ct) >= mn) else "no"
    if decision is None or decision.get("outcome") is None:
        c2 = "pending"
    else:
        c2 = "ok" if decision["outcome"] == "no_same_pico" else "no"
    return c1, c2


BADGE = {"ok": ("ok", "✔"), "no": ("no", "✖"), "nd": ("nd", "·"), "pending": ("nd", "⏳")}


def badge(state, text):
    cls, sym = BADGE[state]
    return '<span class="badge %s">%s %s</span>' % (cls, sym, text)


def manual_cell(e):
    if e is None:
        return nodata("pendiente: búsqueda manual de Laura")
    link = ""
    if e.get("url"):
        link = ' <a href="%s" target="_blank" rel="noopener">abrir</a>' % esc(e["url"], quote=True)
    return "%s <span class=\"muted\">(%s%s)</span>" % (num(e, "query.count", count_of(e)), esc(e["query"]["date"]), link)


def topic_data(entries, tid):
    g = lambda m, t="count": pl.latest(entries, tid, m, t)  # noqa: E731
    return {"total": g("total"), "rct": g("rct_10y"), "ct": g("ct"), "sr": g("sr_5y"), "reg": g("ctgov_records"),
            "pros": g("prospero"), "epi": g("epistemonikos"), "ictrp": g("who_ictrp"),
            "qc": pl.latest(entries, tid, None, "query_check"),
            "dec": pl.latest(entries, tid, None, "decision", kind="same_pico_sr"),
            "choice": pl.latest(entries, tid, None, "decision", kind="topic_choice")}


def card(tid, title, d, cfg_f, y_now):
    c1, c2 = criteria(cfg_f, d["rct"], d["ct"], d["dec"])
    feas = "ok" if (c1 == "ok" and c2 == "ok") else ("no" if "no" in (c1, c2) else "nd")
    L = ['<article class="card" data-topic="%s">' % esc(tid), "<h3>%s <span class=\"muted\">%s</span></h3>" % (esc(tid), esc(title))]
    L.append('<div class="grid">')
    for label, key, fld in (("PubMed total", "total", "query.count"), ("ECA 10 años", "rct", "query.count"),
                            ("Ensayos clínicos", "ct", "query.count"), ("RS 5 años", "sr", "query.count"),
                            ("ClinicalTrials.gov", "reg", "query.count")):
        e = d[key]
        L.append('<div class="kpi"><span class="k">%s</span><b>%s</b></div>' % (label, num(e, fld, count_of(e)) if e else nodata()))
    L.append("</div>")
    L.append('<h4>ECA por año</h4>%s<p class="muted">El último año está incompleto.</p>' % (bars_svg(d["rct"], y_now) if d["rct"] else nodata()))
    L.append('<h4>Registros manuales (Laura)</h4><ul class="plain"><li>PROSPERO: %s</li><li>Epistemonikos: %s</li><li>WHO ICTRP: %s</li></ul>'
             % (manual_cell(d["pros"]), manual_cell(d["epi"]), manual_cell(d["ictrp"])))
    L.append('<h4>Criterios (por defecto; pendiente de validar con tutor)</h4><p>')
    mn_text = "≥ %s ECA/ensayos" % cfg_num("feasibility.min_rct_ct", cfg_f.get("min_rct_ct", 10))
    L.append(badge(c1, mn_text) + " ")
    if d["dec"]:
        L.append(badge(c2, "sin RS con el mismo PICO <span class=\"muted\">(decide Laura, %s)</span>" % d["dec"]["id"]) + " ")
    else:
        L.append(badge(c2, "sin RS con el mismo PICO: <i>decide Laura</i>") + " ")
    L.append(badge(feas, {"ok": "cumple los criterios", "no": "no cumple", "nd": "pendiente"}[feas]) + "</p>")
    if d["qc"]:
        q = d["qc"]["query_check"]
        L.append('<p class="muted">Comprobación de la ecuación (%s): <span class="num" data-journal-id="%s" data-field="query_check.errors" data-agg="len" data-value="%d">%d</span> errores, '
                 '<span class="num" data-journal-id="%s" data-field="query_check.warnings" data-agg="len" data-value="%d">%d</span> avisos.</p>'
                 % (d["qc"]["id"], d["qc"]["id"], len(q["errors"]), len(q["errors"]), d["qc"]["id"], len(q["warnings"]), len(q["warnings"])))
    else:
        L.append('<p class="muted">Ecuación sin comprobar (query_check): %s</p>' % nodata())
    if d["total"]:
        qs = d["total"]["query"]
        L.append('<details><summary>Ecuación y fecha</summary><pre data-journal-id="%s" data-field="query.string" data-value="%s">%s</pre>'
                 '<p>Consultada el %s · <a href="https://pubmed.ncbi.nlm.nih.gov/?term=%s" target="_blank" rel="noopener">abrir en PubMed</a></p></details>'
                 % (d["total"]["id"], esc(qs["string"], quote=True), esc(qs["string"]), esc(qs["date"]),
                    esc(__import__("urllib.parse").parse.quote_plus(qs["string"]))))
    L.append("</article>")
    return "\n".join(L), {"c1": c1, "c2": c2, "feas": feas}


def build_viabilidad(root, entries):
    cfg = pl.project_config(root)
    cfg_f = cfg.get("feasibility") or {}
    y_now = int(paths.today()[:4])
    topics = pl.topic_ids(root, entries)
    topics = [(i, t) for i, t in topics if any(e.get("topic_id") == i for e in entries)]
    cards, rows, ev = [], [], {}
    for tid, title in topics:
        d = topic_data(entries, tid)
        html_card, st = card(tid, title, d, cfg_f, y_now)
        cards.append(html_card)
        ev[tid] = (d, st)
        cell = lambda k: (num(d[k], "query.count", count_of(d[k])) if d[k] else nodata())  # noqa: E731
        rows.append("<tr><th>%s</th><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
                    % (esc(tid), cell("rct"), cell("ct"), cell("sr"), cell("reg"),
                       manual_cell(d["pros"]), badge(st["feas"], {"ok": "cumple", "no": "no cumple", "nd": "pendiente"}[st["feas"]])))
    if not topics:
        body = "<p>%s Aún no hay conteos en el diario: ejecuta <code>topic_counts.py run</code> (o regístralos a mano).</p>" % nodata("sin datos")
        table = ""
        story = "<p><b>Insight:</b> sin datos, no hay recomendación.</p>"
    else:
        body = "\n".join(cards)
        table = ('<table class="cmp"><thead><tr><th>Tema</th><th>ECA 10 años</th><th>Ensayos clínicos</th><th>RS 5 años</th>'
                 '<th>ClinicalTrials.gov</th><th>PROSPERO</th><th>Criterios</th></tr></thead><tbody>%s</tbody></table>' % "".join(rows))
        ok = [(tid, d) for tid, (d, st) in ev.items() if st["c1"] == "ok" and st["c2"] != "no" and d["rct"]]
        if ok:
            tid, d = sorted(ok, key=lambda x: -count_of(x[1]["rct"]))[0]
            pend = ev[tid][1]["c2"] == "pending"
            story = ('<p><b>Insight:</b> %s reúne %s ECA en 10 años y %s revisiones sistemáticas en 5 años.</p>'
                     % (esc(tid), num(d["rct"], "query.count", count_of(d["rct"])),
                        num(d["sr"], "query.count", count_of(d["sr"])) if d["sr"] else nodata()))
            story += ('<p><b>Recomendación:</b> <span class="sig">%s</span> — %s tiene más ECA entre los temas que cumplen el criterio de cantidad%s.</p>'
                      % (pl.SIGNATURE, esc(tid), "; falta tu decisión sobre «mismo PICO»" if pend else ""))
        else:
            story = ('<p><b>Insight:</b> ningún tema cumple todavía el criterio de cantidad con datos registrados.</p>'
                     '<p><b>Recomendación:</b> <span class="sig">%s</span> — sin datos suficientes no hay recomendación.</p>' % pl.SIGNATURE)
    last = journal_io.last_id(root) or "—"
    return {"BODY": body, "TABLE": table, "STORY": story, "LAST_ID": last, "TITLE": "Panel de viabilidad de temas"}


def build_flow(root, entries):
    boxes, miss = [], []
    for metric, label in pl.FLOW_METRICS:
        e = None
        for x in entries:
            if x.get("metric") == metric and x.get("type") == "count":
                e = x
        if e is None:
            miss.append(label)
            boxes.append('<div class="box">%s<br>%s</div>' % (esc(label), nodata()))
        else:
            boxes.append('<div class="box">%s<br><b>%s</b></div>' % (esc(label), num(e, "query.count", count_of(e))))
    body = ('<div class="wm">%s</div><div class="flow">%s</div><p class="muted">Cifras del piloto registradas en el diario. %s</p>'
            % (esc(pl.WATERMARK), '<div class="arrow">↓</div>'.join(boxes),
               ("Faltan: " + ", ".join(miss)) if miss else ""))
    return {"BODY": body, "TABLE": "", "STORY": "", "LAST_ID": journal_io.last_id(root) or "—", "TITLE": "Flujo PRISMA (piloto)"}


def render(panel, parts, root):
    tpl = paths.read_text(os.path.join(TEMPLATE_DIR, "panel_viabilidad_skeleton.html"))
    note = ("Sugerencia; decide Laura. Cada número lleva el identificador del diario (pasa el ratón). Panel generado el %s a partir de journal.jsonl hasta %s."
            % (paths.utc_now(), parts["LAST_ID"]))
    out_ = (tpl.replace("{{TITLE}}", esc(parts["TITLE"])).replace("{{PANEL}}", panel).replace("{{TABLE}}", parts["TABLE"])
            .replace("{{STORY}}", parts["STORY"]).replace("{{BODY}}", parts["BODY"]).replace("{{LAST_ID}}", esc(parts["LAST_ID"]))
            .replace("{{NOTE}}", esc(note)))
    if panel in pl.WATERMARKED:
        out_ = out_.replace("<body", '<body data-watermark="1"', 1)
    return out_


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("--panel", required=True)
    ap.add_argument("--out")
    ap.add_argument("--no-check", action="store_true")
    a = ap.parse_args(argv)
    if a.panel in pl.PANELS_LATER:
        sys.stdout.write(json.dumps({"ok": False, "error_es": "El panel «%s» es de la fase 2–3 y todavía no existe." % a.panel}, ensure_ascii=False) + "\n")
        return 2
    if a.panel not in pl.PANELS_NOW:
        sys.stdout.write(json.dumps({"ok": False, "error_es": "panel desconocido: %s" % a.panel}, ensure_ascii=False) + "\n")
        return 2
    try:
        root = paths.find_root(a.root)
        entries = journal_io.read_all(root)
        parts = build_viabilidad(root, entries) if a.panel == "viabilidad" else build_flow(root, entries)
        rel = a.out or "08_paneles/panel_%s.html" % ("viabilidad" if a.panel == "viabilidad" else "prisma_flow")
        text = render(a.panel, parts, root)
        paths.write_text_atomic(paths.safe_join(root, rel), text)
    except (paths.ProjectNotFound, OSError, journal_io.JournalError, ValueError) as e:
        sys.stdout.write(json.dumps({"ok": False, "error_es": str(e)}, ensure_ascii=False) + "\n")
        return 2
    res = {"ok": True, "file": rel, "panel": a.panel, "bytes": len(text.encode("utf-8")), "journal_last_id": parts["LAST_ID"]}
    if not a.no_check:
        import panel_check
        chk = panel_check.check_file(root, rel)
        res["panel_check"] = {"ok": chk["ok"], "numbers_checked": chk["numbers_checked"], "mismatches": chk["mismatches"],
                              "errors": chk["errors"][:10]}
        res["ok"] = chk["ok"]
    sys.stdout.write(json.dumps(res, ensure_ascii=False) + "\n")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
