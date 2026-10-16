"""Scan project text and tracked dotenv files without printing secret values."""

import argparse
import os
import re
import shutil

# Fixed local Git command; no shell or user arguments.
import subprocess  # nosec B404
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".audit-cache", "htmlcov"}
PATTERN = re.compile(
    r"AIza[\w-]{35}|gsk_[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)


def scan(root: Path, secrets: tuple[str, ...] = ()) -> list[str]:
    """Return file/line references only; local dotenv files are intentionally private."""
    findings = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink() or set(path.relative_to(root).parts) & SKIP:
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            continue
        if path.suffix in {".pyc", ".png", ".jpg", ".whl"} or path.name == ".coverage":
            continue
        try:
            content = path.read_text()
        except (UnicodeError, OSError):
            continue
        for line, text in enumerate(content.splitlines(), 1):
            if PATTERN.search(text) or any(secret and secret in text for secret in secrets):
                findings.append(f"{path.relative_to(root)}:{line}: potential secret")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--history", action="store_true", help="Also scan all locally reachable Git commits"
    )
    args = parser.parse_args()
    git = shutil.which("git")
    result = (
        # Resolved executable and constant arguments only.
        subprocess.run(  # nosec B603
            [git, "ls-files", "-z"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        if git
        else None
    )
    findings = scan(
        ROOT, tuple(os.environ.get(name, "") for name in ("GEMINI_API_KEY", "GROQ_API_KEY"))
    )
    if args.history:
        if git is None or result is None or result.returncode != 0:
            print("Historical scan unavailable: a local Git repository is required.")
            return 1
        try:
            findings += scan_history(
                ROOT,
                git,
                tuple(os.environ.get(name, "") for name in ("GEMINI_API_KEY", "GROQ_API_KEY")),
            )
        except (ValueError, subprocess.SubprocessError):
            print("Historical scan failed; no secret values were printed.")
            return 1
    if result is not None and result.returncode == 0:
        for name in result.stdout.decode().split("\0"):
            if Path(name).name.startswith(".env") and Path(name).name != ".env.example":
                findings.append(f"{name}: dotenv file is tracked by Git")
    else:
        print("Git tracking/history unavailable: this directory is not a Git repository.")
    for finding in findings:
        print(finding)
    print(f"Source secret scan: {len(findings)} finding(s); values never printed.")
    return int(bool(findings))


def scan_history(root: Path, git: str, secrets: tuple[str, ...] = ()) -> list[str]:
    """Read local objects only. Report commit/path, never blob contents or keys."""

    def read(*arguments: str) -> bytes:
        # Object arguments come from local Git output; no shell is used.
        result = subprocess.run(  # nosec B603
            [git, *arguments],
            cwd=root,
            capture_output=True,
            check=False,
            timeout=10,
        )
        if result.returncode:
            raise ValueError("Cannot inspect Git history")
        return result.stdout

    findings = []
    for commit in read("rev-list", "--all").decode().split():
        for raw_path in read("ls-tree", "-rz", "--name-only", commit).split(b"\0"):
            if not raw_path:
                continue
            path = raw_path.decode()
            content = read("show", f"{commit}:{path}").decode(errors="replace")
            dotenv = Path(path).name.startswith(".env") and Path(path).name != ".env.example"
            if dotenv or PATTERN.search(content) or any(key and key in content for key in secrets):
                findings.append(
                    f"{commit[:12]}:{path}: potential historical secret or tracked dotenv"
                )
    return findings


if __name__ == "__main__":
    raise SystemExit(main())
