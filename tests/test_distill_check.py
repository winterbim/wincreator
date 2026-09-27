import importlib.util
import json

from conftest import SKILL


def load_distill():
    path = SKILL / "scripts" / "distill_check.py"
    spec = importlib.util.spec_from_file_location("distill_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reducing_structure_is_measured(tmp_path):
    distill = load_distill()
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"a": "1", "b": "1"}}),
        encoding="utf-8",
    )
    (tmp_path / "a.py").write_text(
        "def f(x):\n    return x + 1\n\ndef g(x):\n    return x + 1\n",
        encoding="utf-8",
    )
    before = distill.build_snapshot(tmp_path)
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"a": "1"}}),
        encoding="utf-8",
    )
    (tmp_path / "a.py").write_text("def f(x):\n    return x + 1\n", encoding="utf-8")
    report, _current = distill.compare_snapshot(before, tmp_path, before["digest"])
    assert report["verdict"] == "IMPROVED"
    assert report["dependency_changes"]["removed"] == ["npm:b"]


def test_new_dependency_forces_review_even_if_count_is_flat(tmp_path):
    distill = load_distill()
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"a": "1"}}),
        encoding="utf-8",
    )
    (tmp_path / "a.py").write_text("print('ok')\n", encoding="utf-8")
    before = distill.build_snapshot(tmp_path)
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"b": "1"}}),
        encoding="utf-8",
    )
    report, _current = distill.compare_snapshot(before, tmp_path, before["digest"])
    assert report["delta"]["declared_dependencies"] == 0
    assert report["dependency_changes"]["added"] == ["npm:b"]
    assert report["verdict"] == "REVIEW_REQUIRED"
    assert "new_dependencies" in report["regressed_dimensions"]


def test_tampered_snapshot_fails_closed(tmp_path):
    distill = load_distill()
    (tmp_path / "a.py").write_text("print('ok')\n", encoding="utf-8")
    before = distill.build_snapshot(tmp_path)
    before["metrics"]["source_files"] += 1
    try:
        distill.compare_snapshot(before, tmp_path, before["digest"])
    except ValueError as exc:
        assert "digest mismatch" in str(exc)
    else:
        raise AssertionError("tampered snapshot was accepted")


def test_scope_cannot_escape_root(tmp_path):
    distill = load_distill()
    outside = tmp_path.parent / "outside.py"
    outside.write_text("print('outside')\n", encoding="utf-8")
    try:
        distill.build_snapshot(tmp_path, scopes=["../outside.py"])
    except ValueError as exc:
        assert "escapes root" in str(exc)
    else:
        raise AssertionError("escaping scope was accepted")


def test_external_baseline_digest_is_required_and_bound(tmp_path):
    distill = load_distill()
    (tmp_path / "a.py").write_text("print('ok')\n", encoding="utf-8")
    before = distill.build_snapshot(tmp_path)

    try:
        distill.compare_snapshot(before, tmp_path)
    except ValueError as exc:
        assert "external baseline digest is required" in str(exc)
    else:
        raise AssertionError("compare accepted an unanchored baseline")

    try:
        distill.compare_snapshot(before, tmp_path, "0" * 64)
    except ValueError as exc:
        assert "external baseline digest mismatch" in str(exc)
    else:
        raise AssertionError("compare accepted the wrong external digest")


def test_narrow_scope_still_tracks_ancestor_manifest(tmp_path):
    distill = load_distill()
    scoped = tmp_path / "src" / "export"
    scoped.mkdir(parents=True)
    (scoped / "module.py").write_text("print('ok')\n", encoding="utf-8")
    package = tmp_path / "package.json"
    package.write_text(json.dumps({"dependencies": {"a": "1"}}), encoding="utf-8")

    before = distill.build_snapshot(tmp_path, scopes=["src/export"])
    assert "package.json" in before["manifests"]

    package.write_text(json.dumps({"dependencies": {"a": "1", "b": "1"}}), encoding="utf-8")
    report, _current = distill.compare_snapshot(before, tmp_path, before["digest"])

    assert report["dependency_changes"]["added"] == ["npm:b"]
    assert report["verdict"] == "REVIEW_REQUIRED"


def test_unparsed_manifests_fail_closed_on_change(tmp_path):
    distill = load_distill()
    cases = {
        "Cargo.toml": (
            "[package] # comment\nname = \"demo\"\n"
            "[dependencies] # runtime\nserde = \"1\"\n"
        ),
        "pyproject.toml": (
            "[project]\nname = \"demo\"\n"
            "dependencies = [\"requests[security]>=2\"]\n"
        ),
        "go.mod": "module example.com/demo\n\nrequire(\nexample.com/a v1.0.0\n)\n",
    }

    for name, content in cases.items():
        root = tmp_path / name.replace(".", "-")
        root.mkdir()
        path = root / name
        path.write_text(content, encoding="utf-8")
        before = distill.build_snapshot(root)

        unchanged, _current = distill.compare_snapshot(
            before, root, before["digest"]
        )
        assert "unparsed_manifest_changes" not in unchanged["regressed_dimensions"]

        path.write_text(content + "\n# changed\n", encoding="utf-8")
        changed, _current = distill.compare_snapshot(
            before, root, before["digest"]
        )
        assert changed["verdict"] == "REVIEW_REQUIRED"
        assert "unparsed_manifest_changes" in changed["regressed_dimensions"]
        assert changed["dependency_changes"]["unparsed_manifest_changes"] == [name]


def test_requirements_includes_and_editables_fail_closed(tmp_path):
    distill = load_distill()
    for body in (
        "-r requirements/base.txt\n",
        "--requirement requirements/base.txt\n",
        "-e ./pkg-a\n",
        "--editable ./pkg-a\n",
    ):
        root = tmp_path / str(abs(hash(body)))
        root.mkdir()
        (root / "requirements.txt").write_text(body, encoding="utf-8")
        before = distill.build_snapshot(root)
        assert any("unsupported requirements syntax" in w for w in before["warnings"])
        report, _current = distill.compare_snapshot(before, root, before["digest"])
        assert report["verdict"] == "REVIEW_REQUIRED"
        assert "scan_warnings" in report["regressed_dimensions"]


def test_symlink_directory_is_reported_and_forces_review(tmp_path):
    distill = load_distill()
    real = tmp_path / "real"
    real.mkdir()
    (real / "module.py").write_text("print('ok')\n", encoding="utf-8")
    before = distill.build_snapshot(tmp_path)

    link = tmp_path / "linked-source"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        import pytest
        pytest.skip("directory symlinks unavailable in this environment")

    current = distill.build_snapshot(tmp_path)
    assert any("symlink directory ignored" in w for w in current["warnings"])
    report, _current = distill.compare_snapshot(before, tmp_path, before["digest"])
    assert report["verdict"] == "REVIEW_REQUIRED"
    assert "scan_warnings" in report["regressed_dimensions"]
