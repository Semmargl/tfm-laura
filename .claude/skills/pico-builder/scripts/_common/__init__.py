"""tfm _common: shared, stdlib-only library vendored into every skill (D-20).

Canonical source: build_kit/skills/_common/. Each skill carries an identical copy in
scripts/_common/ (made by tools/vendor_common.py). Never edit a vendored copy.
"""
from __future__ import annotations

import hashlib
import pathlib

COMMON_VERSION = "1.0.0"


def common_hash() -> str:
    """sha256 over all *.py files of this package (names + LF-normalised bytes).

    Used by 'Revisa el sistema' to detect out-of-sync vendored copies (Q-13, W-8).
    """
    here = pathlib.Path(__file__).resolve().parent
    h = hashlib.sha256()
    for p in sorted(here.glob("*.py")):
        h.update(p.name.encode("utf-8") + b"\0")
        h.update(p.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()
