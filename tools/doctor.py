#!/usr/bin/env python3
"""Pre-flight check for the TFM system (stdlib only, Python >= 3.8).

Usage (from the repo / project folder):
  python tools/doctor.py              all checks (needs internet for the network part)
  python tools/doctor.py --offline    skip network checks
  python tools/doctor.py --json       machine-readable result

Exit code: 0 = ready (warnings allowed), 1 = something blocking is missing.
Messages are Spanish (shown to Laura); code stays English.
"""
import argparse
import importlib.util
import json
import os
import pathlib
import platform
import shutil
import ssl
import sys
import urllib.request

SKILLS = ["tfm-orchestrator", "topic-scout", "pico-builder", "search-strategist", "screening-planner",
          "methods-advisor", "protocol-writer", "verifier", "panel-builder", "registration-finalizer"]
HOSTS = ["https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi",
         "https://api.crossref.org/works?rows=0",
         "https://api.openalex.org/works?per_page=1"]
ROOT = pathlib.Path(__file__).resolve().parent.parent

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass


def read_version(p):
    out = {}
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip()
    except OSError:
        pass
    return out


def check_network(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "tfm-doctor/1.0"})
        with urllib.request.urlopen(req, timeout=10, context=ssl.create_default_context()) as r:
            return r.status < 500, "HTTP %s" % r.status
    except Exception as e:  # noqa: BLE001
        return False, type(e).__name__ + ": " + str(e)[:120]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    res = []  # (id, ok, blocking, message_es)

    v = sys.version_info
    res.append(("python", v >= (3, 8), True,
                "Python %d.%d.%d (%s)" % (v.major, v.minor, v.micro, platform.system())
                + ("" if v >= (3, 8) else " — se necesita 3.8 o superior (recomendado 3.12)")))

    is_root = (ROOT / "state.md").is_file() and (ROOT / "config" / "project.yaml").is_file()
    res.append(("project", is_root, True,
                "Carpeta del proyecto: %s" % ROOT if is_root else "No encuentro state.md + config/project.yaml en %s" % ROOT))

    writable = os.access(str(ROOT), os.W_OK)
    res.append(("write", writable, True, "Se puede escribir en la carpeta" if writable else "La carpeta es de solo lectura"))

    missing, versions, hashes = [], {}, set()
    for s in SKILLS:
        d = ROOT / ".claude" / "skills" / s
        if not (d / "SKILL.md").is_file():
            missing.append(s)
            continue
        info = read_version(d / "VERSION")
        versions[s] = info.get("version", "?")
        hashes.add(info.get("common_hash", "?"))
    ok_sk = not missing and len(hashes) == 1
    msg = "10 skills instalados (v%s)" % ", ".join(sorted(set(versions.values()))) if ok_sk else \
        ("Faltan skills: %s" % ", ".join(missing) if missing else "Los skills tienen versiones de _common distintas")
    res.append(("skills", ok_sk, True, msg))

    git = shutil.which("git")
    res.append(("git", bool(git), False, "git disponible (para actualizaciones)" if git else
                "git no está instalado: el sistema funciona, pero «Actualiza el sistema» no (instala Git for Windows)"))

    docx = importlib.util.find_spec("docx") is not None
    res.append(("python-docx", docx, False, "python-docx instalado (exportar .docx)" if docx else
                "python-docx no está: el protocolo saldrá en Markdown. Para .docx: python -m pip install --user python-docx"))

    if not a.offline:
        for url in HOSTS:
            host = url.split("/")[2]
            ok, detail = check_network(url)
            res.append(("net:" + host, ok, False, ("Internet OK: %s" % host) if ok else
                        "Sin acceso a %s (%s) → el sistema irá en modo LITE-a" % (host, detail)))

        if any(not ok and i.startswith("net:") for i, ok, _, m in res) and \
                any("CERTIFICATE_VERIFY_FAILED" in m for _, _, _, m in res):
            fix = ('macOS: abre «/Applications/Python 3.x/Install Certificates.command» (doble clic) y repite'
                   if platform.system() == "Darwin" else
                   "Windows: python -m pip install --user pip-system-certs  (usa los certificados de Windows) y repite")
            res.append(("ssl-fix", False, False, "Error de certificados SSL de Python. " + fix))

    blocking_fail = any(not ok and blk for _, ok, blk, _ in res)
    if a.json:
        print(json.dumps({"ready": not blocking_fail, "checks": [
            {"id": i, "ok": ok, "blocking": blk, "message_es": m} for i, ok, blk, m in res]}, ensure_ascii=False, indent=2))
    else:
        for _, ok, blk, m in res:
            print(("[OK]    " if ok else ("[FALTA] " if blk else "[AVISO] ")) + m)
        print("RESULTADO: " + ("LISTO — sigue con la prueba del sistema (GATE-0)" if not blocking_fail
                               else "FALTA ALGO — corrige las líneas [FALTA] (ver INSTALL.md)"))
    return 1 if blocking_fail else 0


if __name__ == "__main__":
    sys.exit(main())
