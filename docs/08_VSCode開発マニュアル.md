# VSCode開発マニュアル

VSCodeを使用したローカル開発環境のセットアップと開発ワークフローを説明する。

## 目次

1. [前提条件](#1-前提条件)
2. [初回セットアップ](#2-初回セットアップ)
3. [開発ワークフロー](#3-開発ワークフロー)
4. [よく使うコマンド](#4-よく使うコマンド)
5. [デバッグ方法](#5-デバッグ方法)
6. [コーディング規約](#6-コーディング規約)
7. [テスト実行](#7-テスト実行)
8. [トラブルシューティング](#8-トラブルシューティング)
9. [開発Tips](#9-開発tips)

---

## 1. 前提条件

本プロジェクトの実行・開発は **Dockerに一本化** している。

### 必須ツール

| ツール | バージョン | 用途 |
|--------|-----------|------|
| Docker Desktop | 最新版 | コンテナ環境 |
| Docker Compose | v2.0以上 | マルチコンテナ管理 |
| VSCode | 最新版 | エディタ |
| Git | 最新版 | バージョン管理 |

### 推奨VSCode拡張機能

#### 必須

| 拡張機能ID | 名称 | 用途 |
|-----------|------|------|
| ms-python.python | Python | Python言語サポート |
| ms-azuretools.vscode-docker | Docker | Docker管理 |

#### 推奨

| 拡張機能ID | 名称 | 用途 |
|-----------|------|------|
| ms-python.vscode-pylance | Pylance | 型チェック・補完 |
| ms-python.black-formatter | Black Formatter | コードフォーマット |
| ms-python.flake8 | Flake8 | リンター |
| ms-toolsai.jupyter | Jupyter | ノートブック対応 |
| ms-vscode-remote.remote-containers | Remote Containers | コンテナ内開発 |
| redhat.vscode-yaml | YAML | YAML編集 |
| tamasfe.even-better-toml | TOML | TOML編集 |
| donjayamanne.githistory | Git History | Git履歴 |
| eamodio.gitlens | GitLens | Git強化 |
| yzhang.markdown-all-in-one | Markdown All in One | Markdown編集 |

拡張機能のインストール:

```
VSCode コマンドパレット (Ctrl+Shift+P) → Extensions: Install Extensions
```

---

## 2. 初回セットアップ

### 2.1 リポジトリのクローン

```powershell
# リポジトリをクローン
git clone <repository-url>
cd youtube-data-api-comment-sentiment

# VSCodeで開く
code .
```

### 2.2 環境変数の設定

```powershell
# .env.exampleをコピー
Copy-Item .env.example .env

# .envを編集（必須項目を設定）
notepad .env
```

必須設定項目:

```env
YOUTUBE_API_KEY=your_api_key_here
```

### 2.3 Dockerイメージのビルド

```powershell
# イメージをビルド
docker compose build

# ビルドに成功したら起動
docker compose up -d
```

初回ビルドは5-10分程度かかる（モデルのダウンロード含む）。

### 2.4 動作確認

```powershell
# コンテナの状態確認
docker compose ps

# ログ確認
docker compose logs -f streamlit

# ブラウザでアクセス
# Streamlit: http://localhost:8501
```

---

## 3. 開発ワークフロー

### 基本的な開発サイクル

```
1. ブランチ作成
   ↓
2. コード編集（VSCode）
   ↓
3. ローカルテスト
   ↓
4. コミット & プッシュ
   ↓
5. プルリクエスト
```

### 3.1 新機能開発の開始

```powershell
# 最新のmainブランチを取得
git checkout main
git pull origin main

# 機能ブランチを作成
git checkout -b feature/your-feature-name
```

### 3.2 コードの編集

ソースコードは `./app/` にマウントされているため、VSCodeで編集すると**即座にコンテナ内に反映**される。

```
app/
├── main.py              # CLIエントリーポイント
├── streamlit_app.py     # Streamlit UI
├── fetch/youtube.py     # YouTube API
├── sentiment/analyzer.py # 感情分析
└── aggregate/summarizer.py # 集計
```

### 3.3 変更の確認

#### Streamlitの場合（自動リロード）

- ファイル保存時に自動でリロード
- ブラウザで http://localhost:8501 を確認

#### CLIの場合

```powershell
# コンテナ内でPythonスクリプトを実行
docker compose exec app python main.py --video-id <VIDEO_ID>
```

### 3.4 コミット

```powershell
# 変更を確認
git status

# ステージング
git add <files>

# コミット（わかりやすいメッセージで）
git commit -m "feat: 新機能の説明"

# プッシュ
git push origin feature/your-feature-name
```

#### コミットメッセージ規約

```
feat: 新機能
fix: バグ修正
docs: ドキュメント
style: フォーマット
refactor: リファクタリング
test: テスト追加
chore: その他
```

---

## 4. よく使うコマンド

### Docker操作

```powershell
# コンテナの起動
docker compose up -d

# コンテナの停止
docker compose down

# コンテナの再起動
docker compose restart

# 特定のコンテナを再起動
docker compose restart streamlit

# イメージの再ビルド
docker compose build

# キャッシュなしで再ビルド
docker compose build --no-cache

# コンテナのログを表示
docker compose logs -f

# 特定のコンテナのログ
docker compose logs -f streamlit
```

### コンテナ内でコマンド実行

```powershell
# コンテナ内でシェルを起動
docker compose exec app /bin/bash

# Pythonスクリプトを実行
docker compose exec app python main.py --video-id <VIDEO_ID>

# pytestを実行
docker compose exec app pytest
```

---

## 5. デバッグ方法

### 5.1 ログ出力によるデバッグ

```python
import logging

logger = logging.getLogger(__name__)

def your_function():
    logger.debug("デバッグ情報")
    logger.info("通常情報")
    logger.warning("警告")
    logger.error("エラー")
```

ログファイルの確認:

```powershell
# ホスト側から確認
Get-Content ./logs/app.log -Tail 50

# エラーログのみ
Get-Content ./logs/error.log
```

### 5.2 インタラクティブデバッグ

```python
# コード内にブレークポイントを設定
import pdb; pdb.set_trace()
```

実行:

```powershell
# -itオプションでインタラクティブモード
docker compose exec -it app python main.py --video-id <VIDEO_ID>
```

### 5.3 VSCode Remote - Containers

VSCode拡張「Remote - Containers」を使用すると、コンテナ内で直接VSCodeを使用できる。

```
1. Remote - Containers拡張をインストール
2. Ctrl+Shift+P → "Remote-Containers: Attach to Running Container"
3. youtube-analytics-app を選択
4. コンテナ内でVSCodeが起動
```

### 5.4 debugpy リモートデバッグ

Streamlitコンテナにはdebugpy（ポート5678）が設定されている。

```
1. VSCodeのデバッグパネルを開く
2. "Python: Remote Attach" を選択
3. host: localhost, port: 5678 に接続
```

### 5.5 Streamlitのデバッグ

```python
# streamlit_app.py内でst.write()を使用
import streamlit as st

st.write("デバッグ情報:", variable_name)
st.json(data)  # JSON形式で表示
```

---

## 6. コーディング規約

詳細は [05_詳細設計書.md](05_詳細設計書.md) の「4. 命名規約」を参照。

### 基本ルール

```python
# 関数名: snake_case
def fetch_comments(video_id: str) -> list[dict]:
    pass

# クラス名: PascalCase
class VideoAnalyzer:
    pass

# 定数: UPPER_SNAKE_CASE
MAX_COMMENT_LENGTH = 500

# プライベート変数: _prefix
_internal_cache = {}
```

### 型ヒント

```python
# 必ず型ヒントを記述
def classify_comment(text: str) -> dict:
    """
    コメントの感情を分類する

    Args:
        text: コメント本文

    Returns:
        {"positive": float, "negative": float, "neutral": float, "language": str}
    """
    pass
```

### docstring（Google Style）

```python
def aggregate_video(video: dict, comments: list[dict]) -> dict:
    """
    動画とコメントを集計する

    Args:
        video: 動画情報の辞書
        comments: コメントのリスト

    Returns:
        集計結果の辞書

    Raises:
        ValueError: 入力データが不正な場合
    """
    pass
```

---

## 7. テスト実行

```powershell
# 全テストを実行
docker compose exec app pytest

# 詳細出力付き
docker compose exec app pytest -v

# 特定のテストファイル
docker compose exec app pytest tests/test_analyzer.py

# カバレッジ付き
docker compose exec app pytest --cov=app --cov-report=html

# 失敗したテストのみ再実行
docker compose exec app pytest --lf

# 最初に失敗したテストで停止
docker compose exec app pytest -x
```

詳細は [07_テスト仕様書.md](07_テスト仕様書.md) を参照。

---

## 8. トラブルシューティング

### コンテナが起動しない

```powershell
# エラーログを確認
docker compose logs

# コンテナの状態を確認
docker compose ps

# コンテナとボリュームを削除して再作成
docker compose down -v
docker compose up -d --build
```

### Streamlitが更新されない

```powershell
# Streamlitコンテナを再起動
docker compose restart streamlit

# ブラウザのキャッシュをクリア（Ctrl+Shift+R）
```

### モジュールが見つからないエラー

```powershell
# requirements.txtを更新した場合は再ビルド
docker compose build app
docker compose up -d
```

### ポート競合エラー

```powershell
# ポート使用状況を確認
netstat -ano | findstr :8501

# 使用中のプロセスを終了
# または docker-compose.yml のポート番号を変更
```

### ディスク容量不足

```powershell
# 未使用のDockerリソースを削除
docker system prune -a

# 不要なイメージを削除
docker images
docker rmi <image-id>

# 未使用ボリュームを削除
docker volume prune
```

### Pythonパッケージの追加

```powershell
# 1. requirements.txtに追加
echo "new-package==1.0.0" >> requirements.txt

# 2. イメージを再ビルド
docker compose build app

# 3. コンテナを再起動
docker compose up -d
```

---

## 9. 開発Tips

### 9.1 ホットリロードの活用

`./app/` 配下のファイルはマウントされているため、保存するだけで変更が反映される。

- **Streamlit**: 自動リロード
- **CLI**: 再実行が必要

### 9.2 テストの高速化

```powershell
# 失敗したテストのみ再実行
docker compose exec app pytest --lf

# 最初に失敗したテストで停止
docker compose exec app pytest -x
```

### 9.3 Git管理のベストプラクティス

```powershell
# コミット前にチェック
git status              # 変更ファイル確認
git diff                # 差分確認
```

---

## 10. 関連ドキュメント

| ドキュメント | 内容 |
|-------------|------|
| [05_詳細設計書.md](05_詳細設計書.md) | モジュール仕様・命名規約 |
| [07_テスト仕様書.md](07_テスト仕様書.md) | テスト設計・テストケース |
| [09_運用手順書.md](09_運用手順書.md) | Docker運用・Azure デプロイ |
| [06_ディレクトリ構成.md](06_ディレクトリ構成.md) | プロジェクト構造 |
