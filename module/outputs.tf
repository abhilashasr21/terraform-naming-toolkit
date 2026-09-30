output "name" {
  description = "Generated resource name."
  value       = local.name

  precondition {
    condition     = local.has_rule
    error_message = "No naming rule exists for '${var.resource_type}'."
  }

  precondition {
    condition     = !local.enforce_rule || length(local.missing_components) == 0
    error_message = "Missing required naming components: ${join(", ", local.missing_components)}."
  }

  precondition {
    condition     = !local.enforce_rule || local.pattern_valid
    error_message = "Generated name '${local.name}' does not match the approved pattern '${try(local.rule.pattern, "undefined")}'."
  }

  precondition {
    condition     = !local.enforce_rule || (local.min_length_valid && local.max_length_valid)
    error_message = "Generated name '${local.name}' does not satisfy the approved length constraints."
  }
}

output "status" {
  description = "Lifecycle status of the selected policy rule."
  value       = local.has_rule ? local.rule.status : "missing"
}

output "diagnostics" {
  description = "Policy and offline uniqueness diagnostics."
  value       = local.diagnostics
}
