output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "acr_login_server" {
  value = azurerm_container_registry.main.login_server
}

output "app_url" {
  value = "https://${azurerm_container_app.streamlit.ingress[0].fqdn}"
}
