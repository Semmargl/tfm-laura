#!/usr/bin/env python3
"""version_save.py: edit a protocol draft without losing the previous version (inv. 2, G-C6 «100% versions»).

  replace --section S --text-file new.md --what-es "..." [--why-es ".."] [--actor claude|laura]
      copies the current draft to 06_protocolo/versions/<S>_<ts>.md, writes the new text as [draft-ai]
      (an edit always needs Laura's new confirmation), and journals a `change` with sha256 + previous_version.
  list --section S     previous versions of a section
Claude's text is [draft-ai] until Laura marks it [author-reviewed] (assemble_protocol.py mark-reviewed).
"""
import argparse
import json
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
import protocol_lib as L  # noqa: E402
from _common import journal_io, paths  # noqa: E402


def out(o):
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")


def replace(root, sid, new_text, what_es, why_es="", actor="claude"):
    if sid not in L.SECTION_IDS:
        raise ValueError("sección desconocida: %s" % sid)
    rel = L.draft_rel(sid)
    full = paths.safe_join(root, rel)
    _, body = L.split_marker(new_text)
    if not body.strip():
        raise ValueError("el texto nuevo está vacío")
    prev = None
    if full.is_file() and full.stat().st_size > 0:
        prev = "%s/%s_%s.md" % (L.VERSIONS, sid, paths.utc_now().replace(":", "").replace("-", ""))
        paths.write_text_atomic(paths.safe_join(root, prev), paths.read_text(full))
    paths.write_text_atomic(full, L.join_marker("draft-ai", body))
    e = {"stage": "C6", "type": "change", "actor": actor, "kind": "edit" if prev else "create", "section": sid,
         "what_es": what_es, "why_es": why_es, "tool": journal_io.tool_string("version_save.py", L.VERSION),
         "human_decision": "pendiente", "body_sha256": L.body_sha(body), "outputs": [journal_io.file_ref(root, rel)]}
    if prev:
        e["previous_version"] = prev
    if actor == "claude":
        e["advisory"] = True
    return journal_io.add(root, e)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("replace")
    r.add_argument("--section", required=True)
    r.add_argument("--text-file", required=True)
    r.add_argument("--what-es", required=True)
    r.add_argument("--why-es", default="")
    r.add_argument("--actor", choices=["claude", "laura"], default="claude")
    li = sub.add_parser("list")
    li.add_argument("--section", required=True)
    a = ap.parse_args(argv)
    try:
        root = paths.find_root(a.root)
    except paths.ProjectNotFound as ex:
        out({"ok": False, "error": str(ex)})
        return 2
    try:
        if a.cmd == "list":
            d = paths.safe_join(root, L.VERSIONS)
            out({"ok": True, "versions": sorted(p.name for p in d.glob(a.section + "_*.md")) if d.is_dir() else []})
            return 0
        e = replace(root, a.section, paths.read_text(a.text_file), a.what_es, a.why_es, a.actor)
        out({"ok": True, "journal_id": e["id"], "previous_version": e.get("previous_version")})
        return 0
    except (journal_io.JournalError, ValueError) as ex:
        out({"ok": False, "errors": getattr(ex, "errors", [str(ex)])})
        return 1


if __name__ == "__main__":
    sys.exit(main())
