from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReleaseVerificationTests(unittest.TestCase):
    def run_verifier(self, tag: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "scripts/verify_release.py", tag],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_current_release_tag_is_consistent(self) -> None:
        completed = self.run_verifier("v0.3.0")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "verified release tag v0.3.0")

    def test_mismatched_release_tag_fails_closed(self) -> None:
        completed = self.run_verifier("v9.9.9")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("does not match project version", completed.stderr)


if __name__ == "__main__":
    unittest.main()
