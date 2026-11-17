"""T0 static checks: byte-compile + manifest/zip validation.

Usage: python3 tests/t0_check.py
"""

import compileall
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import build  # noqa: E402


def main():
    ok = compileall.compile_dir(
        str(ROOT / "addon"), quiet=1, force=True, maxlevels=10
    )
    if not ok:
        print("T0 py_compile: FAIL")
        return 1
    print("T0 py_compile: PASS")
    build.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
