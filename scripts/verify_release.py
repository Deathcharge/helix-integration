"""Fail closed when a release tag and project metadata disagree."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r'^version = "(?P<version>\d+\.\d+\.\d+)"$', re.MULTILINE)


def fail(message: str) -> None:
    """Stop a release check without a traceback."""

    raise SystemExit(f"release verification failed: {message}")


def project_version(root: Path = ROOT) -> str:
    """Return the single literal semantic version from project metadata."""

    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    matches = VERSION_PATTERN.findall(pyproject)
    if len(matches) != 1:
        fail("pyproject.toml must contain exactly one literal semantic version")
    return matches[0]


def package_version(source: str) -> str:
    """Return exactly one module-level literal ``__version__`` assignment."""

    try:
        module = ast.parse(source)
    except SyntaxError as error:
        fail(f"package __init__.py is invalid Python: {error.msg}")

    value_nodes: list[ast.expr] = []
    for statement in module.body:
        match statement:
            case ast.Assign(targets=targets, value=value) if any(
                isinstance(target, ast.Name) and target.id == "__version__" for target in targets
            ):
                value_nodes.append(value)
            case ast.AnnAssign(target=ast.Name(id="__version__"), value=value) if value is not None:
                value_nodes.append(value)

    if len(value_nodes) != 1:
        fail("package __init__.py must contain exactly one literal module-level __version__ assignment")
    try:
        value = ast.literal_eval(value_nodes[0])
    except (TypeError, ValueError):
        fail("package __version__ must be a literal string")
    if not isinstance(value, str):
        fail("package __version__ must be a literal string")
    return value


def main(arguments: list[str]) -> int:
    """Verify tag, project, package, and changelog versions agree."""

    if len(arguments) != 2:
        fail("usage: verify_release.py vMAJOR.MINOR.PATCH")

    tag = arguments[1]
    version = project_version()
    expected_tag = f"v{version}"
    if tag != expected_tag:
        fail(f"tag {tag!r} does not match project version {version!r}")

    package_init = (ROOT / "src" / "samsarix_guard" / "__init__.py").read_text(encoding="utf-8")
    if package_version(package_init) != version:
        fail("package __version__ does not match pyproject.toml")

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if re.search(rf"^## {re.escape(version)} - \d{{4}}-\d{{2}}-\d{{2}}$", changelog, re.MULTILINE) is None:
        fail("CHANGELOG.md has no dated heading for the release version")

    print(f"verified release tag {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
