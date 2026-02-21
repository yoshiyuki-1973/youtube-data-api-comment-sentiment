# Docker操作ガイド

YouTube分析バッチシステムのDocker環境の構築・運用方法を説明します。

## 目次
1. [コンテナ構成](#コンテナ構成)
2. [初回セットアップ](#初回セットアップ)
3. [基本操作](#基本操作)
4. [コンテナ別の操作](#コンテナ別の操作)
5. [トラブルシューティング](#トラブルシューティング)
6. [データ管理](#データ管理)

---

## コンテナ構成

本システムは2つのコンテナで構成されています：

| コンテナ名 | 役割 | ポート | 備考 |
|-----------|------|--------|------|
| `youtube-analytics-streamlit` | Streamlit UI | 8501 | Webインターフェース |
| `youtube-analytics-app` | バッチ処理 | - | CLI実行用 |

### ネットワーク構成
- すべてのコンテナは `youtube-analytics-network` ブリッジネットワークで接続
- コンテナ間は内部ネットワークで通信

---

## 初回セットアップ

### 1. 環境変数の設定

`.env.example` をコピーして `.env` を作成：

```powershell
Copy-Item .env.example .env
```

必須設定項目：
```env
# YouTube API
YOUTUBE_API_KEY=your_api_key_here

# その他
COMMENT_LIMIT=100
```

### 2. イメージのビルドとコンテナ起動

```powershell
# ビルドして起動
docker-compose up --build -d

# 起動ログを確認
docker-compose logs -f
```

### 3. 動作確認

```powershell
# コンテナの状態確認
docker-compose ps

# Streamlit UIにアクセス
# ブラウザで http://localhost:8501 を開く
```

---

## 基本操作

### コンテナの起動・停止

```powershell
# すべてのコンテナを起動
docker-compose up -d

# すべてのコンテナを停止
docker-compose down

# コンテナとボリュームを削除（データベース含む）
docker-compose down -v
```

### コンテナの状態確認

```powershell
# 実行中のコンテナ一覧
docker-compose ps

# すべてのコンテナのログを表示
docker-compose logs

# 特定のコンテナのログを表示
docker-compose logs streamlit

# リアルタイムでログを追跡
docker-compose logs -f streamlit
```

### イメージの再ビルド

コードを変更した場合、イメージを再ビルド：

```powershell
# 再ビルド
docker-compose build

# キャッシュを使わずに再ビルド
docker-compose build --no-cache

# 再ビルドして起動
docker-compose up --build -d
```

---

## コンテナ別の操作

### Streamlitコンテナ

Webインターフェースを提供します。

```powershell
# アクセス
# ブラウザで http://localhost:8501

# コンテナ内でシェルを起動
docker exec -it youtube-analytics-streamlit /bin/bash

# Streamlitアプリを再起動
docker-compose restart streamlit
```

### Appコンテナ（バッチ処理）

CLI経由でバッチ処理を実行します。

```powershell
# コンテナ内でPythonスクリプトを実行
docker exec -it youtube-analytics-app python main.py

# コンテナ内でシェルを起動
docker exec -it youtube-analytics-app /bin/bash

# 実行例：動画分析
docker exec -it youtube-analytics-app python main.py --video-id dQw4w9WgXcQ
```

---

## トラブルシューティング

### コンテナが起動しない

```powershell
# エラーログを確認
docker-compose logs

# コンテナの状態を確認
docker-compose ps
```

### ポートが使用中

ポート8501が既に使用されている場合：

```powershell
# 使用中のポートを確認
netstat -ano | findstr :8501

# docker-compose.ymlのポート設定を変更
# 例：8501 → 8502
```

### ソースコードの変更が反映されない

開発環境ではソースコードがマウントされているため、通常は自動反映されます：

```powershell
# Streamlitの場合：ブラウザで再読み込み

# Appコンテナの場合：コンテナを再起動
docker-compose restart app

# それでも反映されない場合：再ビルド
docker-compose up --build -d
```

### ディスク容量不足

```powershell
# 未使用のイメージとコンテナを削除
docker system prune -a

# ボリュームも含めて削除（注意：データベースも削除されます）
docker system prune -a --volumes
```

### コンテナ内のファイルを確認

```powershell
# コンテナ内のファイル一覧
docker exec youtube-analytics-app ls -la /app

# コンテナからファイルをコピー
docker cp youtube-analytics-app:/app/logs/app.log ./logs/
```

---

## ボリューム管理

### マウントされているボリューム

| ホスト側 | コンテナ側 | 用途 |
|---------|-----------|------|
| `./app` | `/app` | ソースコード（ホットリロード） |
| `./logs` | `/app/logs` | ログファイル |
| `./models` | `/app/models` | 感情分析モデル |

> **注**: 本システムではデータの永続化は行いません。分析結果は画面に表示されるのみです。

### データのバックアップ

```powershell
# ログファイルのバックアップ
Copy-Item -Recurse ./logs ./logs_backup_$(Get-Date -Format 'yyyyMMdd')

# モデルファイルのバックアップ
Copy-Item -Recurse ./models ./models_backup_$(Get-Date -Format 'yyyyMMdd')
```

---

## セキュリティに関する注意事項

### 現在のセキュリティ設定

- ✅ コンテナ間通信は内部ネットワークのみ
- ⚠️ Streamlit（8501）は外部公開（開発環境用）

### 本番環境での推奨事項

本番環境にデプロイする場合：

1. **Streamlitに認証を追加**
   ```python
   # streamlit_app.py でパスワード認証を実装
   ```

2. **環境変数を安全に管理**
   - `.env` ファイルをGit管理外に
   - シークレット管理サービスの利用を検討

3. **リソース制限を設定**
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2.0'
         memory: 2G
   ```

---

## よくあるコマンド集

```powershell
# すべてのコンテナを起動
docker-compose up -d

# すべてのコンテナを停止
docker-compose down

# ログをリアルタイム表示
docker-compose logs -f

# 特定のコンテナを再起動
docker-compose restart streamlit

# コンテナ内でシェルを起動
docker exec -it youtube-analytics-app /bin/bash

# コンテナの状態確認
docker-compose ps

# イメージを再ビルド
docker-compose build --no-cache

# 未使用リソースを削除
docker system prune -a
```

---

## 関連ドキュメント

- [10_運用設計書.md](./10_運用設計書.md) - システム運用の全体像
- [05_ディレクトリ構成.md](./05_ディレクトリ構成.md) - プロジェクト構造
- [README.md](../README.md) - プロジェクト概要とクイックスタート
