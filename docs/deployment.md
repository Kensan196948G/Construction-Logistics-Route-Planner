# デプロイ手順書 (Deployment Guide)

## 前提条件

### ランタイム要件

| 要件 | バージョン | 確認コマンド |
|---|---|---|
| Python | 3.12 以上 | `python3 --version` |
| pip | 最新 | `python3 -m pip --version` |
| Git | 2.x | `git --version` |
| Docker (任意) | 24.x 以上 | `docker --version` |
| systemd (任意) | user unit 対応 | `systemctl --user --version` |

### ネットワーク要件

| ポート | 用途 | 方向 |
|---|---|---|
| 18017 | systemd 常駐 | INBOUND (0.0.0.0) |
| 28080 | Docker コンテナ | INBOUND (0.0.0.0) |

### ディスク要件

| リソース | 最低 | 推奨 |
|---|---|---|
| アプリケーション本体 | ~50MB | — |
| state.db (SQLite) | ~10MB | 1GB 空き |
| Docker イメージ | ~300MB | 2GB 空き |

---

## 環境セットアップ

### 1. リポジトリクローン

```bash
git clone https://github.com/Kensan196948G/Construction-Logistics-Route-Planner.git
cd Construction-Logistics-Route-Planner
```

### 2. Python 仮想環境作成

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 依存関係インストール

```bash
# 本番用（最小）
pip install .

# 開発用（test / lint ツール込み）
pip install -e ".[dev]"

# PostgreSQL 使用時（追加）
pip install -e ".[dev,pg]"
```

### 4. 環境変数設定

```bash
# 必須ではないが、必要に応じて設定
export APP_API_KEY="your-secret-key"  # API 認証保護（未設定時はスキップ）
export DATABASE_URL="sqlite+aiosqlite:///./state.db"  # デフォルト値のため省略可
```

### 5. 手動起動確認

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
# → http://127.0.0.1:8000/ で UI 表示確認
# → http://127.0.0.1:8000/api/health で health check
```

---

## データベースマイグレーション

### 概要

このプロジェクトでは Alembic による DB スキーマ管理を行います。マイグレーションスクリプトは `alembic/versions/` に配置され、`alembic/env.py` が `app.db_models.py` のテーブル定義 (`Base.metadata`) を参照します。

### DATABASE_URL 設定

Alembic は `DATABASE_URL` 環境変数を参照します（デフォルト: `sqlite+aiosqlite:///./state.db`）。`alembic.ini` 内の `sqlalchemy.url` はダミー値であり、実行時は環境変数が優先されます。

```bash
# SQLite（デフォルト）
export DATABASE_URL="sqlite+aiosqlite:///./state.db"

# PostgreSQL（将来拡張時）
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/construction_logistics"
```

### マイグレーション実行

```bash
# 【初回】DB を作成し、最新リビジョンまでマイグレーション適用
alembic upgrade head

# 現在のリビジョン確認
alembic current

# マイグレーション履歴表示
alembic history

# 新しいマイグレーションを自動生成（モデル変更後）
alembic revision --autogenerate -m "変更内容の簡潔な説明"

# 手動で空のマイグレーションを作成
alembic revision -m "変更内容の簡潔な説明"

# 1 つ前のリビジョンに戻す（ロールバック時）
alembic downgrade -1
```

### デプロイ前チェックリスト

- [ ] マイグレーションスクリプトが `alembic/versions/` に存在する
- [ ] `alembic upgrade head` がエラーなく完了する
- [ ] `alembic downgrade -1` → `alembic upgrade head` の往復が成功する
- [ ] ステージング環境でマイグレーション適用後の動作確認完了
- [ ] DB バックアップが取得済み

---

## アプリケーションデプロイ

本プロジェクトでは以下の 2 系統のデプロイ経路を提供します。ポートが異なるため同一ホストで同時稼働可能です。

### 方式 A: systemd (user unit)

#### 初回セットアップ

```bash
# 1. unit ファイルを user systemd ディレクトリにコピー
mkdir -p ~/.config/systemd/user
cp deploy/systemd/construction-logistics-route-planner.service \
   ~/.config/systemd/user/

# 2. unit ファイルの WorkingDirectory が正しいか確認
cat ~/.config/systemd/user/construction-logistics-route-planner.service

# 3. (必要に応じて) APP_API_KEY を unit ファイルに追記
# Environment=APP_API_KEY=your-key を [Service] セクションに追加

# 4. systemd 再読み込み
systemctl --user daemon-reload

# 5. サービス有効化 + 起動
systemctl --user enable construction-logistics-route-planner.service
systemctl --user start construction-logistics-route-planner.service

# 6. linger 有効化（ユーザーセッションなしでも起動させる）
loginctl enable-linger $USER
```

#### 日常的なデプロイ更新

```bash
# 1. 最新コードを pull
cd /home/kensan/Projects/Mirai-DX-Project/Construction-Logistics-Route-Planner
git pull origin main

# 2. 依存関係更新（変更があった場合のみ）
source .venv/bin/activate
pip install -e ".[dev]"

# 3. DB マイグレーション（変更があった場合のみ）
alembic upgrade head

# 4. サービス再起動
systemctl --user restart construction-logistics-route-planner.service

# 5. 状態確認
systemctl --user status construction-logistics-route-planner.service

# 6. 動作確認
curl -sf http://127.0.0.1:18017/api/health
```

#### トラブルシューティング

```bash
# ログ確認
journalctl --user -u construction-logistics-route-planner.service -f

# エラーのみ表示
journalctl --user -u construction-logistics-route-planner.service -p 3 -b

# サービスの完全停止 + 再起動
systemctl --user stop construction-logistics-route-planner.service
systemctl --user start construction-logistics-route-planner.service
```

### 方式 B: Docker (docker-compose)

#### 初回セットアップ

```bash
# イメージビルド
docker compose build

# コンテナ起動（バックグラウンド）
docker compose up -d

# 状態確認（health check が "healthy" になるまで待機）
docker compose ps

# DB マイグレーション適用（PostGIS extension + スキーマ）
docker compose exec webui alembic upgrade head

# ログ確認
docker compose logs -f
```

`docker-compose.yml` には `postgis/postgis:16-3.4` の `db` サービスが含まれ、
`webui` は `DATABASE_URL=postgresql+asyncpg://planner:planner@db:5432/route_planner`
で接続します。SQLite で動かす場合は `DATABASE_URL` を設定しないでください。
PostGIS は PostgreSQL 上で migration `9f5c4e3b2a10` により有効化されます。

#### 日常的なデプロイ更新

```bash
# 1. 最新コードを pull
git pull origin main

# 2. イメージ再ビルド + コンテナ再作成
docker compose build --no-cache
docker compose down
docker compose up -d

# 3. health 確認
docker compose ps
# STATUS が "healthy" になるまで待機

# 4. 動作確認
curl -sf http://127.0.0.1:28080/api/health
```

#### API Key 設定 (Docker)

```yaml
# docker-compose.yml
services:
  webui:
    environment:
      PYTHONUNBUFFERED: "1"
      APP_API_KEY: "your-secret-key"   # コメント解除 + 値設定
```

設定変更後は `docker compose up -d` で再起動。

#### トラブルシューティング

```bash
# コンテナが unhealthy の場合の詳細調査
docker inspect construction-logistics-route-planner | grep -A 10 Health

# コンテナ内で直接確認
docker compose exec webui python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health').read())"

# 完全クリーンビルド
docker compose down --rmi all
docker compose build --no-cache
docker compose up -d
```

---

## デプロイ後検証

### 必須確認項目

| No | 確認項目 | コマンド | 期待結果 |
|---|---|---|---|
| 1 | サービス稼働状態 | `systemctl --user status ...` / `docker compose ps` | active / healthy |
| 2 | Health API | `curl -sf http://127.0.0.1:18017/api/health` | 200 + `{"status":"ok"}` |
| 3 | ルートページ | `curl -sf -o /dev/null http://127.0.0.1:18017/` | 200 |
| 4 | 静的アセット | `curl -sf -o /dev/null http://127.0.0.1:18017/assets/vendor/leaflet/leaflet.js` | 200 |
| 5 | プロジェクト API（認証確認） | API Key 付きで `/api/projects` GET | 200 |
| 6 | ナレッジ検索 | `curl -sf -X POST ... /api/knowledge/search -d '{"query":"橋梁"}'` | 200 |
| 7 | DB 接続 | `sqlite3 state.db "PRAGMA integrity_check;"` | `ok` |
| 8 | エラーログ不在 | `journalctl --user -u ... -p 3 --since "1 min ago"` | 出力なし |

### スモークテスト手順

```bash
#!/bin/bash
# デプロイ後スモークテスト

set -e
BASE_URL="${1:-http://127.0.0.1:18017}"

echo "=== Health Check ==="
curl -sf "$BASE_URL/api/health" | python3 -m json.tool

echo "=== UI Index ==="
curl -sf -o /dev/null "$BASE_URL/"

echo "=== Static Assets ==="
curl -sf -o /dev/null "$BASE_URL/assets/vendor/leaflet/leaflet.js"

echo "=== Knowledge Search ==="
curl -sf -X POST "$BASE_URL/api/knowledge/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"橋梁制限"}' | python3 -m json.tool

echo "=== All smoke tests PASSED ==="
```

Docker 環境の場合は `http://127.0.0.1:28080` を指定。

---

## デプロイチェックリスト

### デプロイ前

- [ ] 全 CI ジョブが成功している（`.github/workflows/ci.yml`）
- [ ] `ruff check .` がパス
- [ ] `pytest` が全パス
- [ ] `python3 -m compileall app tests` がパス
- [ ] `bandit -q -r app` がパス（Critical/High なし）
- [ ] DB マイグレーションがある場合、`alembic upgrade head` / `alembic downgrade -1` の往復テスト済み
- [ ] DB バックアップ取得済み
- [ ] リリースノート / CHANGELOG の更新確認

### デプロイ実行

- [ ] `git pull origin main` で最新化
- [ ] `pip install -e ".[dev]"` で依存関係更新
- [ ] `alembic upgrade head` で DB マイグレーション適用（必要な場合）
- [ ] `systemctl --user restart ...` でサービス再起動
- [ ] Docker 更新（必要な場合）

### デプロイ後

- [ ] スモークテスト全項目 PASS
- [ ] ヘルスチェック 200 OK
- [ ] UI ブラウザ確認（ルート検討画面で地図表示されること）
- [ ] エラーログに新規エラーがないこと
- [ ] デプロイ時刻を記録
