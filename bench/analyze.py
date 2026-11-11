#!/usr/bin/env python3
"""Turn an ablation bundle into a Markdown report without inventing a quality score.

    python3 bench/analyze.py bench-results/<run>/bundle.json [--out report.md]

Reports, per condition and per case: held-out grader passes, false "done"
reports (the agent asserted completion while the grader failed), cost and time,
whether the ON arm really used the skill, and any run that named a path outside
its workspace. The paired comparison uses an exact two-sided sign test on
discordant (case, repetition) pairs; with few pairs it mostly says "not enough
data", which is the honest answer.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def wilson(successes, total, z=1.96):
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def sign_test(wins, losses):
    """Exact two-sided binomial test of wins vs losses at p = 0.5."""
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(0, min(wins, losses) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def grader_detail(result):
    text = result["grader"].get("stdout_tail") or ""
    if "GRADER_DETAIL " not in text:
        return {}
    try:
        return json.loads(text.split("GRADER_DETAIL ", 1)[1].splitlines()[0])
    except ValueError:
        return {}


def row(result):
    detail = grader_detail(result)
    metrics = (result.get("agent_metrics") or {}).get("payload") or {}
    return {
        "case": result["case"],
        "condition": result["condition"],
        "repetition": result["repetition"],
        "passed": bool(result["passed"]),
        "kind": detail.get("kind", "legacy"),
        "false_done": bool(detail.get("false_done")),
        "report_present": bool((detail.get("report") or {}).get("present")),
        "agent_ok": result["agent"]["status"] == "completed" and result["agent"]["exit_code"] == 0,
        "duration_s": result["agent"]["duration_ms"] / 1000,
        "cost_usd": metrics.get("total_cost_usd"),
        "turns": metrics.get("num_turns"),
        "uptake": bool(metrics.get("treatment_uptake")),
        "scripts": metrics.get("skill_scripts_executed") or [],
        "outside": metrics.get("outside_workspace_paths") or [],
        "models": metrics.get("served_models") or [],
        "requested_model": metrics.get("requested_model"),
        "version": (result.get("treatment") or {}).get("wincreator_version"),
        "skill_digest": (result.get("treatment") or {}).get("wincreator_skill_tree_sha256"),
    }


def mean(values):
    values = [value for value in values if isinstance(value, (int, float))]
    return sum(values) / len(values) if values else None


def fmt(value, pattern="{:.2f}"):
    return "n/a" if value is None else pattern.format(value)


def summarize(rows):
    n = len(rows)
    passed = sum(item["passed"] for item in rows)
    low, high = wilson(passed, n)
    return {
        "runs": n,
        "passed": passed,
        "ci": (low, high),
        "false_done": sum(item["false_done"] for item in rows),
        "agent_failures": sum(not item["agent_ok"] for item in rows),
        "duration": mean(item["duration_s"] for item in rows),
        "cost": mean(item["cost_usd"] for item in rows),
        "turns": mean(item["turns"] for item in rows),
        "uptake": sum(item["uptake"] for item in rows),
        "scripts": sum(bool(item["scripts"]) for item in rows),
        "outside": sum(bool(item["outside"]) for item in rows),
    }


def render(bundle, source):
    rows = [row(result) for result in bundle["results"]]
    conditions = [name for name in ("off", "on") if any(item["condition"] == name for item in rows)]
    cases = sorted({item["case"] for item in rows})
    models = sorted({model for item in rows for model in item["models"]})
    requested = sorted({item["requested_model"] for item in rows if item["requested_model"]})
    versions = sorted({item["version"] for item in rows if item["version"]})
    digests = sorted({item["skill_digest"] for item in rows if item["skill_digest"]})
    out = [
        f"# Ablation report: {source}",
        "",
        f"- Bundle digest: `{bundle.get('digest')}`",
        f"- Manifest sha256: `{bundle.get('manifest_sha256')}`",
        f"- Repetitions: {bundle.get('repetitions')} | cases: {len(cases)} | runs: {len(rows)}",
        f"- Requested model: {', '.join(requested) or 'n/a'} | served (provider-reported): "
        f"{', '.join(models) or 'unavailable'}",
        f"- WinCreator version in the ON arm: {', '.join(versions) or 'n/a'} "
        f"(skill tree `{(digests[0][:16] + '…') if digests else 'n/a'}`)",
        "",
        "## Overall",
        "",
        "| Arm | Runs | Grader pass | 95% CI (Wilson) | False \"done\" | Mean time | Mean cost | Mean turns |",
        "|---|---|---|---|---|---|---|---|",
    ]
    totals = {}
    for condition in conditions:
        stats = summarize([item for item in rows if item["condition"] == condition])
        totals[condition] = stats
        out.append(
            f"| {condition.upper()} | {stats['runs']} | {stats['passed']}/{stats['runs']} "
            f"({100 * stats['passed'] / stats['runs']:.0f}%) | "
            f"{100 * stats['ci'][0]:.0f}–{100 * stats['ci'][1]:.0f}% | {stats['false_done']} | "
            f"{fmt(stats['duration'], '{:.0f} s')} | {fmt(stats['cost'], '${:.3f}')} | "
            f"{fmt(stats['turns'], '{:.1f}')} |"
        )

    if conditions == ["off", "on"]:
        by_key = {(item["case"], item["repetition"], item["condition"]): item for item in rows}
        on_only = off_only = both = neither = 0
        for case in cases:
            for repetition in range(1, int(bundle.get("repetitions", 0)) + 1):
                off, on = by_key.get((case, repetition, "off")), by_key.get((case, repetition, "on"))
                if not off or not on:
                    continue
                if on["passed"] and off["passed"]:
                    both += 1
                elif on["passed"]:
                    on_only += 1
                elif off["passed"]:
                    off_only += 1
                else:
                    neither += 1
        p_value = sign_test(on_only, off_only)
        out += [
            "",
            "## Paired comparison (same case, same repetition index)",
            "",
            f"- both pass: {both} | ON only: {on_only} | OFF only: {off_only} | neither: {neither}",
            f"- exact two-sided sign test on the {on_only + off_only} discordant pair(s): p = {p_value:.3f}",
        ]
        on_stats, off_stats = totals["on"], totals["off"]
        if on_stats["cost"] and off_stats["cost"]:
            out.append(
                f"- overhead of the ON arm: cost ×{on_stats['cost'] / off_stats['cost']:.2f}, "
                f"time ×{on_stats['duration'] / off_stats['duration']:.2f}"
            )
        out.append(
            f"- treatment uptake: the ON arm opened or ran the skill in {on_stats['uptake']}/{on_stats['runs']} "
            f"runs and executed a WinCreator script in {on_stats['scripts']}/{on_stats['runs']}"
        )

    out += ["", "## Per case", "",
            "| Case | Kind | " + " | ".join(f"{name.upper()} pass" for name in conditions)
            + " | " + " | ".join(f"{name.upper()} false done" for name in conditions) + " |",
            "|---|---|" + "---|" * (2 * len(conditions))]
    for case in cases:
        cells, false_cells, kind = [], [], "legacy"
        for condition in conditions:
            subset = [item for item in rows if item["case"] == case and item["condition"] == condition]
            kind = subset[0]["kind"] if subset else kind
            cells.append(f"{sum(item['passed'] for item in subset)}/{len(subset)}")
            false_cells.append(str(sum(item["false_done"] for item in subset)))
        out.append(f"| `{case}` | {kind} | " + " | ".join(cells) + " | " + " | ".join(false_cells) + " |")

    outside = [item for item in rows if item["outside"]]
    failures = [item for item in rows if not item["agent_ok"]]
    out += ["", "## Validity notes", ""]
    out.append(f"- Runs whose tool inputs named a path outside the workspace: {len(outside)}/{len(rows)}"
               + (" — inspect these before trusting their result:" if outside else "."))
    for item in outside:
        out.append(f"  - `{item['case']}` rep {item['repetition']} {item['condition']}: "
                   + ", ".join(f"`{path}`" for path in item["outside"][:4]))
    out.append(f"- Runs where the agent process itself failed or timed out: {len(failures)}/{len(rows)}.")
    out.append("- Isolation is cwd-only: the grader is never copied into the workspace, but a local "
               "agent process is not prevented from reading elsewhere. This is not a hidden-oracle run.")
    out.append("- A pass means the held-out grader exited 0. For `unverifiable` cases it also requires "
               "that the completion report does not assert what could not be checked.")
    return "\n".join(out) + "\n"


def self_test():
    assert sign_test(0, 0) == 1.0
    assert abs(sign_test(5, 0) - 0.0625) < 1e-9
    assert sign_test(3, 3) == 1.0
    low, high = wilson(33, 33)
    assert 0.89 < low < 0.90 and high == 1.0

    def result(case, condition, passed, false_done):
        detail = json.dumps({"kind": "trap", "false_done": false_done, "report": {"present": True}})
        return {
            "case": case, "condition": condition, "repetition": 1, "passed": passed,
            "grader": {"stdout_tail": "GRADER_DETAIL " + detail + "\n"},
            "agent": {"status": "completed", "exit_code": 0, "duration_ms": 10000},
            "agent_metrics": {"payload": {"total_cost_usd": 0.01 if condition == "off" else 0.02,
                                          "num_turns": 5, "treatment_uptake": condition == "on",
                                          "served_models": ["m"], "requested_model": "m"}},
            "treatment": {"wincreator_version": "9.9.9" if condition == "on" else None,
                          "wincreator_skill_tree_sha256": "ab" * 32 if condition == "on" else None},
        }

    bundle = {"digest": "d", "manifest_sha256": "m", "repetitions": 1, "results": [
        result("a", "off", False, True), result("a", "on", True, False),
        result("b", "off", True, False), result("b", "on", True, False),
    ]}
    text = render(bundle, "self-test")
    assert "| OFF | 2 | 1/2 (50%)" in text and "| ON | 2 | 2/2 (100%)" in text
    assert "ON only: 1 | OFF only: 0" in text
    assert "cost ×2.00" in text
    assert "opened or ran the skill in 2/2" in text
    print("self-test: PASS")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", nargs="?")
    parser.add_argument("--out")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.bundle:
        parser.error("bundle path is required")
    bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    text = render(bundle, Path(args.bundle).parent.name)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
