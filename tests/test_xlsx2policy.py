import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONVERTER = ROOT / "xlsx2policy.py"
NAMINGCTL = ROOT / "namingctl.py"
MAKER = ROOT / "examples" / "excel" / "make_sample_workbook.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


maker = _load("make_sample_workbook", MAKER)
xlsx2policy = _load("xlsx2policy", CONVERTER)


class ConverterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.workbook = self.tmp / "sample-naming.xlsx"
        maker.build(self.workbook)

    def convert(self):
        wb = xlsx2policy.Workbook(self.workbook)
        policy, report_rows, warnings = xlsx2policy.build_policy(wb, self.workbook)
        return policy, report_rows, warnings

    def test_workbook_is_readable(self):
        wb = xlsx2policy.Workbook(self.workbook)
        self.assertIn("Region_Codes", wb.sheets)
        self.assertIn("Comprehensive_Resource_Analysis", wb.sheets)

    def test_region_code_set_extracted(self):
        policy, _, _ = self.convert()
        self.assertEqual(policy["code_sets"]["region"]["east us"], "eus")
        self.assertEqual(policy["code_sets"]["region"]["use"], "eus")

    def test_business_service_section_bounded(self):
        policy, _, _ = self.convert()
        biz = policy["code_sets"]["business_service"]
        self.assertEqual(biz, {"plt": "plt", "platform": "plt", "app": "app", "application": "app"})
        self.assertNotIn("test", biz)

    def test_rules_and_status(self):
        policy, _, _ = self.convert()
        rules = policy["rules"]
        self.assertEqual(rules["resource_group"]["status"], "approved")
        self.assertEqual(rules["virtual_network"]["status"], "draft")
        self.assertEqual(rules["resource_group"]["max_length"], 90)

    def test_storage_constraints_and_separator(self):
        policy, _, _ = self.convert()
        storage = policy["rules"]["storage_account"]
        self.assertEqual(storage["separator"], "")
        self.assertEqual(storage["min_length"], 3)
        self.assertEqual(storage["max_length"], 24)
        self.assertEqual(storage["uniqueness_scope"], "global")

    def test_metadata_hash_present(self):
        policy, _, _ = self.convert()
        self.assertEqual(len(policy["metadata"]["source_sha256"]), 64)

    def test_end_to_end_engine_consumes_policy(self):
        policy_path = self.tmp / "policy.json"
        subprocess.run(
            [sys.executable, str(CONVERTER), str(self.workbook), "--out", str(policy_path)],
            check=True, capture_output=True, text=True,
        )
        result = subprocess.run(
            [sys.executable, str(NAMINGCTL), "generate", "resource_group",
             "--policy", str(policy_path),
             "--values", json.dumps({
                 "business_service": "plt", "region": "East US",
                 "environment": "production", "index": "01"})],
            check=True, capture_output=True, text=True,
        )
        self.assertEqual(result.stdout.strip(), "rg-plt-eus-prd-01")

    def test_check_detects_up_to_date_and_stale(self):
        policy_path = self.tmp / "policy.json"
        subprocess.run(
            [sys.executable, str(CONVERTER), str(self.workbook), "--out", str(policy_path)],
            check=True, capture_output=True, text=True,
        )
        ok = subprocess.run(
            [sys.executable, str(CONVERTER), str(self.workbook), "--out", str(policy_path), "--check"],
            capture_output=True, text=True,
        )
        self.assertEqual(ok.returncode, 0, ok.stderr)

        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        policy["metadata"]["source_sha256"] = "0" * 64
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
        stale = subprocess.run(
            [sys.executable, str(CONVERTER), str(self.workbook), "--out", str(policy_path), "--check"],
            capture_output=True, text=True,
        )
        self.assertEqual(stale.returncode, 1, stale.stdout)


if __name__ == "__main__":
    unittest.main()
