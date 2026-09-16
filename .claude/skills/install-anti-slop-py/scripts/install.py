"""Copy the bundled anti-slop Flake8 plugin into the current repository.

Run from the target repository root:

    python <skill-directory>/scripts/install.py [destination] [--force]

Default destination is `tools/flake8/anti_slop`. The parent directory named
in `.flake8`'s `paths` must be the destination's parent (`tools/flake8`).
Refuses to replace an existing destination unless `--force` is passed.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
BUNDLED_PLUGIN = SKILL_ROOT / "assets" / "src" / "anti_slop"
FALLBACK_PLUGIN = SKILL_ROOT.parent.parent / "src" / "anti_slop"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "destination",
        nargs="?",
        default="tools/flake8/anti_slop",
        help="relative destination inside the target repository",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace an existing destination (back it up and review first)",
    )
    arguments = parser.parse_args()

    source = BUNDLED_PLUGIN if BUNDLED_PLUGIN.is_dir() else FALLBACK_PLUGIN
    if not source.is_dir():
        print(f"bundled plugin not found at {BUNDLED_PLUGIN}", file=sys.stderr)
        return 1

    destination = Path.cwd() / arguments.destination
    if destination.exists():
        if not arguments.force:
            print(
                f"{destination} already exists; review it and rerun with --force",
                file=sys.stderr,
            )
            return 1
        shutil.rmtree(destination)

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__"))
    print(f"copied {source} -> {destination}")

    configs = SKILL_ROOT / "assets" / "configs"
    if configs.is_dir():
        print(f"configuration templates to merge: {configs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
