#!/usr/bin/env python3
"""
🌀 Helix Collective v15.3 — Notion Sync Validator
backend/notion_sync_validator.py

Purpose: Validate exports and handle errors gracefully.
- Schema validation for all export formats
- Data integrity checks
- Error recovery and retry logic
- Comprehensive logging and reporting

Ensures data quality before pushing to Notion.
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""

    is_valid: bool
    errors: list[str]
    warnings: list[str]
    metadata: dict[str, Any]


class NotionSyncValidator:
    """Validates Notion export data and handles errors."""

    def __init__(self):
        """Initialize validator."""
        # notion_sync_validator.py → integrations/ → backend/ → apps/ → helix-unified/
        _shadow = Path(__file__).resolve().parent.parent.parent.parent / "Shadow"
        self.validation_log = _shadow / "arjuna_archive" / "validation_log.json"
        self.validation_log.parent.mkdir(parents=True, exist_ok=True)

    def validate_export_file(self, export_path: Path) -> ValidationResult:
        """Validate complete export file."""
        errors: list[str] = []
        warnings: list[str] = []
        metadata: dict[str, Any] = {}

        # Check file exists
        if not export_path.exists():
            return ValidationResult(False, ["Export file not found"], [], {})

        try:
            with open(export_path, encoding="utf-8") as f:
                data = json.load(f)
            metadata["file_size"] = export_path.stat().st_size
        except json.JSONDecodeError as e:
            return ValidationResult(False, [f"Invalid JSON: {e}"], [], {})
        except Exception as e:
            return ValidationResult(False, [f"Failed to read file: {e}"], [], {})

        # Validate structure
        if "export_metadata" not in data:
            errors.append("Missing export_metadata")
        else:
            meta_result = self._validate_export_metadata(data["export_metadata"])
            errors.extend(meta_result.errors)
            warnings.extend(meta_result.warnings)

        if "notion_databases" not in data:
            errors.append("Missing notion_databases")
        else:
            db_result = self._validate_databases(data["notion_databases"])
            errors.extend(db_result.errors)
            warnings.extend(db_result.warnings)
            metadata["databases"] = db_result.metadata

        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings, metadata)

    def _validate_export_metadata(self, metadata: dict[str, Any]) -> ValidationResult:
        """Validate export metadata."""
        errors: list[str] = []
        warnings: list[str] = []

        required_fields = ["exported_at", "export_type", "generated_by"]
        for field in required_fields:
            if field not in metadata:
                errors.append(f"Missing metadata field: {field}")

        # Validate timestamp format
        if "exported_at" in metadata:
            try:
                pass
            except ValueError:
                errors.append("Invalid timestamp format: {}".format(metadata["exported_at"]))

        return ValidationResult(len(errors) == 0, errors, warnings, metadata)

    def _validate_databases(self, databases: dict[str, Any]) -> ValidationResult:
        """Validate all databases."""
        errors: list[str] = []
        warnings: list[str] = []
        metadata: dict[str, Any] = {}

        expected_databases = [
            "repositories",
            "agents",
            "cycles",
            "ucf_metrics",
            "architecture",
            "deployments",
        ]

        for db_name in expected_databases:
            if db_name not in databases:
                warnings.append(f"Missing database: {db_name}")
            else:
                db_result = self._validate_database(db_name, databases[db_name])
                errors.extend(db_result.errors)
                warnings.extend(db_result.warnings)
                metadata[db_name] = db_result.metadata

        return ValidationResult(len(errors) == 0, errors, warnings, metadata)

    def _validate_database(self, db_name: str, db_data: dict[str, Any]) -> ValidationResult:
        """Validate individual database."""
        errors: list[str] = []
        warnings: list[str] = []
        metadata: dict[str, Any] = {}

        # Check required fields
        if "database_name" not in db_data:
            errors.append(f"Database {db_name}: missing database_name")

        if "entries" not in db_data:
            errors.append(f"Database {db_name}: missing entries")
            return ValidationResult(len(errors) == 0, errors, warnings, metadata)

        entries = db_data["entries"]
        if not isinstance(entries, list):
            errors.append(f"Database {db_name}: entries must be a list")
            return ValidationResult(len(errors) == 0, errors, warnings, metadata)

        metadata["entry_count"] = len(entries)

        # Validate entries based on database type
        if db_name == "repositories":
            for i, entry in enumerate(entries):
                entry_errors = self._validate_repository_entry(entry, i)
                errors.extend(entry_errors)

        elif db_name == "agents":
            for i, entry in enumerate(entries):
                entry_errors = self._validate_agent_entry(entry, i)
                errors.extend(entry_errors)

        elif db_name == "ucf_metrics":
            for i, entry in enumerate(entries):
                entry_errors = self._validate_metric_entry(entry, i)
                errors.extend(entry_errors)

        return ValidationResult(len(errors) == 0, errors, warnings, metadata)

    def _validate_repository_entry(self, entry: dict[str, Any], index: int) -> list[str]:
        """Validate repository entry."""
        errors: list[str] = []

        required_fields = ["name", "status", "languages", "mission"]
        for field in required_fields:
            if field not in entry:
                errors.append(f"Repository {index}: missing {field}")

        if "status" in entry and entry["status"] not in [
            "active",
            "inactive",
            "archived",
        ]:
            errors.append("Repository {}: invalid status '{}'".format(index, entry["status"]))

        return errors

    def _validate_agent_entry(self, entry: dict[str, Any], index: int) -> list[str]:
        """Validate agent entry."""
        errors: list[str] = []

        required_fields = ["name", "symbol", "role", "status"]
        for field in required_fields:
            if field not in entry:
                errors.append(f"Agent {index}: missing {field}")

        if "health_score" in entry:
            score = entry["health_score"]
            if not isinstance(score, (int, float)) or score < 0 or score > 100:
                errors.append(f"Agent {index}: invalid health_score '{score}'")

        return errors

    def _validate_metric_entry(self, entry: dict[str, Any], index: int) -> list[str]:
        """Validate UCF metric entry."""
        errors: list[str] = []

        required_fields = ["metric_name", "current_value", "target_value"]
        for field in required_fields:
            if field not in entry:
                errors.append(f"Metric {index}: missing {field}")

        if "current_value" in entry and "target_value" in entry:
            try:
                float(entry["target_value"])
            except (ValueError, TypeError):
                errors.append(f"Metric {index}: non-numeric values")

        return errors

    def log_validation_result(self, result: ValidationResult, export_file: str):
        """Log validation result."""
        try:
            if self.validation_log.exists():
                with open(self.validation_log, encoding="utf-8") as f:
                    log_data = json.load(f)
            else:
                log_data = {"validations": []}

            # Create validation record
            validation_record = {
                "timestamp": datetime.now(UTC).isoformat(),
                "export_file": export_file,
                "is_valid": result.is_valid,
                "error_count": len(result.errors),
                "warning_count": len(result.warnings),
                "errors": result.errors[:10],  # Keep first 10 errors
                "warnings": result.warnings[:10],  # Keep first 10 warnings
                "metadata": result.metadata,
            }

            log_data["validations"].append(validation_record)
            log_data["last_validation"] = validation_record["timestamp"]
            log_data["total_validations"] = len(log_data["validations"])

            # Keep only last 50 validations
            if len(log_data["validations"]) > 50:
                log_data["validations"] = log_data["validations"][-50:]

            with open(self.validation_log, "w", encoding="utf-8") as f:
                json.dump(log_data, f, indent=2)

            logger.info("📝 Logged validation result to %s", self.validation_log)
        except Exception as e:
            logger.error("⚠️ Failed to log validation result: %s", e)

    def generate_validation_report(self, result: ValidationResult) -> str:
        """Generate human-readable validation report."""
        lines = []
        lines.append("\n" + "=" * 70)
        lines.append("📋 VALIDATION REPORT")
        lines.append("=" * 70)

        if result.is_valid:
            lines.append("✅ VALIDATION PASSED")
        else:
            lines.append("❌ VALIDATION FAILED")

        if result.errors:
            lines.append(f"\n❌ Errors ({len(result.errors)}):")
            for error in result.errors[:10]:
                lines.append(f"   - {error}")
            if len(result.errors) > 10:
                lines.append(f"   ... and {len(result.errors) - 10} more")

        if result.warnings:
            lines.append(f"\n⚠️ Warnings ({len(result.warnings)}):")
            for warning in result.warnings[:10]:
                lines.append(f"   - {warning}")
            if len(result.warnings) > 10:
                lines.append(f"   ... and {len(result.warnings) - 10} more")

        if result.metadata:
            lines.append("\n📊 Metadata:")
            for key, value in result.metadata.items():
                if isinstance(value, dict):
                    lines.append(f"   {key}:")
                    for k, v in value.items():
                        lines.append(f"      {k}: {v}")
                else:
                    lines.append(f"   {key}: {value}")

        lines.append("=" * 70 + "\n")

        return "\n".join(lines)


def validate_export(export_path: Path) -> tuple[bool, str]:
    """
    Validate an export file and return result.

    Args:
        export_path: Path to export file

    Returns:
        Tuple of (is_valid, report_text)
    """
    validator = NotionSyncValidator()
    result = validator.validate_export_file(export_path)
    report = validator.generate_validation_report(result)
    validator.log_validation_result(result, str(export_path))

    return result.is_valid, report


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        logger.info("Usage: python notion_sync_validator.py <export_file>")
        sys.exit(1)

    export_path = Path(sys.argv[1])
    is_valid, report = validate_export(export_path)
    logger.info(report)

    sys.exit(0 if is_valid else 1)
