# 障害対応文書 (Incident Response)

## 障害深刻度 (Severity Levels)

| レベル | 名称 | 定義 | 初動対応目標 | 復旧目標 |
|---|---|---|---|---|
| **P1** | 緊急 (Critical) | サービス完全停止。全ユーザーが全機能を利用不能。 | 15 分以内に検知・対応開始 | 1 時間以内 |
| **P2** | 高 (High) | 主要機能の一部が利用不能。または全ユーザーに影響する性能劣化。 | 30 分以内に対応開始 | 4 時間以内 |
| **P3** | 中 (Medium) | 一部ユーザー・一部機能に限定的影響。 | 翌営業日までに対応開始 | 3 営業日以内 |
| **P4** | 低 (Low) | 軽微な不具合。回避策あり。 | 次回リリースで対応 | 次回計画リリース |

### 本システムでの P1-P4 判定基準

| 事象 | レベル |
|---|---|
| `/api/health` が全経路（systemd + Docker）で 200 以外を返す | P1 |
| 特定の API エンドポイントが全リクエストで 500 エラー | P2 |
| `state.db` が破損し全データ参照不可 | P1 |
| OSM タイルサーバー障害（地図非表示） | P2 |
| 一部の `/api/projects` 操作がタイムアウト | P3 |
| API Key 認証設定ミスにより認証が通らない | P2 |
| UI の静的ファイルが一部 404（`assets/` の一部欠損） | P3 |
| レポート生成が特定の format で失敗 | P3 |

---

## 深刻度別対応手順

### P1 対応フロー

1. **検知**（自動ヘルスチェック失敗 / ユーザー通報）
2. **初動**（15 分以内）:
   - `journalctl --user -u construction-logistics-route-planner.service -f` でログ確認
   - `docker compose ps` でコンテナ状態確認
   - `curl -v http://127.0.0.1:18017/api/health` で詳細エラー取得
3. **原因特定**:
   - プロセス停止 → `systemctl --user restart construction-logistics-route-planner.service`
   - DB 破損 → バックアップからリストア（`docs/backup-restore.md` 参照）
   - ディスクフル → 不要ファイル削除後、再起動
   - 依存パッケージ破損 → `pip install -e ".[dev]"` 再実行
4. **復旧**: サービス再起動後に health check 成功確認
5. **報告**: 障害報告書作成（本ドキュメント末尾テンプレート）

### P2 対応フロー

1. **検知**: ユーザー通報 / 監視ツールアラート
2. **初動**（30 分以内）:
   - 影響範囲の切り分け（どのエンドポイントが失敗しているか）
   - エラーログ収集
3. **原因特定と復旧**:
   - DB 接続エラー → `app/db.py` の `DATABASE_URL` 環境変数確認
   - 外部 API 障害（OSM タイル等）→ 状況確認の上、影響をユーザーに通知
   - API Key 設定ミス → 環境変数修正後に再起動
4. **検証**: 全エンドポイントの疎通確認
5. **報告**: 必要に応じて障害報告

### P3 対応フロー

1. **検知**: ユーザー通報 / CI エラー
2. **記録**: GitHub Issue に起票
3. **対応**: 翌営業日までに原因調査・修正開始
4. **修正反映**: 通常のデプロイフローで反映

### P4 対応フロー

1. **記録**: Issue またはバックログに追加
2. **対応**: 次回計画リリースに含める

---

## 想定障害シナリオと復旧手順

### 1. 外部 API 停止 (OSM タイルサーバー障害)

**影響**: ルート検討画面の背景地図が表示されなくなる。API 自体は正常動作。

**検知方法**:
- UI で地図が白表示
- ブラウザ開発者ツールで `tile.openstreetmap.org` へのリクエストが失敗

**復旧手順**:

1. OSM タイルサーバーの稼働状況を確認: https://status.openstreetmap.org/
2. 一時的な回避策として地理院タイルに切り替え:
   ```
   app/static/component.js の afterRender() 内のタイル URL を
   'https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png' に変更
   ```
   反映にはアプリケーション再起動が必要。
3. 恒久対応として tile cache の検討（次フェーズ）

**復旧確認**:
- ブラウザでルート検討画面を開き、地図が表示されること
- タイル表示に `© OpenStreetMap contributors` または `© 国土地理院` の帰属表示があること

---

### 2. データベース接続障害

**影響**: 全 API エンドポイント（health を除く）が 500 エラー。案件作成・ルート生成・レポート出力がすべて失敗。

**検知方法**:
- health check は成功するが、他の API がエラーを返す
- アプリケーションログに `sqlalchemy.exc.OperationalError` が出力される

**復旧手順**:

```bash
# 1. ログ確認
journalctl --user -u construction-logistics-route-planner.service -n 50

# 2. DB ファイルの存在と権限確認
ls -la state.db
stat state.db

# 3. SQLite の整合性チェック
sqlite3 state.db "PRAGMA integrity_check;"

# 4. 破損している場合: 最新バックアップからリストア
cp state.db state.db.broken.$(date +%Y%m%d_%H%M%S)
cp backups/state_YYYYMMDD_HHMMSS.db state.db

# 5. サービス再起動
systemctl --user restart construction-logistics-route-planner.service

# 6. 動作確認
curl -s http://127.0.0.1:18017/api/health
```

**復旧確認**:
- `GET /api/projects` が 200 を返すこと
- 過去の案件データが参照可能であること

---

### 3. 認証サービス停止 (API Key 設定障害)

**影響**: `APP_API_KEY` が設定されている環境で、API Key が誤って削除・変更された場合、全 API 呼び出しが 401 を返す。

**検知方法**:
- API 呼び出しが `401 Unauthorized` を返す
- `/api/health` は正常（認証対象外のため）

**復旧手順**:

```bash
# systemd 環境の場合
# 1. 環境変数確認
systemctl --user show construction-logistics-route-planner.service | grep Environment

# 2. unit ファイルを修正
# deploy/systemd/construction-logistics-route-planner.service の
# Environment=APP_API_KEY=... 行を正しい値に修正

# 3. systemd 再読み込み + 再起動
systemctl --user daemon-reload
systemctl --user restart construction-logistics-route-planner.service

# 4. 動作確認
curl -H "Authorization: Bearer <正しいキー>" http://127.0.0.1:18017/api/projects
```

**Docker 環境の場合**:
```bash
# docker-compose.yml の APP_API_KEY を修正後
docker compose down && docker compose up -d
```

**復旧確認**: `GET /api/projects` が正しい API Key で 200 を返すこと。

---

### 4. 地図表示障害 (Leaflet / 静的アセット欠損)

**影響**: ルート検討画面で Leaflet が読み込まれず、地図領域にエラー表示。

**検知方法**:
- UI のルート検討画面で地図が表示されない
- ブラウザコンソールに `L is not defined` または Leaflet 関連の 404 エラー

**復旧手順**:

```bash
# 1. 静的アセットの存在確認
ls -la app/static/vendor/leaflet/leaflet.js
ls -la app/static/vendor/leaflet/leaflet.css

# 2. 欠損している場合: Git から再取得
git checkout -- app/static/vendor/leaflet/

# 3. パッケージ同梱確認（Docker 環境の場合）
python scripts/check_package_assets.py

# 4. 欠損時は Docker 再ビルド
docker compose build --no-cache && docker compose up -d

# 5. systemd 環境は再起動のみ
systemctl --user restart construction-logistics-route-planner.service

# 6. 動作確認
curl -sf -o /dev/null http://127.0.0.1:18017/assets/vendor/leaflet/leaflet.js && echo "OK"
```

**復旧確認**:
- ブラウザでルート検討画面を開き、地図が正常表示されること
- ブラウザコンソールに Leaflet 関連のエラーがないこと

---

## エスカレーション連絡先テンプレート

### 連絡先一覧

| 役割 | 名前 | 連絡手段 | エスカレーション条件 |
|---|---|---|---|
| 運用担当者 (Primary) | [未定] | [メール / Slack] | P1-P2 発生時 |
| 開発担当者 (Secondary) | [未定] | [メール / Slack / 電話] | P1 で Primary 不在時 |
| プロジェクト責任者 | [未定] | [メール / 電話] | P1 継続 2 時間以上 |

### 通知テンプレート

```
件名: [障害通知] Construction Logistics Route Planner - [P1/P2/P3/P4] [事象概要]

発生日時: YYYY-MM-DD HH:MM JST
深刻度: P1 / P2 / P3 / P4
状況: 発生中 / 復旧済

影響範囲:
- 影響エンドポイント: [例: /api/projects 全般]
- 影響ユーザー: [例: 全ユーザー]
- ビジネス影響: [例: 新規案件登録不可]

原因: 調査中 / [特定された原因]

対応状況: [実施中の対応 / 完了した対応]
復旧見込み: YYYY-MM-DD HH:MM JST

詳細ログ:
[関連ログ抜粋]

担当者: [名前] / [連絡先]
```

---

## ポストモーテム（障害振り返り）テンプレート

```
# 障害振り返り報告書

## 基本情報
- 発生日時: YYYY-MM-DD HH:MM JST
- 検知日時: YYYY-MM-DD HH:MM JST
- 復旧日時: YYYY-MM-DD HH:MM JST
- 継続時間: X 時間 Y 分
- 深刻度: P1 / P2 / P3 / P4
- 担当者: [名前]

## 影響
- 影響エンドポイント:
- 影響ユーザー数:
- データ損失の有無:

## タイムライン
| 時刻 | イベント |
|---|---|
| HH:MM | 障害発生 |
| HH:MM | 検知（自動 / 手動） |
| HH:MM | 対応開始 |
| HH:MM | 原因特定 |
| HH:MM | 復旧完了 |
| HH:MM | 動作確認完了 |

## 根本原因
[技術的な根本原因の詳細]

## 対応内容
[実施した復旧手順]

## 再発防止策
| No | 対策 | 担当 | 期限 |
|---|---|---|---|
| 1 | [具体的な対策] | [名前] | YYYY-MM-DD |
| 2 | [具体的な対策] | [名前] | YYYY-MM-DD |

## 学び・気づき
[チームとして得られた知見]
```