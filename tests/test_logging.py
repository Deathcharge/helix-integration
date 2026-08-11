from __future__ import annotations

import io
import logging
import unittest

from samsarix_guard import Policy, RedactingFormatter, Redactor


class RedactingFormatterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.logger = logging.getLogger(f"samsarix-guard-test-{id(self)}")
        self.logger.handlers = [self.handler]
        self.logger.propagate = False
        self.logger.setLevel(logging.INFO)

    def tearDown(self) -> None:
        self.logger.handlers = []
        self.handler.close()

    def test_redacts_fully_rendered_message_arguments(self) -> None:
        self.handler.setFormatter(RedactingFormatter(logging.Formatter("%(levelname)s %(message)s")))

        self.logger.info("contact=%s password=%s", "person@example.com", "hunter42")
        output = self.stream.getvalue()

        self.assertIn("INFO", output)
        self.assertIn("[REDACTED:email]", output)
        self.assertIn("[REDACTED:secret]", output)
        self.assertNotIn("person@example.com", output)
        self.assertNotIn("hunter42", output)

    def test_redacts_exception_text(self) -> None:
        self.handler.setFormatter(RedactingFormatter(logging.Formatter("%(message)s\n%(exc_text)s")))

        try:
            raise ValueError("failed for person@example.com")
        except ValueError:
            self.logger.exception("request password=hunter42")
        output = self.stream.getvalue()

        self.assertNotIn("person@example.com", output)
        self.assertNotIn("hunter42", output)
        self.assertIn("[REDACTED:email]", output)
        self.assertIn("[REDACTED:secret]", output)

    def test_policy_profile_controls_logging_detector_scope(self) -> None:
        self.handler.setFormatter(RedactingFormatter(policy=Policy.for_profile("privacy-only")))

        self.logger.info("person@example.com password=hunter42")
        output = self.stream.getvalue()

        self.assertIn("[REDACTED:email]", output)
        self.assertIn("hunter42", output)

    def test_oversized_record_fails_closed_without_partial_content(self) -> None:
        self.handler.setFormatter(RedactingFormatter(redactor=Redactor(max_text_chars=8)))

        self.logger.info("person@example.com")

        self.assertEqual(self.stream.getvalue().strip(), "[REDACTED:log_record_limit]")

    def test_limit_can_raise_for_error_aware_handlers(self) -> None:
        formatter = RedactingFormatter(redactor=Redactor(max_text_chars=8), fail_closed=False)
        record = logging.LogRecord("samsarix-test", logging.INFO, __file__, 1, "person@example.com", (), None)

        with self.assertRaisesRegex(ValueError, "max_text_chars"):
            formatter.format(record)

    def test_invalid_configuration_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "policy or redactor"):
            RedactingFormatter(policy=Policy(), redactor=Redactor())
        with self.assertRaisesRegex(ValueError, "limit_replacement"):
            RedactingFormatter(limit_replacement="line\nbreak")


if __name__ == "__main__":
    unittest.main()
