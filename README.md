# YouTubeコメント感情分析システム

YouTube Data APIを利用した動画コメントの感情分析・集計システム

## 概要

このシステムは、YouTube動画のコメントを収集し、感情分析（ポジティブ/ネガティブ/ニュートラル）を行い、集計結果をMySQLに保存します。

**主な機能:**

- YouTube Data API v3によるコメント取得
- 多言語対応の感情分析（日本語・その他言語）
- Streamlitによる可視化
- Docker Composeによる簡単なセットアップ

## 作者

- 遠藤義之

## 前提条件

- Docker / Docker Compose
- YouTube Data API v3 のAPIキー

本プロジェクトの実行・開発は **Dockerに一本化** しています。

※ 開発者向けの詳細なセットアップ手順は [docs/07\_開発ガイド.md](./docs/07_開発ガイド.md) を参照

## クイックスタート

### 1. 環境変数の設定

`.env.example` をコピーして `.env` を作成し、各値を設定する。

```bash
cp .env.example .env
```

必須設定項目：

- `YOUTUBE_API_KEY`: YouTube Data API v3のAPIキー
- `MYSQL_PASSWORD`: MySQLパスワード
- `MYSQL_ROOT_PASSWORD`: MySQL rootパスワード

### 2. ビルドして起動

```bash
# ビルドと起動を同時に実行（初回）
docker compose up --build

# バックグラウンドで起動する場合
docker compose up -d --build
```

停止する場合：

```bash
docker compose down
```

### 3. 環境変数の詳細

| 変数名                | 説明                         | デフォルト値      |
| --------------------- | ---------------------------- | ----------------- |
| `YOUTUBE_API_KEY`     | YouTube Data API v3のAPIキー | **必須**          |
| `MYSQL_PASSWORD`      | DBパスワード                 | **必須**          |
| `MYSQL_ROOT_PASSWORD` | DB rootパスワード            | **必須**          |
| `MYSQL_HOST`          | MySQLホスト名                | mysql             |
| `MYSQL_PORT`          | MySQLポート                  | 3306              |
| `MYSQL_DATABASE`      | データベース名               | youtube_analytics |
| `MYSQL_USER`          | DBユーザー名                 | app_user          |
| `MYSQL_POOL_SIZE`     | 接続プールサイズ             | 5                 |
| `COMMENT_LIMIT`       | コメント取得件数             | 10                |

## 使い方

### CLI（コマンドライン）

#### 単一動画の分析

```bash
docker compose exec app python main.py --video-id VIDEO_ID
```

#### コメント取得件数を指定

```bash
docker compose exec app python main.py --video-id VIDEO_ID --comment-limit 50
```

#### 複数動画の分析（カンマ区切り）

```bash
docker compose exec app python main.py --video-ids VIDEO_ID1,VIDEO_ID2,VIDEO_ID3
```

### Webインターフェース

### 起動後のアクセスURL

- Streamlit: http://localhost:8501
- Adminer: http://localhost:8080

#### Streamlit（可視化ダッシュボード）

ブラウザで http://localhost:8501 にアクセス

- 動画IDを入力して分析実行
- 感情分析結果をグラフ表示
- コメント一覧を表示

#### Adminer（データベース管理）

ブラウザで http://localhost:8080 にアクセス

- システム: MySQL
- サーバー: mysql
- ユーザー名: root または .envで設定したユーザー名
- パスワード: .envで設定した値
- データベース: youtube_analytics

※ MySQLポート3306は外部非公開のため、Adminer経由でのアクセスを推奨

## Docker操作

### イメージのビルド

```bash
# 通常のビルド
docker compose build

# キャッシュを使わずにビルド
docker compose build --no-cache
```

### コンテナ起動

```bash
# フォアグラウンドで起動
docker compose up

# バックグラウンドで起動
docker compose up -d

# コンテナ停止
docker compose down
```

詳細は [docs/11_Docker操作ガイド.md](./docs/11_Docker操作ガイド.md) を参照

## 感情分析について

本システムは、Hugging Faceの公開モデルを使用した感情分析を行います：

### 使用モデル

- **日本語モデル1**: `christian-phu/bert-finetuned-japanese-sentiment` (3クラス分類)
- **日本語モデル2**: `kit-nlp/bert-base-japanese-sentiment-irony` (2クラス分類、皮肉検出)
- **多言語モデル**: `cardiffnlp/twitter-xlm-roberta-base-sentiment` (Twitter感情分析)

### アンサンブル方式

- 日本語コメント：日本語モデル2つのアンサンブル
- その他言語：多言語モデル
- ルールベース分類：200以上のパターンで補完

詳細は [docs/08\_感情分析仕様書.md](./docs/08_感情分析仕様書.md) を参照

## ディレクトリ構成

```
.
├── docker-compose.yml      # Docker設定
├── Dockerfile              # Dockerfile
├── .env                    # 環境変数（要作成）
├── .env.example            # 環境変数テンプレート
├── init.sql                # DB初期化スクリプト
├── requirements.txt        # Python依存パッケージ
├── pytest.ini              # pytest設定
├── app/
│   ├── main.py             # CLIエントリーポイント
│   ├── streamlit_app.py    # Streamlit WebアプリUI
│   ├── fetch/              # YouTube API取得
│   │   └── youtube.py
│   ├── sentiment/          # 感情分析
│   │   └── analyzer.py
│   ├── aggregate/          # 集計処理
│   │   └── summarizer.py
│   └── repository/         # DB操作（接続プール対応）
│       └── mysql.py
├── data/
│   ├── json/               # 中間JSON出力
│   └── mysql/              # MySQLデータ永続化
├── docs/                   # 設計ドキュメント
├── logs/                   # ログ出力
├── models/                 # 感情分析モデル
│   └── sentiment-finetuned/  # Fine-tunedモデル（学習後に作成）
└── tests/                  # テストコード
    ├── conftest.py
    ├── test_analyzer.py
    ├── test_fetch.py
    ├── test_repository.py
    ├── test_summarizer.py
    └── test_truncate.py
```

## 主な機能

- **YouTube Data API連携**: 動画情報とコメントの自動取得
- **多言語感情分析**: 日本語専用モデル2つ + 多言語モデル1つのアンサンブル
- **ルールベース分類**: 200以上のパターンマッチングで精度向上
- **データ永続化**: MySQLでの履歴管理
- **可視化**: Streamlitによるインタラクティブなダッシュボード
- **接続プール**: 安定したDB接続管理
- **テスト**: pytestによる自動テスト

## テスト実行

```bash
# すべてのテストを実行
docker compose exec app pytest

# カバレッジ付きでテスト実行
docker compose exec app pytest --cov=app --cov-report=html

# 特定のテストファイルのみ実行
docker compose exec app pytest tests/test_analyzer.py
```

## ドキュメント

詳細な設計ドキュメントは [docs/](./docs/) を参照。

### 開発者向けドキュメント（推奨）

- **[07\_開発ガイド](./docs/07_開発ガイド.md)** - VSCodeでのローカル開発手順（最初に読む）
- **[06\_命名規約](./docs/06_命名規約.md)** - コーディング規約
- **[09\_単体テスト仕様書](./docs/09_単体テスト仕様書.md)** - テスト方法

### 全ドキュメント一覧

| ドキュメント                                          | 内容                                  |
| ----------------------------------------------------- | ------------------------------------- |
| [01\_要件定義書](./docs/01_要件定義書.md)             | 機能要件・非機能要件・APIクォータ対策 |
| [02\_基本設計書](./docs/02_基本設計書.md)             | Docker構成・ネットワーク設計          |
| [03\_詳細設計書](./docs/03_詳細設計書.md)             | モジュール構成・関数仕様              |
| [04\_データ仕様書](./docs/04_データ仕様書.md)         | JSONスキーマ・テーブル定義            |
| [05\_ディレクトリ構成](./docs/05_ディレクトリ構成.md) | プロジェクト構造の詳細説明            |
| [06\_命名規約](./docs/06_命名規約.md)                 | コーディング規約                      |
| [07\_開発ガイド](./docs/07_開発ガイド.md)             | VSCodeでのローカル開発手順            |
| [08\_感情分析仕様書](./docs/08_感情分析仕様書.md)     | 感情分析アルゴリズム・多言語対応      |
| [09\_単体テスト仕様書](./docs/09_単体テスト仕様書.md) | テスト方針・テストケース              |
| [10\_運用設計書](./docs/10_運用設計書.md)             | ログ設計・障害対応                    |
| [11_Docker操作ガイド](./docs/11_Docker操作ガイド.md)  | Docker環境の構築・運用方法            |

## トラブルシューティング

### APIクォータ超過エラー

```
APIクォータ超過またはコメントが無効です
```

- YouTube Data APIの1日のクォータ（10,000ユニット）を超過しています
- 翌日まで待つか、Google Cloud Consoleでクォータ増量をリクエストしてください

### MySQL接続エラー

```
MySQL接続プール作成エラー
```

- `.env`ファイルのMySQL設定を確認してください
- MySQLコンテナが起動しているか確認: `docker compose ps`

### 感情分析モデルエラー

- デフォルトではHugging Faceの公開モデルを使用します
- モデルロードに失敗した場合はルールベース分類にフォールバックします
- 初回起動時はモデルのダウンロードに時間がかかる場合があります
