import sys
from pathlib import Path

from conftest import prove


def test_windows_path_is_normalized_for_portable_attestation(wincreator):
    assert wincreator.portable_path(r"C:\Users\Zoë\My Reports\report.ifc") == (
        "C:/Users/Zoë/My Reports/report.ifc"
    )


def test_spaces_and_unicode_paths_are_attested(wincreator, ledger, tmp_path):
    artifact = tmp_path / "résultats finaux" / "rapport été.ifc"
    artifact.parent.mkdir()
    artifact.write_bytes(b"ifc")
    attestation, _path, _code = prove(
        wincreator, ledger, tmp_path, files=[str(artifact)]
    )
    assert attestation["payload"]["files"][0]["path"].endswith(
        "résultats finaux/rapport été.ifc"
    )
