locals {
  has_rule = contains(keys(var.policy.rules), var.resource_type)
  rule     = try(var.policy.rules[var.resource_type], null)

  missing_components = [
    for component in try(local.rule.components, []) : component.key
    if component.required &&
    component.literal == null &&
    trimspace(lookup(var.values, component.key, "")) == ""
  ]

  raw_component_values = {
    for component in try(local.rule.components, []) :
    component.key => (
      component.literal != null
      ? component.literal
      : trimspace(lookup(var.values, component.key, ""))
    )
  }

  mapped_component_values = {
    for component in try(local.rule.components, []) :
    component.key => (
      component.code_set != null
      ? lookup(
        lookup(var.policy.code_sets, component.code_set, {}),
        lower(local.raw_component_values[component.key]),
        local.raw_component_values[component.key]
      )
      : local.raw_component_values[component.key]
    )
  }

  selected_case = coalesce(try(local.rule.case, null), var.policy.normal_case)
  normalized_component_values = {
    for key, value in local.mapped_component_values :
    key => (
      local.selected_case == "lower" ? lower(value) :
      local.selected_case == "upper" ? upper(value) :
      value
    )
  }

  ordered_values = [
    for component in try(local.rule.components, []) :
    local.normalized_component_values[component.key]
    if local.normalized_component_values[component.key] != ""
  ]

  name             = local.has_rule ? join(try(local.rule.separator, "-"), local.ordered_values) : ""
  enforce_rule     = local.has_rule ? contains(var.enforce_statuses, local.rule.status) : false
  pattern_valid    = local.has_rule ? can(regex(local.rule.pattern, local.name)) : false
  min_length_valid = local.has_rule ? local.rule.min_length == null || length(local.name) >= local.rule.min_length : false
  max_length_valid = local.has_rule ? local.rule.max_length == null || length(local.name) <= local.rule.max_length : false
  length_description = local.has_rule ? join(" and ", compact([
    local.rule.min_length == null ? "" : "at least ${local.rule.min_length}",
    local.rule.max_length == null ? "" : "at most ${local.rule.max_length}",
  ])) : ""

  diagnostics = compact([
    !local.has_rule ? "No naming rule exists for '${var.resource_type}'." : "",
    local.has_rule && length(local.missing_components) > 0 ? "Missing required components: ${join(", ", local.missing_components)}." : "",
    local.has_rule && !local.enforce_rule ? "Rule '${var.resource_type}' has status '${local.rule.status}' and is advisory unless that status is explicitly enforced." : "",
    local.has_rule && local.enforce_rule && !local.pattern_valid ? "Generated name does not match ${local.rule.pattern}." : "",
    local.has_rule && local.enforce_rule && (!local.min_length_valid || !local.max_length_valid) ? "Generated name length must be ${local.length_description} characters." : "",
    local.has_rule && local.rule.uniqueness_scope != "unknown" ? "Uniqueness scope: ${local.rule.uniqueness_scope}. Offline generation does not prove external availability." : "",
  ])
}
