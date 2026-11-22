"""Minimal YAML subset reader/writer (stdlib only; Cowork may lack PyYAML).

Supported: block mappings, block lists of scalars, flow lists/maps ([a, b], {k: v}),
quoted/plain scalars, int/float/bool/null, '#' comments. Dates stay strings.
"""
from __future__ import annotations

import json
import re

__all__ = ["loads", "dumps", "parse_scalar", "YamlError"]


class YamlError(ValueError):
    pass


_INT = re.compile(r"^[-+]?\d+$")
_FLOAT = re.compile(r"^[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?$")


def _strip_comment(s: str) -> str:
    out, q = [], None
    for i, ch in enumerate(s):
        if q:
            out.append(ch)
            if ch == q and (q == "'" or s[i - 1] != "\\"):
                q = None
        elif ch in "\"'":
            q = ch
            out.append(ch)
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def parse_scalar(tok: str):
    t = tok.strip()
    if t == "" or t in ("~", "null", "Null", "NULL"):
        return None
    if t in ("true", "True", "TRUE"):
        return True
    if t in ("false", "False", "FALSE"):
        return False
    if t[0] == '"':
        try:
            return json.loads(t)
        except ValueError as e:
            raise YamlError("bad double-quoted scalar: %s" % t) from e
    if t[0] == "'":
        if len(t) < 2 or t[-1] != "'":
            raise YamlError("bad single-quoted scalar: %s" % t)
        return t[1:-1].replace("''", "'")
    if t[0] in "[{":
        return _parse_flow(t)
    if _INT.match(t):
        return int(t)
    if _FLOAT.match(t):
        return float(t)
    return t


def _split_flow(inner: str):
    parts, depth, q, cur = [], 0, None, []
    for i, ch in enumerate(inner):
        if q:
            cur.append(ch)
            if ch == q and (q == "'" or inner[i - 1] != "\\"):
                q = None
            continue
        if ch in "\"'":
            q = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    last = "".join(cur)
    if last.strip() != "" or parts:
        parts.append(last)
    return parts


def _split_key(item: str):
    q = None
    for i, ch in enumerate(item):
        if q:
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
        elif ch == ":" and (i + 1 == len(item) or item[i + 1] == " "):
            return item[:i], item[i + 1:]
    raise YamlError("expected 'key: value' in flow map: %s" % item)


def _parse_flow(t: str):
    if t[0] == "[" and t[-1] == "]":
        return [parse_scalar(p) for p in _split_flow(t[1:-1]) if p.strip() != ""]
    if t[0] == "{" and t[-1] == "}":
        d = {}
        for p in _split_flow(t[1:-1]):
            if p.strip() == "":
                continue
            k, v = _split_key(p.strip())
            d[parse_scalar(k)] = parse_scalar(v)
        return d
    raise YamlError("unbalanced flow collection: %s" % t)


def loads(text: str):
    raw = text.replace("\r\n", "\n").replace("\t", "  ").split("\n")
    lines = []
    for ln in raw:
        s = _strip_comment(ln)
        if s.strip() == "":
            continue
        lines.append((len(s) - len(s.lstrip(" ")), s.strip()))
    if not lines:
        return {}
    val, idx = _block(lines, 0, lines[0][0])
    if idx != len(lines):
        raise YamlError("unexpected content near: %s" % lines[idx][1])
    return val


def _block(lines, i, indent):
    if lines[i][1].startswith("- ") or lines[i][1] == "-":
        return _list(lines, i, indent)
    return _map(lines, i, indent)


def _list(lines, i, indent):
    out = []
    while i < len(lines) and lines[i][0] == indent and (lines[i][1].startswith("- ") or lines[i][1] == "-"):
        item = lines[i][1][1:].strip()
        i += 1
        if item == "":
            if i < len(lines) and lines[i][0] > indent:
                v, i = _block(lines, i, lines[i][0])
                out.append(v)
            else:
                out.append(None)
        else:
            out.append(parse_scalar(item))
    return out, i


def _map(lines, i, indent):
    out = {}
    while i < len(lines) and lines[i][0] == indent:
        txt = lines[i][1]
        if txt.startswith("- "):
            break
        key, rest = _split_key(txt)
        key = parse_scalar(key)
        rest = rest.strip()
        i += 1
        if rest == "":
            if i < len(lines) and (lines[i][0] > indent or (lines[i][0] == indent and lines[i][1].startswith("- "))):
                v, i = _block(lines, i, lines[i][0])
                out[key] = v
            else:
                out[key] = None
        else:
            out[key] = parse_scalar(rest)
    if i < len(lines) and lines[i][0] > indent:
        raise YamlError("bad indentation near: %s" % lines[i][1])
    return out, i


_PLAIN_OK = re.compile(r"^[A-Za-z0-9_./@+()áéíóúñÁÉÍÓÚÑüÜ¿¡ -]*$")


def _scalar_out(v) -> str:
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (int, float)):
        return repr(v)
    s = str(v)
    needs = (
        s == "" or s != s.strip() or not _PLAIN_OK.match(s) or s[0] in "-?:&*!|>%@`" or
        s.lower() in ("true", "false", "null", "~", "yes", "no") or
        bool(_INT.match(s)) or bool(_FLOAT.match(s)) or ": " in s or s.endswith(":")
    )
    return json.dumps(s, ensure_ascii=False) if needs else s


def _dump(v, indent, out):
    pad = " " * indent
    if isinstance(v, dict):
        for k, x in v.items():
            if isinstance(x, dict) and x:
                out.append("%s%s:" % (pad, _scalar_out(k)))
                _dump(x, indent + 2, out)
            elif isinstance(x, list) and x:
                out.append("%s%s:" % (pad, _scalar_out(k)))
                _dump(x, indent + 2, out)
            elif isinstance(x, dict):
                out.append("%s%s: {}" % (pad, _scalar_out(k)))
            elif isinstance(x, list):
                out.append("%s%s: []" % (pad, _scalar_out(k)))
            else:
                out.append("%s%s: %s" % (pad, _scalar_out(k), _scalar_out(x)))
    elif isinstance(v, list):
        for x in v:
            if isinstance(x, (dict, list)):
                out.append("%s- %s" % (pad, json.dumps(x, ensure_ascii=False)))
            else:
                out.append("%s- %s" % (pad, _scalar_out(x)))
    else:
        out.append(pad + _scalar_out(v))


def dumps(obj) -> str:
    out = []
    _dump(obj, 0, out)
    return "\n".join(out) + "\n"
