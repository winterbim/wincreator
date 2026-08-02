from concurrent.futures import ThreadPoolExecutor
import sys


def test_concurrent_captures_never_collide(wincreator, tmp_path):
    def capture(_index):
        _attestation, path, _code = wincreator.run_and_attest(
            "P1",
            [sys.executable, "-c", "print('ok')"],
            ledger=None,
            attest_dir=str(tmp_path / "attestations"),
            cwd=str(tmp_path),
            quiet=True,
            tier="lite",
        )
        return path

    with ThreadPoolExecutor(max_workers=8) as pool:
        paths = list(pool.map(capture, range(16)))

    assert len(paths) == len(set(paths)) == 16
