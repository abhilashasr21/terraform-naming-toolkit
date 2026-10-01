# Offline Terraform Naming Toolkit

This toolkit separates customer naming policy from Terraform implementation. It
does not contact cloud APIs, registries, or external services during name
generation and repository inventory.

## Package layout

- `module/`: Provider-independent Terraform naming module.
- `policies/example/`: Synthetic example policy showing the expected schema.
- `examples/batch/`: Batch generation example driven by JSON requests.
- `namingctl.py`: Single-file, standard-library CLI for offline planning and
  safe literal-name updates.
- `scripts/Scan-TerraformResources.ps1`: Read-only local Terraform inventory and
  policy-coverage report.
- `IMPLEMENTATION-SUMMARY.md`: Detailed implementation and customer handoff
  record.
- `GUIDE.md`: Complete guide to every file, with expected inputs and outputs.

## Policy lifecycle

Each resource rule has one of these states:

- `approved`: Enforced by default.
- `draft`: Generates a name and an advisory diagnostic.
- `conflict`: Generates a name and identifies a policy conflict.
- `missing`: Records that no usable policy exists.
- `legacy`: Documents an accepted legacy form without making it the default.

Only `approved` rules fail Terraform validation by default. This prevents an
unfinished customer workbook from becoming an accidental deployment gate.

## Use in a restricted environment

Copy the entire folder into the customer repository. No module registry source
is used.

Generate names in a Terraform configuration:

```hcl
locals {
  naming_policy = jsondecode(file("${path.root}/naming/policy.json"))
}

module "storage_name" {
  source = "./naming/module"

  policy        = local.naming_policy
  resource_type = "storage_account"
  values = {
    workload    = "payments"
    region      = "eastus"
    environment = "production"
    index       = "01"
  }
}

resource "azurerm_storage_account" "example" {
  name = module.storage_name.name
  # Existing resource arguments remain here.
}
```

Inventory a customer repository without modifying it:

```powershell
.\scripts\Scan-TerraformResources.ps1 `
  -RepoPath C:\customer\terraform `
  -PolicyPath .\policies\example\policy.json `
  -OutputPath .\terraform-resource-inventory.json
```

The scanner is intentionally advisory. It inventories local `resource`, `data`,
and `module` blocks but cannot see resources hidden inside modules that are not
present on disk.

Run the included local checks:

```powershell
terraform -chdir=module init -backend=false
terraform -chdir=module test
terraform -chdir=examples\batch init -backend=false
terraform -chdir=examples\batch plan -input=false
```

## Onboard another customer

1. Copy `policies/example/policy.json` to a new customer/version folder.
2. Replace code sets, rule components, patterns, limits, status, and Terraform
   resource-type mappings with approved customer values.
3. Keep unresolved rows as `draft`, `conflict`, or `missing`.
4. Run the scanner against the customer's local repository.
5. Add module calls only for covered resources.
6. Review `terraform plan` for replacements before applying naming changes.

Existing cloud resource names may be immutable or force replacement. This module
does not rename resources by itself; it only returns deterministic names.

## Standalone naming CLI

`namingctl.py` requires Python 3.10 or later and has no third-party dependencies,
network calls, or provider initialization. Copy it, the approved policy JSON,
and a request manifest into the restricted environment.

The request manifest explicitly maps Terraform addresses to a policy rule and
component values; the tool never guesses missing values:

```json
{
  "azurerm_resource_group.demo": {
    "rule": "resource_group",
    "values": {
      "workload": "payments",
      "environment": "production",
      "region": "eastus",
      "index": "01"
    }
  }
}
```

```powershell
python .\namingctl.py list --policy .\naming-policy.json
python .\namingctl.py explain resource_group --policy .\naming-policy.json
python .\namingctl.py generate resource_group --policy .\naming-policy.json --values '{"workload":"payments","environment":"production","region":"eastus","index":"01"}'
python .\namingctl.py plan C:\customer\terraform --policy .\naming-policy.json --requests .\requests.json
python .\namingctl.py check C:\customer\terraform --policy .\naming-policy.json --requests .\requests.json
python .\namingctl.py apply C:\customer\terraform --policy .\naming-policy.json --requests .\requests.json --out C:\customer\terraform-named
```

`plan` writes `NAMING-CHANGELOG.md` and never changes Terraform files. `check`
returns a non-zero status when a resource needs an approved name change or has a
blocking issue. `apply` only edits a unique, top-level literal `name = "..."` in
a resource matched by exact address and an `approved` policy rule. It creates a
timestamped `.naming-backup` before in-place edits; `--out` leaves the source
tree untouched. Draft/conflict/legacy rules are advisory unless
`--include-advisory` is explicitly provided. Missing policy, computed names,
ambiguous syntax, and unsupported cases are never rewritten.
Output copies contain only `.tf`, `.tf.json`, `.terraform.lock.hcl`, and
`*.tfvars.example` files. Other files (including variable files that might
contain secrets, state, saved plans, and auxiliary assets) are deliberately
omitted; copy any required non-secret assets yourself after review. Blocked
in-place applies only print the report and do not modify the source tree.

The editor supports `.tf` files and intentionally does not rewrite `.tf.json`.
It is not a complete HCL parser; use its plan/changelog as a review artifact and
inspect the Terraform plan before applying infrastructure changes.
