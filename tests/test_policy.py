from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from samsarix_guard import POLICY_VERSION, Policy, PolicyError
from samsarix_guard.policy import MAX_POLICY_BYTES


class PolicyTests(unittest.TestCase):
    def test_round_trip_policy_and_apply_controls(self) -> None:
        source = {
            "version": POLICY_VERSION,
            "profile": "secrets-only",
            "sensitive_keys": ["customer reference"],
            "disabled_categories": ["jwt"],
            "replacement": "<SAFE:{category}>",
            "limits": {"max_bytes": 2048, "max_depth": 8, "max_nodes": 100},
        }

        policy = Policy.from_json(json.dumps(source))
        result = policy.create_redactor().redact_data(
            {
                "customer reference": "C-123",
                "email": "person@example.com",
                "note": "password=hunter42",
            }
        )

        self.assertEqual(policy.to_mapping(), source)
        self.assertEqual(result.data["customer reference"], "<SAFE:sensitive_key>")
        self.assertEqual(result.data["email"], "person@example.com")
        self.assertEqual(result.data["note"], "password=<SAFE:secret>")

    def test_privacy_profile_ignores_secret_detectors(self) -> None:
        result = (
            Policy.for_profile("privacy-only").create_redactor().redact_text("person@example.com password=hunter42")
        )

        self.assertNotIn("person@example.com", result.text)
        self.assertIn("hunter42", result.text)
        self.assertEqual(result.report.counts, {"email": 1})

    def test_schema_is_strict_and_duplicate_safe(self) -> None:
        invalid_policies = (
            '{"version":1,"version":1}',
            '{"version":1,"unknown":true}',
            '{"version":2}',
            '{"version":1,"disabled_categories":["imaginary"]}',
            '{"version":1,"replacement":"unsafe"}',
            '{"version":1,"limits":{"max_nodes":0}}',
            '{"version":1,"limits":{"extra":2}}',
        )

        for policy in invalid_policies:
            with self.subTest(policy=policy), self.assertRaises(PolicyError):
                Policy.from_json(policy)

    def test_policy_file_is_utf8_and_size_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            oversized = Path(directory) / "oversized.json"
            oversized.write_bytes(b" " * (MAX_POLICY_BYTES + 1))
            invalid_utf8 = Path(directory) / "invalid.json"
            invalid_utf8.write_bytes(b"\xff")

            with self.assertRaisesRegex(PolicyError, "exceeds"):
                Policy.load(oversized)
            with self.assertRaisesRegex(PolicyError, "UTF-8"):
                Policy.load(invalid_utf8)


if __name__ == "__main__":
    unittest.main()
