import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import cloud_catalog_automation as automation
import verify_catalog


class CloudCatalogTest(unittest.TestCase):
    def test_prepare_preserves_comparison_dates_and_duplicate_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            state, report = root / "state.json", root / "report.json"
            state.write_text(json.dumps({"gmail_message_id": "old", "workbook_filename": "August25.xlsx", "processed_at": "2026-08-25T22:27:48Z"}))

            def make_report(*args, **kwargs):
                report.write_text(json.dumps({"workbook": "temporary.xlsx"}))

            with patch.object(automation, "STATE", state), patch.object(automation, "REPORT", report), patch.object(automation, "access_token", return_value="test"), patch.object(automation, "newest_workbook", return_value=(b"workbook", "September9.xlsx", "new")), patch.object(automation.subprocess, "run", side_effect=make_report) as run, patch.object(automation, "output") as output:
                automation.prepare()
                data = json.loads(report.read_text())
                self.assertEqual(data["previous_workbook"], "August25.xlsx")
                self.assertEqual(data["previous_update_at"], "2026-08-25T22:27:48Z")
                self.assertEqual(data["workbook"], "September9.xlsx")
                baseline_args = run.call_args.args[0]
                self.assertEqual(baseline_args[baseline_args.index("--baseline") + 1], str(automation.ROOT / "products.csv"))
                automation.prepare()
                self.assertEqual(run.call_count, 1)
                output.assert_called_with("duplicate", "true")
                self.assertEqual(json.loads(report.read_text()), data)

    def test_report_labels_period_and_product_changes(self):
        report = {
            "summary": {"sold_units_including_services": "2", "estimated_sales_dop_including_services": "100"},
            "previous_workbook": "August25.xlsx", "workbook": "September9.xlsx",
            "sold": [], "newly_out_of_stock": [], "price_changes": [], "restocked": [],
            "new_products": [{"sku": "new", "name": "New product"}],
            "removed_products": [{"sku": "old", "name": "Removed product"}],
        }
        body = automation.report_body(report)
        for value in ("August25.xlsx", "September9.xlsx", "New product", "Removed product", "no corresponde únicamente a ventas de hoy"):
            self.assertIn(value, body)

    def test_publication_rejects_stale_catalog_and_accepts_exact_content(self):
        response = MagicMock()
        response.__enter__.return_value = response
        with patch.object(verify_catalog.urllib.request, "urlopen", return_value=response):
            response.read.return_value = b"old"
            with self.assertRaises(RuntimeError):
                verify_catalog.wait_for_catalog(b"new", timeout=0)
            response.read.return_value = b"new"
            verify_catalog.wait_for_catalog(b"new", timeout=0)


if __name__ == "__main__":
    unittest.main()
