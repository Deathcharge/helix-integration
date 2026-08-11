from __future__ import annotations

import random
import string
import unittest

from samsarix_guard import Redactor


class RedactionInvariantTests(unittest.TestCase):
    def test_seeded_synthetic_inputs_are_idempotent_and_value_free(self) -> None:
        random_source = random.Random(20260808)
        redactor = Redactor()

        for index in range(100):
            local = "".join(random_source.choices(string.ascii_lowercase, k=12))
            alphabet = string.ascii_letters + string.digits
            password = "".join(random_source.choices(alphabet, k=24))
            email = f"{local}.{index}@example.test"
            original = f"request={index} contact={email} password={password}"

            first = redactor.redact_text(original)
            second = redactor.redact_text(first.text)

            with self.subTest(index=index):
                self.assertEqual(first.report.counts, {"email": 1, "secret": 1})
                self.assertEqual(second.text, first.text)
                self.assertFalse(second.report.changed)
                self.assertNotIn(email, first.text)
                self.assertNotIn(password, first.text)
                for finding in first.findings:
                    self.assertEqual(
                        set(finding.__dataclass_fields__),
                        {"category", "start", "end"},
                    )

    def test_replacement_labels_scan_clean_across_categories(self) -> None:
        redactor = Redactor()
        original = (
            "person@example.com 212-555-0199 123-45-6789 4111111111111111 "
            "192.0.2.1 password=hunter42 Bearer abcdefghijklmnop"
        )

        first = redactor.redact_text(original)

        self.assertTrue(first.report.changed)
        self.assertEqual(redactor.scan_text(first.text), ())


if __name__ == "__main__":
    unittest.main()
