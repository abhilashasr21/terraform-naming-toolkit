terraform {
  required_version = ">= 1.5.0"
}

variable "policy_file" {
  type    = string
  default = "../../policies/example/policy.json"
}

variable "requests_file" {
  type    = string
  default = "requests.json"
}

locals {
  policy   = jsondecode(file(var.policy_file))
  requests = jsondecode(file(var.requests_file))
}

module "names" {
  source   = "../../module"
  for_each = local.requests

  policy        = local.policy
  resource_type = each.value.resource_type
  values        = each.value.values
}

output "names" {
  value = {
    for key, naming in module.names :
    key => {
      name        = naming.name
      status      = naming.status
      diagnostics = naming.diagnostics
    }
  }
}
