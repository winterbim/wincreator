import json

from conftest import SKILL, load_module


distill = load_module("distill_under_test", SKILL / "scripts" / "distill.py")


def test_snapshot_excludes_generated_tree_and_hashes(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "noise.js").write_text("x = 1\n" * 100, encoding="utf-8")

    snap = distill.snapshot(tmp_path)

    assert distill.verify_snapshot(snap)
    assert snap["metrics"]["source_files"] == 1
    assert [item["path"] for item in snap["files"]] == ["src/app.py"]


def test_refactor_growth_requests_review(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    before = distill.snapshot(tmp_path)
    (tmp_path / "extra.py").write_text("y = 2\n" * 5, encoding="utf-8")
    after = distill.snapshot(tmp_path)

    report = distill.compare(before, after, "refactor")

    assert report["verdict"] == "REVIEW"
    assert report["delta"]["source_files"] == 1
    assert any("source_files" in reason for reason in report["reasons"])


def test_feature_dependency_growth_requests_review(tmp_path):
    package = tmp_path / "package.json"
    package.write_text(json.dumps({"dependencies": {}}), encoding="utf-8")
    before = distill.snapshot(tmp_path)
    package.write_text(json.dumps({"dependencies": {"zod": "4.0.0"}}), encoding="utf-8")
    after = distill.snapshot(tmp_path)

    report = distill.compare(before, after, "feature")

    assert report["verdict"] == "REVIEW"
    assert report["dependencies_added"] == ["zod"]


def test_audit_is_descriptive_not_correctness_claim(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    before = distill.snapshot(tmp_path)
    (tmp_path / "app.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    after = distill.snapshot(tmp_path)

    report = distill.compare(before, after, "audit")

    assert report["verdict"] == "PASS"
    assert report["delta"]["nonblank_lines"] == 1


def test_tampered_snapshot_is_rejected(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n", encoding="utf-8")
    snap = distill.snapshot(tmp_path)
    snap["metrics"]["nonblank_lines"] += 1

    assert not distill.verify_snapshot(snap)
