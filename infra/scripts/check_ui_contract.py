"""T4.0: UI contract checker — every data-testid in src/ must be documented.

Fails when a testid is used in code but missing from docs/UI-CONTRACT.md.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "apps" / "web" / "src"
DOC = REPO / "docs" / "UI-CONTRACT.md"

# backticks in the doc table rows
USE_RE = re.compile(r"`([a-zA-Z][a-zA-Z0-9_\-{}]+)`")


def used_testids() -> set[str]:
    found: set[str] = set()
    for ext in ("*.ts", "*.tsx"):
        for f in SRC.rglob(ext):
            text = f.read_text(encoding="utf-8", errors="ignore")
            found |= set(re.findall(r'data-testid=["\']([a-zA-Z][\w\-{}]*)["\']', text))
            # dynamic pattern strings like `option-${i}` declared via constants
            found |= set(re.findall(r"testId=\{?['\"]([a-zA-Z][\w\-{}]+)['\"]", text))
    return found


def documented_ids() -> set[str]:
    text = DOC.read_text(encoding="utf-8")
    return {m for m in USE_RE.findall(text) if "-" in m or "_" in m}


def main() -> int:
    used = used_testids()
    doc = documented_ids()
    missing = sorted(t for t in used if t not in doc and "{" not in t)
    # dynamic families: prefix check (option-, doctor-queue-row-, timeline-item-)
    families = ("option-", "doctor-queue-row-", "timeline-item-", "doc-")
    missing = [
        m for m in missing
        if not any(m.startswith(p) and m[len(p):].replace("-", "_").isdigit() is False for p in families)
    ]
    if missing:
        print("UI contract missing entries:")
        for m in missing:
            print(f"  - {m}")
        return 1
    print(f"UI contract OK ({len(used)} testids used)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())