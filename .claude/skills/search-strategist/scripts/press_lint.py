#!/usr/bin/env python3
"""press_lint.py - PRESS 2015 peer review of a search string (Q3-3, F-03).

  press_lint.py lint    --string-file 03_busqueda/strings/pubmed_v1.txt     syntax domains ONLY (script can close these)
  press_lint.py init    --string-file ...                                   create 03_busqueda/press/press_<db>_v<N>.md
  press_lint.py status  --string-file ...                                   gate view: syntax pass + 4 content domains signed?
  press_lint.py signoff --file 03_busqueda/press/press_pubmed_v1.md --laura-says "..."   (only after Laura said so)

Domains: syntactic = Boolean/proximity operators + parentheses, spelling/syntax/line numbers (spelling is NOT automated: Laura reads it).
Content = translation of the question, subject headings, text words, limits/filters -> advisory by Claude (`advisory: true`),
closed ONLY by Laura's signature (journal decision, actor laura). An advisory judgment never closes the gate.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_lib as L  # noqa: E402
from _common import journal_io, paths  # noqa: E402

SCRIPT = "press_lint.py"
DOMAINS = [("1", "Traducción de la pregunta de investigación", "¿Cada concepto del PICO está en la cadena, sin añadir ni perder conceptos?"),
           ("3", "Descriptores (subject headings)", "¿Los MeSH son los adecuados, con/sin explosión, y hay texto libre complementario?"),
           ("4", "Palabras de texto libre", "¿Sinónimos, variantes ortográficas EN/UK/US, truncamientos y formas plurales cubiertos?"),
           ("6", "Límites y filtros", "¿Cada límite (fecha, idioma, tipo de estudio) está justificado y no excluye estudios relevantes?")]
SYNTAX_DOMAINS = ["2. Operadores booleanos y de proximidad / paréntesis", "5. Ortografía, sintaxis de campos y números de línea (la ortografía la revisa Laura)"]


def lint(root, string_rel, journal=True):
    L.string_guard(root, string_rel)
    text = L.read_string_file(root, string_rel)
    query, problems = L.build_query(text)
    iss = L.syntax_issues(query)
    errors = [i["msg_es"] for i in iss if i["level"] == "error"] + problems
    warns = [i["msg_es"] for i in iss if i["level"] == "warning"]
    res = {"ok": not errors, "string_file": string_rel, "errors": errors, "warnings": warns,
           "not_automated": ["ortografía de los términos (la revisa Laura)"], "gate": "pass" if not errors else "fail"}
    if journal:
        ref = journal_io.make_script_report(root, SCRIPT, L.unique_rel(root, "03_busqueda/press/lint_%s_%s.json" % (
            os.path.basename(string_rel)[:-4], L.stamp())), res["gate"], details={k: res[k] for k in ("string_file", "errors", "warnings", "not_automated")},
            version=L.VERSION)
        e = journal_io.add(root, {
            "stage": "C3", "type": "verification", "actor": "script", "tool": L.tool(SCRIPT), "gate_name": "G-C3-press-syntax",
            "gate": res["gate"], "script_report": ref, "human_decision": "n/a", "how_verified": "análisis sintáctico determinista",
            "what_es": "PRESS dominios de sintaxis de %s: %d error(es), %d aviso(s)" % (string_rel, len(errors), len(warns)),
            "inputs": [journal_io.file_ref(root, string_rel)]})
        res["journal_id"], res["script_report"] = e["id"], ref
    return res


def checklist_rel(string_rel):
    return "03_busqueda/press/press_%s.md" % os.path.basename(string_rel)[:-4]


def init(root, string_rel):
    L.string_guard(root, string_rel)
    rel = checklist_rel(string_rel)
    full = paths.safe_join(root, rel)
    if full.exists():
        raise L.Refusal("PRESS_EXISTS", "%s ya existe (no se sobrescribe; crea una versión nueva de la cadena)." % rel)
    sha = paths.sha256_file(paths.safe_join(root, string_rel))
    out = ["# Revisión PRESS 2015 - %s" % os.path.basename(string_rel)[:-4], "",
           "Cadena: `%s` (sha256 `%s`)" % (string_rel, sha),
           "Referencia: PRESS 2015 Guideline Statement (McGowan et al., J Clin Epidemiol 2016). Verificar la cita completa antes de usarla en el protocolo.",
           "", "> Las valoraciones de Claude son **advisory**: no cierran nada. Solo la firma de Laura (idealmente con el tutor o una bibliotecaria) cierra cada dominio.",
           "", "## Dominios de sintaxis (los revisa `press_lint.py lint`)", ""]
    out += ["- %s: ver informe de `press_lint.py lint`" % d for d in SYNTAX_DOMAINS]
    out += ["", "## Dominios de contenido (advisory de Claude + firma de Laura)", ""]
    for n, name, q in DOMAINS:
        out += ["### %s. %s" % (n, name), "", "Pregunta guía: %s" % q, "", "Claude (advisory): _pendiente_", "",
                "Estado de Laura: pendiente", "Comentario de Laura:", ""]
    out += ["## Firma", "", "Firma de Laura (fecha): ", "Revisor externo (tutor/bibliotecaria, opcional): ", ""]
    paths.write_text_atomic(full, "\n".join(out))
    return {"ok": True, "path": rel}


def parse_checklist(text):
    doms = {}
    for m in re.finditer(r"(?ms)^### (\d)\. [^\n]*\n(.*?)(?=^### |\Z|^## )", text):
        st = re.search(r"(?m)^Estado de Laura:\s*(\S+)", m.group(2))
        doms[m.group(1)] = (st.group(1).lower() if st else "pendiente")
    return doms


def status(root, string_rel):
    sha = paths.sha256_file(paths.safe_join(root, string_rel))
    syn = [e for e in journal_io.query(root, type="verification") if e.get("gate_name") == "G-C3-press-syntax" and
           any(i.get("path") == string_rel and i.get("sha256") == sha for i in e.get("inputs", []))]
    syntax_ok = bool(syn) and syn[-1].get("gate") == "pass"
    rel = checklist_rel(string_rel)
    full = paths.safe_join(root, rel)
    doms = parse_checklist(paths.read_text(full)) if full.is_file() else {}
    unresolved = [n for n, _, _ in DOMAINS if doms.get(n) != "ok"]
    revise = [n for n in unresolved if doms.get(n) == "revisar"]
    signed = False
    if full.is_file():
        fsha = paths.sha256_file(full)
        signed = any(e.get("actor") == "laura" and e.get("kind") == "press_signoff" and
                     any(o.get("path") == rel and o.get("sha256") == fsha for o in e.get("outputs", []))
                     for e in journal_io.query(root, type="decision"))
    ok = syntax_ok and not unresolved and signed
    return {"ok": ok, "syntax_pass": syntax_ok, "checklist": rel if full.is_file() else None, "domains": doms,
            "unresolved_domains": unresolved, "revisar": revise, "signed_by_laura": signed,
            "message_es": "PRESS cerrado" if ok else "PRESS abierto: sintaxis %s; dominios sin «ok»: %s; firma de Laura: %s" % (
                "ok" if syntax_ok else "pendiente", ",".join(unresolved) or "ninguno", "sí" if signed else "no")}


def signoff(root, file_rel, said):
    if not said.strip():
        raise L.Refusal("MISSING_STATEMENT", "Hace falta lo que Laura dijo (--laura-says): sin su palabra no hay firma.")
    full = paths.safe_join(root, file_rel)
    if not full.is_file():
        raise L.Refusal("PRESS_MISSING", "No existe %s." % file_rel)
    doms = parse_checklist(paths.read_text(full))
    bad = [n for n, _, _ in DOMAINS if doms.get(n) != "ok"]
    if bad:
        raise L.Refusal("DOMAINS_OPEN", "Dominios sin «Estado de Laura: ok»: %s. No se firma." % ", ".join(bad))
    e = journal_io.add(root, {
        "stage": "C3", "type": "decision", "actor": "laura", "kind": "press_signoff", "gate_name": "G-C3-press-content",
        "what_es": "Laura firma los 4 dominios de contenido PRESS de %s" % file_rel, "human_decision": "aprobado por Laura",
        "why_es": said.strip(), "outputs": [journal_io.file_ref(root, file_rel)], "gate": "pass"})
    return {"ok": True, "journal_id": e["id"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("lint", "init", "status"):
        s = sub.add_parser(c)
        s.add_argument("--string-file", required=True)
    g = sub.add_parser("signoff")
    g.add_argument("--file", required=True)
    g.add_argument("--laura-says", default="")
    a = ap.parse_args(argv)

    def go():
        root = L.open_project(a.root)
        if a.cmd == "lint":
            L.need_mode(root, network=False)
            r = lint(root, a.string_file)
        elif a.cmd == "init":
            r = init(root, a.string_file)
        elif a.cmd == "status":
            r = status(root, a.string_file)
        else:
            r = signoff(root, a.file, a.laura_says)
        return r, (0 if r["ok"] else 1)
    return L.finish(go)


if __name__ == "__main__":
    sys.exit(main())
