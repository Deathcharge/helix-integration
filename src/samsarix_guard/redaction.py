"""Deterministic, dependency-free redaction for text and JSON-compatible data.

The detector intentionally favors explainable patterns over probabilistic name or
address recognition. It is a safety layer, not a compliance determination or a
guarantee that every sensitive value will be found.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from re import Pattern
from typing import Any, Final


class RedactionLimitError(ValueError):
    """Raised when structured input exceeds configured traversal limits."""


@dataclass(frozen=True, slots=True)
class Finding:
    """The location and category of a finding, without retaining its value."""

    category: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class RedactionReport:
    """Non-sensitive counts describing a redaction operation."""

    counts: dict[str, int]

    @property
    def detection_count(self) -> int:
        return sum(self.counts.values())

    @property
    def changed(self) -> bool:
        return self.detection_count > 0


@dataclass(frozen=True, slots=True)
class TextRedactionResult:
    """Redacted text, its non-sensitive report, and value-free finding spans."""

    text: str
    report: RedactionReport
    findings: tuple[Finding, ...]


@dataclass(frozen=True, slots=True)
class DataRedactionResult:
    """A redacted JSON-compatible value and its non-sensitive report."""

    data: Any
    report: RedactionReport


@dataclass(frozen=True, slots=True)
class _PatternRule:
    category: str
    pattern: Pattern[str]
    value_group: str | None = None
    validator: Any = None
    needles: tuple[str, ...] = ()
    requires_digit: bool = False


_FLAGS: Final = re.IGNORECASE
_RULES: Final[tuple[_PatternRule, ...]] = (
    _PatternRule(
        "bearer_token",
        re.compile(r"\bBearer[ \t]+(?P<value>[A-Za-z0-9._~+/=-]{8,})", _FLAGS),
        "value",
        needles=("bearer",),
    ),
    _PatternRule(
        "auth_credential",
        re.compile(
            r"\bAuthorization[ \t]*:[ \t]*(?P<value>(?:Basic|Token|ApiKey)[ \t]+[^\s,;]{6,512})",
            _FLAGS,
        ),
        "value",
        needles=("authorization",),
    ),
    _PatternRule(
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b"),
        needles=("eyj",),
    ),
    _PatternRule(
        "github_token",
        re.compile(r"\b(?:gh[oprsu]_[A-Za-z0-9]{20,255}|github_pat_[A-Za-z0-9_]{20,255})\b"),
        needles=("gh",),
    ),
    _PatternRule(
        "aws_access_key",
        re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
        needles=("akia", "asia"),
    ),
    _PatternRule(
        "ai_api_key",
        re.compile(r"\bsk-(?:proj-|svcacct-|ant-api03-)[A-Za-z0-9_-]{20,255}\b"),
        needles=("sk-proj-", "sk-svcacct-", "sk-ant-api03-"),
    ),
    _PatternRule(
        "slack_token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,255}\b"),
        needles=("xox",),
    ),
    _PatternRule(
        "stripe_key",
        re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,255}\b"),
        needles=("sk_live_", "sk_test_", "rk_live_", "rk_test_"),
    ),
    _PatternRule(
        "gitlab_token",
        re.compile(r"\bglpat-[A-Za-z0-9_-]{20,255}\b"),
        needles=("glpat-",),
    ),
    _PatternRule(
        "google_api_key",
        re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
        needles=("aiza",),
    ),
    _PatternRule(
        "npm_token",
        re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"),
        needles=("npm_",),
    ),
    _PatternRule(
        "pypi_token",
        re.compile(r"\bpypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{20,255}\b"),
        needles=("pypi-",),
    ),
    _PatternRule(
        "sendgrid_key",
        re.compile(r"\bSG\.[A-Za-z0-9_-]{16,64}\.[A-Za-z0-9_-]{16,128}\b"),
        needles=("sg.",),
    ),
    _PatternRule(
        "huggingface_token",
        re.compile(r"\bhf_[A-Za-z0-9]{20,255}\b"),
        needles=("hf_",),
    ),
    _PatternRule(
        "private_key",
        re.compile(
            r"-----BEGIN[ \t]+(?P<kind>(?:RSA[ \t]+|EC[ \t]+|OPENSSH[ \t]+)?PRIVATE[ \t]+KEY)-----"
            r"[\s\S]{0,16384}?-----END[ \t]+(?P=kind)-----"
        ),
        needles=("-----begin",),
    ),
    _PatternRule(
        "secret",
        re.compile(
            r"\b(?:api[\s_-]?key|client[\s_-]?secret|secret|password|passwd|pwd|access[\s_-]?token|"
            r"refresh[\s_-]?token|private[\s_-]?key|database[\s_-]?url|connection[\s_-]?string|dsn|cookie)"
            r"[ \t]*[:=][ \t]*(?P<quote>['\"]?)(?P<value>[^\s'\";,}]{6,512})(?P=quote)",
            _FLAGS,
        ),
        "value",
        needles=(
            "api_key",
            "api-key",
            "api key",
            "secret",
            "password",
            "passwd",
            "pwd",
            "token",
            "private_key",
            "private-key",
            "private key",
            "database_url",
            "database-url",
            "database url",
            "connection_string",
            "connection-string",
            "connection string",
            "dsn",
            "cookie",
        ),
    ),
    _PatternRule(
        "url_secret",
        re.compile(
            r"(?:[?&](?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|secret|password|auth)=)"
            r"(?P<value>[^&#\s]{4,512})",
            _FLAGS,
        ),
        "value",
        needles=("?", "&"),
    ),
    _PatternRule(
        "email",
        re.compile(r"(?<![\w.+-])[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+(?![\w.-])", _FLAGS),
        needles=("@",),
    ),
    _PatternRule(
        "ssn",
        re.compile(r"(?<!\d)(?!000|666|9\d\d)\d{3}[- ](?!00)\d{2}[- ](?!0000)\d{4}(?!\d)"),
        requires_digit=True,
    ),
    _PatternRule(
        "phone",
        re.compile(r"(?<!\w)(?:\+\d{1,3}[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]\d{3}[ .-]\d{4}(?!\w)"),
        requires_digit=True,
    ),
    _PatternRule(
        "credit_card",
        re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"),
        validator=lambda value: _passes_luhn(value),
        requires_digit=True,
    ),
    _PatternRule(
        "ipv4",
        re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])"),
        validator=lambda value: _valid_ipv4(value),
        needles=(".",),
        requires_digit=True,
    ),
)

_SENSITIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "client_secret",
        "connection_string",
        "cookie",
        "database_url",
        "db_url",
        "dsn",
        "pass",
        "passwd",
        "password",
        "private_key",
        "refresh_token",
        "secret",
        "session_id",
        "session_token",
        "set_cookie",
        "token",
        "access_token",
    }
)
_SENSITIVE_KEY_SUFFIXES: Final[tuple[str, ...]] = (
    "_api_key",
    "_client_secret",
    "_password",
    "_private_key",
    "_refresh_token",
    "_secret",
    "_session_token",
    "_access_token",
)
SUPPORTED_CATEGORIES: Final[frozenset[str]] = frozenset(
    {rule.category for rule in _RULES} | {"sensitive_key"}
)


def _passes_luhn(value: str) -> bool:
    digits = [int(character) for character in value if character.isdigit()]
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def _valid_ipv4(value: str) -> bool:
    parts = value.split(".")
    return len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)


def _normalize_key(key: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")
    return normalized


def _is_sensitive_key(key: str, extra_keys: frozenset[str]) -> bool:
    normalized = _normalize_key(key)
    return (
        normalized in _SENSITIVE_KEYS
        or normalized in extra_keys
        or normalized.endswith(_SENSITIVE_KEY_SUFFIXES)
    )


def _merge_overlaps(findings: list[Finding]) -> tuple[Finding, ...]:
    if not findings:
        return ()
    ordered = sorted(findings, key=lambda finding: (finding.start, -(finding.end - finding.start), finding.category))
    merged: list[Finding] = []
    for finding in ordered:
        if not merged or finding.start >= merged[-1].end:
            merged.append(finding)
            continue
        previous = merged[-1]
        previous_length = previous.end - previous.start
        finding_length = finding.end - finding.start
        category = previous.category if previous_length >= finding_length else finding.category
        merged[-1] = Finding(category, previous.start, max(previous.end, finding.end))
    return tuple(merged)


class Redactor:
    """Detect and redact sensitive values without network calls or value logging."""

    def __init__(
        self,
        *,
        replacement_template: str = "[REDACTED:{category}]",
        extra_sensitive_keys: Sequence[str] = (),
        disabled_categories: Sequence[str] = (),
        max_text_chars: int = 1_048_576,
        max_depth: int = 64,
        max_nodes: int = 100_000,
    ) -> None:
        if "{category}" not in replacement_template:
            raise ValueError("replacement_template must contain '{category}'")
        if max_depth < 1:
            raise ValueError("max_depth must be at least 1")
        if max_nodes < 1:
            raise ValueError("max_nodes must be at least 1")
        if max_text_chars < 1:
            raise ValueError("max_text_chars must be at least 1")
        disabled = frozenset(disabled_categories)
        unknown_categories = disabled - SUPPORTED_CATEGORIES
        if unknown_categories:
            raise ValueError(f"unknown disabled categories: {sorted(unknown_categories)}")
        self.replacement_template = replacement_template
        replacement_prefix, replacement_suffix = replacement_template.split("{category}", maxsplit=1)
        self._replacement_pattern = re.compile(
            rf"{re.escape(replacement_prefix)}[a-z][a-z0-9_]*{re.escape(replacement_suffix)}"
        )
        self.extra_sensitive_keys = frozenset(_normalize_key(key) for key in extra_sensitive_keys)
        self.disabled_categories = disabled
        self.max_text_chars = max_text_chars
        self.max_depth = max_depth
        self.max_nodes = max_nodes

    def scan_text(self, text: str) -> tuple[Finding, ...]:
        """Return non-value-bearing finding spans for a string."""
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if len(text) > self.max_text_chars:
            raise RedactionLimitError(f"text input exceeds max_text_chars={self.max_text_chars}")
        findings: list[Finding] = []
        folded = text.casefold()
        has_digit = re.search(r"[0-9]", text) is not None
        for rule in _RULES:
            if rule.category in self.disabled_categories:
                continue
            if rule.needles and not any(needle in folded for needle in rule.needles):
                continue
            if rule.requires_digit and not has_digit:
                continue
            for match in rule.pattern.finditer(text):
                start, end = match.span(rule.value_group) if rule.value_group else match.span()
                candidate = text[start:end]
                if self._replacement_pattern.fullmatch(candidate):
                    continue
                if rule.validator is not None and not rule.validator(candidate):
                    continue
                findings.append(Finding(rule.category, start, end))
        return _merge_overlaps(findings)

    def redact_text(self, text: str) -> TextRedactionResult:
        """Replace detected values in text and return a count-only report."""
        findings = self.scan_text(text)
        if not findings:
            return TextRedactionResult(text, RedactionReport({}), ())
        chunks: list[str] = []
        cursor = 0
        counts: Counter[str] = Counter()
        for finding in findings:
            chunks.append(text[cursor : finding.start])
            chunks.append(self.replacement_template.format(category=finding.category))
            cursor = finding.end
            counts[finding.category] += 1
        chunks.append(text[cursor:])
        return TextRedactionResult("".join(chunks), RedactionReport(dict(sorted(counts.items()))), findings)

    def redact_data(self, data: Any) -> DataRedactionResult:
        """Copy and redact JSON-compatible data without mutating the caller's value."""
        counts: Counter[str] = Counter()
        nodes_seen = 0

        def count_node() -> None:
            nonlocal nodes_seen
            nodes_seen += 1
            if nodes_seen > self.max_nodes:
                raise RedactionLimitError(f"structured input exceeds max_nodes={self.max_nodes}")

        def walk(value: Any, depth: int) -> Any:
            count_node()
            if depth > self.max_depth:
                raise RedactionLimitError(f"structured input exceeds max_depth={self.max_depth}")

            if isinstance(value, str):
                result = self.redact_text(value)
                counts.update(result.report.counts)
                return result.text
            if isinstance(value, float):
                if not math.isfinite(value):
                    raise TypeError("structured data cannot contain non-finite floats")
                return value
            if value is None or isinstance(value, (bool, int)):
                return value
            if isinstance(value, Mapping):
                output: dict[str, Any] = {}
                for key, child in value.items():
                    if not isinstance(key, str):
                        raise TypeError("structured data keys must be strings")
                    if (
                        "sensitive_key" not in self.disabled_categories
                        and _is_sensitive_key(key, self.extra_sensitive_keys)
                        and child is not None
                    ):
                        # Sensitive values are deliberately not traversed, but they still
                        # consume work and must count toward the documented node bound.
                        count_node()
                        if isinstance(child, str) and self._replacement_pattern.fullmatch(child):
                            output[key] = child
                        else:
                            output[key] = self.replacement_template.format(category="sensitive_key")
                            counts["sensitive_key"] += 1
                    else:
                        output[key] = walk(child, depth + 1)
                return output
            if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, memoryview)):
                return [walk(child, depth + 1) for child in value]
            raise TypeError(f"unsupported structured value type: {type(value).__name__}")

        redacted = walk(data, 0)
        return DataRedactionResult(redacted, RedactionReport(dict(sorted(counts.items()))))
