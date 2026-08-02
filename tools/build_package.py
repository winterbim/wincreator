#!/usr/bin/env python3
"""Build byte-for-byte reproducible WinCreator archives."""

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import stat
import tempfile
import zipfile


MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
EXCLUDED_PARTS = {".git", ".wincreator", "__pycache__"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
EXCLUDED_NAMES = {".env", ".env.local", ".DS_Store"}


def _files(source):
    source = Path(source).resolve()
    selected = []
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.name in EXCLUDED_NAMES or path.suffix in EXCLUDED_SUFFIXES:
            continue
        if path.is_symlink():
            resolved = path.resolve(strict=True)
            try:
                resolved.relative_to(source)
            except ValueError as error:
                raise ValueError(f"symlink escapes package: {relative}") from error
        if path.is_file():
            selected.append((relative, path))
    return sorted(selected, key=lambda item: item[0].as_posix())


def _write_zip(source, destination):
    source = Path(source).resolve()
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, path in _files(source):
            info = zipfile.ZipInfo(f"{source.name}/{relative.as_posix()}", ZIP_TIMESTAMP)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.flag_bits |= 0x800
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _sha256(path):
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return digest


def build(source, output_dir):
    source = Path(source).resolve()
    output_dir = Path(output_dir).resolve()
    if source.name != "wincreator" or not (source / "SKILL.md").is_file():
        raise ValueError("source must be the wincreator skill directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".wincreator-package-", suffix=".zip", dir=output_dir)
    os.close(fd)
    temporary = Path(temporary)
    try:
        _write_zip(source, temporary)
        if temporary.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ValueError("package exceeds the 25 MiB limit")
        skill_zip = output_dir / "skill.zip"
        alias = output_dir / "wincreator.skill"
        os.replace(temporary, skill_zip)
        shutil.copyfile(skill_zip, alias)
        digests = {}
        for path in (skill_zip, alias):
            digest = _sha256(path)
            (output_dir / f"{path.name}.sha256").write_text(f"{digest}  {path.name}\n", encoding="ascii")
            digests[path.name] = digest
        if digests["skill.zip"] != digests["wincreator.skill"]:
            raise RuntimeError("archive aliases are not byte-identical")
        return digests
    finally:
        if temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", nargs="?", default="dist")
    parser.add_argument("--source", default="skill/wincreator")
    args = parser.parse_args()
    digests = build(args.source, args.output_dir)
    for name, digest in digests.items():
        print(f"{digest}  {name}")


if __name__ == "__main__":
    main()
