variable "policy" {
  description = "Customer-specific naming policy."

  type = object({
    normal_case = optional(string, "lower")
    code_sets   = optional(map(map(string)), {})
    rules = map(object({
      status           = string
      separator        = optional(string, "-")
      case             = optional(string)
      min_length       = optional(number)
      max_length       = optional(number)
      pattern          = string
      uniqueness_scope = optional(string, "unknown")
      components = list(object({
        key      = string
        required = optional(bool, true)
        literal  = optional(string)
        code_set = optional(string)
      }))
    }))
  })

  validation {
    condition     = contains(["lower", "upper", "preserve"], var.policy.normal_case)
    error_message = "policy.normal_case must be lower, upper, or preserve."
  }

  validation {
    condition = alltrue([
      for rule in values(var.policy.rules) :
      contains(["approved", "draft", "conflict", "missing", "legacy"], rule.status)
    ])
    error_message = "Every rule status must be approved, draft, conflict, missing, or legacy."
  }
}

variable "resource_type" {
  description = "Policy rule key used to construct the name."
  type        = string
}

variable "values" {
  description = "Raw component values. Code-set mappings are applied by the policy."
  type        = map(string)
}

variable "enforce_statuses" {
  description = "Rule states that enforce pattern and length constraints."
  type        = set(string)
  default     = ["approved"]

  validation {
    condition = alltrue([
      for status in var.enforce_statuses :
      contains(["approved", "draft", "conflict", "missing", "legacy"], status)
    ])
    error_message = "enforce_statuses contains an unsupported policy state."
  }
}
