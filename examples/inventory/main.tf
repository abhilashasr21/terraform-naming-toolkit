# This file is a scanner fixture; it is not intended for terraform apply.

resource "azurerm_resource_group" "covered" {
  name     = "rg-example-dev-eus-01"
  location = "eastus"
}

resource "azurerm_service_plan" "uncovered" {
  name                = "asp-example-dev-eus-01"
  location            = "eastus"
  resource_group_name = azurerm_resource_group.covered.name
  os_type             = "Linux"
  sku_name            = "B1"
}

data "azurerm_client_config" "current" {}

module "example" {
  source = "../../module"
}

# resource "azurerm_storage_account" "commented_out" {}

locals {
  ignored_heredoc = <<-EOT
    resource "azurerm_storage_account" "inside_heredoc" {}
  EOT
}
