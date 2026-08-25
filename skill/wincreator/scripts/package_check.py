#!/usr/bin/env python3
"""Validate WinCreator's repository package policy without external modules.

This is an internal policy gate, not a claim of official runtime validation.
Run OpenAI Skill Creator's quick_validate.py and `npx skills-ref validate`
separately for official format validation.
"""

import os
import re
import sys
import tempfile


def _tool_version():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "VERSION")
    with open(path, encoding="utf-8") as handle:
        value = handle.read().strip()
    if not value:
        raise RuntimeError("VERSION file is empty")
    return value


VERSION = _tool_version()
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
MAX_SKILL_CHARS = 24000
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
ALLOWED_FRONTMATTER = {"name", "description"}
LINK_RE = re.compile(r"(?:\]\(|`)((?:references|scripts|assets|agents|schemas)/[\w./-]+)")
OPENAI_REQUIRED = {"display_name", "short_description", "default_prompt"}
OPENAI_OPTIONAL = {"icon_small", "icon_large", "brand_color"}


def read_frontmatter(text):
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    raw = text[4:end]
    body = text[end + 5 :]
    data = {}
    active = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z_][\w.-]*):\s*(.*)$", line)
        if match and not line.startswith((" ", "\t")):
            active, value = match.groups()
            data[active] = "" if value.strip() in {">", ">-", "|", "|-"} else value.strip().strip("\"'")
        elif active and line.startswith((" ", "\t")):
            data[active] = (data[active] + " " + line.strip()).strip()
        else:
            data["__invalid__"] = line
    return data, body


def check_openai_yaml(text, skill_name):
    problems = []
    if "\t" in text:
        problems.append("agents/openai.yaml contains tabs; YAML indentation must use spaces")
    if re.search(r"^(name|description|prompt):", text, re.MULTILINE):
        problems.append("agents/openai.yaml uses the obsolete name/description/prompt schema")
    lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines or lines[0] != "interface:":
        problems.append("agents/openai.yaml must start with the current `interface:` mapping")
        return problems
    fields = {}
    for line in lines[1:]:
        match = re.fullmatch(r'  ([a-z_]+):\s+"([^"\\]*(?:\\.[^"\\]*)*)"', line)
        if not match:
            problems.append(f"agents/openai.yaml has invalid or unquoted field: {line}")
            continue
        key, value = match.groups()
        if key in fields:
            problems.append(f"agents/openai.yaml duplicates `{key}`")
        fields[key] = value
    missing = sorted(OPENAI_REQUIRED - set(fields))
    if missing:
        problems.append("agents/openai.yaml missing required interface field(s): " + ", ".join(missing))
    unknown = sorted(set(fields) - OPENAI_REQUIRED - OPENAI_OPTIONAL)
    if unknown:
        problems.append("agents/openai.yaml has unsupported interface field(s): " + ", ".join(unknown))
    short = fields.get("short_description", "")
    if short and not 25 <= len(short) <= 64:
        problems.append("interface.short_description must contain 25–64 characters")
    prompt = fields.get("default_prompt", "")
    if prompt and f"${skill_name}" not in prompt:
        problems.append(f"interface.default_prompt must explicitly mention `${skill_name}`")
    return problems


def check_package(package_dir):
    package_dir = os.path.abspath(package_dir.rstrip("/\\"))
    problems = []
    skill_path = os.path.join(package_dir, "SKILL.md")
    if not os.path.isfile(skill_path):
        return [f"{package_dir}: no SKILL.md"]
    text = open(skill_path, encoding="utf-8").read()
    frontmatter, _body = read_frontmatter(text)
    unknown = sorted(set(frontmatter) - ALLOWED_FRONTMATTER)
    if unknown:
        problems.append("SKILL.md frontmatter has unsupported field(s): " + ", ".join(unknown))
    name = frontmatter.get("name", "")
    if not name:
        problems.append("SKILL.md frontmatter has no `name`")
    elif not NAME_RE.fullmatch(name) or len(name) > MAX_NAME:
        problems.append("SKILL.md name must be lowercase hyphen-case and at most 64 characters")
    elif name != os.path.basename(package_dir):
        problems.append(f"name '{name}' does not match directory '{os.path.basename(package_dir)}'")
    description = frontmatter.get("description", "")
    if not description or len(description) > MAX_DESCRIPTION:
        problems.append("SKILL.md description is missing or exceeds 1024 characters")
    if len(text) > MAX_SKILL_CHARS:
        problems.append(f"SKILL.md is {len(text)} characters (policy limit {MAX_SKILL_CHARS})")
    version_path = os.path.join(package_dir, "VERSION")
    if not os.path.isfile(version_path):
        problems.append("VERSION file missing")
    else:
        packaged_version = open(version_path, encoding="utf-8").read().strip()
        if not VERSION_RE.fullmatch(packaged_version):
            problems.append("VERSION must be semver X.Y.Z")
    for relative in sorted(set(LINK_RE.findall(text))):
        if not os.path.exists(os.path.join(package_dir, relative)):
            problems.append(f"SKILL.md points at a missing path: {relative}")
    openai_path = os.path.join(package_dir, "agents", "openai.yaml")
    if not os.path.isfile(openai_path):
        problems.append("agents/openai.yaml missing")
    else:
        openai_text = open(openai_path, encoding="utf-8").read()
        problems.extend(check_openai_yaml(openai_text, name))
    return problems


def report(package_dir):
    try:
        problems = check_package(package_dir)
    except OSError as error:
        print(f"ERROR: {error}")
        return 2
    if problems:
        print(f"WINCREATOR PACKAGE POLICY: FAIL — {len(problems)} problem(s)")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"WINCREATOR PACKAGE POLICY: PASS — {package_dir}")
    return 0


def self_test():
    valid_skill = "---\nname: demo\ndescription: A useful demo skill for deterministic testing.\n---\n# Demo\n"
    valid_openai = (
        'interface:\n'
        '  display_name: "Demo"\n'
        '  short_description: "A deterministic demo skill"\n'
        '  default_prompt: "Use $demo to run the demo."\n'
    )
    results = []
    with tempfile.TemporaryDirectory() as directory:
        package = os.path.join(directory, "demo")
        os.makedirs(os.path.join(package, "agents"))
        open(os.path.join(package, "SKILL.md"), "w", encoding="utf-8").write(valid_skill)
        open(os.path.join(package, "VERSION"), "w", encoding="utf-8").write("1.2.3\n")
        open(os.path.join(package, "agents", "openai.yaml"), "w", encoding="utf-8").write(valid_openai)
        results.append(("valid_package", not check_package(package)))
        os.remove(os.path.join(package, "VERSION"))
        results.append(("missing_version", any("VERSION file missing" in item for item in check_package(package))))
        open(os.path.join(package, "VERSION"), "w", encoding="utf-8").write("1.2.3\n")
        open(os.path.join(package, "agents", "openai.yaml"), "w", encoding="utf-8").write(
            "name: Demo\ndescription: old\nprompt: old\n"
        )
        results.append(("obsolete_openai_schema", any("obsolete" in item for item in check_package(package))))
        open(os.path.join(package, "agents", "openai.yaml"), "w", encoding="utf-8").write(valid_openai)
        open(os.path.join(package, "SKILL.md"), "w", encoding="utf-8").write(
            valid_skill.replace("description:", "version: 3.0.0\ndescription:")
        )
        results.append(("extra_frontmatter", any("frontmatter" in item for item in check_package(package))))
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    passed = sum(value for _name, value in results)
    print(f"self-test: {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 2


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--self-test":
        return self_test()
    if argv and argv[0] == "--version":
        print(f"package_check.py {VERSION}")
        return 0
    default = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return report(argv[0] if argv else default)


if __name__ == "__main__":
    sys.exit(main())
