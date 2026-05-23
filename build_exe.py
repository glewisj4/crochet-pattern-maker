"""Build the Photo-to-Pattern Windows executable."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "PhotoToPattern",
        "--collect-all",
        "PIL",
        "--add-data",
        f"{root / 'photo_to_pattern'};photo_to_pattern",
        str(root / "run_gui.py"),
    ]
    return subprocess.call(command, cwd=root)


if __name__ == "__main__":
    raise SystemExit(main())

