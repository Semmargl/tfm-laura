"""config/project.yaml + config/databases.yaml access (stdlib; miniyaml)."""
from __future__ import annotations

import copy
import re

from . import miniyaml, paths

DEFAULTS = {
    "schema": "tfm-config/v1",
    "mode": "PENDING",
    "email": "",
    "citation_style": "vancouver",
    "citation_style_status": "provisional",
    "language": "es",
    "caps": {
        "warn_after": 50,
        "eutils_per_s": 3,
        "eutils_per_run": 200,
        "openalex_per_run": 500,
        "crossref_per_run": 1000,
        "clinicaltrials_per_run": 200,
        "europepmc_per_run": 200,
    },
    "feasibility": {"min_rct_ct": 10, "no_sr_same_pico_years": 3, "status": "pendiente de validar con tutor"},
    "supervisor_check_pct": 20,
    "pilot_n": 50,
    "recall": {"seed_min": 10, "held_out_min": 5, "ratio_seed": 0.95, "ratio_held_out": 0.90},
    "verification": {"max_report_age_days": 7},
}


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(root) -> dict:
    p = paths.Paths(root).project_yaml
    data = miniyaml.loads(paths.read_text(p)) if p.is_file() else {}
    return _merge(DEFAULTS, data if isinstance(data, dict) else {})


def load_databases(root) -> dict:
    p = paths.Paths(root).databases_yaml
    return miniyaml.loads(paths.read_text(p)) if p.is_file() else {}


def get_mode(root) -> str:
    return str(load_config(root).get("mode", "PENDING"))


def required_databases(root) -> list:
    return list((load_databases(root).get("required") or []))


def set_scalar(root, dotted_key: str, value) -> None:
    """Line-based edit of an existing scalar in project.yaml (keeps comments/layout).
    dotted_key like 'mode' or 'caps.warn_after'. Raises KeyError if the key is absent."""
    p = paths.Paths(root).project_yaml
    lines = paths.read_text(p).split("\n")
    want = dotted_key.split(".")
    stack = []  # (indent, key)
    for i, ln in enumerate(lines):
        if not ln.strip() or ln.strip().startswith("#"):
            continue
        m = re.match(r"^(\s*)([^\s:#-][^:]*?):(\s*)(.*)$", ln)
        if not m:
            continue
        indent = len(m.group(1))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        key = m.group(2).strip().strip("\"'")
        stack.append((indent, key))
        if [k for _, k in stack] == want:
            val, comment = m.group(4), ""
            cm = re.search(r"\s+#.*$", val)
            if cm and not val.strip().startswith(('"', "'")):
                comment = cm.group(0)
            lines[i] = "%s%s:%s%s%s" % (m.group(1), m.group(2), m.group(3) or " ", miniyaml._scalar_out(value), comment)
            paths.write_text_atomic(p, "\n".join(lines))
            return
    raise KeyError(dotted_key)
