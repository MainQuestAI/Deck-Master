#!/usr/bin/env python3
"""Build hook for the rebuilt package (T05.04).

Syncs the single Skill method source (``skills/deck-master/references/*.md``)
into the package resources so the installed wheel serves methods through
``importlib.resources`` — never by reading the source checkout at runtime.
The synced directory is generated build output and stays out of Git.

Usage: python3 tools/build_hook.py [--check]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL_REFERENCES = REPO / "skills" / "deck-master" / "references"
PACKAGE_TARGET = REPO / "src" / "deck_master" / "resources" / "skills-references"


def sync_skill_references() -> list[str]:
    if not SKILL_REFERENCES.is_dir():
        raise RuntimeError(f"skill reference source missing: {SKILL_REFERENCES}")
    PACKAGE_TARGET.mkdir(parents=True, exist_ok=True)
    copied = []
    for source in sorted(SKILL_REFERENCES.glob("*.md")):
        shutil.copy2(source, PACKAGE_TARGET / source.name)
        copied.append(source.name)
    return copied


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    if check_only:
        if not PACKAGE_TARGET.is_dir() or not any(PACKAGE_TARGET.glob("*.md")):
            sys.stderr.write("skills-references not synced; run tools/build_hook.py before build\n")
            return 1
        return 0
    copied = sync_skill_references()
    sys.stdout.write("synced: " + ", ".join(copied) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
