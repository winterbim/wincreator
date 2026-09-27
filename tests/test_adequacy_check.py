import importlib.util
import sys

from conftest import SKILL


def load_adequacy():
    path = SKILL / "scripts" / "adequacy_check.py"
    spec = importlib.util.spec_from_file_location("adequacy_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_project(tmp_path):
    (tmp_path / "logic.py").write_text(
        "def allowed(age):\n    return age >= 18\n",
        encoding="utf-8",
    )
    (tmp_path / "check.py").write_text(
        "from logic import allowed\n"
        "assert allowed(18) is True\n"
        "assert allowed(17) is False\n",
        encoding="utf-8",
    )
    return [sys.executable, "check.py"]


def test_required_mutation_must_be_killed(tmp_path):
    adequacy = load_adequacy()
    gate = make_project(tmp_path)
    manifest = {
        "schema": adequacy.MANIFEST_SCHEMA,
        "mutations": [
            {
                "id": "flip-boundary",
                "path": "logic.py",
                "find": "age >= 18",
                "replace": "age > 18",
            }
        ],
    }
    report = adequacy.run_adequacy(tmp_path, manifest, gate)
    assert report["verdict"] == "ADEQUATE"
    assert report["mutations"][0]["result"] == "KILLED"
    assert adequacy.verify_report(report)


def test_surviving_required_mutation_is_insufficient(tmp_path):
    adequacy = load_adequacy()
    gate = make_project(tmp_path)
    manifest = {
        "schema": adequacy.MANIFEST_SCHEMA,
        "mutations": [
            {
                "id": "untested-branch",
                "path": "logic.py",
                "find": "return age >= 18",
                "replace": "return age >= 18 if age >= 0 else True",
            }
        ],
    }
    report = adequacy.run_adequacy(tmp_path, manifest, gate)
    assert report["verdict"] == "INSUFFICIENT"
    assert report["mutations"][0]["result"] == "SURVIVED"


def test_optional_survivor_does_not_block(tmp_path):
    adequacy = load_adequacy()
    gate = make_project(tmp_path)
    manifest = {
        "schema": adequacy.MANIFEST_SCHEMA,
        "mutations": [
            {
                "id": "optional-untested",
                "path": "logic.py",
                "find": "return age >= 18",
                "replace": "return age >= 18 if age >= 0 else True",
                "required": False,
            }
        ],
    }
    report = adequacy.run_adequacy(tmp_path, manifest, gate)
    assert report["verdict"] == "ADEQUATE"
    assert report["mutations"][0]["result"] == "SURVIVED"


def test_failing_baseline_cannot_be_called_adequate(tmp_path):
    adequacy = load_adequacy()
    (tmp_path / "logic.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "check.py").write_text("raise SystemExit(3)\n", encoding="utf-8")
    manifest = {
        "schema": adequacy.MANIFEST_SCHEMA,
        "mutations": [
            {"id": "m", "path": "logic.py", "find": "1", "replace": "2"}
        ],
    }
    report = adequacy.run_adequacy(
        tmp_path, manifest, [sys.executable, "check.py"]
    )
    assert report["verdict"] == "ERROR"
    assert report["baseline"]["exit_code"] == 3


def test_missing_or_ambiguous_mutation_fails_closed(tmp_path):
    adequacy = load_adequacy()
    gate = make_project(tmp_path)
    manifest = {
        "schema": adequacy.MANIFEST_SCHEMA,
        "mutations": [
            {
                "id": "ambiguous",
                "path": "logic.py",
                "find": "a",
                "replace": "b",
            }
        ],
    }
    report = adequacy.run_adequacy(tmp_path, manifest, gate)
    assert report["verdict"] == "ERROR"
    assert report["mutations"][0]["result"] == "INVALID"


def test_path_escape_fails_closed(tmp_path):
    adequacy = load_adequacy()
    gate = make_project(tmp_path)
    manifest = {
        "schema": adequacy.MANIFEST_SCHEMA,
        "mutations": [
            {
                "id": "escape",
                "path": "../outside.py",
                "find": "x",
                "replace": "y",
            }
        ],
    }
    report = adequacy.run_adequacy(tmp_path, manifest, gate)
    assert report["verdict"] == "ERROR"
    assert "escapes root" in report["mutations"][0]["error"]


def test_report_tamper_is_detected(tmp_path):
    adequacy = load_adequacy()
    gate = make_project(tmp_path)
    manifest = {
        "schema": adequacy.MANIFEST_SCHEMA,
        "mutations": [
            {
                "id": "flip-boundary",
                "path": "logic.py",
                "find": "age >= 18",
                "replace": "age > 18",
            }
        ],
    }
    report = adequacy.run_adequacy(tmp_path, manifest, gate)
    report["verdict"] = "INSUFFICIENT"
    try:
        adequacy.verify_report(report)
    except ValueError as exc:
        assert "digest mismatch" in str(exc)
    else:
        raise AssertionError("tampered report was accepted")
