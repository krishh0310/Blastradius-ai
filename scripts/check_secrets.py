"""Scan project text and tracked dotenv files without printing secret values."""

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


if __name__ == "__main__":
    raise SystemExit(main())
