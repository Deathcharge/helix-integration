"""Verify that built artifacts contain only the supported package surface."""

from __future__ import annotations

import sys
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path

REQUIRED_MODULES = {
    "helix_integration/__init__.py",
    "helix_integration/__main__.py",
    "helix_integration/cli.py",
    "helix_integration/redaction.py",
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
            fail("wheel contains legacy Helix Unified code")
        unexpected_code = {
            name
            for name in names
            if name.endswith(".py") and not name.startswith("helix_integration/")
        }
        if unexpected_code:
            fail(f"wheel contains unexpected Python modules: {sorted(unexpected_code)}")

        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            fail("wheel must contain exactly one METADATA file")
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
        runtime_requirements = [
            requirement
            for requirement in metadata.get_all("Requires-Dist", [])
            if 'extra == "dev"' not in requirement and "extra == 'dev'" not in requirement
        ]
        if runtime_requirements:
            fail(f"wheel has runtime dependencies: {runtime_requirements}")


def verify_sdist(path: Path) -> None:
    with tarfile.open(path, "r:gz") as archive:
        names = set(archive.getnames())
        if any("/legacy/" in name.casefold() or "/helix_unified_snapshot/" in name.casefold() for name in names):
            fail("source distribution contains the unsupported legacy snapshot")
        suffixes = {name.split("/", 1)[-1] for name in names}
        missing = {f"src/{module}" for module in REQUIRED_MODULES} - suffixes
        if missing:
            fail(f"source distribution is missing {sorted(missing)}")


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
