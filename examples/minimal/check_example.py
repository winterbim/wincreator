#!/usr/bin/env python3
"""Trivial gate for the minimal WinCreator example.

Exit 0 and print OK by default.
Pass --fail to force a non-zero exit (demo of CAPTURED_FAIL).
"""

from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    if "--fail" in argv:
        print("FAIL: intentional demo failure", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
