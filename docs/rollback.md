# ロールバック手順書 (Rollback Procedures)

## ロールバック判断基準

以下のいずれかに該当する場合、ロールバックを実施する：

| 条件 | 判断 |
|---|---|
| デプロイ後 15 分以内に P1/P2 レベルの障害が発生 | 即時ロールバック |
| デプロイ後、`/api/health` が継続的に失敗 | 即時ロールバック |
| CI がすべて成功しているにも関わらず、本番で機能不全 | ロールバック + 原因調査 |
| デプロイ後、パフォーマンスが著しく劣化（応答時間 10 倍以上） | ロールバック |
| データベースマイグレーション失敗（`alembic upgrade head` エラー） | ロールバック（downgrade） |

### ロールバックを避けるべきケース

- データベースの前方互換性がない変更を含むマイグレーション適用後の downgrade は注意（特にカラム削除・型変更を含む場合、データ損失のリスクあり）
- その場合は、DB のバックアップからのフルリストアを前提とする

---

## データベースロールバック (Alembic downgrade)

### 前提

- Alembic によるマイグレーション管理が有効であること
- ロールバック対象のリビジョン番号が判明していること
- 本番 `DATABASE_URL` が正しく設定されていること

### 現在のリビジョン確認

```bash
# 現在の DB リビジョンを確認
alembic current

# 例:
# INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
# INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
# b1d15542540b (head)
```

### マイグレーション履歴確認

```bash
# 全リビジョンの履歴を表示
alembic history

# 例:
# b1d15542540b -> (head), initial schema
# <base> -> b1d15542540b, initial schema
```

### Downgrade 手順

```bash
# 【最重要】ダウングレード前に必ず DB バックアップを取得する
cp state.db backups/pre_rollback_state_$(date +%Y%m%d_%H%M%S).db

# 1 つ前のリビジョンに戻す
alembic downgrade -1

# 特定のリビジョンに戻す場合
alembic downgrade <revision_id>

# 完全に初期状態に戻す場合
alembic downgrade base
```

### Downgrade 時の注意事項

- **SQLite は `ALTER TABLE DROP COLUMN` を直接サポートしない**。Alembic の SQLite サポートは batch mode を使用するが、downgrade でカラム削除を含むマイグレーションを戻す場合、データ損失が発生する可能性がある。必ず事前バックアップを取得すること。
- PostgreSQL 使用時（将来の拡張時）はトランザクション DDL がサポートされるため、より安全に downgrade が可能。

### Downgrade 後の確認

```bash
# リビジョンが正しく戻ったか確認
alembic current

# DB 整合性チェック
sqlite3 state.db "PRAGMA integrity_check;"
# → "ok" が返れば正常

# テーブル一覧確認
sqlite3 state.db ".tables"

# サービス再起動
systemctl --user restart construction-logistics-route-planner.service

# health check
curl -sf http://127.0.0.1:18017/api/health
```

---

## アプリケーションロールバック (git revert + redeploy)

### 状況確認

```bash
# 現在のデプロイ状態確認
git log --oneline -5
git status
```

### 手順

```bash
# 1. ロールバック先のコミットを特定
git log --oneline -20

# 2. revert コミットを作成（問題のあるコミットを打ち消す）
#    単一コミットを revert
git revert <問題のコミットハッシュ>

#    複数コミットを revert（範囲指定、古い方..新しい方）
git revert <古いコミット>..<新しいコミット>

# 3. 品質確認（revert 後コードが CI を通過することを確認）
ruff check .
pytest
python3 -m compileall app tests
bandit -q -r app

# 4. コミットを push
git push origin main

# 5. リモートの最新を pull
git pull origin main

# 6. アプリケーション再起動
systemctl --user restart construction-logistics-route-planner.service

# 7. Docker も使用中の場合
docker compose down
docker compose build --no-cache
docker compose up -d
```

### 手動での強制リセット（緊急時）

```bash
# 【注意】作業中のローカル変更が失われるため、緊急時のみ使用
git fetch origin
git reset --hard <安全なコミットハッシュ>

# アプリケーション再起動
systemctl --user restart construction-logistics-route-planner.service

# Docker 再ビルド
docker compose build --no-cache && docker compose up -d
```

---

## Docker ロールバック (docker compose)

### イメージロールバック

```bash
# 1. 現在のイメージ一覧確認
docker images construction-logistics-route-planner

# 2. 直前のイメージをタグ付けして復元（ビルドキャッシュがある場合）
#    もしくは Git で以前のコミットに戻して再ビルド
git log --oneline -5
git checkout <安全なコミットハッシュ>

# 3. 再ビルド・再起動
docker compose build --no-cache
docker compose up -d

# 4. health 確認
docker compose ps
# STATUS が "healthy" であることを確認

# 5. 元のブランチに戻す（変更を破棄して）
git checkout main
```

### コンテナ設定ロールバック

`docker-compose.yml` の変更を元に戻す場合：

```bash
# 設定ファイルを Git の以前のバージョンに戻す
git checkout <安全なコミットハッシュ> -- docker-compose.yml

# 反映
docker compose down
docker compose up -d
```

---

## systemd ロールバック

### unit ファイルロールバック

```bash
# 1. 変更前の unit ファイルに戻す
git checkout <安全なコミットハッシュ> -- deploy/systemd/construction-logistics-route-planner.service

# 2. systemd に再読み込み
cp deploy/systemd/construction-logistics-route-planner.service \
   ~/.config/systemd/user/construction-logistics-route-planner.service
systemctl --user daemon-reload

# 3. 再起動
systemctl --user restart construction-logistics-route-planner.service

# 4. 状態確認
systemctl --user status construction-logistics-route-planner.service
```

---

## ロールバック検証手順

ロールバック実施後、以下の項目を確認する：

| No | 確認項目 | コマンド / 方法 | 期待結果 |
|---|---|---|---|
| 1 | サービス起動状態 | `systemctl --user status ...` / `docker compose ps` | active / healthy |
| 2 | Health check | `curl -sf http://127.0.0.1:18017/api/health` | 200 + `{"status":"ok"}` |
| 3 | 静的アセット配信 | `curl -sf -o /dev/null http://127.0.0.1:18017/` | 200 |
| 4 | プロジェクト一覧 API | `curl -sf -H "Authorization: Bearer $APP_API_KEY" http://127.0.0.1:18017/api/projects` | 200 |
| 5 | DB 接続 | `sqlite3 state.db "PRAGMA integrity_check;"` | `ok` |
| 6 | DB リビジョン | `alembic current` | 期待するリビジョン |
| 7 | ルート評価 | `curl -sf -H "Authorization: Bearer $APP_API_KEY" -X POST http://127.0.0.1:18017/api/knowledge/search -H "Content-Type: application/json" -d '{"query":"橋梁"}'` | 200 |
| 8 | エラーログ不在 | `journalctl --user -u ... -p 3 --since "5 min ago"` | 出力なし |
| 9 | Docker 環境（併用時） | `docker compose ps` + health check (port 28080) | healthy / 200 |

### ロールバック完了報告

ロールバックが完了したら、以下を記録する：

```
ロールバック実施記録
- 実施日時: YYYY-MM-DD HH:MM JST
- 実施者: [名前]
- ロールバック理由: [例: マイグレーション b1d15542540b の適用後、ルート生成 API が 500 エラー]
- ロールバック内容: [例: alembic downgrade -1 + systemctl restart]
- ロールバック前リビジョン: [revision_id]
- ロールバック後リビジョン: [revision_id]
- 検証結果: [すべての確認項目の結果]
- 復旧時間: X 分
- データ損失: あり / なし [ありの場合の詳細]
- 備考:
```