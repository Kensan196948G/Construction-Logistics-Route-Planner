# 運用文書 (Operations Guide)

## システム概要

Construction Logistics Route Planner（建設物流ルートプランナー）は、土木・建設工事における資材搬入・重機回送ルートの初期検討を支援する Web アプリケーションです。

### システム構成

| コンポーネント | 技術 | 用途 |
|---|---|---|
| Web フレームワーク | FastAPI 0.111+ / Python 3.12 | REST API + 静的ファイル配信 |
| ORM / DB | SQLAlchemy 2.0 (async) / SQLite (デフォルト) または PostgreSQL | 案件・ルート・リスク・監査ログ永続化 |
| DB マイグレーション | Alembic 1.13+ | スキーマ変更管理 |
| クライアント | SPA (app/static/): dc-runtime.js + Leaflet + OSM タイル | 9 画面のシングルページ UI |
| CI/CD | GitHub Actions (.github/workflows/ci.yml) | lint / test / security scan / package check |
| デプロイ経路 | systemd (user unit) + Docker (docker-compose) | ポート分離による 2 系統同時稼働 |

### エンドポイント一覧

| メソッド | パス | 用途 | 認証 |
|---|---|---|---|
| GET | `/` | SPA UI | なし |
| GET | `/api/health` | サービス状態確認 | なし |
| GET | `/api/me` | 現在の利用者情報 | API Key / OIDC |
| GET | `/api/projects` | 案件一覧 | API Key |
| POST | `/api/projects` | 案件作成（planner 以上） | API Key / OIDC |
| GET | `/api/projects/{id}` | 案件詳細 | API Key |
| POST | `/api/projects/{id}/routes/generate` | ルート候補生成（planner 以上） | API Key / OIDC |
| GET | `/api/projects/{id}/routes` | 案件内ルート一覧 | API Key |
| GET | `/api/routes/{id}` | ルート詳細 | API Key |
| POST | `/api/routes/{id}/evaluate` | リスク評価（planner 以上） | API Key / OIDC |
| GET | `/api/routes/{id}/risks` | 注意箇所一覧 | API Key |
| POST | `/api/routes/{id}/risks/{risk_id}/confirm` | リスク確認ステータス更新（site_user 以上） | API Key / OIDC |
| POST | `/api/projects/{id}/submit` | 案件提出（planner 以上） | API Key / OIDC |
| POST | `/api/projects/{id}/approve` | 承認（admin） | API Key / OIDC |
| POST | `/api/projects/{id}/request-changes` | 差戻し（planner 以上） | API Key / OIDC |
| GET | `/api/projects/{id}/report?format=md\|csv\|pdf` | レポート出力（PDF 含む） | API Key |
| GET | `/api/admin/data-sources` | データソース一覧 | API Key |
| GET | `/api/admin/audit-logs` | 監査ログ（admin） | API Key / OIDC |
| POST | `/api/knowledge/search` | ナレッジ検索 | なし |

### デプロイ経路とポート

| 方式 | ポート | 管理コマンド | 用途 |
|---|---|---|---|
| systemd (user unit) | 18017 | `systemctl --user {start,stop,restart,status}` | OS 常駐・自動起動 |
| Docker (docker-compose) | 28080 → 8000 | `docker compose {up,down,build,logs}` | 隔離・再現可能デプロイ |

### 主要外部依存

| 依存 | 現状 | 障害時影響 |
|---|---|---|
| SQLite (state.db) | ローカルファイル | DB 損傷時は全データ消失。バックアップ必須 |
| OSM タイルサーバー | tile.openstreetmap.org | 障害時は地図表示不可（SPA のルート検討画面が白地図） |
| Python パッケージ | fastapi, uvicorn, sqlalchemy, alembic 等 | 実行環境の破損は起動不能 |

---

## 日常運用手順チェックリスト

### 始業時チェック（毎日）

- [ ] `GET /api/health` が 200 `{"status": "ok"}` を返すことを確認
- [ ] systemd サービス稼働確認: `systemctl --user status construction-logistics-route-planner.service`
- [ ] Docker コンテナ稼働確認（使用中の場合）: `docker compose ps` で `healthy` 表示
- [ ] ディスク空き容量確認: `df -h /home/kensan/` — `state.db` の増加を監視
- [ ] `state.db` ファイルサイズ確認: `ls -lh state.db`

### 終業時チェック（毎日）

- [ ] 本日の監査ログ件数確認（必要な場合）: アプリケーションログから action 別集計
- [ ] 当日の異常イベント有無を journalctl で確認
- [ ] `state.db` バックアップ（日次バックアップ手順に従う）

### 週次チェック

- [ ] CI（GitHub Actions）の直近実行がすべて成功していることを確認
- [ ] Dependabot / pip-audit の脆弱性アラートがないことを確認
- [ ] バックアップファイルの保持状態確認（7 世代分あるか）
- [ ] `ruff check .` / `pytest` をローカル実行し、品質ゲート通過を確認

---

## データソース管理

### 管理エンドポイント

```bash
# データソース一覧取得
curl -H "Authorization: Bearer $APP_API_KEY" http://127.0.0.1:18017/api/admin/data-sources
```

### 現在のデータソース（MVP）

| ID | 名称 | 状態 | 備考 |
|---|---|---|---|
| `sample-osm` | OpenStreetMap サンプルオーバーレイ | stub | MVP では外部 API 未接続 |
| `sample-xroad` | xROAD サンプルオーバーレイ | stub | 次フェーズ対象 |
| `sample-ksj` | 国土数値情報サンプルオーバーレイ | stub | 次フェーズ対象 |

### データソース追加手順（将来拡張時）

1. `app/models.py` に新規 `DataSource` モデル定義を追加
2. `alembic revision --autogenerate -m "add_new_datasource"` でマイグレーション作成
3. `alembic upgrade head` で適用
4. `app/main.py` の `GET /api/admin/data-sources` にエントリ追加

---

## ユーザー管理

### 現状（MVP）

MVP では 2 方式の認証を実装しています。

- **OIDC / Entra ID**: `ENTRA_TENANT_ID`／`ENTRA_CLIENT_ID` 設定時に JWT 検証。
  ロールは `roles` クレームから抽出（admin / planner / site_user / viewer）
- **API Key fallback**: `APP_API_KEY` 設定時に `Authorization: Bearer <APP_API_KEY>` を要求。
  監査用の本人識別はクライアントヘッダーではなく `APP_API_KEY_USER_ID`／
  `APP_API_KEY_USER_ROLE`（デフォルト `api-key-operator`／`planner`）から生成
- 未設定時はローカル評価用に認証スキップ（`anonymous` として監査記録）
- `/api/health` と `/api/knowledge/search` は認証対象外

### ロールと主な権限

| ロール | 閲覧 | 案件作成・評価・提出・差戻し | リスク確認 | 承認・監査ログ |
|---|---|---|---|---|
| viewer | ✅ | — | — | — |
| site_user | ✅ | — | ✅ | — |
| planner | ✅ | ✅ | ✅ | — |
| admin | ✅ | ✅ | ✅ | ✅ |

ユーザー管理画面からの操作は未実装です。`app/db_models.py` の `User` テーブルは
今後の管理画面・協力会社ポータル用に用意しています。

### API Key 設定

```bash
# systemd の場合: deploy/systemd/*.service の Environment 行に追記
Environment=APP_API_KEY=your-secret-key

# Docker の場合: docker-compose.yml の environment セクションを有効化
environment:
  APP_API_KEY: "your-secret-key"
```

### 将来拡張予定（フェーズ 3）

- ユーザー一覧・招待・権限変更画面
- ロール別 API・UI テストの本番適用

---

## ログ監視

### systemd ログ（journalctl）

```bash
# リアルタイム追従
journalctl --user -u construction-logistics-route-planner.service -f

# 本日分の全ログ
journalctl --user -u construction-logistics-route-planner.service --since today

# 直近 100 行
journalctl --user -u construction-logistics-route-planner.service -n 100

# エラーのみ抽出
journalctl --user -u construction-logistics-route-planner.service -p 3 -b
```

### Docker ログ

```bash
# リアルタイム追従
docker compose logs -f

# 直近 100 行
docker compose logs --tail 100
```

### 監査ログ（audit_logs テーブル）

アプリケーション内の操作は `audit_logs` テーブルに記録されます。主な action 種別:
- `project_created`: 案件作成
- `routes_generated`: ルート候補生成
- `route_evaluated`: リスク評価実行

ログ項目: `user_id`, `user_role`, `action`, `target_type`, `target_id`, `details`, `ip_address`, `user_agent`, `created_at`

### 注意すべきログパターン

| パターン | 意味 | 対処 |
|---|---|---|
| `sqlalchemy.exc.OperationalError` | DB 接続エラー | 障害対応 P2 |
| `HTTPException: 401` | API Key 不一致 | 設定確認 |
| `HTTPException: 404` | リソース不在（通常範囲内） | 高頻度時は調査 |
| `sqlalchemy.exc.IntegrityError` | DB 整合性違反 | データ修復要 |

---

## パフォーマンス監視

### 観測ポイント

| メトリクス | 取得方法 | 閾値 |
|---|---|---|
| レスポンス時間 | uvicorn アクセスログ | GET /api/health: <100ms, POST: <5s |
| DB ファイルサイズ | `ls -lh state.db` | >1GB で警告 |
| メモリ使用量 | `ps aux \| grep uvicorn` または Docker stats | >1GB で警告 |
| リクエスト数 | journalctl のアクセスログ集計 | 異常スパイク検出 |
| コネクション数 | `ss -tnp \| grep <port>` | 異常増加検出 |

### 簡易監視スクリプト

```bash
#!/bin/bash
# 5 分間隔で health check し、失敗時に標準エラー出力

while true; do
  if ! curl -sf -o /dev/null http://127.0.0.1:18017/api/health; then
    echo "[$(date -Iseconds)] HEALTH CHECK FAILED" >&2
  fi
  sleep 300
done
```

---

## バックアップ手順

### 手動バックアップ

```bash
# DB ファイルのバックアップ
cp state.db backups/state_$(date +%Y%m%d_%H%M%S).db

# Docker 環境の場合
docker compose exec webui cp /app/state.db /tmp/state_backup.db
docker compose cp webui:/tmp/state_backup.db ./backups/
```

### バックアップ元ファイル

| ファイル | 内容 | 頻度 |
|---|---|---|
| `state.db` | SQLite DB（全テーブル） | 日次 + 変更前 |
| `alembic/versions/` | マイグレーション履歴 | Git 管理 |
| `deploy/systemd/*.service` | systemd unit 定義 | Git 管理 |
| `docker-compose.yml` | Docker 設定 | Git 管理 |
| `.env` (存在する場合) | 環境変数 | 手動 |

詳細は `docs/backup-restore.md` を参照。

---

## ヘルスチェックエンドポイント

### エンドポイント

```
GET /api/health
```

### 正常レスポンス

```json
{
  "status": "ok",
  "service": "construction-logistics-route-planner",
  "version": "0.1.0",
  "disclaimer": "本システムは..."
}
```

ステータスコード: `200`

### 確認スクリプト

```bash
# 簡易確認
curl -s http://127.0.0.1:18017/api/health | python3 -m json.tool

# 双方のデプロイ経路確認
curl -sf http://127.0.0.1:18017/api/health && echo "systemd OK"
curl -sf http://127.0.0.1:28080/api/health && echo "Docker OK"
```

### 自動ヘルスチェック

Docker コンテナはビルトイン `HEALTHCHECK` により 30 秒間隔で `/api/health` を監視します。`docker compose ps` で `healthy` / `unhealthy` 状態を確認できます。
