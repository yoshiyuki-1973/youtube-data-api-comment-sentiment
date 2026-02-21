terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.80"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

# ────────────────────────────────────
# Resource Group
# ────────────────────────────────────
resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
}

# ────────────────────────────────────
# Container Registry (ACR)
# ────────────────────────────────────
resource "azurerm_container_registry" "main" {
  name                = var.acr_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = var.acr_sku
  admin_enabled       = true
}

# ────────────────────────────────────
# Log Analytics Workspace
# ────────────────────────────────────
resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${var.app_name}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

# ────────────────────────────────────
# Container Apps Environment
# ────────────────────────────────────
resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${var.app_name}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
}

# ────────────────────────────────────
# Container App (Streamlit)
# ────────────────────────────────────
resource "azurerm_container_app" "streamlit" {
  name                         = "ca-${var.app_name}"
  resource_group_name          = azurerm_resource_group.main.name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"

  secret {
    name  = "youtube-api-key"
    value = var.youtube_api_key
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }

  template {
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "streamlit"
      image  = "${azurerm_container_registry.main.login_server}/${var.app_name}:latest"
      cpu    = var.container_cpu
      memory = var.container_memory

      command = [
        "python", "-m", "streamlit", "run",
        "streamlit_app.py",
        "--server.port=8501",
        "--server.address=0.0.0.0"
      ]

      env {
        name        = "YOUTUBE_API_KEY"
        secret_name = "youtube-api-key"
      }

      env {
        name  = "COMMENT_LIMIT"
        value = tostring(var.comment_limit)
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8501

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
}
