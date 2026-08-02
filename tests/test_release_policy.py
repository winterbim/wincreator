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
