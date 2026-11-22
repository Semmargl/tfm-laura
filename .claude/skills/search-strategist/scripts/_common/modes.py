"""Execution modes (sec 2.2): FULL | LITE-a | LITE-b | LITE-P. Mode is a parameter, not a fork."""
from __future__ import annotations

from . import config, journal_io, paths, state_io

MODES = ("FULL", "LITE-a", "LITE-b", "LITE-P")
NETWORK_MODES = ("FULL",)          # network scripts (E-utils/Crossref/OpenAlex/CT.gov) only here
SCRIPT_MODES = ("FULL", "LITE-a")  # offline scripts also work in LITE-a


def decide_mode(s1: bool, s2: bool, s3: bool) -> str:
    """Table sec 2.2. s2 False -> LITE-P; s1 False -> LITE-b; s3 False -> LITE-a."""
    if not s2:
        return "LITE-P"
    if not s1:
        return "LITE-b"
    return "FULL" if s3 else "LITE-a"


def can_run(mode: str, needs_network: bool, needs_scripts: bool = True) -> bool:
    if needs_network:
        return mode == "FULL"
    return mode in SCRIPT_MODES if needs_scripts else True


def set_mode(root, mode: str, reason_es: str, actor: str = "script", script: str = "modes.py") -> dict:
    """Write mode to project.yaml + state.md and log a `setup` journal entry."""
    if mode not in MODES:
        raise ValueError("bad mode %s" % mode)
    old = config.get_mode(root)
    config.set_scalar(root, "mode", mode)
    e = journal_io.add(root, {"stage": "setup", "type": "setup", "actor": actor,
                              "what_es": "Modo del sistema: %s -> %s" % (old, mode), "why_es": reason_es,
                              "tool": "%s v%s" % (script, "1.0"), "mode_from": old, "mode_to": mode})
    state_io.set_fields(root, mode=mode, last_journal_id=e["id"])
    return e


def degrade_to_lite_a(root, reason_es: str) -> dict:
    """Auto-degradation FULL -> LITE-a after a network error (sec 2.2). Idempotent."""
    if config.get_mode(root) != "FULL":
        return {}
    return set_mode(root, "LITE-a", "Degradacion automatica: " + reason_es)
