# Docker操作ガイド

YouTube分析バッチシステムのDocker環境の構築・運用方法を説明します。

## 目次
1. [コンテナ構成](#コンテナ構成)
2. [初回セットアップ](#初回セットアップ)
3. [基本操作](#基本操作)
4. [コンテナ別の操作](#コンテナ別の操作)
5. [トラブルシューティング](#トラブルシューティング)
6. [データベース接続](#データベース接続)

---

## コンテナ構成

本システムは4つのコンテナで構成されています：

| コンテナ名 | 役割 | ポート | 備考 |
|-----------|------|--------|------|
| `youtube-analytics-streamlit` | Streamlit UI | 8501 | Webインターフェース |
| `youtube-analytics-app` | バッチ処理 | - | CLI実行用 |
| `youtube-analytics-mysql` | データベース | (非公開) | 内部ネットワークのみ |
| `youtube-analytics-adminer` | DB管理ツール | 8080 | データベース閲覧用 |

### ネットワーク構成
- すべてのコンテナは `youtube-analytics-network` ブリッジネットワークで接続
- MySQLポート3306は外部非公開（セキュリティ対策）
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

# MySQL設定
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=youtube_analytics
MYSQL_USER=user
MYSQL_PASSWORD=your_password
MYSQL_ROOT_PASSWORD=your_root_password

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

### 3. 初期化確認

MySQLが正常に起動し、`init.sql` によるテーブル作成が完了したことを確認：

```powershell
# MySQLコンテナのログを確認
docker-compose logs mysql

# Adminerでテーブルを確認
# ブラウザで http://localhost:8080 を開く
```

---

##基本操作

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
docker-compose logs mysql

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

### MySQLコンテナ

データベースを管理します。

```powershell
# MySQLクライアントに接続
docker exec -it youtube-analytics-mysql mysql -u root -p

# データベースのバックアップ
docker exec youtube-analytics-mysql mysqldump -u root -p youtube_analytics > backup.sql

# データベースのリストア
Get-Content backup.sql | docker exec -i youtube-analytics-mysql mysql -u root -p youtube_analytics

# テーブル一覧を確認
docker exec -it youtube-analytics-mysql mysql -u root -p -e "USE youtube_analytics; SHOW TABLES;"
```

### Adminerコンテナ

データベース管理用のWebインターフェースです。

```powershell
# アクセス
# ブラウザで http://localhost:8080

# ログイン情報
# システム: MySQL
# サーバ: mysql
# ユーザ名: root または user
# パスワード: .env で設定した値
# データベース: youtube_analytics
```

---

## トラブルシューティング

### コンテナが起動しない

```powershell
# エラーログを確認
docker-compose logs

# 特定のコンテナのエラーを確認
docker-compose logs mysql

# コンテナの状態を確認
docker-compose ps
```

### MySQLが起動しない

```powershell
# MySQLのヘルスチェック状態を確認
docker-compose ps mysql

# MySQLコンテナのログを確認
docker-compose logs mysql

# データベースを初期化してやり直す
docker-compose down -v
docker-compose up -d
```

### ポートが使用中

ポート8501、8080が既に使用されている場合：

```powershell
# 使用中のポートを確認
netstat -ano | findstr :8501
netstat -ano | findstr :8080

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

## データベース接続

### Adminer経由（推奨）

最も簡単な方法です：

1. ブラウザで http://localhost:8080 を開く
2. ログイン情報を入力：
   - **システム**: MySQL
   - **サーバ**: `mysql`
   - **ユーザ名**: `root` または `user`
   - **パスワード**: `.env` で設定した値
   - **データベース**: `youtube_analytics`

### MySQL CLI経由

```powershell
# rootユーザーで接続
docker exec -it youtube-analytics-mysql mysql -u root -p

# 一般ユーザーで接続
docker exec -it youtube-analytics-mysql mysql -u user -p youtube_analytics
```

接続後のSQL例：

```sql
-- データベース選択
USE youtube_analytics;

-- テーブル一覧
SHOW TABLES;

-- 動画一覧
SELECT * FROM videos;

-- コメント数の集計
SELECT video_id, COUNT(*) FROM comments GROUP BY video_id;

-- 感情分析結果の集計
SELECT sentiment, COUNT(*) FROM sentiment_results GROUP BY sentiment;
```

### アプリケーションから接続

Pythonスクリプトから接続する場合：

```python
import os
from app.repository.mysql import MySQLRepository

# 環境変数から接続情報を取得（docker-compose.ymlで自動設定）
repo = MySQLRepository()

# 動画情報を取得
videos = repo.fetch_all_videos()
```

---

## ボリューム管理

### マウントされているボリューム

| ホスト側 | コンテナ側 | 用途 |
|---------|-----------|------|
| `./app` | `/app` | ソースコード（ホットリロード） |
| `./data/json` | `/app/data/json` | JSONキャッシュ |
| `./logs` | `/app/logs` | ログファイル |
| `./models` | `/app/models` | 感情分析モデル |
| `./data/mysql` | `/var/lib/mysql` | MySQLデータ |
| `./init.sql` | `/docker-entrypoint-initdb.d/init.sql` | DB初期化スクリプト |

### データのバックアップ

```powershell
# MySQLデータベースのバックアップ
docker exec youtube-analytics-mysql mysqldump -u root -p youtube_analytics > backup_$(Get-Date -Format 'yyyyMMdd').sql

# ログファイルのバックアップ
Copy-Item -Recurse ./logs ./logs_backup_$(Get-Date -Format 'yyyyMMdd')

# モデルファイルのバックアップ
Copy-Item -Recurse ./models ./models_backup_$(Get-Date -Format 'yyyyMMdd')
```

---

## セキュリティに関する注意事項

### 現在のセキュリティ設定

- ✅ MySQLポート（3306）は外部非公開
- ✅ コンテナ間通信は内部ネットワークのみ
- ⚠️ Adminer（8080）は開発環境用（本番環境では無効化推奨）
- ⚠️ Streamlit（8501）は外部公開（開発環境用）

### 本番環境での推奨事項

本番環境にデプロイする場合：

1. **Adminerを無効化**
   ```yaml
   # docker-compose.ymlでコメントアウト
   # adminer:
   #   ...
   ```

2. **Streamlitに認証を追加**
   ```python
   # streamlit_app.py でパスワード認証を実装
   ```

3. **環境変数を安全に管理**
   - `.env` ファイルをGit管理外に
   - シークレット管理サービスの利用を検討

4. **リソース制限を設定**
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

# MySQLに接続
docker exec -it youtube-analytics-mysql mysql -u root -p

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
