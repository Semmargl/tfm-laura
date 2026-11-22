#!/usr/bin/env python3
"""declaration.py: build the AI-use declaration (Normativa Euneiz 2.4) from journal `ai_use` entries.

  declaration.py generate [--stdout]        write declaracion/declaracion_IA_es.md (keeps Laura's justification)
  declaration.py set-justification --text-file f.txt   store Laura's text + journal decision (actor laura)
  declaration.py check                      freshness / justification status (exit 1 if not release-ready)
Sections: herramientas, etapas, qué hizo la IA, cómo se verificó, decisión humana, justificación (Laura).
assemble_protocol.py imports render_section(root) and check(root).
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import journal_io, paths  # noqa: E402

VERSION = "1.0"
MARK_A, MARK_B = "<!-- JUSTIFICACION:INICIO -->", "<!-- JUSTIFICACION:FIN -->"
PLACEHOLDER = "[PENDIENTE: este apartado lo redacta Laura con sus palabras]"
STAGES_ES = {"C0": "Organización y diario", "C1": "Elección del tema", "C2": "PICO y criterios", "C3": "Estrategia de búsqueda",
             "C4": "Selección de estudios", "C5": "Métodos", "C6": "Redacción del protocolo", "C7": "Verificación",
             "C8": "Paneles", "C9": "Registro y entrega", "setup": "Instalación"}


def ai_uses(root):
    return [e for e in journal_io.read_all(root) if e.get("type") == "ai_use"]


def read_justification(text):
    if not text or MARK_A not in text or MARK_B not in text:
        return ""
    return text.split(MARK_A, 1)[1].split(MARK_B, 1)[0].strip()


def is_filled(just):
    j = just.strip()
    return bool(j) and not j.startswith("[PENDIENTE")


def build(root, justification=None, level=1):
    uses = ai_uses(root)
    last = uses[-1]["id"] if uses else "J-0000"
    h = "#" * level
    h2 = "#" * (level + 1)
    tools = collections.Counter(e["tool"] for e in uses)
    stages = collections.Counter(e["stage"] for e in uses)
    L = ["%s Declaración de uso de inteligencia artificial" % h, "",
         "Declaración elaborada conforme a la Normativa Euneiz, apartado 2.4. Se genera automáticamente a partir del "
         "diario del proyecto (journal.jsonl); cada uso de IA registrado aparece abajo con su identificador.", "",
         "Hasta: %s · Usos de IA registrados: %d · Generada: %s" % (last, len(uses), paths.utc_now()), "",
         "%s 1. Herramientas utilizadas" % h2, ""]
    L += ["- %s (%d uso%s)" % (t, n, "" if n == 1 else "s") for t, n in sorted(tools.items())] or ["- (ninguna registrada todavía)"]
    L += ["", "%s 2. Etapas del trabajo en las que se usó" % h2, "", "| Etapa | Usos |", "|---|---|"]
    L += ["| %s %s | %d |" % (s, STAGES_ES.get(s, ""), n) for s, n in sorted(stages.items())] or ["| (ninguna) | 0 |"]
    for title, key in (("3. Qué hizo la IA", "what_es"), ("4. Cómo se verificó", "how_verified"), ("5. Decisión humana", "human_decision")):
        L += ["", "%s %s" % (h2, title), ""]
        L += ["- %s · %s · %s" % (e["id"], e["stage"], e[key]) for e in uses] or ["- (ninguno)"]
    L += ["", "%s 6. Justificación de la utilidad para la investigación" % h2, "", MARK_A,
          justification if justification else PLACEHOLDER, MARK_B, ""]
    return "\n".join(L)


def render_section(root, level=2):
    """Markdown for the protocol's mandatory section; keeps Laura's justification if present."""
    P = paths.Paths(root)
    old = read_justification(paths.read_text(P.declaration)) if P.declaration.is_file() else ""
    return build(root, old if is_filled(old) else None, level)


def generate(root):
    P = paths.Paths(root)
    text = render_section(root, 1)
    paths.write_text_atomic(P.declaration, text)
    return text


def set_justification(root, text):
    if not is_filled(text):
        raise ValueError("justificación vacía")
    P = paths.Paths(root)
    body = build(root, text.strip(), 1)
    paths.write_text_atomic(P.declaration, body)
    return journal_io.add(root, {"stage": "C0", "type": "decision", "actor": "laura", "what_es": "Laura redactó la justificación de la utilidad de la IA",
                                 "kind": "justificacion_utilidad", "justification_sha256": paths.sha256_bytes(text.strip().encode("utf-8")),
                                 "human_decision": "aprobado por Laura", "tool": "declaration.py v" + VERSION})


def check(root):
    """Release-readiness of the declaration (G-C6 / G-C9 / F-08)."""
    P = paths.Paths(root)
    issues = []
    uses = ai_uses(root)
    last = uses[-1]["id"] if uses else "J-0000"
    text = paths.read_text(P.declaration) if P.declaration.is_file() else ""
    m = re.search(r"Hasta: (J-\d+)", text)
    fresh = bool(m) and m.group(1) >= last
    if not text:
        issues.append("declaración no generada")
    elif not fresh:
        issues.append("declaración desactualizada (hasta %s, último ai_use %s)" % (m.group(1) if m else "?", last))
    else:
        missing = [e["id"] for e in uses if e["id"] not in text]
        if missing:
            issues.append("faltan usos de IA en la declaración: %s" % missing)
    just = read_justification(text)
    filled = is_filled(just)
    by_laura = False
    if filled:
        sha = paths.sha256_bytes(just.encode("utf-8"))
        by_laura = any(e.get("kind") == "justificacion_utilidad" and e.get("actor") == "laura" and e.get("justification_sha256") == sha
                       for e in journal_io.read_all(root))
    if not filled:
        issues.append("falta la justificación de la utilidad (la escribe Laura)")
    elif not by_laura:
        issues.append("la justificación no tiene registro de Laura en el diario")
    return {"ok": not issues, "fresh": fresh, "justification_filled": filled, "justification_by_laura": by_laura,
            "ai_use_count": len(uses), "issues": issues}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--stdout", action="store_true")
    s = sub.add_parser("set-justification")
    s.add_argument("--text-file", required=True)
    sub.add_parser("check")
    a = ap.parse_args(argv)
    try:
        root = paths.find_root(a.root)
    except paths.ProjectNotFound as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2
    if a.cmd == "generate":
        t = generate(root)
        print(t if a.stdout else json.dumps({"ok": True, "path": "declaracion/declaracion_IA_es.md", "ai_use": len(ai_uses(root))}, ensure_ascii=False))
        return 0
    if a.cmd == "set-justification":
        try:
            e = set_justification(root, paths.read_text(a.text_file))
        except (ValueError, journal_io.JournalError) as ex:
            print(json.dumps({"ok": False, "error": str(ex)}, ensure_ascii=False))
            return 1
        print(json.dumps({"ok": True, "journal_id": e["id"]}, ensure_ascii=False))
        return 0
    r = check(root)
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
