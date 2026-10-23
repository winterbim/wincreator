#!/usr/bin/env python3
"""Run the G02 integration tests, turning a missing VEOR checkout into failure.

A skipped test exits zero, which would let a gate report a pass it never earned.
This wrapper sets ``WINCREATOR_REQUIRE_VEOR=1`` so the integration module fails
instead of skipping, then hands the exit code of pytest through unchanged.

Usage: python3 tools/veor_gate.py [pytest args...]
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TARGET = "tests/test_g02_integration.py"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv) or [DEFAULT_TARGET]
    environment = os.environ.copy()
    environment["WINCREATOR_REQUIRE_VEOR"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *argv],
        cwd=ROOT,
        env=environment,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
