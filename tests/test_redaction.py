import re
import sys
from pathlib import Path

from conftest import prove


def test_literal_and_regex_secrets_are_redacted_before_storage(wincreator, ledger, tmp_path):
    command = [
        sys.executable,
        "-c",
        "import sys; print('token=abc123'); sys.stderr.write('password=hunter2')",
    ]
    attestation, _path, _code = prove(
        wincreator,
        ledger,
        tmp_path,
        command=command,
        redact=["abc123"],
        redact_regex=[r"password=[^\\s]+"],
    )
    stdout = (tmp_path / attestation["payload"]["stdout"]["path"]).read_text(encoding="utf-8")
    stderr = (tmp_path / attestation["payload"]["stderr"]["path"]).read_text(encoding="utf-8")
    assert "abc123" not in stdout
    assert "hunter2" not in stderr
    assert "[REDACTED]" in stdout + stderr


def test_oversized_output_is_truncated_with_original_and_stored_sizes(wincreator, ledger, tmp_path):
    attestation, _path, _code = prove(
        wincreator,
        ledger,
        tmp_path,
        command=[sys.executable, "-c", "print('x' * 10000)"],
        max_output_bytes=128,
    )
    record = attestation["payload"]["stdout"]
    assert record["original_bytes"] > 128
    assert record["stored_bytes"] <= 128
    assert record["truncated"] is True


def test_no_output_body_writes_empty_logs_and_keeps_sizes(wincreator, ledger, tmp_path):
    attestation, _path, _code = prove(
        wincreator,
        ledger,
        tmp_path,
        command=[sys.executable, "-c", "print('sensitive body')"],
        no_output_body=True,
    )
    record = attestation["payload"]["stdout"]
    assert record["original_bytes"] > 0
    assert record["stored_bytes"] == 0
    assert (tmp_path / record["path"]).read_bytes() == b""
