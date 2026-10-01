# Terraform Naming Toolkit - Implementation Summary

## Purpose

This repository provides a reusable Terraform naming solution for customer
environments where source code, naming documents, and runtime access are
restricted. The toolkit is offline-first and keeps customer-specific naming
policy separate from the implementation.

It is designed to:

- analyse and represent a customer naming convention as replaceable JSON;
- inventory Terraform resources without executing customer code;
- generate deterministic names through a local Terraform module;
- plan and safely apply literal Terraform name changes through a standalone CLI;
- preserve unresolved policy decisions as explicit diagnostics rather than
  silently inventing values.

## Requirements addressed

- Customer repositories and naming documents vary between engagements.
- Customer Terraform code need not be uploaded or shared.
- The implementation must work without registry access, cloud APIs, or Python
  packages.
- Existing resource addresses must remain stable where possible.
- Renaming must be treated as potentially replacement-prone.
- A Markdown handoff containing the implementation details must be available at
  the end of the work.

## Architecture

### Workbook as source of truth

The customer's naming-convention **Excel workbook is the authoritative source**.
`xlsx2policy.py` compiles it into `policy.json`:

- Reads `.xlsx` as a zip of XML using only the Python standard library (no
  openpyxl, pandas, Office, or network).
- Maps recognised sheets: `Region_Codes` -> region codes; `Code_Reference` ->
  environment/business_service/use codes; `Comprehensive_Resource_Analysis`
  (or `Resource_List`) -> rules; `MSFT_Constraint` -> length/uniqueness limits.
- Derives rule `status` from the workbook ("Done (No Conflict)" -> `approved`,
  unresolved/blank -> `draft`), so unfinished rows stay advisory.
- Emits a Markdown conversion report of every rule, its source pattern, Terraform
  mapping, and ambiguities (such as inconsistent separators).
- Embeds the workbook `source_sha256` in policy metadata; `--check` fails when the
  policy is stale versus the workbook.

`policy.json` is therefore a generated artifact. Customers edit the workbook and
re-run the converter rather than hand-editing JSON.

### Replaceable policy schema

- code sets and abbreviations;
- resource rules and component order;
- separators, casing, allowed patterns, and maximum lengths;
- Terraform resource-type mappings;
- rule lifecycle status.

Policy statuses are:

| Status | Behaviour |
| --- | --- |
| `approved` | Enforced by default. |
| `draft` | Advisory by default; indicates incomplete policy work. |
| `conflict` | Advisory by default; records contradictory source rules. |
| `legacy` | Documents an accepted old form without making it the default. |
| `missing` | No usable rule exists; automatic generation is blocked. |

Customer or workbook-specific values are not embedded in the public repository.

### Terraform module

The provider-independent module in `module/`:

- accepts a typed policy object and resource type;
- normalizes and maps input components;
- constructs deterministic names;
- applies resource-specific patterns and length rules;
- exposes generated names, rule status, and diagnostics;
- uses Terraform validation and preconditions for enforced rules.

The module does not rename deployed resources. Consumers must review the
provider plan because a remote name change can force replacement.

### Local scanner

`scripts/Scan-TerraformResources.ps1` produces a read-only inventory of local
`.tf` and `.tf.json` files. It reports resources, data sources, modules, and
policy coverage. It is intentionally advisory and cannot inspect module code
that is not present on disk.

### Standalone CLI

`namingctl.py` is a single-file Python 3.10+ CLI using only the standard
library. It supports:

- `list` - list policy rules;
- `explain` - show one rule and its constraints;
- `generate` - generate one deterministic name;
- `plan` - create a Markdown changelog and optional JSON report;
- `check` - report naming gaps and blocking conditions;
- `apply` - guarded in-place edits or a safe output copy.

The CLI requires an explicit request manifest keyed by exact Terraform resource
address. It never guesses workload, region, environment, index, or other
components.

## Safety model

The CLI:

- edits only a unique top-level literal `name = "..."` assignment;
- never rewrites computed expressions, interpolations, or ambiguous syntax;
- ignores comments and heredoc content;
- treats child-module resources as inventory-only;
- revalidates the current source before applying a planned change;
- creates timestamped `.naming-backup` files for in-place edits;
- leaves the source tree untouched when `--out` is used;
- rejects symlinks, junctions, hard-linked files, stale plans, and protected
  input/output collisions;
- does not modify Terraform state, saved plans, policy files, request files,
  variable files, or lock files;
- restricts output copies to Terraform source, lock, and example variable files;
- uses atomic report and backup writes.

`apply` is a source-editing utility, not an infrastructure deployment command.
The customer must inspect the generated changelog and run the repository's
normal Terraform validation and plan workflow before deployment.

## Repository contents

| Path | Purpose |
| --- | --- |
| `xlsx2policy.py` | Offline converter: naming workbook (.xlsx) -> `policy.json`. |
| `module/` | Reusable Terraform naming module. |
| `module/tests/naming.tftest.hcl` | Terraform-native module tests. |
| `policies/example/policy.json` | Synthetic, customer-neutral policy example. |
| `examples/excel/` | Synthetic sample workbook, generator, converted policy + report. |
| `examples/batch/` | Batch Terraform name-generation example. |
| `examples/inventory/` | Scanner fixtures. |
| `examples/cli/` | CLI editing and ignored-case fixtures. |
| `scripts/Scan-TerraformResources.ps1` | Offline Terraform inventory scanner. |
| `namingctl.py` | Standalone offline planning and apply CLI. |
| `tests/test_namingctl.py` | CLI regression and safety tests. |
| `tests/test_xlsx2policy.py` | Converter tests (sheet parsing, section bounds, staleness, end-to-end). |
| `README.md` | Quick start and operating instructions. |
| `GUIDE.md` | Complete guide to every file, inputs, and outputs. |
| `IMPLEMENTATION-SUMMARY.md` | Detailed implementation and handoff record. |

## Customer onboarding

1. Copy the repository into the restricted environment.
2. Compile the customer's naming workbook into a policy with `xlsx2policy.py`.
3. Review the conversion report; fix unresolved rows in the workbook and re-run.
4. Keep unresolved rows as `draft`, `conflict`, or `missing`.
5. Run the PowerShell scanner against the local Terraform repository.
6. Map discovered root resources to explicit request-manifest entries.
7. Run `namingctl.py plan` and review `NAMING-CHANGELOG.md`.
8. Run `namingctl.py check` and resolve blocking findings.
9. Use `apply --out` first when a separate reviewed tree is preferred.
10. Run formatting, validation, tests, and `terraform plan` using approved local
    tools and cached providers.
11. Review all replacement-prone changes before deployment.

Example:

```powershell
python .\xlsx2policy.py C:\customer\NamingConvention.xlsx `
  --out C:\customer\policy.json `
  --report C:\customer\conversion-report.md

python .\namingctl.py plan C:\customer\terraform `
  --policy C:\customer\policy.json `
  --requests C:\customer\requests.json

python .\namingctl.py apply C:\customer\terraform `
  --policy C:\customer\policy.json `
  --requests C:\customer\requests.json `
  --out C:\customer\terraform-named
```

## Validation completed

- Python tests: 34 passed, 2 skipped (converter + CLI suites).
- Windows symlink tests: 2 skipped because the current account lacks symlink
  privileges.
- Terraform module tests: 6 passed.
- Terraform version exercised locally: `v1.15.2`.
- Public repository scan found no private workbook references, SharePoint URLs,
  customer identifiers, or local machine paths.

## Known limitations

- The CLI is deliberately not a complete HCL parser.
- `.tf.json` files are scanned but not rewritten.
- The scanner cannot discover resources in unavailable child modules.
- Policy correctness still requires customer approval and source-document
  reconciliation.
- Remote name immutability and replacement behaviour remain provider-specific.
- The toolkit does not deploy infrastructure or mutate Terraform state.

## Publication

Repository: <https://github.com/abhilashasr21/terraform-naming-toolkit>

The public repository contains only synthetic examples and customer-neutral
implementation code. Customer policy files and restricted Terraform source
remain local to each customer environment.
