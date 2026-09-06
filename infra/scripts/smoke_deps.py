"""Dependency smoke test — the "v1 lied" guard.

Verifies that every heavy dependency the plan relies on actually imports
in a fresh environment BEFORE we build on top of it. v1 of the plan shipped
code with a wrong PyPI name (`fhir-resources` instead of `fhir.resources`)
and a fabricated streaming API; this script makes that class of failure
impossible to miss at Phase 0.

Decision rule (see plan T0.4):
  - Core deps (must import): fhir.resources, sqlalchemy, redis, rq,
    edge_tts, faster_whisper.
  - Docker-only deps (may SKIP on Windows host): paddleocr, pytesseract —
    these run in the Linux `ocr` container only. A SKIP is acceptable; a
    FAIL of a core dep is not.

Exit code 0 = all core deps OK (SKIPs allowed). Any core FAIL = exit 1.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys

CORE = ["fhir.resources", "sqlalchemy", "redis", "rq", "edge_tts", "faster_whisper"]
DOCKER_ONLY = ["paddleocr", "pytesseract"]

# openai-whisper must NOT appear anywhere in the workspace requirements —
# we moved to faster-whisper (plan AD-1).
FORBIDDEN = "openai-whisper"


def import_in_subprocess(module: str) -> tuple[bool, str]:
    """Import a module in a fresh subprocess; return (ok, version_or_err)."""
    code = (
        "import importlib, sys\n"
        f"m = importlib.import_module({module!r})\n"
        "v = getattr(m, '__version__', None) or getattr(m, 'VERSION', '?')\n"
        "print(v)\n"
    )
    r = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120
    )
    if r.returncode == 0:
        return True, r.stdout.strip().splitlines()[-1]
    return False, (r.stderr.strip().splitlines() or ["unknown error"])[-1]


def check_forbidden() -> list[str]:
    """Return list of workspace pyproject files that declare openai-whisper."""
    hits = []
    for path in ("packages/shared/pyproject.toml", "services/asr/pyproject.toml"):
        try:
            with open(path, encoding="utf-8") as f:
                if FORBIDDEN in f.read():
                    hits.append(path)
        except FileNotFoundError:
            pass  # packages created in later phases
    return hits


def main() -> int:
    failures: list[str] = []

    for mod in CORE:
        ok, info = import_in_subprocess(mod)
        print(f"{'OK' if ok else 'FAIL'} {mod} {info}")
        if not ok:
            failures.append(mod)

    for mod in DOCKER_ONLY:
        ok, info = import_in_subprocess(mod)
        if ok:
            print(f"OK {mod} {info}")
        else:
            print(f"SKIP {mod} (docker-only; runs in ocr container)")

    forbidden = check_forbidden()
    if forbidden:
        print(f"FAIL forbidden dependency '{FORBIDDEN}' declared in: {forbidden}")
        failures.append(FORBIDDEN)

    if failures:
        print(f"\nSMOKE FAILED: {failures}")
        return 1
    print("\nSMOKE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
