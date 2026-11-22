#!/usr/bin/env python3
"""pico_check.py new|check|checklist|freeze   (C2; offline, works in FULL and LITE-a)

  new       --version N [--topic T1] [--framework PICO|PECO] [--from M]   create 02_pico/pico_vN.md from the template
            (or copy of version M) and journal it as a `change` (tracked file, inv. 2). Never overwrites.
  check     --file 02_pico/pico_vN.md [--write-report]   completeness 100% (or «no definido»), every term has a source and a
            verification date, >= 1 COMET row verified, framework consistent. JSON on stdout, exit 1 if not ok.
  checklist --file ...                                     Spanish markdown checklist (LITE: Claude fills, Laura signs).
  freeze    --version N --approval-text "<Laura's words>"  needs check ok + Laura's approval; journals `decision` actor laura
            (gate pass by a human), sets state.pico_version = N. A frozen file that changes later -> FROZEN_MODIFIED.
Findings are advisory for meaning (mixed population etc.); only the structural errors close the gate.
"""
import argparse
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if not os.path.isdir(os.path.join(HERE, "_common")):
    sys.path.append(os.path.dirname(os.path.dirname(HERE)))
from _common import integrity_core, journal_io, miniyaml, paths, state_io  # noqa: E402

VERSION = "1.0"
SCRIPT = "pico_check.py"
TEMPLATE = os.path.join(os.path.dirname(HERE), "templates", "pico_template_es.md")
PLACEHOLDERS = {"", "...", "…", "[completar]", "completar", "todo", "xxx", "tbd", "?", "-", "—", "n/a"}
ND = "no definido"
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TERM_FIELDS = ("P", "I", "E", "C", "O")
SIMPLE = ("diseno", "idioma", "periodo", "contexto", "objetivo", "inclusion", "exclusion")
LABEL_ES = {"P": "Poblacion", "I": "Intervencion", "E": "Exposicion", "C": "Comparador", "O": "Resultados (outcomes)",
            "diseno": "Diseno de estudios", "idioma": "Idioma", "periodo": "Periodo", "contexto": "Contexto (setting)",
            "objetivo": "Pregunta y objetivo", "inclusion": "Criterios de inclusion", "exclusion": "Criterios de exclusion",
            "comet": "COMET (core outcome set)"}


def _fold(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn").strip()


def heading_key(h):
    t = _fold(re.sub(r"[*_`]", "", h))
    for key, pat in (("P", r"^p\b"), ("I", r"^i\b"), ("E", r"^e\b"), ("C", r"^c\b"), ("O", r"^o\b"),
                     ("diseno", r"^dise"), ("idioma", r"^idioma"), ("periodo", r"^period"),
                     ("contexto", r"^(contexto|setting)"), ("objetivo", r"^(pregunta|objetivo)"),
                     ("inclusion", r"^criterios de inclusi"), ("exclusion", r"^criterios de exclusi"), ("comet", r"^comet")):
        if re.search(pat, t):
            return key
    return None


def parse(text):
    """-> (meta, sections{key: {'prose': [...], 'bullets': [...], 'rows': [[cells]]}})"""
    meta, body = {}, text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = miniyaml.loads(parts[1]) or {}
            except Exception:
                meta = {}
            body = parts[2]
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    secs, cur = {}, None
    for ln in body.split("\n"):
        m = re.match(r"^##\s+(.*)$", ln)
        if m:
            cur = heading_key(m.group(1))
            if cur:
                secs.setdefault(cur, {"prose": [], "bullets": [], "rows": []})
            continue
        if re.match(r"^#\s", ln) or cur is None:
            continue
        s = ln.strip()
        if not s:
            continue
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.match(r"^:?-{2,}:?$", c) for c in cells if c):
                continue
            secs[cur]["rows"].append(cells)
        elif re.match(r"^[-*]\s+", s):
            secs[cur]["bullets"].append(re.sub(r"^[-*]\s+", "", s))
        else:
            secs[cur]["prose"].append(s)
    for sec in secs.values():                      # first table row is the header
        if sec["rows"]:
            sec["header"] = sec["rows"][0]
            sec["rows"] = sec["rows"][1:]
    return meta, secs


def _blank(v):
    v = re.sub(r"^\*\*[^*]+\*\*\s*", "", v.strip())            # «**Pregunta:** [completar]» -> «[completar]»
    return _fold(v) in PLACEHOLDERS or re.fullmatch(r"\[[^\]]*\]", v.strip()) is not None


def _is_nd(sec):
    txt = " ".join(sec["prose"] + sec["bullets"]).lower()
    return ND in txt


def _filled(sec):
    # the field itself = prose / bullets; the terms table only documents sources and does not make an empty field "filled"
    return any(not _blank(x) for x in sec["prose"] + sec["bullets"])


def analyse(text, root=None, rel=None):
    meta, secs = parse(text)
    errors, warns = [], []

    def err(code, field, msg):
        errors.append({"code": code, "field": field, "msg_es": msg})

    if meta.get("schema") != "tfm-pico/v1":
        err("BAD_FRONTMATTER", "-", "falta 'schema: tfm-pico/v1' en la cabecera")
    fw = str(meta.get("framework", "")).upper()
    if fw not in ("PICO", "PECO"):
        err("BAD_FRAMEWORK", "-", "framework debe ser PICO o PECO")
        fw = "PICO"
    if not isinstance(meta.get("version"), int):
        err("BAD_VERSION", "-", "version debe ser un numero entero")
    third = "I" if fw == "PICO" else "E"
    other = "E" if fw == "PICO" else "I"
    if other in secs and third not in secs:
        err("FRAMEWORK_MISMATCH", other, "el marco es %s pero la seccion es %s: usa %s" % (fw, other, third))
    required = ["objetivo", "P", third, "C", "O", "diseno", "idioma", "periodo", "contexto", "inclusion", "exclusion"]
    fields, terms_total, terms_ok = {}, 0, 0
    for k in required:
        sec = secs.get(k)
        if sec is None:
            err("MISSING_FIELD", k, "falta la seccion «%s»" % LABEL_ES[k])
            fields[k] = "missing"
            continue
        if _is_nd(sec):
            fields[k] = "no_definido"
            continue
        if not _filled(sec):
            err("MISSING_FIELD", k, "«%s» esta vacio: completalo o escribe «no definido»" % LABEL_ES[k])
            fields[k] = "missing"
            continue
        fields[k] = "ok"
        if k in ("inclusion", "exclusion") and not sec["bullets"]:
            err("MISSING_FIELD", k, "«%s»: escribe cada criterio como una vineta (- ...)" % LABEL_ES[k])
            fields[k] = "missing"
        if k in TERM_FIELDS:
            rows = [r for r in sec["rows"] if any(c for c in r)]
            if not rows:
                err("NO_TERMS", k, "«%s» no tiene tabla de terminos con fuente" % LABEL_ES[k])
            for r in rows:
                terms_total += 1
                term = r[0] if r else ""
                src = r[2] if len(r) > 2 else ""
                dt = r[3] if len(r) > 3 else ""
                bad = None
                if _blank(term):
                    bad = ("TERM_EMPTY", "fila sin termino")
                elif _blank(src):
                    bad = ("TERM_NO_SOURCE", "termino «%s» sin fuente" % term)
                elif "pendiente" in _fold(src):
                    bad = ("TERM_SOURCE_PENDING", "termino «%s»: la fuente sigue «pendiente de verificar»" % term)
                elif not DATE.match(dt):
                    bad = ("TERM_NO_DATE", "termino «%s»: falta fecha de verificacion AAAA-MM-DD" % term)
                if bad:
                    err(bad[0], k, bad[1])
                else:
                    terms_ok += 1
                    if len(r) < 2 or _blank(r[1]):
                        warns.append({"code": "TERM_NO_DEFINITION", "field": k, "msg_es": "termino «%s» sin definicion" % term})
    # COMET (at least one verified row)
    comet = secs.get("comet")
    comet_ok = 0
    if comet:
        for r in comet["rows"]:
            if len(r) >= 4 and r[1].startswith("http") and DATE.match(r[2]) and not _blank(r[3]) and "pendiente" not in _fold(r[3]):
                comet_ok += 1
    if comet_ok < 1:
        err("NO_COMET", "comet", "falta al menos 1 core outcome set de COMET comprobado (nombre | URL | fecha | resultado)")
    # advisory heuristics (meaning is Laura's / the supervisor's call)
    p = secs.get("P")
    if p:
        t = _fold(" ".join(p["prose"] + p["bullets"] + [" ".join(r[:1]) for r in p["rows"]]))
        if re.search(r"mujer|femenin", t) and re.search(r"hombre|varon|masculin|ambos sexos", t):
            warns.append({"code": "MIXED_POPULATION", "field": "P", "msg_es": "la poblacion mezcla mujeres y hombres: ¿es una sola poblacion?"})
        if re.search(r"adult", t) and re.search(r"nino|pediatr|adolescen", t):
            warns.append({"code": "MIXED_POPULATION", "field": "P", "msg_es": "la poblacion mezcla adultos y ninos/adolescentes"})
    # frozen-version integrity
    if root and rel and isinstance(meta.get("version"), int):
        for e in journal_io.query(root, type="decision"):
            if e.get("kind") == "pico_freeze" and e.get("pico_version") == meta["version"]:
                frozen = [o for o in e.get("outputs", []) if o.get("path") == rel]
                if frozen and frozen[-1]["sha256"] != paths.sha256_file(paths.safe_join(root, rel)):
                    err("FROZEN_MODIFIED", "-", "la version %d esta congelada y el archivo cambio: crea una version nueva" % meta["version"])
    n_fields = len(required)
    n_ok = sum(1 for v in fields.values() if v in ("ok", "no_definido"))
    return {"ok": not errors, "errors": errors, "warnings": warns, "fields": fields,
            "stats": {"fields_total": n_fields, "fields_filled": n_ok, "completeness_pct": round(100.0 * n_ok / n_fields, 1),
                      "terms_total": terms_total, "terms_with_source": terms_ok, "comet_verified": comet_ok,
                      "no_definido": sum(1 for v in fields.values() if v == "no_definido")},
            "version": meta.get("version"), "framework": fw, "topic_id": meta.get("topic_id")}


def unique_rel(root, rel):
    base, ext = os.path.splitext(rel)
    n, cand = 1, rel
    while (paths.Paths(root).root / cand).exists():
        n += 1
        cand = "%s_r%d%s" % (base, n, ext)
    return cand


def out(o):
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")


def checklist(res, rel):
    L = ["# Lista de comprobacion PICO — %s" % rel, "", "Claude marca lo que ve; **Laura confirma con su firma** (modo LITE).", "",
         "| Campo | Estado | Confirma Laura |", "|---|---|---|"]
    for k, v in res["fields"].items():
        L.append("| %s | %s | ☐ |" % (LABEL_ES[k], {"ok": "☑ completo", "no_definido": "☑ «no definido»", "missing": "☐ FALTA"}[v]))
    L += ["", "- Terminos con fuente y fecha: %d de %d ☐" % (res["stats"]["terms_with_source"], res["stats"]["terms_total"]),
          "- COMET comprobados (>= 1): %d ☐" % res["stats"]["comet_verified"], ""]
    for e in res["errors"]:
        L.append("- ☐ %s (%s)" % (e["msg_es"], e["code"]))
    for w in res["warnings"]:
        L.append("- ☐ (aviso, juicio tuyo) %s" % w["msg_es"])
    L += ["", "Firma de Laura: ____________  Fecha: ____________", ""]
    return "\n".join(L)


def cmd_new(root, a):
    n = a.version
    rel = "02_pico/pico_v%d.md" % n
    dst = paths.safe_join(root, rel)
    if dst.exists():
        return {"ok": False, "error_es": "%s ya existe: no se sobrescribe. Usa otra version." % rel}, 1
    if a.src:
        src = paths.safe_join(root, "02_pico/pico_v%d.md" % a.src)
        if not src.is_file():
            return {"ok": False, "error_es": "no existe la version %d" % a.src}, 1
        text = paths.read_text(src)
        text = re.sub(r"(?m)^version:.*$", "version: %d" % n, text, count=1)
        text = re.sub(r"(?m)^status:.*$", "status: borrador", text, count=1)
    else:
        text = paths.read_text(TEMPLATE)
        text = text.replace("version: 1", "version: %d" % n, 1).replace("PICO v1", "PICO v%d" % n)
        text = re.sub(r"(?m)^framework:.*$", "framework: %s" % a.framework, text, count=1)
        if a.topic:
            text = re.sub(r"(?m)^topic_id:.*$", "topic_id: %s" % a.topic, text, count=1)
        if a.framework == "PECO":
            text = text.replace("## I — Intervención", "## E — Exposición")
    paths.write_text_atomic(dst, text)
    e = integrity_core.record_change(root, rel, "Nueva plantilla PICO v%d [draft-ai]" % n, "C2",
                                     why_es="borrador inicial para completar con Laura", human_decision="pendiente")
    return {"ok": True, "file": rel, "journal_id": e["id"],
            "message_es": "Cree %s con la plantilla. Rellenala con Laura; cada edicion se anota con integrity.py record-change." % rel}, 0


def cmd_check(root, a):
    rel = paths.rel(root, paths.Paths(root).root / a.file) if not os.path.isabs(a.file) else paths.rel(root, a.file)
    text = paths.read_text(paths.safe_join(root, rel))
    res = analyse(text, root, rel)
    res["file"] = rel
    if a.write_report:
        ts = paths.utc_now().replace(":", "").replace("-", "")
        rep_rel = unique_rel(root, "07_verificacion/reports/pico_check_v%s_%s.json" % (res["version"], ts))
        res["script_report"] = journal_io.make_script_report(root, SCRIPT, rep_rel, "pass" if res["ok"] else "fail",
                                                             details={"file": rel, "sha256": paths.sha256_file(paths.safe_join(root, rel)),
                                                                      "stats": res["stats"], "errors": [e["code"] for e in res["errors"]]},
                                                             version=VERSION)
    return res, 0 if res["ok"] else 1


def cmd_freeze(root, a):
    n = a.version
    rel = "02_pico/pico_v%d.md" % n
    full = paths.safe_join(root, rel)
    if not full.is_file():
        return {"ok": False, "error_es": "no existe %s" % rel}, 1
    if not a.approval_text.strip():
        return {"ok": False, "error_es": "falta el texto de aprobacion de Laura (sus palabras)"}, 1
    res = analyse(paths.read_text(full), root, rel)
    if not res["ok"]:
        return {"ok": False, "error_es": "la PICO no pasa la comprobacion: " + "; ".join(e["msg_es"] for e in res["errors"]),
                "errors": res["errors"]}, 1
    outs = journal_io.find_for_path(root, rel)
    sha = paths.sha256_file(full)
    if not outs or [o for o in outs[-1]["outputs"] if o["path"] == rel][-1]["sha256"] != sha:
        return {"ok": False, "error_es": "el archivo tiene cambios sin anotar: ejecuta integrity.py record-change antes de congelar"}, 1
    ts = paths.utc_now().replace(":", "").replace("-", "")
    rep = journal_io.make_script_report(root, SCRIPT, unique_rel(root, "07_verificacion/reports/pico_check_v%d_%s.json" % (n, ts)), "pass",
                                        details={"file": rel, "sha256": sha, "stats": res["stats"]}, version=VERSION)
    e = journal_io.add(root, {
        "stage": "C2", "type": "decision", "actor": "laura", "kind": "pico_freeze", "pico_version": n, "gate": "pass",
        "gate_name": "G-C2", "what_es": "Laura aprueba y congela la PICO v%d" % n, "human_decision": a.approval_text.strip(),
        "tool": journal_io.tool_string(SCRIPT, VERSION), "how_verified": "pico_check.py ok (campos, terminos, COMET)",
        "outputs": [{"path": rel, "sha256": sha}], "script_report": rep})
    state_io.set_fields(root, pico_version=n, last_journal_id=e["id"])
    return {"ok": True, "journal_id": e["id"], "pico_version": n,
            "message_es": "PICO v%d congelada. Cualquier cambio posterior sera una version nueva (v%d)." % (n, n + 1)}, 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("--version", type=int, required=True)
    n.add_argument("--topic")
    n.add_argument("--framework", default="PICO", choices=["PICO", "PECO"])
    n.add_argument("--from", dest="src", type=int)
    c = sub.add_parser("check")
    c.add_argument("--file", required=True)
    c.add_argument("--write-report", action="store_true")
    k = sub.add_parser("checklist")
    k.add_argument("--file", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--version", type=int, required=True)
    f.add_argument("--approval-text", required=True)
    a = ap.parse_args(argv)
    try:
        root = paths.find_root(a.root)
        if a.cmd == "new":
            r, rc = cmd_new(root, a)
        elif a.cmd == "check":
            r, rc = cmd_check(root, a)
        elif a.cmd == "freeze":
            r, rc = cmd_freeze(root, a)
        else:
            rel = paths.rel(root, paths.Paths(root).root / a.file) if not os.path.isabs(a.file) else paths.rel(root, a.file)
            res = analyse(paths.read_text(paths.safe_join(root, rel)), root, rel)
            sys.stdout.write(checklist(res, rel))
            return 0 if res["ok"] else 1
    except (paths.ProjectNotFound, ValueError, OSError, journal_io.JournalError) as e:
        out({"ok": False, "error_es": str(e)})
        return 2
    out(r)
    return rc


if __name__ == "__main__":
    sys.exit(main())
