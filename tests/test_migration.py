from pathlib import Path
import zipfile

from conftest import SKILL


def test_migration_backs_up_known_legacy_installations_and_installs_only_v3(
    migration_tool, tmp_path
):
    skills_root = tmp_path / ".claude" / "skills"
    old = skills_root / "Skill_WinCreator"
    unrelated = skills_root / "unrelated-skill"
    old.mkdir(parents=True)
    unrelated.mkdir()
    (old / "user-notes.txt").write_text("keep me", encoding="utf-8")
    (unrelated / "SKILL.md").write_text("unrelated", encoding="utf-8")

    result = migration_tool.migrate(SKILL, skills_root, run_validation=False)

    assert not old.exists()
    assert unrelated.exists()
    assert (skills_root / "wincreator" / "SKILL.md").is_file()
    assert result["installed_name"] == "wincreator"
    assert result["backups"]
    assert all(backup.suffix == ".zip" for backup in result["backups"])
    with zipfile.ZipFile(result["backups"][0]) as archive:
        assert "user-notes.txt" in archive.namelist()
    assert list((skills_root / ".wincreator-backups").rglob("SKILL.md")) == []
    wincreator_entries = [
        path for path in skills_root.iterdir()
        if path.is_dir() and path.name.lower() in {"skill_wincreator", "skill-wincreator", "wincreator"}
    ]
    assert [path.name for path in wincreator_entries] == ["wincreator"]
