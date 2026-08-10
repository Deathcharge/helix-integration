"""Offline redaction for integration payloads and application logs."""

from .logging import RedactingFormatter
from .policy import POLICY_VERSION, PROFILE_NAMES, Policy, PolicyError
from .redaction import (
    SUPPORTED_CATEGORIES,
    DataRedactionResult,
    Finding,
    RedactionLimitError,
    RedactionReport,
    Redactor,
    TextRedactionResult,
)

__all__ = [
    "POLICY_VERSION",
    "PROFILE_NAMES",
    "SUPPORTED_CATEGORIES",
    "DataRedactionResult",
    "Finding",
    "Policy",
    "PolicyError",
    "RedactingFormatter",
    "RedactionLimitError",
    "RedactionReport",
    "Redactor",
    "TextRedactionResult",
]

__version__ = "0.3.0"
