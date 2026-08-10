"""Fail-closed redaction for Python logging handlers."""

from __future__ import annotations

import logging

from .policy import Policy
from .redaction import RedactionLimitError, Redactor


class RedactingFormatter(logging.Formatter):
    """Wrap a formatter and redact its complete rendered record before output."""

    def __init__(
        self,
        formatter: logging.Formatter | None = None,
        *,
        policy: Policy | None = None,
        redactor: Redactor | None = None,
        fail_closed: bool = True,
        limit_replacement: str = "[REDACTED:log_record_limit]",
    ) -> None:
        super().__init__()
        if policy is not None and redactor is not None:
            raise ValueError("provide policy or redactor, not both")
        if not limit_replacement or len(limit_replacement) > 256 or not limit_replacement.isprintable():
            raise ValueError("limit_replacement must be 1-256 printable characters")
        self.formatter = formatter or logging.Formatter()
        self.redactor = redactor or (policy or Policy()).create_redactor()
        self.fail_closed = fail_closed
        self.limit_replacement = limit_replacement

    def format(self, record: logging.LogRecord) -> str:
        rendered = self.formatter.format(record)
        try:
            return self.redactor.redact_text(rendered).text
        except RedactionLimitError:
            if self.fail_closed:
                return self.limit_replacement
            raise
