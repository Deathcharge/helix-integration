"""Verify that built artifacts contain only the supported package surface."""

from __future__ import annotations

import sys
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path

REQUIRED_MODULES = {
    "samsarix_guard/__init__.py",
    "samsarix_guard/__main__.py",
    "samsarix_guard/cli.py",
    "samsarix_guard/policy.py",
    "samsarix_guard/redaction.py",
    "samsarix_guard/reporting.py",
}
REQUIRED_SDIST_FILES = {
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "LICENSING.md",
    "NOTICE",
    "README.md",
    "SECURITY.md",
    "SUPPORT.md",
    "TRADEMARKS.md",
    "action.yml",
}


def fail(message: str) -> None:
    raise SystemExit(f"distribution verification failed: {message}")


def verify_wheel(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        missing = REQUIRED_MODULES - names
        if missing:
            fail(f"wheel is missing {sorted(missing)}")
        if any("legacy" in name.casefold() or "saas_router" in name.casefold() for name in names):
            fail("wheel contains the legacy Helix Unified snapshot")
        unexpected_code = {
            name
            for name in names
            if name.endswith(".py") and not name.startswith("samsarix_guard/")
        }
        if unexpected_code:
            fail(f"wheel contains unexpected Python modules: {sorted(unexpected_code)}")

        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            fail("wheel must contain exactly one METADATA file")
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
        if metadata.get("Name") != "samsarix-integration-guard":
            fail(f"wheel has unexpected project name: {metadata.get('Name')!r}")
        if metadata.get("License-Expression") != "MPL-2.0":
            fail(f"wheel has unexpected license: {metadata.get('License-Expression')!r}")
        runtime_requirements = [
            requirement
            for requirement in metadata.get_all("Requires-Dist", [])
            if 'extra == "dev"' not in requirement and "extra == 'dev'" not in requirement
        ]
        if runtime_requirements:
            fail(f"wheel has runtime dependencies: {runtime_requirements}")
        if not any(name.endswith(".dist-info/licenses/LICENSE") for name in names):
            fail("wheel does not contain LICENSE")
        if not any(name.endswith(".dist-info/licenses/NOTICE") for name in names):
            fail("wheel does not contain NOTICE")

        entry_point_names = [name for name in names if name.endswith(".dist-info/entry_points.txt")]
        if len(entry_point_names) != 1:
            fail("wheel must contain exactly one entry_points.txt file")
        entry_points = archive.read(entry_point_names[0]).decode("utf-8")
        if "samsarix-guard = samsarix_guard.cli:main" not in entry_points:
            fail("wheel does not expose the samsarix-guard command")


def verify_sdist(path: Path) -> None:
    with tarfile.open(path, "r:gz") as archive:
        names = set(archive.getnames())
        if any("/legacy/" in name.casefold() or "/helix_unified_snapshot/" in name.casefold() for name in names):
            fail("source distribution contains the unsupported legacy snapshot")
        suffixes = {name.split("/", 1)[-1] for name in names}
        missing = {f"src/{module}" for module in REQUIRED_MODULES} - suffixes
        if missing:
            fail(f"source distribution is missing {sorted(missing)}")
        missing_files = REQUIRED_SDIST_FILES - suffixes
        if missing_files:
            fail(f"source distribution is missing {sorted(missing_files)}")


def main(arguments: list[str]) -> int:
    directory = Path(arguments[1] if len(arguments) > 1 else "dist")
    wheels = sorted(directory.glob("*.whl"))
    sdists = sorted(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        fail(f"expected one wheel and one sdist in {directory}")
    verify_wheel(wheels[0])
    verify_sdist(sdists[0])
    print(f"verified {wheels[0].name} and {sdists[0].name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
