#!/usr/bin/env python3
"""journal.py add|validate|tail|query  (append-only journal; owner = orchestrator).

  add --json -            read one JSON entry from stdin (preferred: no shell-escaping problems)
  add --file entry.json   or from a file
  validate                whole-file validation (exit 1 on error)
  tail [-n 20]            last N entries
  query --type ai_use [--stage C1] [--actor laura] [--gate pass]
Entry fields: see README_BUILD.md. id/ts are assigned by the script.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import journal_io, paths  # noqa: E402

VERSION = "1.0"


def out(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--json")
    a.add_argument("--file")
    sub.add_parser("validate")
    t = sub.add_parser("tail")
    t.add_argument("-n", type=int, default=20)
    q = sub.add_parser("query")
    for k in ("type", "stage", "actor", "gate"):
        q.add_argument("--" + k)
    args = ap.parse_args(argv)
    try:
        root = paths.find_root(args.root)
    except paths.ProjectNotFound as e:
        out({"ok": False, "error": str(e)})
        return 2
    if args.cmd == "add":
        raw = sys.stdin.read() if args.json == "-" else (open(args.file, encoding="utf-8-sig").read() if args.file else args.json)
        if not raw:
            out({"ok": False, "error": "no entry given (--json - | --json '{..}' | --file)"})
            return 2
        try:
            e = journal_io.add(root, json.loads(raw))
        except (journal_io.JournalError, ValueError) as ex:
            out({"ok": False, "errors": getattr(ex, "errors", [str(ex)])})
            return 1
        out({"ok": True, "id": e["id"], "entry": e})
        return 0
    if args.cmd == "validate":
        r = journal_io.validate_file(root)
        out(r)
        return 0 if r["ok"] else 1
    if args.cmd == "tail":
        for e in journal_io.tail(root, args.n):
            out(e)
        return 0
    for e in journal_io.query(root, type=args.type, stage=args.stage, actor=args.actor, gate=args.gate):
        out(e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
