variable "subscription_id" {
  description = "AzureサブスクリプションID（未指定時はデフォルトサブスクリプションを使用）"
  type        = string
  default     = null
}

variable "resource_group_name" {
  description = "リソースグループ名"
  type        = string
  default     = "rg-youtube-sentiment"
}

variable "location" {
  description = "Azureリージョン"
  type        = string
  default     = "japaneast"
}

variable "acr_name" {
  description = "Container Registry名（グローバルで一意）"
  type        = string
}

variable "acr_sku" {
  description = "Container RegistryのSKU（Basic, Standard, Premium）"
  type        = string
  default     = "Basic"

  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.acr_sku)
    error_message = "acr_skuはBasic, Standard, Premiumのいずれかを指定してください。"
  }
}

variable "app_name" {
  description = "Container App名"
  type        = string
  default     = "youtube-sentiment"
}

variable "youtube_api_key" {
  description = "YouTube Data API v3キー"
  type        = string
  sensitive   = true
}

variable "comment_limit" {
  description = "コメント取得件数"
  type        = number
  default     = 100
}

variable "container_cpu" {
  description = "コンテナのCPU割り当て"
  type        = number
  default     = 2.0
}

variable "container_memory" {
  description = "コンテナのメモリ割り当て（Gi）"
  type        = string
  default     = "4Gi"
}
