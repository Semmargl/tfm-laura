#!/usr/bin/env python3
"""Build the Cowork install package from this repo (stdlib only).

  python tools/build_release.py            -> dist/TFM_Laura_instalacion_v<VERSION>.zip + dist/skills/*.zip

The package = EMPIEZA_AQUI.md (Cowork steps) + skills/<name>.zip (folder at zip root, for
Customize -> Skills -> Upload) + TFM_Laura/ (Laura's project folder skeleton).
Used locally and by .github/workflows/release.yml on every tag v*.
"""
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
NOT_PROJECT = {".claude", ".git", ".github", "tools", "dist", "docs", "README.md", "INSTALL.md",
               "CHANGELOG.md", "VERSION", ".gitignore", ".gitattributes", ".DS_Store", "_index.md"}
SKIP_PARTS = {"__pycache__", ".DS_Store"}
STAMP = (2026, 1, 1, 0, 0, 0)  # deterministic zips


def files_under(base):
    for p in sorted(base.rglob("*")):
        if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_PARTS) and p.suffix != ".pyc":
            yield p


def add(zf, src, arc):
    zi = zipfile.ZipInfo(arc, STAMP)
    zi.compress_type = zipfile.ZIP_DEFLATED
    zi.external_attr = 0o644 << 16
    zf.writestr(zi, src.read_bytes())


def main():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    (DIST / "skills").mkdir(parents=True, exist_ok=True)
    skills_dir = ROOT / ".claude" / "skills"
    skill_zips = []
    for sk in sorted(d for d in skills_dir.iterdir() if d.is_dir()):
        out = DIST / "skills" / (sk.name + ".zip")
        with zipfile.ZipFile(out, "w") as zf:
            for f in files_under(sk):
                add(zf, f, sk.name + "/" + f.relative_to(sk).as_posix())
        skill_zips.append(out)

    pkg = DIST / ("TFM_Laura_instalacion_v%s.zip" % version)
    top = "TFM_Laura_instalacion/"
    with zipfile.ZipFile(pkg, "w") as zf:
        add(zf, ROOT / "docs" / "EMPIEZA_AQUI_COWORK.md", top + "EMPIEZA_AQUI.md")
        for z in skill_zips:
            add(zf, z, top + "skills/" + z.name)
        for item in sorted(ROOT.iterdir()):
            if item.name in NOT_PROJECT:
                continue
            for f in ([item] if item.is_file() else files_under(item)):
                add(zf, f, top + "TFM_Laura/" + f.relative_to(ROOT).as_posix())
    print("OK %s (%d skills)" % (pkg.relative_to(ROOT), len(skill_zips)))
    return 0 if len(skill_zips) == 10 else 1


if __name__ == "__main__":
    sys.exit(main())
