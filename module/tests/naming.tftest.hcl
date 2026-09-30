variables {
  policy = {
    normal_case = "lower"
    code_sets = {
      environment = {
        production = "prd"
        prod       = "prd"
      }
    }
    rules = {
      approved_example = {
        status     = "approved"
        separator  = "-"
        min_length = 3
        max_length = 20
        pattern    = "^[a-z0-9]+(?:-[a-z0-9]+)*$"
        components = [
          {
            key     = "prefix"
            literal = "app"
          },
          {
            key = "workload"
          },
          {
            key      = "environment"
            code_set = "environment"
          }
        ]
      }
      draft_example = {
        status    = "draft"
        separator = ""
        pattern   = "^never-match$"
        components = [
          {
            key     = "prefix"
            literal = "draft"
          },
          {
            key = "index"
          }
        ]
      }
    }
  }
  resource_type = "approved_example"
  values = {
    workload    = "Payments"
    environment = "Production"
  }
}

run "generates_and_normalizes_approved_name" {
  command = plan

  assert {
    condition     = output.name == "app-payments-prd"
    error_message = "The module did not normalize components or apply the code set."
  }

  assert {
    condition     = output.status == "approved"
    error_message = "The approved policy state was not returned."
  }
}

run "allows_advisory_draft_rule" {
  command = plan

  variables {
    resource_type = "draft_example"
    values = {
      index = "01"
    }
  }

  assert {
    condition     = output.name == "draft01"
    error_message = "Draft rules should generate advisory names."
  }

  assert {
    condition     = length(output.diagnostics) > 0
    error_message = "Draft rules should return an advisory diagnostic."
  }
}

run "allows_incomplete_advisory_rule" {
  command = plan

  variables {
    resource_type = "draft_example"
    values        = {}
  }

  assert {
    condition     = output.name == "draft"
    error_message = "Incomplete advisory rules should return a partial name without blocking."
  }

  assert {
    condition     = length(output.diagnostics) == 2
    error_message = "Incomplete draft rules should report missing components and advisory status."
  }
}

run "rejects_invalid_approved_name" {
  command = plan

  variables {
    values = {
      workload    = "bad_value"
      environment = "Production"
    }
  }

  expect_failures = [
    output.name,
  ]
}

run "rejects_missing_required_component" {
  command = plan

  variables {
    values = {
      environment = "Production"
    }
  }

  expect_failures = [
    output.name,
  ]
}

run "rejects_unknown_rule" {
  command = plan

  variables {
    resource_type = "unknown"
    values        = {}
  }

  expect_failures = [
    output.name,
  ]
}
