import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import jsonschema

from conftest import REPO, SKILL


def test_skill_frontmatter_has_only_official_keys(package_check):
    problems = package_check.check_package(str(SKILL))
    assert not any("frontmatter" in problem for problem in problems), problems
    front, _body = package_check.read_frontmatter(
        (SKILL / "SKILL.md").read_text(encoding="utf-8")
    )
    assert set(front) == {"name", "description"}


def test_openai_yaml_uses_current_interface_schema(package_check):
    problems = package_check.check_package(str(SKILL))
    assert not any("openai.yaml" in problem for problem in problems), problems
    text = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")
    assert "interface:" in text
    assert 'display_name: "WinCreator"' in text
    assert "$wincreator" in text
    assert not text.startswith("name:")


def test_package_check_rejects_obsolete_openai_schema(package_check, tmp_path):
    pkg = tmp_path / "demo"
    (pkg / "agents").mkdir(parents=True)
    (pkg / "SKILL.md").write_text(
        "---\nname: demo\ndescription: A sufficiently useful demo skill.\n---\n# Demo\n",
        encoding="utf-8",
    )
    (pkg / "agents" / "openai.yaml").write_text(
        "name: Demo\ndescription: old\nprompt: old\n", encoding="utf-8"
    )
    assert any("obsolete" in problem for problem in package_check.check_package(str(pkg)))


def test_attestation_matches_published_json_schema(wincreator, ledger, tmp_path):
    attestation, _path, _code = wincreator.run_and_attest(
        "P1",
        ["python3", "-c", "print('ok')"],
        ledger=str(ledger),
        attest_dir=str(tmp_path / "attestations"),
        cwd=str(tmp_path),
        quiet=True,
        tier="standard",
    )
    schema = json.loads((SKILL / "schemas" / "attestation-v1.schema.json").read_text())
    jsonschema.validate(attestation, schema)


def test_reproducible_builder_emits_identical_aliases(package_builder, tmp_path):
    first = tmp_path / "build-1"
    second = tmp_path / "build-2"
    package_builder.build(SKILL, first)
    package_builder.build(SKILL, second)
    first_zip = (first / "skill.zip").read_bytes()
    second_zip = (second / "skill.zip").read_bytes()
    assert hashlib.sha256(first_zip).digest() == hashlib.sha256(second_zip).digest()
    assert first_zip == (first / "wincreator.skill").read_bytes()
    with zipfile.ZipFile(first / "skill.zip") as archive:
        skill_entries = [name for name in archive.namelist() if name.endswith("SKILL.md")]
        assert skill_entries == ["wincreator/SKILL.md"]


def test_builder_excludes_secret_environment_files(package_builder, tmp_path):
    source = tmp_path / "wincreator"
    shutil.copytree(SKILL, source)
    (source / ".env").write_text("TOKEN=must-not-ship", encoding="utf-8")
    output = tmp_path / "dist"
    package_builder.build(source, output)
    with zipfile.ZipFile(output / "skill.zip") as archive:
        assert "wincreator/.env" not in archive.namelist()


def test_builder_rejects_symlink_escaping_package(package_builder, tmp_path):
    source = tmp_path / "wincreator"
    shutil.copytree(SKILL, source)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    (source / "escape.txt").symlink_to(outside)
    import pytest
    with pytest.raises(ValueError, match="symlink escapes"):
        package_builder.build(source, tmp_path / "dist")
