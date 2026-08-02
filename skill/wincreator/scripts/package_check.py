#!/usr/bin/env python3
"""package_check.py — is this directory a valid Agent Skill package?

The open Agent Skills format (Claude Code, Codex, Cursor and others) is
opinionated about a few things that are easy to get silently wrong: the skill
name must be lowercase-hyphenated AND match its parent directory, the
frontmatter must carry a description, and every path the SKILL.md points at
must exist. WinCreator shipped for months with `name: skill-wincreator` inside
a directory called `Skill_WinCreator` — a packaging claim nobody had gated.

Stdlib only (a deliberately minimal frontmatter reader, not a YAML parser).

    python3 package_check.py [PACKAGE_DIR]     (default: the parent of scripts/)
    python3 package_check.py --self-test

Exit codes: 0 valid | 1 problems found | 2 unreadable / self-test failed
"""
import os
import re
import sys
import tempfile

VERSION = "3.0.0"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
MAX_SKILL_CHARS = 16000  # keeps SKILL.md cheap to always-load
LINK_RE = re.compile(r"(?:\]\(|`)((?:references|scripts|assets|agents)/[\w./-]+)")
REQUIRED_OPENAI_KEYS = ("name", "description", "prompt")


def read_frontmatter(text):
    """Return (frontmatter_dict, body). Top-level scalar keys only — enough to
    validate the fields the format requires, without pulling in a YAML dep."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end]
    body = text[end + 4:]
    data, key = {}, None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^(\w[\w.-]*):\s*(.*)$", line)
        if match and not line.startswith((" ", "\t")):
            key, value = match.group(1), match.group(2).strip()
            data[key] = "" if value in (">-", "|", ">", "|-") else value.strip("\"'")
        elif key and line.startswith((" ", "\t")):
            data[key] = (data.get(key, "") + " " + line.strip()).strip()
    return data, body


def check_package(pkg_dir):
    problems = []
    pkg_dir = os.path.abspath(pkg_dir.rstrip("/"))
    dir_name = os.path.basename(pkg_dir)
    skill_path = os.path.join(pkg_dir, "SKILL.md")
    if not os.path.isfile(skill_path):
        return [f"{pkg_dir}: no SKILL.md — not a skill package"]
    with open(skill_path, encoding="utf-8") as f:
        text = f.read()
    front, _body = read_frontmatter(text)

    name = front.get("name", "")
    if not name:
        problems.append("SKILL.md frontmatter has no `name`")
    else:
        if not NAME_RE.match(name):
            problems.append(f"name '{name}' is not lowercase-hyphenated "
                            f"(Agent Skills requires [a-z0-9] and '-')")
        if len(name) > MAX_NAME:
            problems.append(f"name is {len(name)} chars (max {MAX_NAME})")
        if name != dir_name:
            problems.append(f"name '{name}' != directory '{dir_name}' — the package "
                            f"directory must be named after the skill")

    description = front.get("description", "")
    if not description:
        problems.append("SKILL.md frontmatter has no `description` (it is what an "
                        "agent reads to decide whether to load the skill)")
    elif len(description) > MAX_DESCRIPTION:
        problems.append(f"description is {len(description)} chars (max {MAX_DESCRIPTION})")

    if len(text) > MAX_SKILL_CHARS:
        problems.append(f"SKILL.md is {len(text)} chars (budget {MAX_SKILL_CHARS})")

    for rel in sorted(set(LINK_RE.findall(text))):
        if not os.path.exists(os.path.join(pkg_dir, rel)):
            problems.append(f"SKILL.md points at a missing path: {rel}")

    openai_path = os.path.join(pkg_dir, "agents", "openai.yaml")
    if not os.path.isfile(openai_path):
        problems.append("agents/openai.yaml missing (recommended by OpenAI for the "
                        "display name, short description and start prompt)")
    else:
        with open(openai_path, encoding="utf-8") as f:
            openai_text = f.read()
        for key in REQUIRED_OPENAI_KEYS:
            if not re.search(rf"^{key}:", openai_text, re.MULTILINE):
                problems.append(f"agents/openai.yaml has no `{key}:` key")
    return problems


def report(pkg_dir):
    try:
        problems = check_package(pkg_dir)
    except OSError as e:
        print(f"ERROR: {e}")
        return 2
    if problems:
        print(f"PACKAGE INVALID — {len(problems)} problem(s) in {pkg_dir}:")
        for p in problems:
            print(f"  ✗ {p}")
        return 1
    print(f"PACKAGE VALID — {pkg_dir} matches the Agent Skills conventions")
    return 0


# ---------------------------------------------------------------- self-test
GOOD_SKILL = """---
name: {name}
description: >-
  A description long enough to be meaningful for skill selection.
metadata:
  version: 1.0.0
---

# Demo

See `references/x.md` and [the script](scripts/y.py).
"""

GOOD_OPENAI = "name: demo\ndescription: short\nprompt: |\n  do the thing\n"


def _make_pkg(root, dir_name, name, openai=GOOD_OPENAI, extra_files=True):
    pkg = os.path.join(root, dir_name)
    os.makedirs(os.path.join(pkg, "agents"), exist_ok=True)
    with open(os.path.join(pkg, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(GOOD_SKILL.format(name=name))
    if extra_files:
        for rel in ("references/x.md", "scripts/y.py"):
            path = os.path.join(pkg, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").close()
    if openai is not None:
        with open(os.path.join(pkg, "agents", "openai.yaml"), "w", encoding="utf-8") as f:
            f.write(openai)
    return pkg


def self_test():
    cases = []
    with tempfile.TemporaryDirectory() as root:
        cases.append(("valid_package_passes",
                      _make_pkg(root, "demo", "demo"), False))
        cases.append(("name_directory_mismatch_caught",
                      _make_pkg(root, "Demo_Skill", "demo-skill"), True))
        cases.append(("uppercase_name_caught",
                      _make_pkg(root, "Demo2", "Demo2"), True))
        cases.append(("missing_openai_yaml_caught",
                      _make_pkg(root, "demo3", "demo3", openai=None), True))
        cases.append(("incomplete_openai_yaml_caught",
                      _make_pkg(root, "demo4", "demo4",
                                openai="name: demo\ndescription: short\n"), True))
        cases.append(("broken_reference_caught",
                      _make_pkg(root, "demo5", "demo5", extra_files=False), True))
        failed = 0
        for name, pkg, expect_problems in cases:
            problems = check_package(pkg)
            ok = bool(problems) == expect_problems
            if not ok:
                failed += 1
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}"
                  f" (expected {'problems' if expect_problems else 'valid'},"
                  f" got {len(problems)})")
    print(f"self-test: {len(cases)-failed}/{len(cases)} passed")
    return 2 if failed else 0


def main(argv):
    if argv and argv[0] == "--self-test":
        return self_test()
    if argv and argv[0] == "--version":
        print(f"package_check.py {VERSION}")
        return 0
    default = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return report(argv[0] if argv else default)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
