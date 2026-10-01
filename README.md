# Offline Terraform Naming Toolkit

This toolkit separates customer naming policy from Terraform implementation. It
does not contact cloud APIs, registries, or external services during name
generation and repository inventory.

## Source of truth: the naming workbook

The customer's naming-convention **Excel workbook is the source of truth**.
`xlsx2policy.py` compiles that workbook into `policy.json`, the structured file
the engine reads. You edit the workbook; you regenerate the policy:

```powershell
python .\xlsx2policy.py C:\customer\NamingConvention.xlsx --out .\policy.json --report .\conversion-report.md
```

`policy.json` is therefore a **generated artifact**, not a hand-edited file. Run
`--check` in CI or before a plan to fail fast when the policy is stale versus the
workbook:

```powershell
python .\xlsx2policy.py C:\customer\NamingConvention.xlsx --out .\policy.json --check
```

The converter is offline and uses only the Python standard library (it reads the
`.xlsx` as a zip of XML - no openpyxl, pandas, or Office needed). It recognises
these sheets:

- `Region_Codes` -> `code_sets.region`
- `Code_Reference` -> `code_sets.environment` / `business_service` / `use`
- `Comprehensive_Resource_Analysis` (preferred) or `Resource_List` -> `rules`
- `MSFT_Constraint` -> per-rule length limits and uniqueness scope
- `Resource_List` -> rule status enrichment

Resources whose workbook status reads "Done (No Conflict)"/"Agreed" become
`approved`; unresolved rows ("In-Progress", "To Be Discussed", blank) become
`draft` and stay advisory. The converter also writes a Markdown report listing
every rule, its source pattern, Terraform mapping, and any ambiguities (such as
inconsistent separators) for customer review.

A runnable, customer-neutral example lives in `examples/excel/`:

```powershell
python .\examples\excel\make_sample_workbook.py .\examples\excel\sample-naming.xlsx
python .\xlsx2policy.py .\examples\excel\sample-naming.xlsx --out .\examples\excel\policy.json --report .\examples\excel\conversion-report.md
```

## Microsoft CAF fallback

When a customer has **not** defined their own abbreviation for a resource, the
converter can fall back to Microsoft's
[Cloud Adoption Framework (CAF)](https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-abbreviations)
recommendations. The customer workbook always wins; CAF only fills the gaps.

```powershell
# Fill missing abbreviations / Terraform mappings from CAF while converting:
python .\xlsx2policy.py C:\customer\NamingConvention.xlsx --out .\policy.json --report .\report.md --caf-fallback
```

Any rule that used a CAF value is flagged in the report's `CAF` column and noted
in `metadata.caf_fallback`, so the fallback is always auditable.

If a team has **no workbook at all**, generate a compliant Microsoft baseline
directly from the bundled catalog - usable by anyone:

```powershell
python .\xlsx2policy.py --caf-only --out .\policy.json --report .\report.md
```

This emits a rule per catalogued resource using CAF's recommended component order
(`resource-workload-environment-region-instance`), e.g. `afw-hub-prod-cnc-01`,
`st-app-prod-cnc-01`, `vnet-shared-prod-eus2-001`. Add a `region` code set for
your target regions, then override any rule with a customer workbook later. A
ready-made baseline lives in `examples/caf/`. The catalog itself is generated
from `catalogs/build_caf_catalog.py` (offline, stdlib only); re-run it to refresh
from Microsoft Learn.

## Package layout

- `xlsx2policy.py`: Offline converter that compiles the naming workbook (.xlsx)
  into `policy.json`. The workbook is the source of truth; `--caf-fallback` and
  `--caf-only` draw on the Microsoft CAF catalog.
- `catalogs/`: Microsoft CAF abbreviation catalog (`azure-caf.json`) and its
  generator `build_caf_catalog.py`.
- `module/`: Provider-independent Terraform naming module.
- `policies/example/`: Synthetic example policy showing the expected schema.
- `examples/excel/`: Synthetic sample workbook, its generator, and the converted
  policy + report.
- `examples/caf/`: CAF baseline policy + report generated with `--caf-only`.
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

1. Obtain the customer's approved naming workbook (.xlsx).
2. Run `xlsx2policy.py` to compile it into `policy.json` and review the
   generated conversion report. Add `--caf-fallback` to let Microsoft CAF fill
   any resources the customer has not abbreviated.
3. Reconcile unresolved rows in the workbook (keep them `draft`/`conflict`/
   `missing`), then re-run the converter.
4. Run the scanner against the customer's local repository.
5. Add module calls only for covered, `approved` resources.
6. Review `terraform plan` for replacements before applying naming changes.

If a customer has no workbook yet, generate a Microsoft CAF baseline with
`python xlsx2policy.py --caf-only --out policy.json` and tailor it, or copy
`policies/example/policy.json` as a schema starting point.

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
