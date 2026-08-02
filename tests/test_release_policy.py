from conftest import REPO


def test_tag_pointing_to_wrong_commit_is_rejected(release_policy):
    problems = release_policy.validate_release_state(
        expected_tag="v3.0.0",
        workflow_sha="a" * 40,
        tag_commit="b" * 40,
        default_branch_contains_tag=True,
        latest_tag="v3.0.0",
        pr_checks_green=True,
        badge_branch="master",
    )
    assert any("tag commit" in problem for problem in problems)


def test_tag_on_old_default_branch_ancestor_is_rejected(release_policy):
    problems = release_policy.validate_release_state(
        expected_tag="v3.0.0",
        workflow_sha="a" * 40,
        tag_commit="a" * 40,
        default_branch_contains_tag=True,
        default_branch_head="b" * 40,
    )
    assert any("default branch head" in problem for problem in problems)


def test_release_tag_must_match_packaged_version(release_policy):
    problems = release_policy.validate_release_state(
        expected_tag="v9.9.9",
        workflow_sha="a" * 40,
        tag_commit="a" * 40,
        default_branch_contains_tag=True,
        default_branch_head="a" * 40,
        package_version="3.0.0",
    )
    assert any("package version" in problem for problem in problems)


def test_release_requires_successful_ci_success_on_tag_commit(release_policy):
    problems = release_policy.validate_release_state(
        expected_tag="v3.0.0",
        workflow_sha="a" * 40,
        tag_commit="a" * 40,
        default_branch_contains_tag=True,
        default_branch_head="a" * 40,
        package_version="3.0.0",
        required_check="ci-success",
        check_runs={"check_runs": [
            {"name": "ci-success", "status": "completed", "conclusion": "failure"}
        ]},
    )
    assert any("ci-success" in problem and "successful" in problem for problem in problems)


def test_release_rejects_spoofed_ci_success_from_wrong_app(release_policy):
    problems = release_policy.validate_release_state(
        expected_tag="v3.0.0",
        workflow_sha="a" * 40,
        tag_commit="a" * 40,
        default_branch_contains_tag=True,
        default_branch_head="a" * 40,
        package_version="3.0.0",
        required_check="ci-success",
        required_check_app="github-actions",
        check_runs={"check_runs": [{
            "name": "ci-success",
            "status": "completed",
            "conclusion": "success",
            "app": {"slug": "untrusted-app"},
        }]},
    )
    assert any("ci-success" in problem and "successful" in problem for problem in problems)


def test_release_accepts_exact_version_and_github_actions_success(release_policy):
    problems = release_policy.validate_release_state(
        expected_tag="v3.0.0",
        workflow_sha="a" * 40,
        tag_commit="a" * 40,
        default_branch_contains_tag=True,
        default_branch_head="a" * 40,
        package_version="3.0.0",
        required_check="ci-success",
        required_check_app="github-actions",
        check_runs={"check_runs": [{
            "name": "ci-success",
            "status": "completed",
            "conclusion": "success",
            "app": {"slug": "github-actions"},
        }]},
    )
    assert problems == []


def test_release_workflow_is_read_only_until_publish_step():
    workflow = (REPO / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "persist-credentials: false" in workflow
    assert "prepare:\n    permissions:\n      contents: read" in workflow
    assert "publish:\n    needs: prepare\n    permissions:\n      contents: write" in workflow
    assert "--required-check ci-success" in workflow
    assert "--required-check-app github-actions" in workflow
    assert "--package-version" in workflow
    assert "--file dist/skill.zip" in workflow
    ci_workflow = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "Prepare deterministic package inputs" in ci_workflow
    assert "--file dist/skill.zip" in ci_workflow


def test_official_validator_dependencies_are_installed_before_validation():
    workflow = (REPO / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    dependency = "PyYAML==6.0.3"
    validator = "quick_validate.py"
    assert dependency in workflow
    assert workflow.index(dependency) < workflow.index(validator)


def test_latest_release_must_match_expected_tag(release_policy):
    problems = release_policy.validate_release_state(
        expected_tag="v3.0.0",
        workflow_sha="a" * 40,
        tag_commit="a" * 40,
        default_branch_contains_tag=True,
        latest_tag="v2.5.0",
        pr_checks_green=True,
        badge_branch="master",
    )
    assert any("latest" in problem for problem in problems)


def test_green_default_branch_badge_does_not_override_red_pr(release_policy):
    problems = release_policy.validate_release_state(
        expected_tag="v3.0.0",
        workflow_sha="a" * 40,
        tag_commit="a" * 40,
        default_branch_contains_tag=True,
        latest_tag="v3.0.0",
        pr_checks_green=False,
        badge_branch="master",
    )
    assert any("badge" in problem and "PR" in problem for problem in problems)


def test_old_release_notice_is_added_once(release_deprecation_tool):
    original = "Original release notes."
    first = release_deprecation_tool.with_deprecation_notice(original)
    second = release_deprecation_tool.with_deprecation_notice(first)
    assert "Cette version est obsolète" in first
    assert "releases/latest" in first
    assert second == first
