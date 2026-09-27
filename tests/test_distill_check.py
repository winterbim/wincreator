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


def test_cargo_subtables_and_target_dependencies_are_seen(tmp_path):
    distill = load_distill()
    cargo = tmp_path / "Cargo.toml"
    cargo.write_text(
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n"
        "[dependencies.serde]\nversion = \"1\"\n"
        "[target.'cfg(unix)'.dependencies]\nlibc = \"0.2\"\n"
        "[target.'cfg(windows)'.dependencies.winapi]\nversion = \"0.3\"\n",
        encoding="utf-8",
    )

    snap = distill.build_snapshot(tmp_path)

    assert "cargo:serde" in snap["dependencies"]
    assert "cargo:libc" in snap["dependencies"]
    assert "cargo:winapi" in snap["dependencies"]
