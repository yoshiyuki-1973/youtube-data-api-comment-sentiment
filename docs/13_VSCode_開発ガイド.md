# VS Code 開発ガイド

この資料は、本プロジェクトを Visual Studio Code で開発するための最小構成の手順と運用ルールをまとめたものです。

## 1. 対象ファイル

- 設定ファイル: .vscode/settings.json / .vscode/extensions.json / .vscode/launch.json / .vscode/tasks.json
- Dev Containers: .devcontainer/devcontainer.json
- 既存ドキュメント: docs/07\_開発ガイド.md など

## 2. 前提

- Windows + PowerShell を想定
- 実行環境は Docker（ローカル venv は使用しない）

## 3. 初回セットアップ

1. リポジトリを開く
2. 推奨拡張機能をインストール（Docker / Dev Containers）
3. .env を作成（.env.example を参考）
4. Docker Desktop を起動
5. 「Dev Containers: Reopen in Container」を実行
6. 必要に応じて Docker コンテナを起動（docker-compose.yml）

## 4. デバッグ/実行

- Dev Containers で開いた状態で実行する
- 「実行とデバッグ」で起動できる（コンテナ内 Python を使用）
  - `Pytest (tests)`
  - `Streamlit (app/streamlit_app.py)`
- Docker 操作はタスクから実行する
  - ビルド: `Docker: Compose Build`
  - 起動: `Docker: Compose Up`
  - 終了: `Docker: Compose Down`
  - Streamlit のログ: `Docker: Logs (streamlit)`
  - テスト: `Docker: Pytest (app)`
- 起動後のアクセス
  - Streamlit: http://localhost:8501
  - Adminer: http://localhost:8080

## 5. コーディング規約（概要）

- 文字コード: UTF-8
- 改行: LF
- インデント: スペース4
- 1行の目安: 100文字

## 6. テスト

- VS Code の Testing UI で pytest を実行
- テスト対象は tests 配下

## 7. よくある注意点

- .env はコミットしない
- data/mysql 配下は大量ファイルになるため、誤って操作しない
- GPU/大規模モデル利用時はローカル環境のリソースに注意
- VS Code の Python 実行はコンテナ内の Python を使う

## 8. 補足

- 追加の詳細は docs/07\_開発ガイド.md と docs/11_Docker操作ガイド.md を参照
