# Azure Terraform デプロイガイド

本システムを Azure Container Apps + Azure Container Registry にデプロイする手順。

## 1. 構成概要

```
┌─────────────────────────────────────────────┐
│  Azure Resource Group                       │
│                                             │
│  ┌───────────────────┐                      │
│  │ Container Registry │ ← Docker イメージ   │
│  │ (ACR)             │   を Push            │
│  └────────┬──────────┘                      │
│           │ Pull                            │
│  ┌────────▼──────────────────────────────┐  │
│  │ Container Apps Environment            │  │
│  │  ┌─────────────────────────────────┐  │  │
│  │  │ Container App (Streamlit)       │  │  │
│  │  │  - Port 8501                    │  │  │
│  │  │  - YOUTUBE_API_KEY (Secret)     │  │  │
│  │  └─────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────┐  │  │
│  │  │ Log Analytics Workspace         │  │  │
│  │  └─────────────────────────────────┘  │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

**使用するAzureサービス**:

| サービス | 用途 | 月額目安 |
|---|---|---|
| Azure Container Registry (Basic) | Dockerイメージ保管 | ~$5 |
| Azure Container Apps | Streamlitアプリ実行 | ~$0-10（従量課金） |
| Log Analytics Workspace | ログ収集 | 無料枠内 |

**合計**: 月額約 $5〜15（低トラフィック時）

## 2. 前提条件

### 必要なツール

```bash
# Azure CLI
az --version   # 2.50以上

# Terraform
terraform --version   # 1.5以上

# Docker
docker --version
```

### インストール（未導入の場合）

```bash
# Azure CLI (Windows)
winget install Microsoft.AzureCLI

# Terraform (Windows)
winget install Hashicorp.Terraform

# または chocolatey
choco install azure-cli terraform
```

### Azure アカウント設定

```bash
# Azureにログイン
az login

# サブスクリプション確認
az account show

# サブスクリプションを指定（複数ある場合）
az account set --subscription "YOUR_SUBSCRIPTION_ID"
```

> **Note**: サブスクリプションIDは `terraform.tfvars` の `subscription_id` でも指定可能。
> 未指定の場合は `az account` のデフォルトサブスクリプションが使用される。

### リソースプロバイダーの登録（初回のみ）

新規サブスクリプションでは、Container Apps関連のリソースプロバイダーが未登録の場合がある。

```bash
# 登録状態を確認
az provider show --namespace Microsoft.App --query "registrationState"
az provider show --namespace Microsoft.OperationalInsights --query "registrationState"

# "NotRegistered" の場合は登録（数十秒〜数分で完了）
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
```

## 3. ディレクトリ構成

プロジェクトルートに `terraform/` ディレクトリを作成する。

```
youtube-data-api-comment-sentiment/
├── terraform/
│   ├── main.tf              # メインリソース定義
│   ├── variables.tf         # 変数定義
│   ├── outputs.tf           # 出力定義
│   ├── terraform.tfvars     # 変数値（Git管理外）
│   └── .terraform.lock.hcl  # プロバイダーロック（自動生成）
├── Dockerfile
├── app/
└── ...
```

## 4. Terraformファイル作成

### 4.1 variables.tf（変数定義）

```hcl
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
```

### 4.2 main.tf（メインリソース定義）

```hcl
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
```

### 4.3 outputs.tf（出力定義）

```hcl
output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "acr_login_server" {
  value = azurerm_container_registry.main.login_server
}

output "app_url" {
  value = "https://${azurerm_container_app.streamlit.ingress[0].fqdn}"
}
```

### 4.4 terraform.tfvars（変数値）

```hcl
# このファイルはGit管理外にすること

# 必須設定
acr_name        = "youtubesentimentacr"   # グローバルで一意な名前に変更
youtube_api_key = "YOUR_YOUTUBE_API_KEY"

# オプション（デフォルト値を変更する場合のみ）
# subscription_id     = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
# resource_group_name = "rg-youtube-sentiment"
# acr_sku             = "Basic"
# location            = "japaneast"
# comment_limit       = 100
# container_cpu       = 2.0
# container_memory    = "4Gi"
```

### 4.5 .gitignore に追加

```gitignore
# Terraform
terraform/.terraform/
terraform/*.tfstate
terraform/*.tfstate.backup
terraform/*.tfvars
terraform/.terraform.lock.hcl
```

## 5. Dockerfile の調整

本番用はdebugpy不要。Dockerfile はそのまま使用可能だが、`docker-compose.yml` の
debugpy付きコマンドではなく、Terraform側で直接Streamlitを起動するコマンドを指定している。

## 6. デプロイ手順

### Step 1: Terraformファイルの準備

```bash
# terraform/ ディレクトリに移動
cd terraform

# 変数ファイルを作成
cp terraform.tfvars.example terraform.tfvars
# terraform.tfvars を編集して acr_name と youtube_api_key を設定
```

### Step 2: Terraform 初期化・実行

```bash
# 初期化（プロバイダーのダウンロード）
terraform init

# コードの整形（HCL標準スタイルに自動フォーマット）
terraform fmt

# 実行計画の確認（何が作成されるか確認）
terraform plan

# リソースの作成
terraform apply

# 確認プロンプトで yes を入力
```

出力例:
```
Apply complete! Resources: 5 added, 0 changed, 0 destroyed.

Outputs:
acr_login_server   = "youtubesentimentacr.azurecr.io"
app_url            = "https://ca-youtube-sentiment.xxx.japaneast.azurecontainerapps.io"
resource_group_name = "rg-youtube-sentiment"
```

### Step 3: Dockerイメージのビルド・プッシュ

```bash
# プロジェクトルートに戻る
cd ..

# ACRにログイン（terraform output からACR名を取得）
az acr login --name youtubesentimentacr

# イメージをビルド（ACR用タグ付き）
docker build -t youtubesentimentacr.azurecr.io/youtube-sentiment:latest .

# ACRにプッシュ
docker push youtubesentimentacr.azurecr.io/youtube-sentiment:latest
```

### Step 4: Container App の更新

イメージをプッシュした後、Container Appが自動的に最新イメージを取得する。
手動で更新する場合：

```bash
# リビジョンの更新を強制
az containerapp update \
  --name ca-youtube-sentiment \
  --resource-group rg-youtube-sentiment \
  --image youtubesentimentacr.azurecr.io/youtube-sentiment:latest
```

### Step 5: 動作確認

```bash
# アプリURLの確認
terraform output app_url

# ブラウザでアクセス
# https://ca-youtube-sentiment.xxx.japaneast.azurecontainerapps.io
```

## 7. 更新デプロイ（コード変更時）

```bash
# 1. イメージを再ビルド
docker build -t youtubesentimentacr.azurecr.io/youtube-sentiment:latest .

# 2. プッシュ
docker push youtubesentimentacr.azurecr.io/youtube-sentiment:latest

# 3. Container App を更新
az containerapp update \
  --name ca-youtube-sentiment \
  --resource-group rg-youtube-sentiment \
  --image youtubesentimentacr.azurecr.io/youtube-sentiment:latest
```

## 8. 環境変数の変更

```bash
# YouTube APIキーの変更
az containerapp secret set \
  --name ca-youtube-sentiment \
  --resource-group rg-youtube-sentiment \
  --secrets youtube-api-key=NEW_API_KEY

# COMMENT_LIMITの変更
az containerapp update \
  --name ca-youtube-sentiment \
  --resource-group rg-youtube-sentiment \
  --set-env-vars COMMENT_LIMIT=200
```

## 9. リソースの削除

```bash
cd terraform

# 全リソースを削除
terraform destroy

# 確認プロンプトで yes を入力
```

## 10. トラブルシューティング

### コンテナが起動しない

```bash
# コンテナのログを確認
az containerapp logs show \
  --name ca-youtube-sentiment \
  --resource-group rg-youtube-sentiment \
  --follow

# リビジョンの状態を確認
az containerapp revision list \
  --name ca-youtube-sentiment \
  --resource-group rg-youtube-sentiment \
  --output table
```

### メモリ不足エラー

感情分析モデル（PyTorch + transformers）は約2-3GBのメモリを消費する。
`variables.tf` の `container_memory` を増やす。

```hcl
# terraform.tfvars
container_cpu    = 2.0
container_memory = "4Gi"   # 必要に応じて増やす
```

### ACRへのプッシュが失敗する

```bash
# ACRへのログインを再試行
az acr login --name youtubesentimentacr

# ACRの認証情報を確認
az acr credential show --name youtubesentimentacr
```

### 初回起動が遅い

初回起動時にHugging Faceからモデルをダウンロードするため、数分かかる場合がある。
Container Appsのヘルスチェックタイムアウトに注意。

## 11. コスト管理

### 月額コスト目安

| 項目 | 条件 | 月額 |
|---|---|---|
| ACR Basic | 10GB ストレージ | ~$5 |
| Container Apps | min_replicas=0, 低トラフィック | ~$0-10 |
| Log Analytics | 無料枠 5GB/月 | $0 |
| **合計** | | **~$5-15** |

### コスト削減のポイント

- `min_replicas = 0` でアイドル時はコスト$0
- 使用しない時は `terraform destroy` で全削除
- ACR Basic SKU（$5/月）で十分
