from __future__ import annotations

import json
import unittest

from samsarix_guard import RedactionReport
from samsarix_guard.reporting import ScanRecord, json_scan_report, sarif_scan_report


class ReportingTests(unittest.TestCase):
    def test_batch_json_report_is_deterministic_and_value_free(self) -> None:
        records = (
            ScanRecord("logs/one.log", "text", RedactionReport({"email": 2})),
            ScanRecord("events/two.json", "json", RedactionReport({"sensitive_key": 1})),
            ScanRecord("events/clean.json", "json", RedactionReport({})),
        )

        report = json_scan_report(records, single_input=False)

        self.assertEqual(report["counts"], {"email": 2, "sensitive_key": 1})
        self.assertEqual(report["detections"], 3)
        self.assertEqual(report["files_scanned"], 3)
        self.assertEqual(report["files_with_findings"], 2)
        self.assertEqual([result["path"] for result in report["results"]], [record.path for record in records])

    def test_sarif_is_21_with_stable_rules_and_no_payload_values(self) -> None:
        records = (ScanRecord("logs/app.log", "text", RedactionReport({"email": 1, "secret": 2})),)

        report = sarif_scan_report(records, semantic_version="0.3.0")
        encoded = json.dumps(report)
        run = report["runs"][0]

        self.assertEqual(report["version"], "2.1.0")
        self.assertEqual(run["tool"]["driver"]["semanticVersion"], "0.3.0")
        self.assertEqual([rule["id"] for rule in run["tool"]["driver"]["rules"]], ["email", "secret"])
        self.assertEqual([result["ruleId"] for result in run["results"]], ["email", "secret"])
        self.assertIn("logs/app.log", encoded)
        self.assertNotIn("person@example.com", encoded)
        self.assertNotIn("hunter42", encoded)

    def test_empty_batch_produces_valid_empty_sarif(self) -> None:
        report = sarif_scan_report((), semantic_version="0.3.0")

        self.assertEqual(report["runs"][0]["results"], [])
        self.assertEqual(report["runs"][0]["tool"]["driver"]["rules"], [])


if __name__ == "__main__":
    unittest.main()
