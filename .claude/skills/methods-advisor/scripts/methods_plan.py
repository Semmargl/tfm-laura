#!/usr/bin/env python3
"""methods_plan.py: C5 planning helper (no RoB assessment, no network).

  tools [--design D | --topic T]            list applicable tools (JSON)
  plan --designs rct,nrsi [--exercise yes]  write 05_metodos/{extraccion,rob_grade,sintesis}_es.md (options, nothing chosen)
  record-choice --topic rob:rct --tool rob2 [--pedro use|skip] --laura-confirmed [--note ..]
  confirm-source --choice J-0007 --laura-confirmed
  check [--journal]                         gate G-C5 (exit 1 if not met)
A choice is Laura's: the journal entry is a `decision` with actor laura; --laura-confirmed states that she said it.
"""
import argparse
import json
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
if not os.path.isdir(os.path.join(_here, "_common")):      # dev layout: skills/_common next to the skill folder
    sys.path.insert(1, os.path.dirname(os.path.dirname(_here)))
from _common import journal_io, paths, config  # noqa: E402
import methods_data as D  # noqa: E402

VERSION = "1.0"
PLAN_REL = "05_metodos/plan.json"
FILES = {"extraccion_es.md": "extraction", "rob_grade_es.md": "rob_grade", "sintesis_es.md": "synthesis"}
STAMP = "[draft-ai]"


def out(o):
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")


def _tool_line(tid):
    t = D.TOOLS[tid]
    return "- **%s** (`%s`): %s Fuente: %s · fecha de verificación: [PENDIENTE]" % (t["name"], tid, t["note_es"], t["url"])


def _tpl(name):
    p = os.path.join(os.path.dirname(_here), "templates", name)
    with open(p, encoding="utf-8") as f:
        return f.read().replace("\r\n", "\n")


def render_rob_grade(designs, exercise):
    L = [STAMP, "", "# Riesgo de sesgo, certeza (GRADE) y herramientas — opciones", "",
         "Documento de planificación del protocolo. **No se valora aquí el riesgo de sesgo de ningún estudio.** "
         "Las herramientas siguientes son opciones; la elección es de Laura (queda registrada en el diario).", ""]
    for d in designs:
        L += ["## Diseño: %s" % D.DESIGNS.get(d, d), ""]
        L += [_tool_line(t) for t in D.tools_for("rob:" + d)] or ["- (sin herramienta catalogada: consultar a la tutora)"]
        if d == "rct":
            L += ["", "**PEDro frente a RoB 2.** PEDro puntúa la calidad metodológica de ensayos de fisioterapia; no es una "
                  "herramienta de riesgo de sesgo en sentido estricto y no sustituye a RoB 2. Laura decide si la usa como complemento.", ""]
        L += ["", "Herramienta elegida: [PENDIENTE: la elige Laura]", ""]
    L += ["## Certeza de la evidencia", ""] + [_tool_line("grade"), "", "Decisión sobre GRADE: [PENDIENTE: la toma Laura]", "",
          "| Desenlace | Diseño de partida | Riesgo de sesgo | Inconsistencia | Evidencia indirecta | Imprecisión | Sesgo de publicación | Certeza |",
          "|---|---|---|---|---|---|---|---|", "| [PENDIENTE: desenlace del PICO] | | | | | | | (se valora al ejecutar la revisión, no en el protocolo) |", ""]
    L += ["## Lista de comprobación G-C5 (modo LITE: la firma Laura)", ""]
    L += ["- [ ] Cada diseño tiene herramienta elegida por Laura, con su fuente abierta y fecha.",
          "- [ ] PEDro: decisión de Laura anotada (complemento / no usar).",
          "- [ ] Elección de GRADE y de síntesis anotadas.", "- [ ] Firma y fecha de Laura: ____________", ""]
    return "\n".join(L)


def render_extraction(exercise):
    L = [STAMP, "", "# Formulario de extracción de datos — borrador", "",
         "Campos propuestos; Laura los ajusta con su tutora. Los datos se extraerán durante la revisión, no en el protocolo.", "",
         "| Campo | Contenido |", "|---|---|"]
    for f in ("Identificador del estudio (ref_id)", "Diseño del estudio", "País y contexto", "Población (tamaño, edad, condición)",
              "Intervención y comparador", "Desenlaces y momentos de medición", "Resultados principales (con unidad)",
              "Pérdidas y abandonos", "Fuente de financiación", "Notas de la revisora"):
        L.append("| %s | |" % f)
    if exercise:
        L += ["", "## Descripción del ejercicio (TIDieR / CERT)", "", _tool_line("tidier"), _tool_line("cert"), "",
              "Elección de Laura (TIDieR / CERT / ambas): [PENDIENTE: la elige Laura]", "",
              "| Elemento | Qué se extrae |", "|---|---|"]
        for e in ("Nombre y justificación", "Materiales", "Procedimientos y pautas", "Quién lo aplica (formación)", "Modo de entrega (individual/grupo, supervisado o no)",
                  "Lugar", "Cuándo y cuánto (frecuencia, duración, intensidad, progresión)", "Adaptación", "Modificaciones durante el estudio", "Fidelidad / adherencia"):
            L.append("| %s | |" % e)
    L.append("")
    return "\n".join(L)


def render_synthesis():
    return "\n".join([STAMP, "", "# Plan de síntesis — opciones", "",
                      "El protocolo debe fijar de antemano cómo se sintetizarán los resultados. Opciones:", "",
                      _tool_line("swim_narrative"), _tool_line("meta_analysis"), "",
                      "Decisiones que toma Laura con su tutora (no las toma Claude):", "",
                      "- [ ] Criterio para decidir si se combinan estudios: [PENDIENTE]",
                      "- [ ] Medida del efecto y modelo (si hay metaanálisis): [PENDIENTE]",
                      "- [ ] Evaluación de la heterogeneidad: [PENDIENTE]",
                      "- [ ] Análisis de subgrupos o sensibilidad: [PENDIENTE]", ""])


def cmd_plan(root, a):
    designs = [d.strip() for d in a.designs.split(",") if d.strip()]
    bad = [d for d in designs if d not in D.DESIGNS]
    if bad or not designs:
        out({"ok": False, "error": "diseños no válidos: %s (válidos: %s)" % (bad, ", ".join(D.DESIGNS))})
        return 1
    exercise = a.exercise == "yes"
    texts = {"extraccion_es.md": render_extraction(exercise), "rob_grade_es.md": render_rob_grade(designs, exercise),
             "sintesis_es.md": render_synthesis()}
    written, skipped = [], []
    for name, text in texts.items():
        rel = "05_metodos/" + name
        full = paths.safe_join(root, rel)
        if full.exists():
            if not a.force:
                skipped.append(rel)
                continue
            old = paths.read_text(full)
            paths.write_text_atomic(paths.safe_join(root, "05_metodos/versions/%s_%s.md" % (name[:-3], paths.utc_now().replace(":", ""))), old)
        paths.write_text_atomic(full, text)
        written.append(rel)
    paths.write_text_atomic(paths.safe_join(root, PLAN_REL), json.dumps({"designs": designs, "exercise": exercise}, ensure_ascii=False, indent=1) + "\n")
    e = journal_io.add(root, {"stage": "C5", "type": "change", "actor": "claude", "advisory": True,
                              "what_es": "Borradores de planificación de métodos (opciones, sin elegir): " + ", ".join(written or ["ninguno nuevo"]),
                              "tool": journal_io.tool_string("methods_plan.py", VERSION), "human_decision": "pendiente",
                              "outputs": [journal_io.file_ref(root, r) for r in written]})
    out({"ok": True, "written": written, "skipped_existing": skipped, "journal_id": e["id"]})
    return 0


def _choices(root):
    return [e for e in journal_io.read_all(root) if e.get("kind") == "c5_choice" and e.get("actor") == "laura"]


def cmd_record(root, a):
    if not a.laura_confirmed:
        out({"ok": False, "error": "falta --laura-confirmed: la elección es de Laura"})
        return 1
    ok_tools = D.tools_for(a.topic)
    if a.tool not in D.TOOLS or a.tool not in ok_tools:
        out({"ok": False, "error": "la herramienta '%s' no es aplicable a '%s'. Aplicables: %s" % (a.tool, a.topic, sorted(ok_tools))})
        return 1
    if a.topic == "rob:rct" and a.pedro not in ("use", "skip"):
        out({"ok": False, "error": "para ensayos hace falta la decisión de Laura sobre PEDro: --pedro use|skip"})
        return 1
    t = D.TOOLS[a.tool]
    e = journal_io.add(root, {"stage": "C5", "type": "decision", "actor": "laura", "kind": "c5_choice", "topic": a.topic, "tool_id": a.tool,
                              "tool_name": t["name"], "source_url": t["url"], "pedro": a.pedro or "",
                              "what_es": "Laura elige %s para %s%s" % (t["name"], a.topic, (" (" + a.note + ")") if a.note else ""),
                              "human_decision": "aprobado por Laura", "tool": journal_io.tool_string("methods_plan.py", VERSION)})
    out({"ok": True, "journal_id": e["id"], "source_url": t["url"], "next_es": "Abre la fuente y confirma: confirm-source --choice %s" % e["id"]})
    return 0


def cmd_confirm(root, a):
    if not a.laura_confirmed:
        out({"ok": False, "error": "falta --laura-confirmed"})
        return 1
    ch = [c for c in _choices(root) if c["id"] == a.choice]
    if not ch:
        out({"ok": False, "error": "no existe la elección %s" % a.choice})
        return 1
    e = journal_io.add(root, {"stage": "C5", "type": "decision", "actor": "laura", "kind": "c5_source_confirmed", "choice_id": a.choice,
                              "source_url": ch[0]["source_url"], "gate": "pass", "gate_name": "G-C5-source",
                              "what_es": "Laura abrió la fuente de %s y confirma que corresponde" % ch[0]["tool_name"],
                              "human_decision": "aprobado por Laura", "tool": journal_io.tool_string("methods_plan.py", VERSION)})
    out({"ok": True, "journal_id": e["id"]})
    return 0


def evaluate(root):
    """Gate G-C5. Latest choice per topic wins."""
    plan_p = paths.safe_join(root, PLAN_REL)
    issues, rows = [], []
    if not plan_p.is_file():
        return {"ok": False, "issues": ["no hay plan (05_metodos/plan.json): ejecutar `plan` primero"], "rows": []}
    plan = json.loads(paths.read_text(plan_p))
    entries = journal_io.read_all(root)
    latest = {}
    for c in _choices(root):
        latest[c["topic"]] = c
    confirmed = {e["choice_id"] for e in entries if e.get("kind") == "c5_source_confirmed" and e.get("actor") == "laura"}
    for topic in D.topics_for_designs(plan["designs"], plan.get("exercise")):
        c = latest.get(topic)
        if not c:
            issues.append("falta la elección de Laura para %s" % topic)
            continue
        if c["tool_id"] not in D.tools_for(topic):
            issues.append("%s: la herramienta %s no es aplicable" % (topic, c["tool_id"]))
        if not str(c.get("source_url", "")).startswith("http"):
            issues.append("%s: sin URL de fuente" % topic)
        if c["id"] not in confirmed:
            issues.append("%s: fuente sin confirmar (%s)" % (topic, c["id"]))
        if topic == "rob:rct" and c.get("pedro") not in ("use", "skip"):
            issues.append("rob:rct: falta la decisión sobre PEDro")
        rows.append({"topic": topic, "tool": c["tool_id"], "choice": c["id"], "source_confirmed": c["id"] in confirmed})
    return {"ok": not issues, "issues": issues, "rows": rows, "plan": plan}


def cmd_check(root, a):
    r = evaluate(root)
    if a.journal:
        ts = paths.utc_now().replace(":", "").replace("-", "")
        ref = journal_io.make_script_report(root, "methods_plan.py", "07_verificacion/reports/g_c5_%s.json" % ts,
                                            "pass" if r["ok"] else "fail", details={"issues": r["issues"], "rows": r["rows"]}, version=VERSION)
        e = journal_io.add(root, {"stage": "C5", "type": "verification", "actor": "script", "gate_name": "G-C5",
                                  "gate": "pass" if r["ok"] else "fail", "script_report": ref, "tool": journal_io.tool_string("methods_plan.py", VERSION),
                                  "what_es": "Puerta G-C5 (métodos): %s" % ("cumplida" if r["ok"] else "no cumplida: " + "; ".join(r["issues"][:3])),
                                  "human_decision": "n/a"})
        r["journal_id"] = e["id"]
    out(r)
    return 0 if r["ok"] else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tools")
    t.add_argument("--design")
    t.add_argument("--topic")
    p = sub.add_parser("plan")
    p.add_argument("--designs", required=True)
    p.add_argument("--exercise", choices=["yes", "no"], default="no")
    p.add_argument("--force", action="store_true")
    r = sub.add_parser("record-choice")
    r.add_argument("--topic", required=True)
    r.add_argument("--tool", required=True)
    r.add_argument("--pedro", choices=["use", "skip"])
    r.add_argument("--note", default="")
    r.add_argument("--laura-confirmed", action="store_true")
    c = sub.add_parser("confirm-source")
    c.add_argument("--choice", required=True)
    c.add_argument("--laura-confirmed", action="store_true")
    k = sub.add_parser("check")
    k.add_argument("--journal", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "tools":
        topic = a.topic or ("rob:" + a.design if a.design else None)
        out({"ok": True, "tools": D.tools_for(topic) if topic else D.TOOLS, "designs": D.DESIGNS})
        return 0
    try:
        root = paths.find_root(a.root)
    except paths.ProjectNotFound as e:
        out({"ok": False, "error": str(e)})
        return 2
    if config.get_mode(root) in ("LITE-b", "LITE-P"):
        out({"ok": False, "error": "modo %s: sin scripts; usa la lista de comprobación de templates/rob_grade_es.md" % config.get_mode(root)})
        return 2
    try:
        return {"plan": cmd_plan, "record-choice": cmd_record, "confirm-source": cmd_confirm, "check": cmd_check}[a.cmd](root, a)
    except (journal_io.JournalError, ValueError) as ex:
        out({"ok": False, "errors": getattr(ex, "errors", [str(ex)])})
        return 1


if __name__ == "__main__":
    sys.exit(main())
