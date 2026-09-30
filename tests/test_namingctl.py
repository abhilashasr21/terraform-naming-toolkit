import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import namingctl


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "namingctl.py"
POLICY = ROOT / "policies" / "example" / "policy.json"
REQUESTS = ROOT / "examples" / "cli" / "requests.json"


class NamingCliTests(unittest.TestCase):
    def run_cli(self, *arguments, expected=0):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, arguments)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, expected, result.stderr + result.stdout)
        return result

    def test_generate_maps_and_normalizes_components(self):
        result = self.run_cli(
            "generate",
            "resource_group",
            "--policy",
            POLICY,
            "--values",
            json.dumps(
                {
                    "workload": "Payments",
                    "environment": "Production",
                    "region": "eastus",
                    "index": "01",
                }
            ),
        )
        self.assertEqual(result.stdout.strip(), "rg-payments-prd-eus-01")

    def test_plan_ignores_heredoc_resource_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            shutil.copy(ROOT / "examples" / "cli" / "main.tf", repo / "main.tf")
            result = self.run_cli(
                "plan",
                repo,
                "--policy",
                POLICY,
                "--requests",
                REQUESTS,
            )
            self.assertIn("`azurerm_resource_group.demo`", result.stdout)
            self.assertNotIn("azurerm_resource_group.fake", result.stdout)
            self.assertTrue((repo / "NAMING-CHANGELOG.md").exists())

    def test_scan_prunes_junction_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            child = root / "linked-module"
            child.mkdir()
            (child / "main.tf").write_text(
                'resource "azurerm_resource_group" "outside" { name = "rg-outside" }\n',
                encoding="utf-8",
            )
            with patch.object(
                namingctl,
                "is_link_or_junction",
                side_effect=lambda path: Path(path) == child,
            ):
                self.assertEqual(namingctl.scan_terraform(root), [])

    def test_apply_refuses_stale_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_file = root / "main.tf"
            source_file.write_text(
                'resource "azurerm_resource_group" "demo" {\n'
                '  name = "rg-old-dev-eus-01"\n'
                '}\n',
                encoding="utf-8",
            )
            policy = namingctl.load_policy(POLICY)
            requests = namingctl.load_json(REQUESTS)
            plan = namingctl.build_plan(root, policy, requests, False)
            source_file.write_text(
                source_file.read_text(encoding="utf-8").replace(
                    "rg-old-dev-eus-01", "rg-new-dev-eus-01"
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(namingctl.NamingError, "changed since planning"):
                namingctl.apply_plan(root, plan, None, False)
            self.assertIn("rg-new-dev-eus-01", source_file.read_text(encoding="utf-8"))
            self.assertFalse((root / ".naming-backup").exists())

    def test_apply_refuses_resource_address_changed_after_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_file = root / "main.tf"
            source_file.write_text(
                'resource "azurerm_resource_group" "demo" {\n'
                '  name = "rg-old-dev-eus-01"\n'
                '}\n',
                encoding="utf-8",
            )
            plan = namingctl.build_plan(
                root,
                namingctl.load_policy(POLICY),
                namingctl.load_json(REQUESTS),
                False,
            )
            source_file.write_text(
                source_file.read_text(encoding="utf-8").replace('"demo"', '"else"'),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(namingctl.NamingError, "address changed since planning"):
                namingctl.apply_plan(root, plan, None, False)
            self.assertIn('"else"', source_file.read_text(encoding="utf-8"))
            self.assertFalse((root / ".naming-backup").exists())

    def test_apply_output_copy_keeps_source_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            output = base / "output"
            source.mkdir()
            shutil.copy(ROOT / "examples" / "cli" / "main.tf", source / "main.tf")
            original = (source / "main.tf").read_text(encoding="utf-8")

            result = self.run_cli(
                "apply",
                source,
                "--policy",
                POLICY,
                "--requests",
                REQUESTS,
                "--out",
                output,
            )

            self.assertEqual((source / "main.tf").read_text(encoding="utf-8"), original)
            self.assertIn('name     = "rg-payments-prd-eus-01"', (output / "main.tf").read_text(encoding="utf-8"))
            self.assertTrue((output / "NAMING-CHANGELOG.md").exists())
            self.assertNotIn(str(source), result.stdout)
            self.assertNotIn(str(output), result.stdout)

    def test_computed_name_is_never_rewritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            output = base / "output"
            source.mkdir()
            (source / "main.tf").write_text(
                'resource "azurerm_resource_group" "demo" {\n'
                '  name = var.generated_name\n'
                '  location = "eastus"\n'
                '}\n',
                encoding="utf-8",
            )
            request = base / "requests.json"
            request.write_text(REQUESTS.read_text(encoding="utf-8"), encoding="utf-8")
            self.run_cli(
                "apply",
                source,
                "--policy",
                POLICY,
                "--requests",
                request,
                "--out",
                output,
                expected=1,
            )
            self.assertIn("var.generated_name", (source / "main.tf").read_text(encoding="utf-8"))
            self.assertTrue((output / "NAMING-CHANGELOG.md").exists())

    def test_in_place_apply_creates_verbatim_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            source.mkdir()
            original_file = source / "main.tf"
            shutil.copy(ROOT / "examples" / "cli" / "main.tf", original_file)
            original = original_file.read_bytes()

            self.run_cli(
                "apply",
                source,
                "--policy",
                POLICY,
                "--requests",
                REQUESTS,
            )

            backups = list((source / ".naming-backup").glob("*/main.tf"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original)
            self.assertIn("rg-payments-prd-eus-01", original_file.read_text(encoding="utf-8"))

    def test_interpolated_quoted_name_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            output = base / "output"
            source.mkdir()
            (source / "main.tf").write_text(
                'resource "azurerm_resource_group" "demo" {\n'
                '  name = "${var.prefix}-custom"\n'
                '  location = "eastus"\n'
                '}\n',
                encoding="utf-8",
            )
            self.run_cli(
                "apply",
                source,
                "--policy",
                POLICY,
                "--requests",
                REQUESTS,
                "--out",
                output,
                expected=1,
            )
            self.assertIn('${var.prefix}-custom', (source / "main.tf").read_text(encoding="utf-8"))
            self.assertTrue((output / "NAMING-CHANGELOG.md").exists())

    def test_blocked_out_apply_does_not_write_to_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            output = base / "output"
            source.mkdir()
            (source / "main.tf").write_text(
                'resource "azurerm_resource_group" "demo" {\n'
                '  name = var.generated_name\n'
                '  location = "eastus"\n'
                '}\n',
                encoding="utf-8",
            )
            self.run_cli(
                "apply",
                source,
                "--policy",
                POLICY,
                "--requests",
                REQUESTS,
                "--out",
                output,
                expected=1,
            )
            self.assertFalse((source / "NAMING-CHANGELOG.md").exists())
            self.assertTrue((output / "NAMING-CHANGELOG.md").exists())

    def test_child_module_resource_is_not_selected(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            child = source / "modules" / "child"
            child.mkdir(parents=True)
            (child / "main.tf").write_text(
                'resource "azurerm_resource_group" "demo" {\n'
                '  name = "rg-child-dev-eus-01"\n'
                '}\n',
                encoding="utf-8",
            )
            report = self.run_cli(
                "plan",
                source,
                "--policy",
                POLICY,
                "--requests",
                REQUESTS,
                expected=1,
            )
            self.assertIn("Child-module resources are inventory-only", report.stdout)
            self.assertIn("rg-child-dev-eus-01", (child / "main.tf").read_text(encoding="utf-8"))

    def test_root_resource_wins_over_same_child_module_address(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            child = source / "modules" / "child"
            child.mkdir(parents=True)
            (source / "main.tf").write_text(
                'resource "azurerm_resource_group" "demo" {\n'
                '  name = "rg-root-dev-eus-01"\n'
                '}\n',
                encoding="utf-8",
            )
            (child / "main.tf").write_text(
                'resource "azurerm_resource_group" "demo" {\n'
                '  name = "rg-child-dev-eus-01"\n'
                '}\n',
                encoding="utf-8",
            )
            report = self.run_cli(
                "plan",
                source,
                "--policy",
                POLICY,
                "--requests",
                REQUESTS,
            )
            self.assertIn("`rg-root-dev-eus-01` -> `rg-payments-prd-eus-01`", report.stdout)
            self.assertNotIn("modules\\child\\main.tf", report.stdout)

    def test_missing_policy_rule_cannot_generate_name(self):
        result = self.run_cli(
            "generate",
            "managed_disk",
            "--policy",
            POLICY,
            "--values",
            "{}",
            expected=2,
        )
        self.assertIn("marked missing", result.stderr)

    def test_cli_errors_do_not_print_absolute_policy_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            missing_policy = Path(temporary) / "private-customer-policy.json"
            result = self.run_cli(
                "list",
                "--policy",
                missing_policy,
                expected=2,
            )
            self.assertNotIn(str(missing_policy), result.stderr)
            self.assertIn("private-customer-policy.json", result.stderr)

    def test_custom_report_cannot_overwrite_terraform_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_file = root / "main.tf"
            shutil.copy(ROOT / "examples" / "cli" / "main.tf", source_file)
            original = source_file.read_bytes()
            self.run_cli(
                "plan",
                root,
                "--policy",
                POLICY,
                "--requests",
                REQUESTS,
                "--report",
                source_file,
                expected=2,
            )
            self.assertEqual(source_file.read_bytes(), original)

    def test_report_cannot_overwrite_external_terraform_or_request_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_file = root / "main.tf"
            shutil.copy(ROOT / "examples" / "cli" / "main.tf", source_file)
            external_tf = ROOT / "examples" / "batch" / "main.tf"
            external_original = external_tf.read_bytes()
            self.run_cli(
                "plan",
                root,
                "--policy",
                POLICY,
                "--requests",
                REQUESTS,
                "--report",
                external_tf,
                expected=2,
            )
            self.assertEqual(external_tf.read_bytes(), external_original)

            request_original = REQUESTS.read_bytes()
            self.run_cli(
                "plan",
                root,
                "--policy",
                POLICY,
                "--requests",
                REQUESTS,
                "--report",
                REQUESTS,
                expected=2,
            )
            self.assertEqual(REQUESTS.read_bytes(), request_original)

    def test_report_cannot_overwrite_tfvars_or_lockfile(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_file = root / "main.tf"
            shutil.copy(ROOT / "examples" / "cli" / "main.tf", source_file)
            inputs = [
                root / "terraform.tfvars",
                root / ".terraform.lock.hcl",
            ]
            for path in inputs:
                path.write_text("customer-input", encoding="utf-8")
                original = path.read_bytes()
                self.run_cli(
                    "plan",
                    root,
                    "--policy",
                    POLICY,
                    "--requests",
                    REQUESTS,
                    "--report",
                    path,
                    expected=2,
                )
                self.assertEqual(path.read_bytes(), original)

    def test_invalid_policy_regex_is_reported_without_traceback(self):
        with tempfile.TemporaryDirectory() as temporary:
            policy = json.loads(POLICY.read_text(encoding="utf-8"))
            policy["rules"]["resource_group"]["pattern"] = "["
            policy_path = Path(temporary) / "invalid-policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            result = self.run_cli(
                "generate",
                "resource_group",
                "--policy",
                policy_path,
                "--values",
                "{}",
                expected=2,
            )
            self.assertIn("invalid regex pattern", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertNotIn(str(policy_path), result.stderr)

    def test_oversized_json_integer_is_reported_without_traceback(self):
        digits = "1" * 5000
        result = self.run_cli(
            "generate",
            "resource_group",
            "--policy",
            POLICY,
            "--values",
            '{"workload":' + digits + ',"environment":"production","region":"eastus","index":"01"}',
            expected=2,
        )
        self.assertIn("invalid input value", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_invalid_utf8_is_reported_without_traceback(self):
        with tempfile.TemporaryDirectory() as temporary:
            policy_path = Path(temporary) / "private-policy.json"
            policy_path.write_bytes(b"\xff\xfe")
            result = self.run_cli(
                "list",
                "--policy",
                policy_path,
                expected=2,
            )
            self.assertIn("invalid UTF-8", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertNotIn(str(policy_path), result.stderr)

    def test_pattern_error_does_not_echo_rejected_value(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = "private_customer_name"
            result = self.run_cli(
                "generate",
                "resource_group",
                "--policy",
                POLICY,
                "--values",
                json.dumps(
                    {
                        "workload": marker,
                        "environment": "production",
                        "region": "eastus",
                        "index": "01",
                    }
                ),
                expected=2,
            )
            self.assertIn("does not match the pattern", result.stderr)
            self.assertNotIn(marker, result.stderr)

    def test_plan_refuses_symlinked_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_file = root / "main.tf"
            source_file.write_text(
                'resource "azurerm_resource_group" "demo" {\n'
                '  name = "rg-old-dev-eus-01"\n'
                '}\n',
                encoding="utf-8",
            )
            report = root / "NAMING-CHANGELOG.md"
            try:
                report.symlink_to(source_file)
            except OSError as error:
                self.skipTest(f"Symlinks are unavailable: {error}")
            original = source_file.read_text(encoding="utf-8")
            self.run_cli(
                "plan",
                root,
                "--policy",
                POLICY,
                "--requests",
                REQUESTS,
                expected=2,
            )
            self.assertEqual(source_file.read_text(encoding="utf-8"), original)

    def test_write_guard_rejects_windows_junctions(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "report.md"
            with patch.object(Path, "is_junction", return_value=True, create=True):
                with self.assertRaisesRegex(namingctl.NamingError, "symbolic link"):
                    namingctl.ensure_safe_write_path(destination)

    def test_junction_detection_supports_python_310_and_311(self):
        with patch.object(namingctl.os, "name", "nt"):
            with patch.object(Path, "is_junction", return_value=False, create=True):
                with patch.object(
                    Path,
                    "lstat",
                    return_value=SimpleNamespace(st_file_attributes=0x410),
                ):
                    self.assertTrue(namingctl.is_link_or_junction(Path("junction")))

    def test_plan_refuses_hardlinked_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_file = root / "main.tf"
            source_file.write_text(
                'resource "azurerm_resource_group" "demo" {\n'
                '  name = "rg-old-dev-eus-01"\n'
                '}\n',
                encoding="utf-8",
            )
            report = root / "NAMING-CHANGELOG.md"
            try:
                os.link(source_file, report)
            except OSError as error:
                self.skipTest(f"Hard links are unavailable: {error}")
            original = source_file.read_bytes()
            self.run_cli(
                "plan",
                root,
                "--policy",
                POLICY,
                "--requests",
                REQUESTS,
                expected=2,
            )
            self.assertEqual(source_file.read_bytes(), original)

    def test_in_place_apply_refuses_hardlinked_terraform_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            source_file = root / "main.tf"
            shutil.copy(ROOT / "examples" / "cli" / "main.tf", source_file)
            linked_file = Path(temporary) / "linked-copy.tf"
            try:
                os.link(source_file, linked_file)
            except OSError as error:
                self.skipTest(f"Hard links are unavailable: {error}")
            original = source_file.read_bytes()
            result = self.run_cli(
                "apply",
                root,
                "--policy",
                POLICY,
                "--requests",
                REQUESTS,
                expected=2,
            )
            self.assertIn("hard-linked file", result.stderr)
            self.assertEqual(source_file.read_bytes(), original)
            self.assertEqual(linked_file.read_bytes(), original)

    def test_in_place_apply_refuses_symlinked_backup_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            external = base / "external"
            source.mkdir()
            external.mkdir()
            source_file = source / "main.tf"
            shutil.copy(ROOT / "examples" / "cli" / "main.tf", source_file)
            backup_link = source / ".naming-backup"
            try:
                backup_link.symlink_to(external, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"Directory symlinks are unavailable: {error}")
            original = source_file.read_text(encoding="utf-8")
            result = self.run_cli(
                "apply",
                source,
                "--policy",
                POLICY,
                "--requests",
                REQUESTS,
                expected=2,
            )
            self.assertIn("symbolic link", result.stderr)
            self.assertEqual(source_file.read_text(encoding="utf-8"), original)
            self.assertEqual(list(external.iterdir()), [])

    def test_output_copy_excludes_state_and_plan_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            output = base / "output"
            source.mkdir()
            shutil.copy(ROOT / "examples" / "cli" / "main.tf", source / "main.tf")
            (source / "terraform.tfstate").write_text("sensitive-state", encoding="utf-8")
            (source / "saved.tfstate.backup").write_text("sensitive-backup", encoding="utf-8")
            (source / "deployment.tfplan").write_text("saved-plan", encoding="utf-8")

            self.run_cli(
                "apply",
                source,
                "--policy",
                POLICY,
                "--requests",
                REQUESTS,
                "--out",
                output,
            )

            self.assertFalse((output / "terraform.tfstate").exists())
            self.assertFalse((output / "saved.tfstate.backup").exists())
            self.assertFalse((output / "deployment.tfplan").exists())
            self.assertFalse((output / "terraform.tfvars").exists())
            self.assertFalse((output / "plan.out").exists())


if __name__ == "__main__":
    unittest.main()
