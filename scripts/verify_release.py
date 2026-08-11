"""Fail closed when a release tag and project metadata disagree."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r'^version = "(?P<version>\d+\.\d+\.\d+)"$', re.MULTILINE)


def fail(message: str) -> None:
    raise SystemExit(f"release verification failed: {message}")


def project_version(root: Path = ROOT) -> str:
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    matches = VERSION_PATTERN.findall(pyproject)
    if len(matches) != 1:
        fail("pyproject.toml must contain exactly one literal semantic version")
    return matches[0]


def main(arguments: list[str]) -> int:
    if len(arguments) != 2:
        fail("usage: verify_release.py vMAJOR.MINOR.PATCH")

    tag = arguments[1]
    version = project_version()
    expected_tag = f"v{version}"
    if tag != expected_tag:
        fail(f"tag {tag!r} does not match project version {version!r}")

    package_init = (ROOT / "src" / "samsarix_guard" / "__init__.py").read_text(encoding="utf-8")
    if f'__version__ = "{version}"' not in package_init:
        fail("package __version__ does not match pyproject.toml")

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if re.search(rf"^## {re.escape(version)} - \d{{4}}-\d{{2}}-\d{{2}}$", changelog, re.MULTILINE) is None:
        fail("CHANGELOG.md has no dated heading for the release version")

    print(f"verified release tag {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
