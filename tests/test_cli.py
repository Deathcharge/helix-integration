from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
SOURCE = REPOSITORY / "src"


def run_cli(*arguments: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(SOURCE)
    return subprocess.run(
        [sys.executable, "-m", "samsarix_guard", *arguments],
        cwd=REPOSITORY,
        env=environment,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )


class CLITests(unittest.TestCase):
    def test_redact_json_from_stdin_keeps_payload_off_stderr(self) -> None:
        payload = '{"email":"person@example.com","password":"do-not-print","ok":true}'

        completed = run_cli("redact", "--format", "json", "--report", input_text=payload)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        report = json.loads(completed.stderr)
        self.assertEqual(output["email"], "[REDACTED:email]")
        self.assertEqual(output["password"], "[REDACTED:sensitive_key]")
        self.assertTrue(output["ok"])
        self.assertNotIn("do-not-print", completed.stderr)
        self.assertEqual(report["detections"], 2)

    def test_scan_is_a_ci_gate_and_never_echoes_sensitive_content(self) -> None:
        secret = "person@example.com"

        completed = run_cli("scan", "--format", "text", input_text=secret)

        self.assertEqual(completed.returncode, 1)
        report = json.loads(completed.stdout)
        self.assertEqual(report["counts"], {"email": 1})
        self.assertNotIn(secret, completed.stdout + completed.stderr)

    def test_clean_scan_exits_zero(self) -> None:
        completed = run_cli("scan", "--format", "text", input_text="ordinary build event")

        self.assertEqual(completed.returncode, 0)
        self.assertFalse(json.loads(completed.stdout)["changed"])

    def test_redact_jsonl_and_preserve_blank_records(self) -> None:
        payload = '{"token":"abc"}\n\n{"note":"person@example.com"}\n'

        completed = run_cli("redact", "--format", "jsonl", input_text=payload)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        lines = completed.stdout.splitlines()
        self.assertEqual(json.loads(lines[0])["token"], "[REDACTED:sensitive_key]")
        self.assertEqual(lines[1], "")
        self.assertEqual(json.loads(lines[2])["note"], "[REDACTED:email]")

    def test_invalid_json_fails_without_partial_payload_output(self) -> None:
        completed = run_cli("redact", "--format", "json", input_text='{"broken":')

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("invalid JSON", completed.stderr)

    def test_duplicate_keys_and_non_standard_numbers_are_rejected(self) -> None:
        duplicate = run_cli("redact", "--format", "json", input_text='{"value":1,"value":2}')
        not_a_number = run_cli("redact", "--format", "json", input_text='{"value":NaN}')

        self.assertEqual(duplicate.returncode, 2)
        self.assertIn("duplicate JSON object keys", duplicate.stderr)
        self.assertEqual(duplicate.stdout, "")
        self.assertEqual(not_a_number.returncode, 2)
        self.assertIn("non-standard JSON constant", not_a_number.stderr)
        self.assertEqual(not_a_number.stdout, "")

    def test_refuses_to_overwrite_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload.txt"
            path.write_text("person@example.com", encoding="utf-8")

            completed = run_cli("redact", str(path), "--output", str(path), "--format", "text")

            self.assertEqual(completed.returncode, 2)
            self.assertIn("refusing to overwrite", completed.stderr)
            self.assertEqual(path.read_text(encoding="utf-8"), "person@example.com")

    def test_writes_a_complete_separate_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "payload.json"
            output = Path(directory) / "safe.json"
            source.write_text('{"email":"person@example.com"}', encoding="utf-8")

            completed = run_cli("redact", str(source), "--output", str(output))

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["email"], "[REDACTED:email]")
            self.assertEqual(source.read_text(encoding="utf-8"), '{"email":"person@example.com"}')

    def test_size_limit_rejects_input(self) -> None:
        completed = run_cli("scan", "--max-bytes", "4", input_text="12345")

        self.assertEqual(completed.returncode, 2)
        self.assertIn("exceeds --max-bytes=4", completed.stderr)

    def test_policy_file_controls_profile_keys_and_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / "policy.json"
            policy.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "profile": "secrets-only",
                        "sensitive_keys": ["customer_reference"],
                        "replacement": "<REMOVED:{category}>",
                    }
                ),
                encoding="utf-8",
            )
            completed = run_cli(
                "redact",
                "--format",
                "json",
                "--policy",
                str(policy),
                input_text='{"email":"person@example.com","customer_reference":"C-123"}',
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output["email"], "person@example.com")
        self.assertEqual(output["customer_reference"], "<REMOVED:sensitive_key>")

    def test_policy_init_and_validate(self) -> None:
        initialized = run_cli("policy", "init", "--profile", "privacy-only")
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        template = json.loads(initialized.stdout)
        self.assertEqual(template["version"], 1)
        self.assertEqual(template["profile"], "privacy-only")

        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / "policy.json"
            policy.write_text(initialized.stdout, encoding="utf-8")
            validated = run_cli("policy", "validate", str(policy))

        self.assertEqual(validated.returncode, 0, validated.stderr)
        self.assertEqual(json.loads(validated.stdout), {"profile": "privacy-only", "valid": True, "version": 1})

    def test_invalid_policy_fails_without_reading_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            policy = Path(directory) / "policy.json"
            policy.write_text('{"version":2}', encoding="utf-8")
            completed = run_cli("scan", "--policy", str(policy), input_text="person@example.com")

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("policy version", completed.stderr)

    def test_version(self) -> None:
        completed = run_cli("--version")

        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout.strip(), "samsarix-guard 0.3.0")


if __name__ == "__main__":
    unittest.main()
