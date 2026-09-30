resource "azurerm_resource_group" "demo" {
  name     = "rg-old-dev-eus-01"
  location = "eastus"
}

resource "azurerm_storage_account" "computed" {
  name = "${var.prefix}${var.suffix}"
}

locals {
  example = <<-EOT
    resource "azurerm_resource_group" "fake" {
      name = "not-a-resource"
    }
  EOT
}
