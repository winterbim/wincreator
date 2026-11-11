#!/usr/bin/env python3
"""False green in 5 seconds: a passing gate that cannot see the bug it is cited against.

Run from anywhere:

    python3 examples/false-green/run_demo.py

Nothing here is simulated. The script calls the shipped Evidence Adequacy Gate
(`skill/wincreator/scripts/adequacy_check.py`) twice on the files in this
folder and prints what it measured. No LLM, no network, no dependency.

The printed transcript is deterministic on purpose: `tests/test_false_green_demo.py`
fails if the README stops matching what this script really prints.
"""
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "skill" / "wincreator" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import adequacy_check  # noqa: E402

CLAIM = "a refund never exceeds what was paid"


def _last_line(gate):
    text = (gate.get("stderr_tail") or "").strip() or (gate.get("stdout_tail") or "").strip()
    return text.splitlines()[-1] if text else "(no output)"


def _run(check_file):
    manifest = json.loads((HERE / "adequacy.json").read_text(encoding="utf-8"))
    return adequacy_check.run_adequacy(HERE, manifest, [sys.executable, check_file])


def transcript():
    manifest = json.loads((HERE / "adequacy.json").read_text(encoding="utf-8"))
    fault = manifest["mutations"][0]
    weak, strong = _run("check_weak.py"), _run("check_strong.py")
    weak_mutant, strong_mutant = weak["mutations"][0], strong["mutations"][0]
    lines = [
        f"CLAIM   {CLAIM}",
        "",
        "$ python3 check_weak.py",
        f"{_last_line(weak['baseline'])}   (exit {weak['baseline']['exit_code']})",
        "        green. This is where an agent says \"done\".",
        "",
        f"seed the bug the claim is about:  {fault['find']}  ->  {fault['replace']}",
        "$ python3 check_weak.py            # against the broken code",
        f"{_last_line(weak_mutant['gate'])}   (exit {weak_mutant['gate']['exit_code']})",
        f"        still green: the fault {weak_mutant['result']}.",
        "",
        f"VERDICT {weak['verdict']}",
        "        the gate passed, but it cannot detect the failure it is cited against.",
        "",
        "$ python3 check_strong.py          # one added check, same broken code",
        f"{_last_line(strong_mutant['gate'])}   (exit {strong_mutant['gate']['exit_code']})",
        f"        red: the fault is {strong_mutant['result']}.",
        "",
        f"VERDICT {strong['verdict']}",
        "        now a green run of this gate is evidence for the claim.",
    ]
    return "\n".join(lines) + "\n", weak, strong


def main():
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    text, weak, strong = transcript()
    sys.stdout.write(text)
    expected = (weak["verdict"], strong["verdict"]) == ("INSUFFICIENT", "ADEQUATE")
    return 0 if expected else 1


if __name__ == "__main__":
    sys.exit(main())
