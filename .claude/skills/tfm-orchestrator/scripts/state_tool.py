#!/usr/bin/env python3
"""state_tool.py get|set|validate|init  (state.md contract tfm-state/v1; <= 1500 tokens).

  get [key]                       print state frontmatter (or one key) as JSON
  set key=value [key=value ...]   value parsed as YAML scalar/flow: stage=C1  open_decisions='[a, b]'
      [--body-file f.md]          also replace the Spanish body
      last_journal_id is refreshed automatically from the journal
  validate [--always-load]        schema + size; --always-load adds CLAUDE.md + 10 descriptions (~50 tok each) <= 2000
  init                            create a fresh state.md (only if absent)
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import journal_io, miniyaml, paths, state_io  # noqa: E402


def out(o):
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("get")
    g.add_argument("key", nargs="?")
    s = sub.add_parser("set")
    s.add_argument("pairs", nargs="+")
    s.add_argument("--body-file")
    v = sub.add_parser("validate")
    v.add_argument("--always-load", action="store_true")
    sub.add_parser("init")
    args = ap.parse_args(argv)
    try:
        root = paths.find_root(args.root)
    except paths.ProjectNotFound as e:
        if args.cmd != "init" or not args.root:
            out({"ok": False, "error": str(e)})
            return 2
        root = paths.Paths(args.root).root
    if args.cmd == "init":
        p = paths.Paths(root).state
        if p.exists():
            out({"ok": False, "error": "state.md already exists"})
            return 1
        meta, body = state_io.initial_state()
        state_io.save_state(root, meta, body)
        out({"ok": True})
        return 0
    if args.cmd == "get":
        meta, _ = state_io.load_state(root)
        out(meta if not args.key else {args.key: meta.get(args.key)})
        return 0
    if args.cmd == "set":
        fields = {}
        for pr in args.pairs:
            if "=" not in pr:
                out({"ok": False, "error": "use key=value: %s" % pr})
                return 2
            k, val = pr.split("=", 1)
            fields[k.strip()] = miniyaml.parse_scalar(val)
        meta, body = state_io.load_state(root)
        meta.update(fields)
        meta["last_journal_id"] = journal_io.last_id(root)
        meta["updated"] = paths.utc_now()
        if args.body_file:
            body = paths.read_text(args.body_file)
        errs = state_io.validate_meta(meta)
        tokens = state_io.estimate_tokens(state_io.render(meta, body))
        if tokens > state_io.MAX_STATE_TOKENS:
            errs.append("state.md would be ~%d tokens (> %d)" % (tokens, state_io.MAX_STATE_TOKENS))
        if errs:
            out({"ok": False, "errors": errs})
            return 1
        state_io.save_state(root, meta, body)
        out({"ok": True, "tokens": tokens})
        return 0
    r = state_io.validate_state(root, journal_io.last_id(root))
    if args.always_load:
        claude = paths.Paths(root).root / "CLAUDE.md"
        ct = state_io.estimate_tokens(paths.read_text(claude)) if claude.is_file() else 0
        total = ct + r["tokens"] + 10 * 50
        r["always_load_tokens"] = total
        r["claude_md_tokens"] = ct
        if total > state_io.MAX_ALWAYS_LOAD_TOKENS:
            r["ok"] = False
            r["errors"].append("always-load ~%d tokens > %d" % (total, state_io.MAX_ALWAYS_LOAD_TOKENS))
    out(r)
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
