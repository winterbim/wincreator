#!/usr/bin/env python3
"""Fail closed on release/tag/default-branch state contradictions."""

import argparse
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
    parser.add_argument("--latest-tag")
    parser.add_argument("--pr-checks-green", type=_boolean)
    parser.add_argument("--badge-branch")
    args = parser.parse_args(argv)
    problems = validate_release_state(
        expected_tag=args.expected_tag,
        workflow_sha=args.workflow_sha,
        tag_commit=args.tag_commit,
        default_branch_contains_tag=args.default_branch_contains_tag,
        default_branch_head=args.default_branch_head,
        latest_tag=args.latest_tag,
        pr_checks_green=args.pr_checks_green,
        badge_branch=args.badge_branch,
    )
    if problems:
        for problem in problems:
            print(f"RELEASE POLICY: FAIL — {problem}")
        return 1
    print("RELEASE POLICY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
