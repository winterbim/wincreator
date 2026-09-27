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
    report, _current = distill.compare_snapshot(before, tmp_path)
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
    report, _current = distill.compare_snapshot(before, tmp_path)
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
        distill.compare_snapshot(before, tmp_path)
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
