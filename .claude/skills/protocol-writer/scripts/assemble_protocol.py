#!/usr/bin/env python3
"""assemble_protocol.py: build the PRISMA-P protocol from 06_protocolo/drafts/*.md (C6). Euneiz format: TNR 12, 1.5.

  init-skeleton                       create missing drafts from templates/protocol_skeleton_es.md as [draft-ai]
  mark-reviewed --section S --laura-confirmed    [draft-ai] -> [author-reviewed] (Laura's decision, journaled)
  mark-final    --section S --laura-confirmed    [author-reviewed] -> [final]
  assemble [--style vancouver|apa|harvard] [--docx] [--placement anexo|metodologia] [--release]
           [--title T --author A --supervisor S --institution I --date D]
  check [--journal]                   gate G-C6 (exit 1 if not met); release_ready is reported separately
The mandatory section «Declaración de uso de inteligencia artificial» is rendered by declaration.render_section (F-08).
"""
import argparse
import json
import os
import re
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
import protocol_lib as L  # noqa: E402  (sets up _common path)
from _common import config, integrity_core, journal_io, paths  # noqa: E402
import docx_export  # noqa: E402

VERSION = L.VERSION
OUT_MD = L.EXPORT + "/protocolo_ensamblado_es.md"
OUT_DOCX = L.EXPORT + "/protocolo_ensamblado_es.docx"
CITE = re.compile(r"\[ref:([^\]|]+)(?:\|[^\]]*)?\]")


def out(o):
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")


def _tool():
    return journal_io.tool_string("assemble_protocol.py", VERSION)


def _stamp():
    return paths.utc_now().replace(":", "").replace("-", "")


# ---- drafts -------------------------------------------------------------------------------------
def init_skeleton(root):
    blocks = L.template_blocks()
    missing = [s for s in L.SECTION_IDS if s not in blocks]
    if missing:
        raise ValueError("la plantilla no tiene bloques para: %s" % missing)
    created = []
    for sid in L.SECTION_IDS:
        p = paths.safe_join(root, L.draft_rel(sid))
        if p.is_file() and p.stat().st_size > 0:
            continue
        paths.write_text_atomic(p, L.join_marker("draft-ai", blocks[sid]))
        created.append(sid)
    e = None
    if created:
        e = journal_io.add(root, {"stage": "C6", "type": "change", "actor": "claude", "advisory": True, "tool": _tool(),
                                  "what_es": "Esqueleto del protocolo creado a partir de la plantilla (instrucciones [PENDIENTE], sin contenido): " + ", ".join(created),
                                  "human_decision": "pendiente", "outputs": [journal_io.file_ref(root, L.draft_rel(s)) for s in created]})
    return {"created": created, "journal_id": e["id"] if e else None}


def _set_marker(root, sid, new_marker, kind, what_es):
    marker, body = L.read_draft(root, sid)
    if body is None:
        raise ValueError("no existe el borrador %s" % sid)
    rel = L.draft_rel(sid)
    prev = "%s/%s_%s.md" % (L.VERSIONS, sid, _stamp())
    paths.write_text_atomic(paths.safe_join(root, prev), paths.read_text(paths.safe_join(root, rel)))
    paths.write_text_atomic(paths.safe_join(root, rel), L.join_marker(new_marker, body))
    return journal_io.add(root, {"stage": "C6", "type": "decision", "actor": "laura", "kind": kind, "section": sid,
                                 "what_es": what_es, "body_sha256": L.body_sha(body), "previous_version": prev,
                                 "human_decision": "aprobado por Laura", "tool": _tool(),
                                 "outputs": [journal_io.file_ref(root, rel)]})


def mark_reviewed(root, sid):
    st = L.review_state(root, sid)
    marker, body = L.read_draft(root, sid)
    if body is None:
        raise ValueError("no existe el borrador %s" % sid)
    if marker != "draft-ai":
        raise ValueError("el borrador está en estado [%s]" % marker)
    if L.PLACEHOLDER in body:
        raise ValueError("quedan marcas [PENDIENTE] en %s: no se puede marcar como revisada" % sid)
    return _set_marker(root, sid, "author-reviewed", "author_reviewed", "Laura revisó y reescribió con sus palabras la sección «%s»" % L.TITLES[sid])


def mark_final(root, sid):
    st = L.review_state(root, sid)
    if st["marker"] != "author-reviewed" or not st["valid"]:
        raise ValueError("solo se puede cerrar una sección [author-reviewed] válida (%s)" % st["reason"])
    return _set_marker(root, sid, "final", "section_final", "Laura cierra la sección «%s» como definitiva" % L.TITLES[sid])


# ---- composition ----------------------------------------------------------------------------------
def ia_paragraph(root, decl, where):
    uses = decl.ai_uses(root)
    if not uses:
        return "Hasta la fecha no se ha registrado ningún uso de herramientas de inteligencia artificial en la elaboración de este protocolo. La declaración completa figura en %s." % where
    tools = sorted({e["tool"] for e in uses})
    stages = []
    for e in uses:
        s = "%s (%s)" % (e["stage"], decl.STAGES_ES.get(e["stage"], ""))
        if s not in stages:
            stages.append(s)
    return ("En la elaboración de este protocolo se han utilizado herramientas de inteligencia artificial (%s) como apoyo en las etapas: %s. "
            "Cada uso queda registrado en el diario del proyecto; su descripción, la forma de verificarlo, la decisión humana y la justificación de su utilidad "
            "para la investigación figuran en la «%s» (%s)." % ("; ".join(tools), "; ".join(stages), L.DECL_TITLE, where))


def compose(root, style, meta, placement="anexo", number_citations=False):
    decl = L.load_declaration()
    if decl is None:
        raise RuntimeError("no encuentro declaration.py del orquestador (skill tfm-orchestrator); sin ella no se puede insertar la declaración de IA")
    bodies, states = {}, {}
    for sid in L.SECTION_IDS:
        states[sid] = L.review_state(root, sid)
        marker, body = L.read_draft(root, sid)
        bodies[sid] = body if body is not None else "[PENDIENTE: falta el borrador %s]" % sid
    pending_portada = [k for k in ("title", "author", "supervisor") if not meta.get(k)]
    P = lambda k, d: meta.get(k) or "[PENDIENTE: %s]" % d  # noqa: E731
    not_reviewed = [s for s in L.SECTION_IDS if states[s]["marker"] not in ("author-reviewed", "final") or not states[s]["valid"]]
    blocks = []
    if not_reviewed:
        blocks.append(("banner", "BORRADOR: secciones aún sin revisar por la autora (%s). No entregar." % ", ".join(not_reviewed)))
    blocks += [("title", P("title", "título del protocolo")), ("center", "Protocolo de revisión sistemática (PRISMA-P)"),
               ("center", "Autora: " + P("author", "nombre de Laura")), ("center", "Tutor/a: " + P("supervisor", "nombre del tutor/a")),
               ("center", meta.get("institution") or "Euneiz"), ("center", meta.get("date") or paths.today()), ("pagebreak",), ("toc",), ("pagebreak",)]
    where_annex = "Anexo B"
    where_met = "apartado «Declaración de uso de inteligencia artificial» de la Metodología"
    H = []     # headings for the static index
    body_blocks = []

    def h(level, text):
        H.append((level, text))
        body_blocks.append(("h", level, text))

    def md(sid):
        body_blocks.append(("md", bodies[sid]))

    h(1, "Resumen"); md("resumen")
    h(1, "Información administrativa"); md("administrativo")
    h(1, "Introducción"); md("introduccion")
    h(1, "Objetivos y metodología")
    h(2, "Objetivos"); md("objetivos")
    h(2, "Metodología")
    for sid in ("met_elegibilidad", "met_fuentes", "met_busqueda", "met_seleccion", "met_extraccion", "met_sesgo", "met_sintesis"):
        h(3, L.TITLES[sid]); md(sid)
    h(3, "Uso de herramientas de inteligencia artificial")
    body_blocks.append(("md", ia_paragraph(root, decl, where_annex if placement == "anexo" else where_met)))
    if placement == "metodologia":
        sec = decl.render_section(root, 3)
        H.append((3, L.DECL_TITLE))
        body_blocks.append(("md", sec))
    h(1, "Resultados esperados"); md("resultados")
    h(1, "Conclusiones"); md("conclusiones")
    h(1, "Bibliografía")
    body_blocks.append(("md", "Estilo de citación: %s%s.\n" % (style.capitalize(), " (provisional, hasta recibir la guía docente)" if
                                                                  config.load_config(root).get("citation_style_status") == "provisional" else "")))
    md("bibliografia")
    h(1, "Anexos")
    h(2, L.TITLES["anexo_a_busqueda"]); md("anexo_a_busqueda")
    if placement == "anexo":
        sec = decl.render_section(root, 2)
        first, _, rest = sec.partition("\n")
        sec = "## Anexo B. " + first.lstrip("# ").strip() + "\n" + rest
        H.append((2, "Anexo B. " + L.DECL_TITLE))
        body_blocks.append(("md", sec))
    cmap = {}
    if number_citations:
        if style != "vancouver":
            raise ValueError("la numeración automática solo está implementada para Vancouver; en %s usa ref_style.py del verifier" % style)

        def sub(m):
            return "[%d]" % cmap.setdefault(m.group(1).strip(), len(cmap) + 1)
        body_blocks = [(b[0], CITE.sub(sub, b[1])) if b[0] == "md" else b for b in body_blocks]
    return blocks + body_blocks, {"pending_portada": pending_portada, "not_reviewed": not_reviewed, "citation_map": cmap, "headings": H}


def render_md(blocks, info, digest, style):
    o = ["<!-- assembled: drafts_digest=%s style=%s ts=%s tool=assemble_protocol.py v%s -->" % (digest, style, paths.utc_now(), VERSION), ""]
    for b in blocks:
        k = b[0]
        if k == "banner":
            o += ["**%s**" % b[1], ""]
        elif k == "title":
            o += ["**%s**" % b[1].upper(), ""]
        elif k == "center":
            o += [b[1], ""]
        elif k == "pagebreak":
            o += ["<!-- pagebreak -->", ""]
        elif k == "toc":
            o += ["**Índice**", "", "<!-- toc -->"]
            o += ["%s- %s" % ("  " * (lvl - 1), t) for lvl, t in info["headings"]]
            o += ["<!-- /toc -->", ""]
        elif k == "h":
            o += ["#" * b[1] + " " + b[2], ""]
        elif k == "md":
            o += [b[1].strip("\n"), ""]
    if info["citation_map"]:
        o.append("<!-- citation-map: %s -->" % json.dumps(info["citation_map"], ensure_ascii=False))
    return "\n".join(o) + "\n"


def assemble(root, style=None, docx=False, placement="anexo", release=False, meta=None):
    cfg = config.load_config(root)
    style = (style or cfg.get("citation_style") or "vancouver").lower()
    if style not in L.STYLES:
        raise ValueError("estilo no válido: %s" % style)
    res = {"ok": True, "warnings": []}
    if release:
        c = check(root)
        if not (c["ok"] and c["release_ready"]):
            return {"ok": False, "error": "release bloqueado", "issues": c["issues"] + c["unreviewed"]}
    blocks, info = compose(root, style, meta or {}, placement, number_citations=release)
    digest = L.drafts_digest(root)
    text = render_md(blocks, info, digest, style)
    paths.write_text_atomic(paths.safe_join(root, OUT_MD), text)
    outputs = [OUT_MD]
    if docx:
        if docx_export.available():
            docx_export.write_docx(blocks, paths.safe_join(root, OUT_DOCX))
            outputs.append(OUT_DOCX)
        else:
            res["warnings"].append("python-docx no está disponible: se entrega Markdown. Pide a Claude que lo convierta con su habilidad docx (TNR 12, interlineado 1,5) o pégalo en Word con ese formato.")
    if style != "vancouver" or cfg.get("citation_style_status") == "provisional":
        res["warnings"].append("estilo de citación %s%s" % (style, " (provisional hasta la guía docente)" if cfg.get("citation_style_status") == "provisional" else ""))
    if info["pending_portada"]:
        res["warnings"].append("portada incompleta: %s" % info["pending_portada"])
    e = journal_io.add(root, {"stage": "C6", "type": "change", "actor": "script", "tool": _tool(), "human_decision": "n/a",
                              "what_es": "Protocolo ensamblado desde los borradores (%s)%s" % (", ".join(outputs), " [versión de entrega]" if release else " [borrador]"),
                              "drafts_digest": digest, "outputs": [journal_io.file_ref(root, r) for r in outputs]})
    res.update({"outputs": outputs, "journal_id": e["id"], "not_reviewed": info["not_reviewed"], "drafts_digest": digest})
    return res


# ---- gate G-C6 --------------------------------------------------------------------------------------
def assembled_status(root, decl):
    issues = []
    p = paths.safe_join(root, OUT_MD)
    if not p.is_file():
        return ["protocolo no ensamblado (ejecutar assemble)"]
    t = paths.read_text(p)
    m = re.search(r"drafts_digest=([0-9a-f]{64})", t)
    if not m or m.group(1) != L.drafts_digest(root):
        issues.append("el protocolo ensamblado está desactualizado respecto a los borradores")
    if L.DECL_TITLE not in t:
        issues.append("el documento no contiene la sección «%s» (Normativa Euneiz 2.4)" % L.DECL_TITLE)
    else:
        uses = decl.ai_uses(root)
        last = uses[-1]["id"] if uses else "J-0000"
        h = re.search(r"Hasta: (J-\d+)", t)
        if not h or h.group(1) < last:
            issues.append("la declaración dentro del documento es más antigua que el último ai_use (%s)" % last)
        just = decl.read_justification(paths.read_text(paths.Paths(root).declaration)) if paths.Paths(root).declaration.is_file() else ""
        if not decl.is_filled(just) or just not in t:
            issues.append("el documento no contiene la justificación de la utilidad escrita por Laura")
    if "Uso de herramientas de inteligencia artificial" not in t:
        issues.append("falta el párrafo «Uso de herramientas de inteligencia artificial» en la metodología")
    return issues


def check(root):
    issues, unreviewed, rows = [], [], []
    for sid in L.SECTION_IDS:
        st = L.review_state(root, sid)
        marker, body = L.read_draft(root, sid)
        row = {"section": sid, "marker": st["marker"], "valid": st["valid"]}
        rows.append(row)
        if body is None:
            issues.append("falta el borrador de «%s»" % L.TITLES[sid])
            continue
        if not body.strip():
            issues.append("sección vacía: %s" % sid)
        if L.PLACEHOLDER in body:
            issues.append("sección con marcas [PENDIENTE]: %s" % sid)
        if not st["valid"]:
            issues.append("%s: %s" % (sid, st["reason"]))
        if sid == "resumen" and L.resumen_lines(body) > L.RESUMEN_MAX_LINES:
            issues.append("el resumen supera %d líneas (estimadas %d)" % (L.RESUMEN_MAX_LINES, L.resumen_lines(body)))
        if st["marker"] not in ("author-reviewed", "final") or not st["valid"]:
            unreviewed.append(sid)
    covered = {i for s in L.SECTIONS for i in s[3]}
    miss = [i for i in L.PRISMA_P_ITEMS if i not in covered]
    if miss:
        issues.append("ítems PRISMA-P sin sección: %s" % miss)
    # versions (100% of edits keep the previous version)
    for sid in L.SECTION_IDS:
        for e in journal_io.find_for_path(root, L.draft_rel(sid)):
            pv = e.get("previous_version")
            if e.get("kind") in ("edit", "author_reviewed", "section_final") and (not pv or not paths.safe_join(root, pv).is_file()):
                issues.append("%s: la entrada %s no conserva la versión anterior en versions/" % (sid, e["id"]))
    for b in integrity_core.check(root)["blockers"]:
        if b["code"].startswith("TRACKED_"):
            issues.append("integridad: %s %s" % (b["code"], b["path"]))
    decl = L.load_declaration()
    decl_state = {}
    if decl is None:
        issues.append("falta declaration.py (skill tfm-orchestrator)")
    else:
        decl_state = decl.check(root)
        issues += ["declaración IA: " + i for i in decl_state["issues"]]
        issues += assembled_status(root, decl)
    return {"ok": not issues, "issues": issues, "sections": rows, "unreviewed": unreviewed,
            "release_ready": not issues and not unreviewed, "declaration": decl_state,
            "citation_style": config.load_config(root).get("citation_style")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-skeleton")
    for n in ("mark-reviewed", "mark-final"):
        s = sub.add_parser(n)
        s.add_argument("--section", required=True, choices=L.SECTION_IDS)
        s.add_argument("--laura-confirmed", action="store_true")
    a_ = sub.add_parser("assemble")
    a_.add_argument("--style", choices=L.STYLES)
    a_.add_argument("--docx", action="store_true")
    a_.add_argument("--placement", choices=["anexo", "metodologia"], default="anexo")
    a_.add_argument("--release", action="store_true")
    for k in ("title", "author", "supervisor", "institution", "date"):
        a_.add_argument("--" + k)
    c = sub.add_parser("check")
    c.add_argument("--journal", action="store_true")
    a = ap.parse_args(argv)
    try:
        root = paths.find_root(a.root)
    except paths.ProjectNotFound as e:
        out({"ok": False, "error": str(e)})
        return 2
    if config.get_mode(root) in ("LITE-b", "LITE-P"):
        out({"ok": False, "error": "modo %s: sin scripts; ensambla a mano con la lista de comprobación del SKILL.md" % config.get_mode(root)})
        return 2
    try:
        if a.cmd == "init-skeleton":
            out(dict(ok=True, **init_skeleton(root)))
            return 0
        if a.cmd in ("mark-reviewed", "mark-final"):
            if not a.laura_confirmed:
                out({"ok": False, "error": "falta --laura-confirmed: solo Laura cambia esta etiqueta"})
                return 1
            e = (mark_reviewed if a.cmd == "mark-reviewed" else mark_final)(root, a.section)
            out({"ok": True, "journal_id": e["id"]})
            return 0
        if a.cmd == "assemble":
            meta = {k: getattr(a, k) for k in ("title", "author", "supervisor", "institution", "date")}
            r = assemble(root, a.style, a.docx, a.placement, a.release, meta)
            out(r)
            return 0 if r["ok"] else 1
        r = check(root)
        if a.journal:
            ts = _stamp()
            ref = journal_io.make_script_report(root, "assemble_protocol.py", "07_verificacion/reports/g_c6_%s.json" % ts,
                                                "pass" if r["ok"] else "fail", details={"issues": r["issues"], "unreviewed": r["unreviewed"]}, version=VERSION)
            e = journal_io.add(root, {"stage": "C6", "type": "verification", "actor": "script", "gate_name": "G-C6", "gate": "pass" if r["ok"] else "fail",
                                      "script_report": ref, "tool": _tool(), "human_decision": "n/a",
                                      "what_es": "Puerta G-C6 (protocolo): %s" % ("cumplida" if r["ok"] else "no cumplida (%d problemas)" % len(r["issues"]))})
            r["journal_id"] = e["id"]
        out(r)
        return 0 if r["ok"] else 1
    except (journal_io.JournalError, ValueError, RuntimeError) as ex:
        out({"ok": False, "errors": getattr(ex, "errors", [str(ex)])})
        return 1


if __name__ == "__main__":
    sys.exit(main())
