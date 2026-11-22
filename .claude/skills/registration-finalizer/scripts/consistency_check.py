#!/usr/bin/env python3
"""consistency_check.py: C9 final consistency check + registration fields. Never registers anything (0 external actions).

  check [--journal]                       gate G-C9: writes 09_registro/checklist_entrega_es.md; exit 1 if not 100%
  sign --item M1 --laura-confirmed        Laura signs a manual item of the checklist (journal decision, actor laura)
  fields --target prospero|osf [--force]  fill 09_registro/<target>_campos_es.md from the protocol drafts (copy, [draft-ai])
Auto items are computed from files/journal; manual items need Laura's signature. FULL/LITE-a: scripts; LITE-b/P: use the checklist by hand.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
if not os.path.isdir(os.path.join(_here, "_common")):      # dev layout
    sys.path.insert(1, os.path.dirname(os.path.dirname(_here)))
from _common import config, integrity_core, journal_io, paths, state_io  # noqa: E402

VERSION = "1.0"
CHECKLIST_REL = "09_registro/checklist_entrega_es.md"
DRAFTS = "06_protocolo/drafts"
SECTION_IDS = ["resumen", "administrativo", "introduccion", "objetivos", "met_elegibilidad", "met_fuentes", "met_busqueda", "met_seleccion",
               "met_extraccion", "met_sesgo", "met_sintesis", "resultados", "conclusiones", "bibliografia", "anexo_a_busqueda"]
EXPORT_MD = "06_protocolo/export/protocolo_ensamblado_es.md"
DECL_TITLE = "Declaración de uso de inteligencia artificial"
MANUAL = {
    "M1": "Laura contrastó los campos de PROSPERO/OSF con el formulario vigente de la plataforma",
    "M2": "El tutor/a revisó el protocolo completo",
    "M3": "Laura registra y envía ella misma el protocolo (el sistema no registra nada en su nombre)",
}


def out(o):
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")


def _tool():
    return journal_io.tool_string("consistency_check.py", VERSION)


def load_declaration():
    try:
        import declaration  # noqa
        return declaration
    except ImportError:
        pass
    sib = os.path.join(os.path.dirname(os.path.dirname(_here)), "tfm-orchestrator", "scripts")
    if os.path.isdir(sib):
        sys.path.append(sib)
        try:
            import declaration  # noqa
            return declaration
        except ImportError:
            return None
    return None


def drafts_digest(root):
    """Same algorithm as protocol-writer/protocol_lib.drafts_digest."""
    parts = []
    for sid in sorted(SECTION_IDS):
        p = paths.safe_join(root, "%s/%s.md" % (DRAFTS, sid))
        if p.is_file():
            parts.append("%s:%s" % (sid, paths.sha256_file(p)))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _marker(text):
    m = re.match(r"^\[(draft-ai|author-reviewed|final)\]\s*\n", text, re.I)
    return (m.group(1).lower(), text[m.end():]) if m else (None, text)


def _draft(root, sid):
    p = paths.safe_join(root, "%s/%s.md" % (DRAFTS, sid))
    return _marker(paths.read_text(p)) if p.is_file() else (None, None)


def _age_days(ts, now):
    f = "%Y-%m-%dT%H:%M:%SZ"
    return (datetime.datetime.strptime(now, f) - datetime.datetime.strptime(ts, f)).total_seconds() / 86400.0


def _latest_ver(root, gate_name):
    v = [e for e in journal_io.read_all(root) if e.get("type") == "verification" and e.get("gate_name") == gate_name]
    return v[-1] if v else None


def _idnum(e):
    return int(e["id"].split("-")[1])


# ---- individual checks: each returns (ok, detail) ------------------------------------------------------
def c_g6(root):
    g = _latest_ver(root, "G-C6")
    if not g or g.get("gate") != "pass":
        return False, "no hay una puerta G-C6 aprobada por script (assemble_protocol.py check --journal)"
    late = [e["id"] for e in journal_io.read_all(root) if _idnum(e) > _idnum(g) and any(
        str(o.get("path", "")).startswith(DRAFTS + "/") for o in (e.get("outputs") or []))]
    if late:
        return False, "hay cambios en los borradores después de G-C6 (%s)" % ", ".join(late[:4])
    return True, g["id"]


def c_sections_reviewed(root):
    bad = []
    for sid in SECTION_IDS:
        m, body = _draft(root, sid)
        if body is None or m not in ("author-reviewed", "final") or "[PENDIENTE" in body:
            bad.append(sid)
    return (not bad), ("secciones sin revisar o incompletas: %s" % bad) if bad else "100%"


def c_assembled(root):
    p = paths.safe_join(root, EXPORT_MD)
    if not p.is_file():
        return False, "protocolo no ensamblado"
    m = re.search(r"drafts_digest=([0-9a-f]{64})", paths.read_text(p))
    return (bool(m) and m.group(1) == drafts_digest(root)), "el ensamblado coincide con los borradores" if m and m.group(1) == drafts_digest(root) else "ensamblado desactualizado"


def c_declaration(root):
    decl = load_declaration()
    if decl is None:
        return False, "falta declaration.py (skill tfm-orchestrator)"
    st = decl.check(root)
    if not st["ok"]:
        return False, "; ".join(st["issues"])
    p = paths.safe_join(root, EXPORT_MD)
    if not p.is_file():
        return False, "protocolo no ensamblado"
    t = paths.read_text(p)
    just = decl.read_justification(paths.read_text(paths.Paths(root).declaration))
    uses = decl.ai_uses(root)
    last = uses[-1]["id"] if uses else "J-0000"
    h = re.search(r"Hasta: (J-\d+)", t)
    if DECL_TITLE not in t:
        return False, "la sección «%s» no está dentro del documento (F-08)" % DECL_TITLE
    if not h or h.group(1) < last:
        return False, "la declaración del documento es anterior al último ai_use (%s)" % last
    if not just.strip() or just not in t:
        return False, "el documento no contiene la justificación de la utilidad de Laura"
    return True, "sección presente, actualizada hasta %s, con justificación de Laura" % h.group(1)


def c_versions(root):
    """PICO and search-string versions cited in the protocol match the latest files (tags [pico:vN], [busqueda:db_vM])."""
    issues, warns = [], []
    pico = sorted(int(m.group(1)) for p in paths.safe_join(root, "02_pico").glob("pico_v*.md") for m in [re.match(r"pico_v(\d+)\.md$", p.name)] if m) \
        if paths.safe_join(root, "02_pico").is_dir() else []
    texts = {sid: (_draft(root, sid)[1] or "") for sid in SECTION_IDS}
    alltext = "\n".join(texts.values())
    if not pico:
        issues.append("no hay 02_pico/pico_v<N>.md")
    else:
        n = pico[-1]
        tags = {int(x) for x in re.findall(r"\[pico:v(\d+)\]", alltext)}
        if n not in tags:
            issues.append("el protocolo no cita la versión vigente del PICO con [pico:v%d]" % n)
        if tags - {n}:
            issues.append("el protocolo cita versiones antiguas del PICO: %s" % sorted("v%d" % t for t in tags - {n}))
        for sid in ("objetivos", "met_elegibilidad"):
            if "[pico:v%d]" % n not in texts[sid]:
                issues.append("falta [pico:v%d] en %s" % (n, sid))
        meta, _ = state_io.load_state(root)
        pv = meta.get("pico_version")
        if pv not in (None, "") and re.sub(r"\D", "", str(pv)) != str(n):
            issues.append("state.md pico_version (%s) no coincide con el último PICO v%d" % (pv, n))
        pf = paths.safe_join(root, "02_pico/pico_v%d.md" % n)
        words = {w for w in re.findall(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]{9,}", paths.read_text(pf).lower())}
        missing = sorted(w for w in words if w not in (texts["objetivos"] + texts["met_elegibilidad"]).lower())[:10]
        if missing:
            warns.append("términos del PICO que no aparecen en objetivos/elegibilidad (aviso, no bloquea): %s" % missing)
    latest = {}
    sd = paths.safe_join(root, "03_busqueda/strings")
    for p in (sd.glob("*_v*.txt") if sd.is_dir() else []):
        m = re.match(r"^(.+)_v(\d+)\.txt$", p.name)
        if m:
            latest[m.group(1)] = max(latest.get(m.group(1), 0), int(m.group(2)))
    for db, v in sorted(latest.items()):
        if "[busqueda:%s_v%d]" % (db, v) not in alltext:
            issues.append("el protocolo no cita la cadena vigente [busqueda:%s_v%d]" % (db, v))
        old = [int(x) for x in re.findall(r"\[busqueda:%s_v(\d+)\]" % re.escape(db), alltext) if int(x) != v]
        if old:
            issues.append("el protocolo cita una versión antigua de la cadena de %s: %s" % (db, old))
    if not latest:
        issues.append("no hay cadenas de búsqueda en 03_busqueda/strings/")
    return (not issues), ("; ".join(issues) if issues else "versiones coherentes"), warns


def _lite_checklist_ok(root):
    p = paths.safe_join(root, "07_verificacion/checklist_refs_LITE.md")
    if not p.is_file():
        return False, "falta checklist_refs_LITE.md"
    first = paths.read_text(p).split("## Referencias sin DOI", 1)[0]
    rows = [l for l in first.split("\n") if l.startswith("|") and not re.match(r"^\|[-| ]+\|$", l)][1:]
    if not rows:
        return False, "la lista LITE no tiene filas"
    bad = [r for r in rows if "✔" not in r.strip().strip("|").split("|")[-1]]
    return (not bad), ("%d fila(s) sin ✔ de Laura" % len(bad)) if bad else "100% filas con ✔"


def c_references(root):
    p = paths.safe_join(root, "07_verificacion/references.csv")
    import csv
    rows = []
    if p.is_file():
        with open(str(p), encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
    if not rows:
        return False, "references.csv vacío o ausente"
    bad = [r.get("ref_id", "?") for r in rows if (r.get("provenance_status") or "").strip().upper() in ("", "NO_PROVENANCE", "UNVERIFIABLE", "UNVERIFIED")]
    if bad:
        return False, "referencias sin procedencia/verificación: %s" % bad[:8]
    max_age = config.load_config(root).get("verification", {}).get("max_report_age_days", 7)
    g = _latest_ver(root, "G-C7")
    if config.get_mode(root) in ("FULL", "LITE-a", "PENDING") and g and g.get("gate") == "pass" and g.get("actor") in ("script", "claude"):
        age = _age_days(g["ts"], paths.utc_now())
        if age > max_age:
            return False, "la última verificación G-C7 tiene %.1f días (máximo %s)" % (age, max_age)
        return True, "G-C7 %s (%.1f días)" % (g["id"], age)
    ok, why = _lite_checklist_ok(root)
    return ok, "verificación por lista LITE firmada por Laura: " + why


def c_integrity(root):
    b = integrity_core.check(root)["blockers"]
    return (not b), ("; ".join("%s %s" % (x["code"], x["path"]) for x in b[:4]) if b else "sin bloqueos")


def c_no_external(root):
    ext = [e["id"] for e in journal_io.read_all(root) if e.get("external_action")]
    return (not ext), ("acciones externas registradas: %s" % ext) if ext else "0 acciones externas"


AUTO = [("A1", "Puerta G-C6 aprobada y sin cambios posteriores en los borradores", c_g6),
        ("A2", "Todas las secciones revisadas por Laura y sin marcas [PENDIENTE]", c_sections_reviewed),
        ("A3", "Protocolo ensamblado al día", c_assembled),
        ("A4", "Sección «Declaración de uso de inteligencia artificial» dentro del documento, con justificación de Laura", c_declaration),
        ("A5", "Versiones de PICO, criterios y cadenas de búsqueda coherentes con el texto del protocolo", None),
        ("A6", "Referencias: 0 NO_PROVENANCE, 0 UNVERIFIABLE y verificación reciente (≤ 7 días) o lista LITE firmada", c_references),
        ("A7", "Integridad del proyecto sin bloqueos", c_integrity),
        ("A8", "0 acciones externas (el sistema no registra nada)", c_no_external)]


def evaluate(root):
    rows, warns = [], []
    for key, label, fn in AUTO:
        if key == "A5":
            ok, detail, w = c_versions(root)
            warns += w
        else:
            ok, detail = fn(root)
        rows.append({"item": key, "label": label, "ok": bool(ok), "detail": detail, "kind": "auto"})
    signed = {}
    for e in journal_io.read_all(root):
        if e.get("kind") == "c9_item_signed" and e.get("actor") == "laura":
            signed[e["item"]] = e["id"]
    for key, label in MANUAL.items():
        rows.append({"item": key, "label": label, "ok": key in signed, "detail": ("firmado %s" % signed[key]) if key in signed else "pendiente de la firma de Laura", "kind": "manual"})
    return {"ok": all(r["ok"] for r in rows), "rows": rows, "warnings": warns}


def render_checklist(res):
    n = sum(1 for r in res["rows"] if r["ok"])
    L = ["# Lista de entrega (calculada por consistency_check.py)", "",
         "Estado: **%d/%d** (%d%%). Se exige el 100%% antes de entregar. El sistema no registra ni envía nada: el registro lo hace Laura." % (n, len(res["rows"]), 100 * n // len(res["rows"])), "",
         "| Ítem | Control | Estado | Detalle |", "|---|---|---|---|"]
    L += ["| %s | %s | %s | %s |" % (r["item"], r["label"], "[x]" if r["ok"] else "[ ]", r["detail"].replace("|", "/")) for r in res["rows"]]
    if res["warnings"]:
        L += ["", "Avisos (no bloquean):", ""] + ["- " + w for w in res["warnings"]]
    L += ["", "Fecha del cálculo: " + paths.utc_now(), ""]
    return "\n".join(L)


def cmd_check(root, a):
    res = evaluate(root)
    paths.write_text_atomic(paths.safe_join(root, CHECKLIST_REL), render_checklist(res))
    if a.journal:
        ts = paths.utc_now().replace(":", "").replace("-", "")
        ref = journal_io.make_script_report(root, "consistency_check.py", "07_verificacion/reports/g_c9_%s.json" % ts, "pass" if res["ok"] else "fail",
                                            details={"rows": res["rows"]}, version=VERSION)
        e = journal_io.add(root, {"stage": "C9", "type": "verification", "actor": "script", "gate_name": "G-C9", "gate": "pass" if res["ok"] else "fail",
                                  "script_report": ref, "tool": _tool(), "human_decision": "n/a",
                                  "what_es": "Puerta G-C9 (entrega): %s" % ("cumplida" if res["ok"] else "no cumplida: " + "; ".join(r["item"] for r in res["rows"] if not r["ok"]))})
        res["journal_id"] = e["id"]
    res["checklist"] = CHECKLIST_REL
    out(res)
    return 0 if res["ok"] else 1


def cmd_sign(root, a):
    if not a.laura_confirmed:
        out({"ok": False, "error": "falta --laura-confirmed: solo Laura firma"})
        return 1
    if a.item not in MANUAL:
        out({"ok": False, "error": "ítem no válido: %s (válidos: %s)" % (a.item, ", ".join(MANUAL))})
        return 1
    e = journal_io.add(root, {"stage": "C9", "type": "decision", "actor": "laura", "kind": "c9_item_signed", "item": a.item,
                              "what_es": "Laura firma: " + MANUAL[a.item], "human_decision": "aprobado por Laura", "tool": _tool()})
    out({"ok": True, "journal_id": e["id"]})
    return 0


def parse_template(target):
    p = os.path.join(os.path.dirname(_here), "templates", "%s_fields_es.md" % target)
    with open(p, encoding="utf-8") as f:
        text = f.read().replace("\r\n", "\n")
    fields, cur = [], None
    for line in text.split("\n"):
        if line.startswith("### "):
            cur = {"label": line[4:].strip(), "sources": []}
            fields.append(cur)
        elif cur is not None:
            m = re.match(r"^<!-- source: (.+) -->$", line.strip())
            if m and m.group(1).strip() != "none":
                cur["sources"] = [s.strip() for s in m.group(1).split(",")]
    return fields


def cmd_fields(root, a):
    rel = "09_registro/%s_campos_es.md" % ("prospero" if a.target == "prospero" else "osf")
    full = paths.safe_join(root, rel)
    if full.is_file() and not a.force:
        out({"ok": False, "error": "%s ya existe; usa --force (se guarda la versión anterior)" % rel})
        return 1
    if full.is_file():
        paths.write_text_atomic(paths.safe_join(root, "09_registro/versions/%s_%s.md" % (os.path.basename(rel)[:-3], paths.utc_now().replace(":", ""))), paths.read_text(full))
    L = ["[draft-ai]", "", "# Campos de %s para el registro (borrador)" % a.target.upper(), "",
         "Texto copiado del protocolo; Laura lo adapta al formulario vigente de la plataforma y lo envía ella misma. "
         "Estado: **NO ENVIADO**. Los campos [PENDIENTE] los completa Laura.", ""]
    for f in parse_template(a.target):
        L += ["## " + f["label"], ""]
        parts = []
        for sid in f["sources"]:
            m, body = _draft(root, sid)
            if body and "[PENDIENTE" not in body:
                parts.append("%s\n\n*(copiado de la sección «%s» del protocolo)*" % (body.strip(), sid))
        L += ["\n\n".join(parts) if parts else "[PENDIENTE: lo escribe Laura%s]" % ((" a partir de: " + ", ".join(f["sources"])) if f["sources"] else ""), ""]
    paths.write_text_atomic(full, "\n".join(L))
    e = journal_io.add(root, {"stage": "C9", "type": "change", "actor": "claude", "advisory": True, "tool": _tool(), "human_decision": "pendiente",
                              "what_es": "Borrador de campos %s a partir del protocolo (no enviado)" % a.target.upper(), "outputs": [journal_io.file_ref(root, rel)]})
    out({"ok": True, "path": rel, "journal_id": e["id"]})
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--journal", action="store_true")
    s = sub.add_parser("sign")
    s.add_argument("--item", required=True)
    s.add_argument("--laura-confirmed", action="store_true")
    f = sub.add_parser("fields")
    f.add_argument("--target", choices=["prospero", "osf"], required=True)
    f.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    try:
        root = paths.find_root(a.root)
    except paths.ProjectNotFound as e:
        out({"ok": False, "error": str(e)})
        return 2
    if config.get_mode(root) in ("LITE-b", "LITE-P"):
        out({"ok": False, "error": "modo %s: sin scripts; usa la lista de entrega a mano (SKILL.md)" % config.get_mode(root)})
        return 2
    try:
        return {"check": cmd_check, "sign": cmd_sign, "fields": cmd_fields}[a.cmd](root, a)
    except (journal_io.JournalError, ValueError) as ex:
        out({"ok": False, "errors": getattr(ex, "errors", [str(ex)])})
        return 1


if __name__ == "__main__":
    sys.exit(main())
