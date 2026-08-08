"""Strict, dependency-free policy files for repeatable redaction behavior."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from .redaction import SUPPORTED_CATEGORIES, Redactor

POLICY_VERSION: Final = 1
MAX_POLICY_BYTES: Final = 65_536
PROFILE_NAMES: Final[tuple[str, ...]] = ("balanced", "privacy-only", "secrets-only")
_PRIVACY_CATEGORIES: Final[frozenset[str]] = frozenset({"credit_card", "email", "ipv4", "phone", "ssn"})
_SECRET_CATEGORIES: Final[frozenset[str]] = SUPPORTED_CATEGORIES - _PRIVACY_CATEGORIES
_PROFILE_DISABLED: Final[dict[str, frozenset[str]]] = {
    "balanced": frozenset(),
    "privacy-only": _SECRET_CATEGORIES,
    "secrets-only": _PRIVACY_CATEGORIES,
}


class PolicyError(ValueError):
    """Raised when a policy file is malformed, unsafe, or unsupported."""


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise PolicyError(f"duplicate policy key: {key}")
        output[key] = value
    return output


def _reject_json_constant(value: str) -> None:
    raise PolicyError(f"invalid constant: {value}")


def _expect_string_list(value: Any, field: str, *, limit: int) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise PolicyError(f"{field} must be an array of strings")
    if len(value) > limit:
        raise PolicyError(f"{field} cannot contain more than {limit} entries")
    if any(not item or len(item) > 128 or not item.isprintable() for item in value):
        raise PolicyError(f"{field} entries must be 1-128 printable characters")
    if len(set(value)) != len(value):
        raise PolicyError(f"{field} cannot contain duplicates")
    return tuple(value)


def _bounded_integer(value: Any, field: str, *, maximum: int) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise PolicyError(f"{field} must be an integer from 1 through {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class Policy:
    """Validated controls for detector scope, replacements, and resource limits."""

    profile: str = "balanced"
    sensitive_keys: tuple[str, ...] = ()
    disabled_categories: frozenset[str] = frozenset()
    replacement_template: str = "[REDACTED:{category}]"
    max_bytes: int = 1_048_576
    max_depth: int = 64
    max_nodes: int = 100_000

    @classmethod
    def for_profile(cls, profile: str) -> Policy:
        if profile not in _PROFILE_DISABLED:
            raise PolicyError(f"unknown profile {profile!r}; choose from {', '.join(PROFILE_NAMES)}")
        return cls(profile=profile, disabled_categories=_PROFILE_DISABLED[profile])

    @classmethod
    def from_mapping(cls, data: Any) -> Policy:
        if not isinstance(data, dict):
            raise PolicyError("policy root must be a JSON object")
        allowed = {"version", "profile", "sensitive_keys", "disabled_categories", "replacement", "limits"}
        unknown = set(data) - allowed
        if unknown:
            raise PolicyError(f"unknown policy fields: {sorted(unknown)}")
        if data.get("version") != POLICY_VERSION:
            raise PolicyError(f"policy version must be {POLICY_VERSION}")

        profile = data.get("profile", "balanced")
        if not isinstance(profile, str):
            raise PolicyError("profile must be a string")
        base = cls.for_profile(profile)
        sensitive_keys = _expect_string_list(data.get("sensitive_keys", []), "sensitive_keys", limit=256)
        disabled = _expect_string_list(data.get("disabled_categories", []), "disabled_categories", limit=64)
        unknown_categories = set(disabled) - SUPPORTED_CATEGORIES
        if unknown_categories:
            raise PolicyError(f"unknown disabled categories: {sorted(unknown_categories)}")

        replacement = data.get("replacement", "[REDACTED:{category}]")
        if not isinstance(replacement, str):
            raise PolicyError("replacement must be a string")
        if replacement.count("{category}") != 1:
            raise PolicyError("replacement must contain '{category}' exactly once")
        if not 1 <= len(replacement) <= 256 or not replacement.isprintable():
            raise PolicyError("replacement must be 1-256 printable characters")

        limits = data.get("limits", {})
        if not isinstance(limits, dict):
            raise PolicyError("limits must be a JSON object")
        unknown_limits = set(limits) - {"max_bytes", "max_depth", "max_nodes"}
        if unknown_limits:
            raise PolicyError(f"unknown limit fields: {sorted(unknown_limits)}")

        return cls(
            profile=profile,
            sensitive_keys=sensitive_keys,
            disabled_categories=base.disabled_categories | frozenset(disabled),
            replacement_template=replacement,
            max_bytes=_bounded_integer(limits.get("max_bytes", 1_048_576), "max_bytes", maximum=104_857_600),
            max_depth=_bounded_integer(limits.get("max_depth", 64), "max_depth", maximum=256),
            max_nodes=_bounded_integer(limits.get("max_nodes", 100_000), "max_nodes", maximum=10_000_000),
        )

    @classmethod
    def from_json(cls, text: str) -> Policy:
        try:
            data = json.loads(
                text,
                object_pairs_hook=_object_without_duplicates,
                parse_constant=_reject_json_constant,
            )
        except json.JSONDecodeError as error:
            raise PolicyError(
                f"invalid policy JSON at line {error.lineno}, column {error.colno}: {error.msg}"
            ) from error
        return cls.from_mapping(data)

    @classmethod
    def load(cls, path: str | Path) -> Policy:
        policy_path = Path(path).expanduser()
        try:
            with policy_path.open("rb") as policy_file:
                payload = policy_file.read(MAX_POLICY_BYTES + 1)
        except OSError as error:
            raise PolicyError(f"cannot read policy {policy_path}: {error.strerror or error}") from error
        if len(payload) > MAX_POLICY_BYTES:
            raise PolicyError(f"policy exceeds {MAX_POLICY_BYTES} bytes")
        try:
            return cls.from_json(payload.decode("utf-8-sig"))
        except UnicodeDecodeError as error:
            raise PolicyError("policy is not valid UTF-8") from error

    def to_mapping(self) -> dict[str, Any]:
        return {
            "version": POLICY_VERSION,
            "profile": self.profile,
            "sensitive_keys": list(self.sensitive_keys),
            "disabled_categories": sorted(self.disabled_categories - _PROFILE_DISABLED[self.profile]),
            "replacement": self.replacement_template,
            "limits": {
                "max_bytes": self.max_bytes,
                "max_depth": self.max_depth,
                "max_nodes": self.max_nodes,
            },
        }

    def create_redactor(
        self,
        *,
        extra_sensitive_keys: tuple[str, ...] = (),
        disabled_categories: tuple[str, ...] = (),
        max_bytes: int | None = None,
        max_depth: int | None = None,
        max_nodes: int | None = None,
    ) -> Redactor:
        return Redactor(
            replacement_template=self.replacement_template,
            extra_sensitive_keys=(*self.sensitive_keys, *extra_sensitive_keys),
            disabled_categories=tuple(self.disabled_categories | frozenset(disabled_categories)),
            max_text_chars=max_bytes if max_bytes is not None else self.max_bytes,
            max_depth=max_depth if max_depth is not None else self.max_depth,
            max_nodes=max_nodes if max_nodes is not None else self.max_nodes,
        )
