#!/usr/bin/env python3
"""GATE-0 smoke test (sec 2): probes S1-S3 by script, S0/S4/S5 + S2 manual parts as flags.

  python smoke_test.py --all --s0 yes --s4 pass --s5 pass     full GATE-0, writes report, sets mode
  python smoke_test.py --s1 | --s2 | --s3                      single probes (no mode change unless --apply)
  python smoke_test.py --degrade "motivo"                       FULL -> LITE-a after a network error
Manual flags: --s0 yes|no  --s2-resume pass|fail  --s2-visible pass|fail  --s4 pass|fail  --s5 pass|fail
Output: JSON on stdout (+ summary_es). Report: _smoke/smoke_report.json. Mode table: modes.decide_mode.
"""
import argparse
import hashlib
import json
import os
import platform
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import config, http_client, journal_io, modes, paths, state_io  # noqa: E402

VERSION = "1.0"
UNICODE_SAMPLE = "ñ á é í ó ú ü ¿¡ diástasis — 診"
S3_URLS = {
    "eutils": ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
               {"db": "pubmed", "term": "diastasis recti", "rettype": "count"}),
    "crossref": ("https://api.crossref.org/works/10.1186/2046-4053-4-1", None),
    "openalex": ("https://api.openalex.org/works/doi:10.1186/2046-4053-4-1", None),
}
S3_OPTIONAL = ("https://clinicaltrials.gov/api/v2/studies", {"pageSize": "1"})

FALLBACK_ES = {
    "S0": "Revisa Settings > Capabilities: activa «Create and edit files» y «Allow network egress»; actualiza Claude para Windows.",
    "S1": "Sin ejecución de código: modo LITE-b (sin scripts; todo por lista de comprobación).",
    "S2": "Sin carpeta conectada: modo LITE-P (estado en un Proyecto de Claude; descarga y reemplaza state.md y journal.jsonl al final de cada sesión).",
    "S3": "Sin acceso a internet desde el código: modo LITE-a (scripts sin red; conteos y verificación por PubMed/pubmed.gov con tu confirmación).",
    "S4": "El conector PubMed no responde: las comprobaciones se hacen a mano en pubmed.ncbi.nlm.nih.gov.",
    "S5": "CLAUDE.md no se aplica: pega su texto en Settings > Cowork > Global instructions (o en las instrucciones de la carpeta). «Personal preferences» solo sirve en modo LITE-P.",
}


def probe_s1():
    r = {"id": "S1", "name": "Ejecución de código", "checks": {}}
    r["checks"]["python>=3.10"] = sys.version_info >= (3, 10)
    r["python"] = platform.python_version()
    try:
        d = tempfile.mkdtemp(prefix="tfm_s1_")
        p = os.path.join(d, "diástasis_ñ.txt")
        data = UNICODE_SAMPLE.encode("utf-8")
        with open(p, "wb") as f:
            f.write(data)
        with open(p, "rb") as f:
            back = f.read()
        r["checks"]["utf8_roundtrip"] = back == data and hashlib.sha256(back).hexdigest() == hashlib.sha256(data).hexdigest()
        r["checks"]["utf8_filename"] = os.path.basename(p) in os.listdir(d)
    except Exception as e:  # noqa: BLE001
        r["checks"]["utf8_roundtrip"] = False
        r["error"] = str(e)
    r["pass"] = all(r["checks"].values())
    return r


def probe_s2(root, resume="pending", visible="pending"):
    r = {"id": "S2", "name": "Carpeta conectada", "checks": {}}
    P = paths.Paths(root)
    try:
        P.smoke_dir.mkdir(parents=True, exist_ok=True)
        probe = P.smoke_dir / "probe.txt"
        content = "tfm smoke probe %s\n%s\n" % (paths.utc_now(), UNICODE_SAMPLE)
        probe.write_bytes(content.encode("utf-8"))
        back = probe.read_bytes()
        r["checks"]["write_read"] = back == content.encode("utf-8")
        r["sha256"] = paths.sha256_bytes(back)
        uni = P.smoke_dir / "diástasis_ñ.txt"
        uni.write_bytes(UNICODE_SAMPLE.encode("utf-8"))
        r["checks"]["unicode_filename"] = uni.read_bytes().decode("utf-8") == UNICODE_SAMPLE
        r["mounted_path"] = str(probe)
    except Exception as e:  # noqa: BLE001
        r["checks"]["write_read"] = False
        r["error"] = str(e)
    r["manual"] = {"resume_new_session": resume, "visible_in_windows": visible}
    r["pass"] = all(r["checks"].values()) and resume != "fail" and visible != "fail"
    r["manual_pending"] = [k for k, v in r["manual"].items() if v == "pending"]
    return r


def _xml_count(text):
    return int(ET.fromstring(text).findtext("Count"))


def probe_s3(root, client=None):
    r = {"id": "S3", "name": "Acceso a internet (egress)", "checks": {}, "details": {}}
    client = client or http_client.HttpClient(root, use_cache=False, max_retries=1)

    def run(name, url, params, validate):
        try:
            resp = client.get(url, params, cache="none")
            ok = resp.status == 200 and validate(resp)
            r["checks"][name] = bool(ok)
            r["details"][name] = {"status": resp.status, "url": url}
        except http_client.NetworkError as e:
            r["checks"][name] = False
            r["details"][name] = {"error": "red: %s" % e}
        except http_client.HttpError as e:
            r["checks"][name] = False
            r["details"][name] = {"error": "HTTP %s" % e.status}
        except Exception as e:  # noqa: BLE001  (bad XML/JSON = FAIL, not crash)
            r["checks"][name] = False
            r["details"][name] = {"error": "respuesta no válida: %s" % e}

    run("eutils", *S3_URLS["eutils"], validate=lambda x: _xml_count(x.text) > 0)
    run("crossref", *S3_URLS["crossref"],
        validate=lambda x: any("PRISMA-P" in t for t in x.json()["message"]["title"]))
    run("openalex", *S3_URLS["openalex"], validate=lambda x: "id" in x.json())
    opt = {}
    try:
        resp = client.get(S3_OPTIONAL[0], S3_OPTIONAL[1], cache="none")
        opt = {"status": resp.status, "ok": resp.status == 200 and "studies" in resp.json()}
    except Exception as e:  # noqa: BLE001
        opt = {"ok": False, "error": str(e)}
    r["optional_clinicaltrials"] = opt
    r["pass"] = all(r["checks"].get(k) for k in ("eutils", "crossref", "openalex"))
    return r


def manual_probe(pid, name, val):
    ok = {"yes": True, "pass": True, "no": False, "fail": False}.get(val)
    return {"id": pid, "name": name, "pass": ok, "manual": val}


def run(root, which, manual=None, client=None, apply=True):
    manual = manual or {}
    probes = {}
    if "S1" in which:
        probes["S1"] = probe_s1()
    if "S2" in which:
        probes["S2"] = probe_s2(root, manual.get("s2_resume", "pending"), manual.get("s2_visible", "pending"))
    if "S3" in which:
        probes["S3"] = probe_s3(root, client)
    for pid, name, key in (("S0", "Entorno (Claude para Windows, Cowork)", "s0"), ("S4", "Conector PubMed", "s4"),
                           ("S5", "Reglas de la carpeta (CLAUDE.md)", "s5")):
        if manual.get(key):
            probes[pid] = manual_probe(pid, name, manual[key])
    rep = {"schema": "tfm-smoke/v1", "ts": paths.utc_now(), "script_version": VERSION, "python": platform.python_version(),
           "platform": platform.platform(), "root": str(root), "probes": probes, "fallbacks_es": {}}
    for pid, p in probes.items():
        if p["pass"] is False:
            rep["fallbacks_es"][pid] = FALLBACK_ES[pid]
    full = {"S1", "S2", "S3"} <= set(probes)
    if full:
        rep["mode"] = modes.decide_mode(probes["S1"]["pass"], probes["S2"]["pass"], probes["S3"]["pass"])
        rep["gate0_complete"] = all(k in probes for k in ("S0", "S4", "S5")) and not probes["S2"].get("manual_pending")
        names = {"FULL": "FULL", "LITE-a": "LITE-a (sin red)", "LITE-b": "LITE-b (sin scripts)", "LITE-P": "LITE-P (sin carpeta)"}
        rep["summary_es"] = "Modo: %s" % names[rep["mode"]]
        if not rep["gate0_complete"]:
            rep["summary_es"] += " (provisional: faltan respuestas de Laura en S0/S2/S4/S5)"
    else:
        rep["summary_es"] = "Sonda(s) ejecutada(s): %s" % ", ".join(
            "%s=%s" % (k, "OK" if v["pass"] else ("pendiente" if v["pass"] is None else "FALLO")) for k, v in probes.items())
    if full or apply:
        P = paths.Paths(root)
        P.smoke_dir.mkdir(parents=True, exist_ok=True)
        paths.write_text_atomic(P.smoke_report, json.dumps(rep, ensure_ascii=False, indent=1) + "\n")
    if full and apply:
        old = config.get_mode(root)
        e = modes.set_mode(root, rep["mode"], "Resultado de la prueba del sistema (GATE-0). " + rep["summary_es"],
                           script="smoke_test.py")
        # link the report to the setup entry (second, informative entry keeps set_mode generic)
        e2 = journal_io.add(root, {"stage": "setup", "type": "setup", "actor": "script", "tool": "smoke_test.py v" + VERSION,
                                   "what_es": "Informe GATE-0 guardado (modo %s, antes %s)" % (rep["mode"], old),
                                   "outputs": [journal_io.file_ref(root, "_smoke/smoke_report.json")]})
        state_io.set_fields(root, last_journal_id=e2["id"])
        rep["journal_id"] = e["id"]
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    for k in ("s1", "s2", "s3", "all"):
        ap.add_argument("--" + k, action="store_true")
    ap.add_argument("--s0")
    ap.add_argument("--s4")
    ap.add_argument("--s5")
    ap.add_argument("--s2-resume", dest="s2_resume")
    ap.add_argument("--s2-visible", dest="s2_visible")
    ap.add_argument("--no-apply", action="store_true", help="do not change mode/journal")
    ap.add_argument("--degrade", metavar="MOTIVO")
    a = ap.parse_args(argv)
    try:
        root = paths.find_root(a.root)
    except paths.ProjectNotFound as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2
    if a.degrade:
        e = modes.degrade_to_lite_a(root, a.degrade)
        print(json.dumps({"ok": True, "changed": bool(e), "mode": config.get_mode(root),
                          "summary_es": "Modo: LITE-a (sin red). Motivo: " + a.degrade if e else "Sin cambios (no estaba en FULL)"},
                         ensure_ascii=False))
        return 0
    which = {"S1", "S2", "S3"} if a.all or not (a.s1 or a.s2 or a.s3) else {k.upper() for k in ("s1", "s2", "s3") if getattr(a, k)}
    manual = {k: getattr(a, k) for k in ("s0", "s4", "s5", "s2_resume", "s2_visible") if getattr(a, k)}
    rep = run(root, which, manual, apply=not a.no_apply)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if all(p["pass"] is not False for p in rep["probes"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
