#!/usr/bin/env python3
"""Fail closed on release/tag/default-branch state contradictions."""

import argparse
import json
import sys


def validate_release_state(
    expected_tag,
    workflow_sha,
    tag_commit,
    default_branch_contains_tag,
    default_branch_head=None,
    latest_tag=None,
    pr_checks_green=None,
    badge_branch=None,
    package_version=None,
    required_check=None,
    required_check_app=None,
    check_runs=None,
):
    problems = []
    if workflow_sha != tag_commit:
        problems.append(
            f"workflow SHA {workflow_sha} does not equal tag commit {tag_commit}"
        )
    if not default_branch_contains_tag:
        problems.append("tag commit is not contained in the default branch")
    if default_branch_head is not None and tag_commit != default_branch_head:
        problems.append(
            f"tag commit {tag_commit} does not equal default branch head "
            f"{default_branch_head}"
        )
    if package_version is not None and expected_tag != f"v{package_version}":
        problems.append(
            f"release tag {expected_tag} does not match package version "
            f"{package_version}"
        )
    if required_check is not None:
        runs = (check_runs or {}).get("check_runs", [])
        successful = [
            run for run in runs
            if run.get("name") == required_check
            and run.get("status") == "completed"
            and run.get("conclusion") == "success"
            and (required_check_app is None
                 or (run.get("app") or {}).get("slug") == required_check_app)
        ]
        if not successful:
            problems.append(
                f"required check {required_check} is not successfully completed "
                "on the tag commit"
            )
    if latest_tag is not None and latest_tag != expected_tag:
        problems.append(
            f"latest release is {latest_tag}, expected {expected_tag}"
        )
    if pr_checks_green is False:
        branch = badge_branch or "default branch"
        problems.append(
            f"a green {branch} badge cannot override red or missing PR checks"
        )
    return problems


def _boolean(value):
    lowered = value.lower()
    if lowered in {"true", "1", "yes"}:
        return True
    if lowered in {"false", "0", "no"}:
        return False
    raise argparse.ArgumentTypeError("expected true or false")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-tag", required=True)
    parser.add_argument("--workflow-sha", required=True)
    parser.add_argument("--tag-commit", required=True)
    parser.add_argument("--default-branch-contains-tag", required=True, type=_boolean)
    parser.add_argument("--default-branch-head", required=True)
    parser.add_argument("--package-version", required=True)
    parser.add_argument("--required-check", required=True)
    parser.add_argument("--required-check-app", required=True)
    parser.add_argument("--check-runs-json", required=True)
    parser.add_argument("--latest-tag")
    parser.add_argument("--pr-checks-green", type=_boolean)
    parser.add_argument("--badge-branch")
    args = parser.parse_args(argv)
    try:
        with open(args.check_runs_json, encoding="utf-8") as handle:
            check_runs = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        print(f"RELEASE POLICY: FAIL — cannot read check runs: {error}")
        return 1
    problems = validate_release_state(
        expected_tag=args.expected_tag,
        workflow_sha=args.workflow_sha,
        tag_commit=args.tag_commit,
        default_branch_contains_tag=args.default_branch_contains_tag,
        default_branch_head=args.default_branch_head,
        latest_tag=args.latest_tag,
        pr_checks_green=args.pr_checks_green,
        badge_branch=args.badge_branch,
        package_version=args.package_version,
        required_check=args.required_check,
        required_check_app=args.required_check_app,
        check_runs=check_runs,
    )
    if problems:
        for problem in problems:
            print(f"RELEASE POLICY: FAIL — {problem}")
        return 1
    print("RELEASE POLICY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
