from pathlib import Path
import importlib.util
import types

ROOT = Path(__file__).parent

VISIBLE = [
    ("simple", """# Ledger\n| ID | Level | Claim | Gate (what proves it) | Status | Evidence |\n|----|-------|-------|------------------------|--------|----------|\n| P1 | Micro | parser works | pytest | EVIDENCED | run: 1 passed |\n""", ["P1"], None),
    ("stops_after_table", """| ID | Level | Claim | Gate (what proves it) | Status | Evidence |\n|----|-------|-------|------------------------|--------|----------|\n| P1 | Micro | ok | pytest | EVIDENCED | pass |\n\nnot table\n| P2 | Micro | should not parse | pytest | CLAIMED | |\n""", ["P1"], None),
]

ADVERSARIAL = [
    ("escaped_pipe", """| ID | Level | Claim | Gate (what proves it) | Status | Evidence |\n|----|-------|-------|------------------------|--------|----------|\n| P1 | Micro | value contains \| pipe | pytest | EVIDENCED | raw pass |\n""", ["P1"], "value contains | pipe"),
    ("fenced_example", """\x60\x60\x60markdown\n| ID | Level | Claim | Gate (what proves it) | Status | Evidence |\n|----|-------|-------|------------------------|--------|----------|\n| FAKE | Micro | example | pytest | EVIDENCED | pass |\n\x60\x60\x60\n\n| ID | Level | Claim | Gate (what proves it) | Status | Evidence |\n|----|-------|-------|------------------------|--------|----------|\n| REAL | Micro | live | pytest | EVIDENCED | pass |\n""", ["REAL"], None),
    ("foreign_table", """| Name | Status |\n|------|--------|\n| deploy | CLAIMED |\n\n| ID | Level | Claim | Gate (what proves it) | Status | Evidence |\n|----|-------|-------|------------------------|--------|----------|\n| P1 | Meso | live | pytest | EVIDENCED | pass |\n""", ["P1"], None),
    ("blank_line_ends", """| ID | Level | Claim | Gate (what proves it) | Status | Evidence |\n|----|-------|-------|------------------------|--------|----------|\n| P1 | Micro | live | pytest | EVIDENCED | pass |\n\n| P2 | Micro | detached | pytest | CLAIMED | |\n""", ["P1"], None),
    ("edge_pipes", """| ID | Level | Claim | Gate (what proves it) | Status | Evidence |\n|----|-------|-------|------------------------|--------|----------|\nP1 | Micro | malformed | pytest | CLAIMED | \n""", [], None),
]

INVALID_SEPARATOR = ("invalid_separator", """| ID | Level | Claim | Gate (what proves it) | Status | Evidence |\n| nope | nope | nope | nope | nope | nope |\n| P1 | Micro | should not parse | pytest | EVIDENCED | pass |\n""", [], None)

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def from_source(source, name):
    mod = types.ModuleType(name)
    exec(compile(source, name, "exec"), mod.__dict__)
    return mod

def run(mod, cases):
    failures = []
    for name, text, expected_ids, expected_claim in cases:
        try:
            rows = mod.parse_ledger(text)
            assert [row["id"] for row in rows] == expected_ids
            if expected_claim is not None:
                assert rows[0]["claim"] == expected_claim
        except Exception as exc:
            failures.append((name, type(exc).__name__))
    return len(cases) - len(failures), failures

def metric(path):
    text = path.read_text(encoding="utf-8")
    return sum(bool(line.strip()) for line in text.splitlines()), len(text.encode())

baseline = load(ROOT / "baseline.py", "baseline")
candidate = load(ROOT / "candidate.py", "candidate")
distilled = load(ROOT / "distilled.py", "distilled")

b_vis = run(baseline, VISIBLE)
b_adv = run(baseline, ADVERSARIAL)
c7 = run(candidate, VISIBLE + ADVERSARIAL)

candidate_source = (ROOT / "candidate.py").read_text(encoding="utf-8")
separator_mutant = candidate_source.replace(
    '        if state == "separator":\n            if not cells or len(cells) != 6 or not all(c and set(c) <= {"-", ":"} for c in cells):\n                return []\n            state = "rows"\n            continue\n',
    '        if state == "separator":\n            state = "rows"\n            continue\n',
)
m7 = run(from_source(separator_mutant, "separator_mutant"), VISIBLE + ADVERSARIAL)
m8 = run(from_source(separator_mutant, "separator_mutant2"), VISIBLE + ADVERSARIAL + [INVALID_SEPARATOR])
d8 = run(distilled, VISIBLE + ADVERSARIAL + [INVALID_SEPARATOR])

distilled_source = (ROOT / "distilled.py").read_text(encoding="utf-8")
mutants = {
    "no_fence_filter": distilled_source.replace('        if fence:\n            continue\n', '        if False and fence:\n            continue\n'),
    "break_escaped_pipe": distilled_source.replace('part.replace(r"\\|", "|").strip()', 'part.strip()'),
    "do_not_end_on_blank": distilled_source.replace('        elif not line or cells is None:\n            break\n', '        elif not line:\n            continue\n        elif cells is None:\n            continue\n'),
    "skip_separator_validation": distilled_source.replace('        elif state == 1:\n            if not cells or len(cells) != 6 or not all(c and set(c) <= {"-", ":"} for c in cells):\n                return []\n            state = 2\n', '        elif state == 1:\n            state = 2\n'),
}
killed = {}
all_cases = VISIBLE + ADVERSARIAL + [INVALID_SEPARATOR]
for name, source in mutants.items():
    passed, failures = run(from_source(source, name), all_cases)
    killed[name] = {"killed": bool(failures), "passed": passed, "failures": failures}

print("baseline_visible", b_vis)
print("baseline_adversarial", b_adv)
print("candidate_7", c7)
print("separator_mutant_before_new_test", m7)
print("separator_mutant_after_new_test", m8)
print("distilled_8", d8)
print("mutants", killed)
print("candidate_metric", metric(ROOT / "candidate.py"))
print("distilled_metric", metric(ROOT / "distilled.py"))

assert b_vis[0] == 2
assert b_adv[0] == 3
assert c7[0] == 7
assert m7[0] == 7
assert m8[0] == 7 and m8[1]
assert d8[0] == 8
assert all(item["killed"] for item in killed.values())
assert metric(ROOT / "distilled.py")[0] < metric(ROOT / "candidate.py")[0]
print("SELF-ABLATION: PASS")
