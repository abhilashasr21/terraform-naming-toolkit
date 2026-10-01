# Terraform Naming Toolkit - Complete Guide

Repository: <https://github.com/abhilashasr21/terraform-naming-toolkit>

This guide explains what the toolkit is, what every file does, and the inputs
and outputs each component expects.

## 1. The core idea

The toolkit separates three concerns that are usually tangled together:

| Concern | Where it lives | Who owns it |
| --- | --- | --- |
| **What** names should look like | Excel workbook -> `policy.json` | The customer |
| **How** names are constructed | `module/` + `namingctl.py` (engine) | This toolkit |
| **Where** names are applied | Customer's Terraform repo | The customer's engineers |

The engine is offline - no cloud calls, no registry, no pip packages. The naming
rules start life in the customer's **Excel workbook (the source of truth)** and
are compiled by `xlsx2policy.py` into `policy.json`, which the engine reads. The
same engine serves every customer by swapping one workbook.

```
  +------------------+     +---------------+     +------------------+     +---------------+
  | Naming workbook  | --> | xlsx2policy   | --> | policy.json      | --> |  Engine       |
  | (.xlsx, source   |     | (converter)   |     | (generated)      |     |  module/ or   |
  |  of truth)       |     +---------------+     +------------------+     |  namingctl.py |
  +------------------+                                    ^               +-------+-------+
                                                          |                       |
                          +-------------+                 |                       v
                          | requests /  | ----------------+               +---------------+
                          | values      |                                 | Generated     |
                          +-------------+                                 | names + diags |
                                                                          +---------------+
```

## 2. File-by-file breakdown

### A0. The converter (`xlsx2policy.py`) - workbook to policy

Use this first. It compiles the customer's naming workbook into `policy.json`.

- **Input:** a naming workbook (`.xlsx`) with the recognised sheets (`Region_Codes`,
  `Code_Reference`, `Comprehensive_Resource_Analysis`, `Resource_List`,
  `MSFT_Constraint`).
- **Output:** `policy.json` (engine input) + an optional Markdown conversion
  report of rules, source patterns, Terraform mappings, and ambiguities.
- **Offline:** reads `.xlsx` as a zip of XML with the Python standard library
  only (no openpyxl/pandas/Office).

| Command | Effect |
| --- | --- |
| `python xlsx2policy.py book.xlsx --out policy.json` | Compile the workbook into a policy. |
| `... --report conversion-report.md` | Also write the human review report. |
| `... --check` | Exit non-zero if `policy.json` is missing or stale versus the workbook (CI gate). |
| `... --caf-fallback` | Fill missing abbreviations / Terraform types from Microsoft CAF (workbook still wins). |
| `xlsx2policy.py --caf-only --out policy.json` | Generate a Microsoft CAF baseline policy with no workbook. |

Sheet-to-policy mapping:

| Workbook sheet | Produces |
| --- | --- |
| `Region_Codes` | `code_sets.region` (Region Name/Code -> code) |
| `Code_Reference` | `code_sets.environment`, `business_service`, `use` |
| `Comprehensive_Resource_Analysis` or `Resource_List` | `rules` (parsed from `<token>` patterns) |
| `MSFT_Constraint` | per-rule `min_length`/`max_length`/`uniqueness_scope` |
| `Resource_List` status column | rule `status` enrichment |

Status mapping: "Done (No Conflict)"/"Agreed" -> `approved`; "In-Progress",
"To Be Discussed", blank -> `draft` (advisory). The embedded `source_sha256` in
the policy metadata is what `--check` compares.

**Microsoft CAF fallback (`catalogs/azure-caf.json`).** When a customer has no
abbreviation for a resource, the converter can fall back to Microsoft's
[Cloud Adoption Framework](https://learn.microsoft.com/azure/cloud-adoption-framework/ready/azure-best-practices/resource-abbreviations)
recommendations - 150+ resources mapped to abbreviation, ARM namespace, and
Terraform type. The customer workbook always takes precedence; CAF only fills
gaps, and every fallback is flagged in the report's `CAF` column and in
`metadata.caf_fallback`. With `--caf-only` the catalog alone produces a compliant
baseline (`afw-hub-prod-cnc-01`, `st-app-prod-cnc-01`, ...) usable by any team.
The catalog is generated offline by `catalogs/build_caf_catalog.py`; re-run it to
refresh from Microsoft Learn.


### A. The policy (the engine's input - generated from Excel)

`policies/example/policy.json` - a schema example. In production this file is
**generated from the customer's Excel workbook** by `xlsx2policy.py`; treat it as
a build artifact, not a hand-edited file.

- **Input to:** the Terraform module and the CLI.
- **Structure:**
  - `normal_case` - global casing (`lower` / `upper` / `preserve`).
  - `code_sets` - abbreviation dictionaries, e.g. `production -> prd`,
    `eastus -> eus`. Multiple spellings can map to one code.
  - `rules` - one entry per resource type. Each rule has:
    - `status` - `approved` | `draft` | `conflict` | `legacy` | `missing`
    - `separator` - e.g. `-` for resource groups, `""` for storage accounts
    - `min_length` / `max_length` - length limits
    - `pattern` - regex the final name must satisfy
    - `terraform_resource_types` - which `.tf` resources this rule governs
    - `components` - the ordered parts of the name (`literal`, `key`, optional
      `code_set`)

Example - how a name is assembled from the `resource_group` rule:

```
components: [literal "rg"] [workload] [environment->code] [region->code] [index]
values:      rg            payments     production->prd      eastus->eus    01
separator:   -
result:     rg-payments-prd-eus-01   (matches ^rg-[a-z0-9]+(?:-[a-z0-9]+)*$)
```

### B. The Terraform module (`module/`)

Use this when you want names generated inside Terraform at plan time.

| File | Role |
| --- | --- |
| `variables.tf` | Declares and validates inputs: `policy`, `resource_type`, `values`, `enforce_statuses`. Rejects bad statuses, bad cases, unknown code_sets. |
| `main.tf` | The logic: looks up the rule, fills literals, maps code sets, applies casing, joins with the separator, checks pattern + length, builds diagnostics. |
| `outputs.tf` | Returns `name`, `status`, `diagnostics`. Uses preconditions so an `approved` rule that fails its pattern/length blocks the plan. |
| `tests/naming.tftest.hcl` | 6 native Terraform tests (normalization, advisory rules, invalid names, missing inputs, unknown rules). |

Inputs:

```hcl
policy        = jsondecode(file("policy.json"))
resource_type = "storage_account"
values        = { workload = "payments", environment = "production", region = "eastus", index = "01" }
```

Outputs:

- `name` -> `"stpaymentsprdeus01"`
- `status` -> `"approved"`
- `diagnostics` -> list of advisory messages (e.g. uniqueness scope notes)

### C. The standalone CLI (`namingctl.py`)

Use this when you want to analyse or edit `.tf` files without running Terraform.
Python 3.10+, standard library only.

| Command | Input | Output | Changes files? |
| --- | --- | --- | --- |
| `list` | `--policy` | All rules + statuses | No |
| `explain <rule>` | `--policy` | One rule's components and constraints | No |
| `generate <rule>` | `--policy --values '{...}'` | One name to stdout | No |
| `plan <dir>` | `--policy --requests` | `NAMING-CHANGELOG.md` (+ optional `--json`) | No |
| `check <dir>` | `--policy --requests` | Findings + non-zero exit if a change/block exists | No |
| `apply <dir>` | `--policy --requests` | Edits literal names, or `--out` copy | Yes (guarded) |

The request manifest (`--requests`) - explicit, never guessed:

```json
{
  "azurerm_resource_group.demo": {
    "rule": "resource_group",
    "values": { "workload": "payments", "environment": "production", "region": "eastus", "index": "01" }
  }
}
```

Keyed by exact Terraform address -> which rule + which component values.

What `apply` will and won't touch (demonstrated in `examples/cli/main.tf`):

- Rewritten: `name = "rg-old-dev-eus-01"` (unique top-level literal)
- Never touched: `name = "${var.prefix}${var.suffix}"` (computed)
- Ignored: `name = "not-a-resource"` inside a heredoc

Safety: timestamped `.naming-backup`, atomic writes, refuses
symlinks/junctions/hard-links/stale plans, never edits state/vars/policy/request
files, `--out` leaves the source untouched.

### D. The scanner (`scripts/Scan-TerraformResources.ps1`)

Read-only inventory of a customer repo (PowerShell 5.1+).

- **Inputs:** `-RepoPath` (required), `-PolicyPath` (optional), `-OutputPath`.
- **Output:** JSON inventory of every `resource`, `data`, `module` block + policy
  coverage.
- Strips comments/strings properly; cannot see resources inside modules not on
  disk (advisory).

### E. Examples and tests

| Path | Purpose |
| --- | --- |
| `catalogs/` | Microsoft CAF abbreviation catalog (`azure-caf.json`) + its generator. |
| `examples/excel/` | Synthetic sample workbook, its generator, and the converted policy + report. |
| `examples/caf/` | Microsoft CAF baseline policy + report (produced by `--caf-only`). |
| `examples/batch/` | Generate many names at once via the module + `requests.json` (keyed by `resource_type`). |
| `examples/inventory/` | Fixtures for the scanner. |
| `examples/cli/` | Fixtures proving safe literal edit vs. ignored computed/heredoc cases. |
| `tests/test_namingctl.py` | 28 CLI safety/behaviour tests. |
| `tests/test_xlsx2policy.py` | 8 converter tests (sheet parsing, section bounds, constraints, end-to-end, staleness). |
| `tests/test_caf_catalog.py` | 13 CAF tests (catalog load, abbreviation match, fallback, `--caf-only` end-to-end). |

### F. Docs and housekeeping

`README.md` (quick start), `IMPLEMENTATION-SUMMARY.md` (full handoff),
`GUIDE.md` (this file), `LICENSE` (MIT), `.gitignore`.

## 3. The policy lifecycle (why names don't silently deploy)

| Status | Generates a name? | Enforced (blocks)? | Meaning |
| --- | --- | --- | --- |
| `approved` | Yes | Yes | Signed-off rule |
| `draft` | Yes | No (advisory) | Still being worked |
| `conflict` | Yes | No (advisory) | Source document contradicts itself |
| `legacy` | Yes | No (advisory) | Old accepted form |
| `missing` | No | Blocks generation | No usable rule exists |

This is the key safety design: an unfinished customer workbook cannot become an
accidental deployment gate. Only `approved` rules enforce.

## 4. End-to-end workflow for a new customer

```
1. Copy the toolkit into the restricted environment.
2. Compile the customer's naming workbook into a policy:
   python xlsx2policy.py C:\customer\NamingConvention.xlsx --out customer\policy.json --report customer\conversion-report.md
3. Review the conversion report; fix unresolved rows in the WORKBOOK, then re-run step 2.
4. Scan the repo:
   .\scripts\Scan-TerraformResources.ps1 -RepoPath C:\customer\tf -PolicyPath customer\policy.json
5. Write requests.json mapping each root resource address -> rule + values.
6. Preview:  python namingctl.py plan  C:\customer\tf --policy customer\policy.json --requests requests.json
7. Gate:     python namingctl.py check C:\customer\tf --policy customer\policy.json --requests requests.json
8. Apply:    python namingctl.py apply C:\customer\tf --policy customer\policy.json --requests requests.json --out C:\customer\tf-named
9. Review NAMING-CHANGELOG.md, then run the repo's normal terraform fmt/validate/plan.
10. Inspect replacement-prone changes BEFORE deploying.
```

## 5. Validation already passed

- Python tests: 47 passed, 2 skipped (CLI + converter + CAF suites; skips are
  Windows symlink-privilege cases).
- Terraform module tests: 6 passed (Terraform v1.15.2).
- Repository scanned clean: no workbook, SharePoint, customer, or local-path
  references.

## 6. Important boundaries

- Not a full HCL parser - treat the changelog as a review artifact.
- Scans `.tf.json` but never rewrites it.
- Does not deploy infrastructure or touch Terraform state.
- Remote name immutability/replacement is provider-specific - always review the
  Terraform plan.
