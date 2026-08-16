#!/usr/bin/env python3
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "update_catalog.py"
WORKBOOK = Path("/Users/macbookair/Downloads/Productos_2026-8-15.xlsx")


class CatalogUpdateTest(unittest.TestCase):
    def test_preview_does_not_modify_catalog_and_preserves_overrides(self):
        self.assertTrue(WORKBOOK.exists())
        original = (ROOT / "products.csv").read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            baseline = temp / "baseline.csv"
            baseline.write_bytes(
                subprocess.check_output(["git", "show", "HEAD^:products.csv"], cwd=ROOT)
            )
            report = temp / "report.json"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(WORKBOOK),
                    "--baseline",
                    str(baseline),
                    "--overrides",
                    str(ROOT / "inventory_overrides.json"),
                    "--report",
                    str(report),
                ],
                cwd=ROOT,
                check=True,
            )
            data = json.loads(report.read_text())
            self.assertEqual(data["status"], "preview")
            self.assertEqual(len(data["manual_overrides"]), 2)
            self.assertEqual(data["summary"]["sold_units_excluding_services"], "106")
            self.assertEqual(data["summary"]["estimated_sales_dop_excluding_services"], "2295")
            self.assertEqual((ROOT / "products.csv").read_bytes(), original)

    def test_apply_and_duplicate_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            baseline = temp / "baseline.csv"
            baseline.write_bytes((ROOT / "products.csv").read_bytes())
            output, report, state = temp / "products.csv", temp / "report.json", temp / "state.json"
            command = [
                sys.executable,
                str(SCRIPT),
                "--input",
                str(WORKBOOK),
                "--baseline",
                str(baseline),
                "--output",
                str(output),
                "--overrides",
                str(ROOT / "inventory_overrides.json"),
                "--report",
                str(report),
                "--state",
                str(state),
                "--apply",
            ]
            subprocess.run(command, cwd=ROOT, check=True)
            duplicate = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(duplicate.stdout)["status"], "duplicate")
            with output.open(encoding="utf-8-sig", newline="") as handle:
                rows = {row["sku"]: row for row in csv.DictReader(handle)}
            self.assertEqual(rows["SOBREM"]["stock"], "0")
            self.assertEqual(rows["HANI-1039-180GSM"]["stock"], "0")


if __name__ == "__main__":
    unittest.main()
