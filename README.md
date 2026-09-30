# Offline Terraform Naming Toolkit

This toolkit separates customer naming policy from Terraform implementation. It
does not contact cloud APIs, registries, or external services during name
generation and repository inventory.

## Package layout

- `module/`: Provider-independent Terraform naming module.
- `policies/example/`: Synthetic example policy showing the expected schema.
- `examples/batch/`: Batch generation example driven by JSON requests.
- `scripts/Scan-TerraformResources.ps1`: Read-only local Terraform inventory and
  policy-coverage report.

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
