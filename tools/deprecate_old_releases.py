#!/usr/bin/env python3
"""Prepend an idempotent v3 migration notice to older GitHub releases."""

import argparse
import json
import os
import subprocess


NOTICE = (
    "Cette version est obsolète. Installez la dernière version de WinCreator :\n"
    "https://github.com/winterbim/wincreator/releases/latest"
)


def with_deprecation_notice(body):
    body = body or ""
    if NOTICE in body:
        return body
    return NOTICE + ("\n\n" + body if body else "")


def _gh_json(arguments):
    result = subprocess.run(
        ["gh", *arguments], check=True, capture_output=True, text=True
    )
    return json.loads(result.stdout)


def deprecate(repository, current_tag):
    releases = _gh_json(["api", f"repos/{repository}/releases?per_page=100"])
    updated = []
    for release in releases:
        if release["tag_name"] == current_tag:
            continue
        body = with_deprecation_notice(release.get("body"))
        if body == (release.get("body") or ""):
            continue
        subprocess.run(
            [
                "gh",
                "api",
                "--method",
                "PATCH",
                f"repos/{repository}/releases/{release['id']}",
                "--field",
                f"body={body}",
            ],
            check=True,
        )
        updated.append(release["tag_name"])
    return updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--current-tag", default=os.environ.get("GITHUB_REF_NAME"))
    args = parser.parse_args()
    if not args.repository or not args.current_tag:
        parser.error("--repository and --current-tag are required outside GitHub Actions")
    for tag in deprecate(args.repository, args.current_tag):
        print(f"deprecated release notice added: {tag}")


if __name__ == "__main__":
    main()
