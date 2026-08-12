# バックアップ・リストア手順書 (Backup & Restore)

## バックアップ対象

| 対象 | パス | 内容 | 重要度 |
|---|---|---|---|
| DB ファイル | `state.db` | SQLite DB（全テーブル：users, projects, routes, risks, reports, audit_logs 等） | 高 |
| マイグレーション履歴 | `alembic/versions/` | Alembic マイグレーションスクリプト | 中（Git 管理） |
| systemd unit | `deploy/systemd/*.service` | サービス定義 | 低（Git 管理） |
| Docker 設定 | `docker-compose.yml`, `Dockerfile` | コンテナ設定 | 低（Git 管理） |
| 環境変数 | 環境変数（APP_API_KEY 等） | シークレット | 高（手動管理） |

> Git 管理されているファイルはリポジトリに復元可能ですが、緊急時の迅速な復旧のためバックアップに含めることを推奨します。

---

## バックアップスケジュール

### 推奨スケジュール

| 頻度 | 対象 | 保持期間 | 方法 |
|---|---|---|---|
| 日次 | `state.db` フルバックアップ | 7 世代（1 週間） | cron 自動 |
| 週次 | `state.db` + 設定ファイル一式 | 4 世代（1 ヶ月） | 手動 / cron |
| デプロイ直前 | `state.db` フルバックアップ | 直近 3 回分 | 手動 |
| マイグレーション直前 | `state.db` フルバックアップ | 永続（手動管理） | 手動必須 |

---

## データベースバックアップ

### 推奨バックアップディレクトリ構造

```
backups/
├── daily/
│   ├── state_20260718.db
│   ├── state_20260717.db
│   └── ...（7 世代保持）
├── weekly/
│   ├── state_week27_2026.db
│   └── ...（4 世代保持）
├── pre_deploy/
│   ├── state_pre_deploy_20260718_143000.db
│   └── ...（直近 3 回分）
└── pre_migration/
    └── state_pre_migration_b1d15542540b_20260718.db
```

### 手動バックアップ

```bash
# バックアップディレクトリ作成
mkdir -p backups/{daily,weekly,pre_deploy,pre_migration}

# 日次バックアップ
cp state.db backups/daily/state_$(date +%Y%m%d).db

# デプロイ前バックアップ
cp state.db backups/pre_deploy/state_pre_deploy_$(date +%Y%m%d_%H%M%S).db

# マイグレーション前バックアップ（必須）
cp state.db backups/pre_migration/state_pre_migration_$(date +%Y%m%d_%H%M%S).db

# バックアップファイルの圧縮（容量節約）
gzip backups/daily/state_$(date +%Y%m%d).db
```

### 自動バックアップスクリプト

リポジトリの `scripts/backup_db.sh` を使用します。SQLite（既定）と
PostgreSQL／PostGIS（`DATABASE_URL` 設定時は `pg_dump`）の両方に対応し、
7 世代保持・旧世代自動削除を行います。

```bash
PROJECT_DIR="/home/kensan/Projects/Mirai-DX-Project/Construction-Logistics-Route-Planner"
chmod +x "$PROJECT_DIR/scripts/backup_db.sh"
"$PROJECT_DIR/scripts/backup_db.sh"
```

### cron 登録

```bash
# crontab に追加
crontab -e

# 以下の行を追加（毎日 2:00 AM 実行）
0 2 * * * /home/kensan/Projects/Mirai-DX-Project/Construction-Logistics-Route-Planner/scripts/backup_db.sh >> /home/kensan/backups/backup.log 2>&1
```

PostgreSQL 使用時は `DATABASE_URL` を環境変数に設定した状態で実行します。
リストアは `scripts/restore_db.sh <backup-file>` を使用します。

---

## 設定ファイルバックアップ

```bash
#!/bin/bash
# 設定ファイルバックアップスクリプト（週次実行推奨）

PROJECT_DIR="/home/kensan/Projects/Mirai-DX-Project/Construction-Logistics-Route-Planner"
BACKUP_DIR="$PROJECT_DIR/backups/weekly"
TIMESTAMP=$(date +%Y%m%d)

mkdir -p "$BACKUP_DIR"

tar -czf "$BACKUP_DIR/config_${TIMESTAMP}.tar.gz" \
    -C "$PROJECT_DIR" \
    deploy/systemd/construction-logistics-route-planner.service \
    docker-compose.yml \
    Dockerfile \
    alembic.ini \
    pyproject.toml \
    .github/workflows/ci.yml

echo "[OK] Config backup created: $BACKUP_DIR/config_${TIMESTAMP}.tar.gz"
```

---

## リストア手順

### DB ファイルのリストア

```bash
# 1. アプリケーションの停止
systemctl --user stop construction-logistics-route-planner.service
docker compose down  # Docker も使用中の場合

# 2. 破損 DB の退避（調査用）
mv state.db state.db.broken.$(date +%Y%m%d_%H%M%S)

# 3. バックアップからリストア
# 非圧縮バックアップの場合
cp backups/daily/state_20260718.db state.db

# 圧縮バックアップの場合
gunzip -c backups/daily/state_20260718.db.gz > state.db

# 4. リストア後の整合性チェック
sqlite3 state.db "PRAGMA integrity_check;"
# → "ok" が返れば正常

# 5. テーブル一覧・データ件数確認
sqlite3 state.db ".tables"
sqlite3 state.db "SELECT COUNT(*) FROM projects;"

# 6. アプリケーション再起動
systemctl --user start construction-logistics-route-planner.service
docker compose up -d  # Docker も使用中の場合

# 7. 動作確認
curl -sf http://127.0.0.1:18017/api/health
```

### Docker 環境でのリストア

```bash
# Docker コンテナ内の DB をリストアする場合

# 1. コンテナ内の DB ファイル位置を確認
docker compose exec webui ls -la /app/state.db

# 2. バックアップファイルをコンテナにコピー
docker compose cp backups/daily/state_20260718.db webui:/tmp/restore.db

# 3. コンテナ内で置き換え
docker compose exec webui sh -c "cp /tmp/restore.db /app/state.db"

# 4. コンテナ再起動
docker compose restart

# 5. health 確認
docker compose ps
```

### 特定テーブルのみのリストア（上級者向け）

```bash
# 特定テーブルのみ復元する場合（例: projects テーブルのみ）
# 注意: 外部キー制約に違反しないよう、関連テーブルも考慮すること

sqlite3 backups/daily/state_20260718.db ".dump projects" > /tmp/restore_projects.sql
sqlite3 state.db < /tmp/restore_projects.sql
```

---

## バックアップ検証

### 日次自動検証

バックアップ作成後に以下の検証を実施する：

```bash
#!/bin/bash
# バックアップ検証スクリプト（backup-db.sh に組み込み推奨）

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "[ERROR] Backup file not found: $BACKUP_FILE" >&2
    exit 1
fi

# ファイルサイズ確認（0 バイトでないこと）
SIZE=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE" 2>/dev/null)
if [ "$SIZE" -lt 1024 ]; then
    echo "[ERROR] Backup file too small: $SIZE bytes" >&2
    exit 1
fi

# 圧縮ファイルの場合は展開してチェック
if [[ "$BACKUP_FILE" == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" > /tmp/backup_verify.db
    VERIFY_DB="/tmp/backup_verify.db"
else
    VERIFY_DB="$BACKUP_FILE"
fi

# 整合性チェック
if ! sqlite3 "$VERIFY_DB" "PRAGMA integrity_check;" | grep -q "ok"; then
    echo "[ERROR] Backup integrity check failed" >&2
    exit 1
fi

# 主要テーブルの行数確認
TABLE_COUNT=$(sqlite3 "$VERIFY_DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
echo "[OK] Backup verified: $SIZE bytes, $TABLE_COUNT tables, integrity ok"

# 一時ファイルの削除
[ -f /tmp/backup_verify.db ] && rm -f /tmp/backup_verify.db
```

### 月次リストア訓練

月に一度、最新のバックアップから実際にリストアし、アプリケーションが正常に動作することを確認する。手順:
1. 最新バックアップを別ディレクトリに展開
2. アプリケーションの別インスタンス（別ポート）で起動
3. health check と主要 API の疎通確認
4. UI の表示確認

---

## 保持ポリシー

### 保持ルール

| バックアップ種別 | 世代数 | 保存場所 | 自動削除 |
|---|---|---|---|
| 日次 | 7 世代 | `backups/daily/` | 7 日経過で自動削除 |
| 週次 | 4 世代 | `backups/weekly/` | 手動管理 |
| デプロイ前 | 直近 3 回分 | `backups/pre_deploy/` | 手動管理（古いものから削除） |
| マイグレーション前 | 永続 | `backups/pre_migration/` | 手動管理 |

### クリーンアップ手順

```bash
# 日次バックアップの古い世代を手動削除
find backups/daily/ -name "state_*.db.gz" -mtime +7 -delete

# デプロイ前バックアップを直近 3 回分に制限
ls -1t backups/pre_deploy/state_pre_deploy_* | tail -n +4 | xargs rm -f

# バックアップの合計サイズ確認
du -sh backups/
```

### 外部保管

重要なバックアップは、ローカル障害に備えて外部ストレージにも保管することを推奨：

```bash
# 例: 別サーバーに scp
scp backups/weekly/state_week*.db.gz user@backup-server:/backups/route-planner/

# 例: AWS S3 にアップロード（aws-cli 利用）
aws s3 cp backups/daily/state_$(date +%Y%m%d).db.gz \
  s3://my-backup-bucket/route-planner/daily/
```
