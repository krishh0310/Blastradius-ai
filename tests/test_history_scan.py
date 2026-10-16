"""Historical secret checks must report locations, never credential material."""

import shutil
import subprocess
from importlib import import_module

import pytest


def test_history_scan_finds_only_commit_and_path(tmp_path):
    git = shutil.which("git")
    if not git:
        pytest.skip("Git unavailable")
    subprocess.run([git, "init", "-q", str(tmp_path)], check=True)
    secret = "gsk_" + "a" * 30
    (tmp_path / "leak.txt").write_text(secret)
    subprocess.run([git, "add", "leak.txt"], cwd=tmp_path, check=True)
    subprocess.run(
        [
            git,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=tmp_path,
        check=True,
    )
    scanner = import_module("scripts.check_secrets")
    findings = scanner.scan_history(tmp_path, git)
    assert len(findings) == 1
    assert "leak.txt" in findings[0]
    assert secret not in str(findings)
