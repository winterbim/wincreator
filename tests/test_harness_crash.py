import subprocess
import sys
import time

from conftest import REPO, harness_contract

from harness.runtime import Executor

GATE_SCRIPT = """import pathlib, sys, time

marker = pathlib.Path(sys.argv[1])
release = pathlib.Path(sys.argv[2])
if not marker.exists():
    marker.write_text("armed")
    deadline = time.monotonic() + 30
    while not release.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
print("gate ok")
"""


def _wait_for_open_attempt(store, task_id, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        attempt = store.open_attempt(task_id)
        if attempt is not None:
            return attempt
        time.sleep(0.05)
    raise AssertionError("the runtime never opened an attempt")


def test_killed_runtime_is_recovered_by_resume(tmp_path):
    gate = tmp_path / "gate.py"
    gate.write_text(GATE_SCRIPT, encoding="utf-8")
    marker = tmp_path / "armed"
    release = tmp_path / "release"
    executor = Executor(str(tmp_path), builder="builder-01", quiet=True)
    executor.initialize()
    contract = harness_contract(
        tier="lite",
        max_attempts=2,
        command=[sys.executable, str(gate), str(marker), str(release)],
    )
    executor.register(contract)

    process = subprocess.Popen(
        [sys.executable, "-m", "harness", "--root", str(tmp_path), "run", contract.task_id],
        cwd=str(REPO),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        attempt = _wait_for_open_attempt(executor.store, contract.task_id)
        assert attempt["attempt_no"] == 1
        assert attempt["state"] == "RUNNING"
        process.kill()
        process.wait(timeout=30)
    finally:
        release.write_text("go", encoding="utf-8")
        if process.poll() is None:  # pragma: no cover - defensive cleanup
            process.kill()
            process.wait(timeout=30)

    recovered = Executor(str(tmp_path), builder="builder-01", quiet=True)
    outcome = recovered.resume()

    assert outcome["reaped"], "the killed owner must be reaped"
    assert outcome["reaped"][0]["attempt_no"] == 1
    assert outcome["results"][0]["state"] == "SUCCEEDED"
    task = recovered.store.get_task(contract.task_id)
    assert [item["state"] for item in task.attempts] == ["ABANDONED", "COMPLETED"]
    assert recovered.store.verify_integrity() == []
    assert recovered.verify(require_complete=True)[0] == []
    event_types = [event["type"] for event in recovered.store.events(contract.task_id)]
    assert event_types.count("attempt_started") == 2
    assert "attempt_abandoned" in event_types
    assert "retry_scheduled" in event_types
    assert event_types[-1] == "state_changed"
