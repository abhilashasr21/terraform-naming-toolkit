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
BUILDER = ROOT / "catalogs" / "build_caf_catalog.py"
CATALOG = ROOT / "catalogs" / "azure-caf.json"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


maker = _load("make_sample_workbook", MAKER)
xlsx2policy = _load("xlsx2policy", CONVERTER)


class CatalogTests(unittest.TestCase):
    def test_catalog_file_exists_and_loads(self):
        self.assertTrue(CATALOG.is_file(), "catalogs/azure-caf.json must be generated")
        caf = xlsx2policy.load_caf_catalog(CATALOG)
        self.assertIsNotNone(caf)
        self.assertGreater(len(caf.resources), 100)

    def test_catalog_matches_generator_output(self):
        """The committed catalog must match build_caf_catalog.py output."""
        builder = _load("build_caf_catalog", BUILDER)
        regenerated = builder.build()
        committed = json.loads(CATALOG.read_text(encoding="utf-8"))
        self.assertEqual(regenerated["resources"], committed["resources"])

    def test_known_abbreviations(self):
        caf = xlsx2policy.load_caf_catalog(CATALOG)
        self.assertEqual(caf.match("firewall", "Firewall")["abbreviation"], "afw")
        self.assertEqual(caf.match("storage_account", "Storage account")["abbreviation"], "st")
        self.assertEqual(caf.match("key_vault", "Key vault")["abbreviation"], "kv")
        self.assertEqual(caf.match("bastion", "Azure Bastion")["abbreviation"], "bas")

    def test_plural_tolerance(self):
        caf = xlsx2policy.load_caf_catalog(CATALOG)
        # 'Public IP addresses' -> public IP address entry.
        entry = caf.match("public_ip_addresses", "Public IP addresses")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["abbreviation"], "pip")


class CafOnlyTests(unittest.TestCase):
    def setUp(self):
        self.caf = xlsx2policy.load_caf_catalog(CATALOG)
        self.policy, self.rows, _ = xlsx2policy.build_caf_policy(self.caf)
        self.tmp = Path(tempfile.mkdtemp())

    def test_every_rule_has_abbreviation_literal(self):
        for key, rule in self.policy["rules"].items():
            first = rule["components"][0]
            self.assertEqual(first["key"], "resource")
            self.assertIn("literal", first, f"{key} missing abbreviation literal")

    def test_caf_component_order(self):
        rule = self.policy["rules"]["firewall"]
        keys = [c["key"] for c in rule["components"]]
        self.assertEqual(keys, ["resource", "workload", "environment", "region", "index"])

    def test_environment_code_set_present(self):
        self.assertIn("environment", self.policy["code_sets"])
        self.assertEqual(self.policy["code_sets"]["environment"]["prod"], "prod")

    def test_end_to_end_name_generation(self):
        policy_path = self.tmp / "caf.json"
        policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        out = subprocess.run(
            [sys.executable, str(NAMINGCTL), "generate", "firewall",
             "--policy", str(policy_path),
             "--values", json.dumps({"workload": "hub", "environment": "prod",
                                     "region": "cnc", "index": "01"})],
            capture_output=True, text=True,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "afw-hub-prod-cnc-01")

    def test_metadata_cites_caf(self):
        self.assertIn("caf_baseline", self.policy["metadata"])
        self.assertIn("learn.microsoft.com", self.policy["metadata"]["caf_baseline"]["source_url"])


class CafFallbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.workbook = self.tmp / "sample-naming.xlsx"
        maker.build(self.workbook)
        self.caf = xlsx2policy.load_caf_catalog(CATALOG)

    def test_fallback_does_not_change_existing_abbreviations(self):
        """Customer abbreviations in the workbook must always win over CAF."""
        wb = xlsx2policy.Workbook(self.workbook)
        policy, _, _ = xlsx2policy.build_policy(wb, self.workbook, self.caf)
        # The sample firewall pattern begins with its own 'afw' literal.
        fw = policy["rules"]["azure_firewall"]
        self.assertEqual(fw["components"][0]["literal"], "afw")

    def test_fallback_fills_missing_terraform_types(self):
        wb = xlsx2policy.Workbook(self.workbook)
        policy, rows, _ = xlsx2policy.build_policy(wb, self.workbook, self.caf)
        # Every rule should end up with a Terraform mapping once CAF fills gaps.
        for key, rule in policy["rules"].items():
            self.assertTrue(rule["terraform_resource_types"], f"{key} has no TF type")

    def test_fallback_flag_recorded_in_metadata(self):
        wb = xlsx2policy.Workbook(self.workbook)
        policy, rows, _ = xlsx2policy.build_policy(wb, self.workbook, self.caf)
        if any(r.get("caf_fallback") for r in rows):
            self.assertIn("caf_fallback", policy["metadata"])

    def test_without_fallback_behaviour_unchanged(self):
        """Omitting the catalog leaves the baseline converter behaviour intact."""
        wb = xlsx2policy.Workbook(self.workbook)
        policy, _, _ = xlsx2policy.build_policy(wb, self.workbook, None)
        self.assertNotIn("caf_fallback", policy["metadata"])


if __name__ == "__main__":
    unittest.main()
