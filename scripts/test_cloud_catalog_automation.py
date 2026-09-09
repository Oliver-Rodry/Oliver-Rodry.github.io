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
                command = args[0]
                self.assertEqual(Path(command[command.index("--baseline") + 1]).read_bytes(), b"original baseline")
                report.write_text(json.dumps({"workbook": "temporary.xlsx"}))

            def git_output(command, **kwargs):
                return "original-commit" if command[1] == "rev-parse" else b"original baseline"

            with patch.object(automation, "STATE", state), patch.object(automation, "REPORT", report), patch.object(automation, "access_token", return_value="test"), patch.object(automation, "newest_workbook", return_value=(b"workbook", "September9.xlsx", "new")) as newest, patch.object(automation, "message_workbook", return_value=(b"workbook", "September9.xlsx", "new")), patch.object(automation.subprocess, "check_output", side_effect=git_output) as git, patch.object(automation.subprocess, "run", side_effect=make_report) as run, patch.object(automation, "output") as output:
                automation.prepare()
                data = json.loads(report.read_text())
                self.assertEqual(data["previous_workbook"], "August25.xlsx")
                self.assertEqual(data["previous_update_at"], "2026-08-25T22:27:48Z")
                self.assertEqual(data["workbook"], "September9.xlsx")
                # A new runner has no local report and HEAD may contain the updated CSV.
                # The pending state must recover the original baseline and original email.
                report.unlink()
                automation.prepare()
                self.assertEqual(run.call_count, 2)
                self.assertEqual(newest.call_count, 1)
                self.assertEqual(json.loads(report.read_text()), data)
                git.assert_called_with(["git", "show", "original-commit:products.csv"], cwd=automation.ROOT)
                saved = json.loads(state.read_text())
                saved["report_pending"] = False
                state.write_text(json.dumps(saved))
                automation.prepare()
                self.assertEqual(run.call_count, 2)
                output.assert_called_with("duplicate", "true")
                self.assertEqual(json.loads(report.read_text()), data)

    def test_send_failure_remains_pending_and_sent_lookup_prevents_duplicate(self):
        with tempfile.TemporaryDirectory() as folder:
            state, report = Path(folder) / "state.json", Path(folder) / "report.json"
            state.write_text(json.dumps({"gmail_message_id": "inventory-id", "report_pending": True}))
            report.write_text(json.dumps({"gmail_message_id": "inventory-id"}))
            with patch.object(automation, "STATE", state), patch.object(automation, "REPORT", report), patch.object(automation, "access_token", return_value="test"), patch.object(automation, "report_body", return_value="Report"), patch.object(automation, "request_json") as request:
                request.side_effect = [{}, TimeoutError("Response lost")]
                with self.assertRaises(TimeoutError):
                    automation.send()
                self.assertTrue(json.loads(state.read_text())["report_pending"])
                raw = request.call_args.kwargs["body"]["raw"]
                decoded = automation.base64.urlsafe_b64decode(raw + "===").decode()
                self.assertIn("<catalog-inventory-inventory-id@papeleriasolnaciente.com>", decoded)
                request.reset_mock()
                request.side_effect = [{"messages": [{"id": "sent-id"}]}]
                automation.send()
                self.assertEqual(request.call_count, 1)
                self.assertFalse(json.loads(state.read_text())["report_pending"])
                self.assertIn("rfc822msgid", request.call_args.args[0])

    def test_successful_send_records_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            state, report = Path(folder) / "state.json", Path(folder) / "report.json"
            state.write_text(json.dumps({"gmail_message_id": "inventory-id", "report_pending": True}))
            report.write_text(json.dumps({"gmail_message_id": "inventory-id"}))
            with patch.object(automation, "STATE", state), patch.object(automation, "REPORT", report), patch.object(automation, "access_token", return_value="test"), patch.object(automation, "report_body", return_value="Report"), patch.object(automation, "request_json", side_effect=[{}, {"id": "sent-id"}]) as request:
                automation.send()
                self.assertEqual(request.call_count, 2)
                self.assertFalse(json.loads(state.read_text())["report_pending"])

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
