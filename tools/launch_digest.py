#!/usr/bin/env python3
"""Build the launch packet for a release from repo facts and launch drafts.

Reads only files checked into the repository. Writes one Markdown file.
No network access; recorded metrics live in the packet the marketer agent
updates per round, not here.
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import sys

REPO_SLUG = "winterbim/wincreator"
ROOT = pathlib.Path(__file__).resolve().parent.parent

CHECKLIST = [
    ("Show HN", "docs/marketing/show-hn.md", "post Tue-Thu morning US time, with issue #20 linked"),
    ("r/ClaudeAI", "docs/marketing/social-posts.md", "section r/ClaudeAI"),
    ("r/LocalLLaMA", "docs/marketing/social-posts.md", "section r/LocalLLaMA"),
    ("X / Twitter", "docs/marketing/social-posts.md", "thread, 5 posts"),
    ("LinkedIn", "docs/marketing/social-posts.md", "short form"),
]


def build_packet(tag: str, root: pathlib.Path = ROOT) -> str:
    lines: list[str] = []
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    lines.append(f"# Launch packet — {REPO_SLUG} — {tag}")
    lines.append("")
    lines.append(f"Built {now}. Rebuild with: `python3 tools/launch_digest.py --tag {tag}`")
    lines.append("")
    lines.append("## Install line (required in every post)")
    lines.append("")
    lines.append("```")
    lines.append("npx skills add winterbim/wincreator")
    lines.append("```")
    lines.append("")
    lines.append("## Rules (from docs/marketing-plan.md)")
    lines.append("")
    lines.append(
        "- Disclose the ON/OFF ablation result and the 1.57x overhead whenever "
        "wincreator is presented; the null result is published, not hidden."
    )
    lines.append(
        "- No benefit claim that no published run supports. Current honest line: "
        "mechanism plus overhead measured; benefit on long sessions, large repos "
        "and weaker models not yet proven."
    )
    lines.append("- Every post maps to a countable skills.sh install.")
    lines.append("- Nothing goes out without human approval of that exact text.")
    lines.append("")
    lines.append("## Channel checklist")
    lines.append("")
    for name, path, note in CHECKLIST:
        full = root / path
        state = "draft ready" if full.is_file() else "DRAFT MISSING"
        lines.append(f"- [ ] {name} — {path} ({state}; {note})")
    lines.append("")
    lines.append("## Metrics to record before and after the round")
    lines.append("")
    lines.append("- skills.sh installs (https://skills.sh/winterbim/wincreator)")
    lines.append("- GitHub stars, forks, issues")
    lines.append("- Inbound referrers from posted channels")
    lines.append("- One qualitative artefact per round (best third-party write-up, or its absence)")
    lines.append("")
    lines.append("## Release links")
    lines.append("")
    lines.append(f"- Release: https://github.com/{REPO_SLUG}/releases/tag/{tag}")
    lines.append(f"- Ablation results: https://github.com/{REPO_SLUG}/tree/master/bench/results")
    lines.append(f"- Installed skill: https://skills.sh/{REPO_SLUG}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", default="latest", help="release tag the packet is for")
    parser.add_argument("--out", default="dist/launch-digest.md", help="output path")
    parser.add_argument("--root", default=str(ROOT), help="repository root")
    args = parser.parse_args(argv)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = build_packet(args.tag, pathlib.Path(args.root).resolve())
    out.write_text(text, encoding="utf-8")
    print(f"launch packet written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
