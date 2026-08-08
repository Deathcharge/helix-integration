from __future__ import annotations

import unittest

from samsarix_guard import RedactionLimitError, Redactor


class TextRedactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.redactor = Redactor()

    def test_redacts_common_pii_and_secrets_without_retaining_values(self) -> None:
        original = (
            "email=andrew@example.com password=hunter42 "
            "Authorization: Bearer abcdefghijklmnop phone 212-555-0199"
        )

        result = self.redactor.redact_text(original)

        self.assertNotIn("andrew@example.com", result.text)
        self.assertNotIn("hunter42", result.text)
        self.assertNotIn("abcdefghijklmnop", result.text)
        self.assertNotIn("212-555-0199", result.text)
        self.assertEqual(result.report.detection_count, 4)
        self.assertEqual(
            set(result.report.counts),
            {"bearer_token", "email", "phone", "secret"},
        )
        self.assertEqual(set(result.findings[0].__dataclass_fields__), {"category", "start", "end"})

    def test_redacts_only_luhn_valid_card_numbers(self) -> None:
        result = self.redactor.redact_text("valid 4111 1111 1111 1111 invalid 4111 1111 1111 1112")

        self.assertNotIn("4111 1111 1111 1111", result.text)
        self.assertIn("4111 1111 1111 1112", result.text)
        self.assertEqual(result.report.counts, {"credit_card": 1})

    def test_invalid_ipv4_and_benign_token_count_are_unchanged(self) -> None:
        original = "build token_count=123 at 999.999.1.2"

        result = self.redactor.redact_text(original)

        self.assertEqual(result.text, original)
        self.assertFalse(result.report.changed)

    def test_url_secret_redacts_value_but_preserves_url_shape(self) -> None:
        result = self.redactor.redact_text("https://example.test/hook?token=supersecretvalue&mode=test")

        self.assertIn("?token=[REDACTED:url_secret]&mode=test", result.text)
        self.assertEqual(result.report.counts, {"url_secret": 1})

    def test_text_redaction_is_idempotent(self) -> None:
        first = self.redactor.redact_text("password=hunter42 token=not-a-generic-token")

        second = self.redactor.redact_text(first.text)

        self.assertEqual(second.text, first.text)
        self.assertFalse(second.report.changed)

    def test_redacts_authentication_and_connection_assignments(self) -> None:
        original = (
            "Authorization: Basic dXNlcjpwYXNz "
            "DATABASE_URL=postgres://user:pass@example.test/db Cookie=session=abcdef"
        )

        result = self.redactor.redact_text(original)

        self.assertNotIn("dXNlcjpwYXNz", result.text)
        self.assertNotIn("postgres://user:pass@example.test/db", result.text)
        self.assertNotIn("session=abcdef", result.text)
        self.assertEqual(result.report.detection_count, 3)

    def test_redacts_current_provider_token_families(self) -> None:
        values = {
            "ai_api_key": "sk-proj-" + "A" * 32,
            "slack_token": "xoxb-123456789012-123456789012-" + "a" * 24,
            "stripe_key": "sk_live_" + "B" * 24,
            "gitlab_token": "glpat-" + "C" * 24,
            "google_api_key": "AIza" + "D" * 35,
            "npm_token": "npm_" + "E" * 36,
            "pypi_token": "pypi-AgEIcHlwaS5vcmc" + "F" * 24,
            "sendgrid_key": "SG." + "G" * 22 + "." + "H" * 43,
            "huggingface_token": "hf_" + "J" * 24,
        }

        result = self.redactor.redact_text("\n".join(values.values()))

        self.assertEqual(result.report.counts, {category: 1 for category in sorted(values)})
        for value in values.values():
            self.assertNotIn(value, result.text)

    def test_disabled_categories_are_not_scanned(self) -> None:
        result = Redactor(disabled_categories=["email"]).redact_text(
            "person@example.com password=hunter42"
        )

        self.assertIn("person@example.com", result.text)
        self.assertEqual(result.report.counts, {"secret": 1})

    def test_unknown_disabled_category_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown disabled"):
            Redactor(disabled_categories=["imaginary"])

    def test_private_key_block_is_removed_as_one_finding(self) -> None:
        private_key = "-----BEGIN PRIVATE KEY-----\nvery-sensitive-material\n-----END PRIVATE KEY-----"

        result = self.redactor.redact_text(f"prefix\n{private_key}\nsuffix")

        self.assertNotIn("very-sensitive-material", result.text)
        self.assertEqual(result.report.counts, {"private_key": 1})

    def test_custom_replacement_must_include_category(self) -> None:
        with self.assertRaisesRegex(ValueError, "category"):
            Redactor(replacement_template="[REMOVED]")

    def test_text_size_limit_fails_before_scanning(self) -> None:
        with self.assertRaises(RedactionLimitError):
            Redactor(max_text_chars=4).redact_text("12345")


class StructuredRedactionTests(unittest.TestCase):
    def test_redacts_sensitive_keys_and_nested_string_values_without_mutation(self) -> None:
        original = {
            "authorization": "Bearer original-token",
            "profile": {"email": "person@example.com", "token_count": 12},
            "items": ["from 192.0.2.1", 4, None],
        }

        result = Redactor().redact_data(original)

        self.assertEqual(result.data["authorization"], "[REDACTED:sensitive_key]")
        self.assertEqual(result.data["profile"]["email"], "[REDACTED:email]")
        self.assertEqual(result.data["profile"]["token_count"], 12)
        self.assertEqual(result.data["items"][0], "from [REDACTED:ipv4]")
        self.assertEqual(original["authorization"], "Bearer original-token")
        self.assertEqual(result.report.detection_count, 3)

    def test_extra_sensitive_key_is_normalized(self) -> None:
        result = Redactor(extra_sensitive_keys=["customer-reference"]).redact_data(
            {"Customer Reference": "C-123", "safe": "ok"}
        )

        self.assertEqual(result.data["Customer Reference"], "[REDACTED:sensitive_key]")

    def test_disabling_sensitive_keys_still_scans_string_values(self) -> None:
        result = Redactor(disabled_categories=["sensitive_key"]).redact_data(
            {"password": "person@example.com"}
        )

        self.assertEqual(result.data["password"], "[REDACTED:email]")
        self.assertEqual(result.report.counts, {"email": 1})

    def test_redaction_is_idempotent_and_scans_clean(self) -> None:
        redactor = Redactor()
        first = redactor.redact_data({"password": "secret-value", "email": "person@example.com"})

        second = redactor.redact_data(first.data)

        self.assertEqual(second.data, first.data)
        self.assertFalse(second.report.changed)

    def test_depth_and_node_limits_fail_closed(self) -> None:
        with self.assertRaises(RedactionLimitError):
            Redactor(max_depth=1).redact_data({"one": {"two": "value"}})
        with self.assertRaises(RedactionLimitError):
            Redactor(max_nodes=2).redact_data([1, 2])
        with self.assertRaises(RedactionLimitError):
            Redactor(max_nodes=2).redact_data({"password": "first", "authorization": "second"})

    def test_rejects_non_json_types(self) -> None:
        with self.assertRaisesRegex(TypeError, "unsupported"):
            Redactor().redact_data({"unsafe": object()})

    def test_rejects_non_finite_floats(self) -> None:
        with self.assertRaisesRegex(TypeError, "non-finite"):
            Redactor().redact_data({"unsafe": float("nan")})


if __name__ == "__main__":
    unittest.main()
