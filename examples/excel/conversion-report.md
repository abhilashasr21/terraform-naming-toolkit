# Naming Workbook Conversion Report

- Source workbook: `sample-naming.xlsx`
- Source SHA-256: `7f1e6c6c2b4d27d2ccb8b4c5fb6507cc751b04842a7cf987dd7bc0f490a9037c`
- Code sets: business_service, environment, region, use
- Rules generated: 6
- Approved (enforced) rules: 4

## Rules

| Rule | Resource | Status | TF mapped | Source pattern | Notes |
| --- | --- | --- | --- | --- | --- |
| `azure_firewall` | Azure Firewall | approved | yes | `afw-<BusinessService>-<RegionCode>-<Environment>-<index>` |  |
| `key_vault` | Key Vault | approved | yes | `kv-<BusinessService>-<RegionCode>-<Environment>-<index>` |  |
| `resource_group` | Resource Group | approved | yes | `rg-<BusinessService>-<RegionCode>-<Environment>-<index>` |  |
| `storage_account` | Storage Account | approved | yes | `st<BusinessService><RegionCode><Environment><index>` |  |
| `subnet` | Subnet | draft | yes | `snet-<Purpose>-<BusinessService>-<RegionCode>-<Environment>-<index>` |  |
| `virtual_network` | Virtual Network | draft | yes | `vnet-<BusinessService>-<RegionCode>-<Environment>-<index>` |  |

Only `approved` rules are enforced by the engine. Review `draft`, `conflict`, and `missing` rows with the customer before promoting them.
