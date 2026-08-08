"""Value-free JSON and SARIF reports for one or more scanned payloads."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from typing import Any, Final

from .redaction import RedactionReport

SARIF_VERSION: Final = "2.1.0"
SARIF_SCHEMA: Final = "https://json.schemastore.org/sarif-2.1.0.json"


@dataclass(frozen=True, slots=True)
class ScanRecord:
    """A value-free result for one input payload."""

    path: str
    format_name: str
    report: RedactionReport


def json_scan_report(records: tuple[ScanRecord, ...], *, single_input: bool) -> dict[str, Any]:
    """Create the stable count-only JSON report shape."""
    counts: Counter[str] = Counter()
    for record in records:
        counts.update(record.report.counts)
    sorted_counts = dict(sorted(counts.items()))
    detections = sum(sorted_counts.values())

    if single_input and len(records) == 1:
        return {
            "changed": detections > 0,
            "counts": sorted_counts,
            "detections": detections,
            "format": records[0].format_name,
        }

    return {
        "changed": detections > 0,
        "counts": sorted_counts,
        "detections": detections,
        "files_scanned": len(records),
        "files_with_findings": sum(record.report.changed for record in records),
        "results": [
            {
                "counts": record.report.counts,
                "detections": record.report.detection_count,
                "format": record.format_name,
                "path": record.path,
            }
            for record in records
        ],
    }


def sarif_scan_report(records: tuple[ScanRecord, ...], *, semantic_version: str) -> dict[str, Any]:
    """Create a GitHub-compatible SARIF 2.1.0 report without payload values."""
    categories = sorted({category for record in records for category in record.report.counts})
    rule_indexes = {category: index for index, category in enumerate(categories)}
    results: list[dict[str, Any]] = []

    for record in records:
        for category, count in sorted(record.report.counts.items()):
            locator = f"{record.path}:{record.format_name}:{category}"
            fingerprint = hashlib.sha256(locator.encode("utf-8")).hexdigest()
            results.append(
                {
                    "level": "warning",
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": record.path.replace("\\", "/")},
                                "region": {"startColumn": 1, "startLine": 1},
                            }
                        }
                    ],
                    "message": {
                        "text": (
                            f"Detected {count} {category.replace('_', ' ')} finding(s) in a "
                            f"{record.format_name} integration payload. Payload values are omitted."
                        )
                    },
                    "partialFingerprints": {"primaryLocationLineHash": fingerprint},
                    "ruleId": category,
                    "ruleIndex": rule_indexes[category],
                }
            )

    return {
        "$schema": SARIF_SCHEMA,
        "runs": [
            {
                "results": results,
                "tool": {
                    "driver": {
                        "informationUri": "https://github.com/Deathcharge/samsarix-integration-guard",
                        "name": "Samsarix Integration Guard",
                        "rules": [
                            {
                                "fullDescription": {
                                    "text": (
                                        f"Samsarix Integration Guard detected {category.replace('_', ' ')} "
                                        "without retaining or reporting the matched value."
                                    )
                                },
                                "helpUri": (
                                    "https://github.com/Deathcharge/samsarix-integration-guard#what-it-detects"
                                ),
                                "id": category,
                                "name": category,
                                "shortDescription": {
                                    "text": f"Sensitive payload category: {category.replace('_', ' ')}"
                                },
                            }
                            for category in categories
                        ],
                        "semanticVersion": semantic_version,
                    }
                },
            }
        ],
        "version": SARIF_VERSION,
    }
