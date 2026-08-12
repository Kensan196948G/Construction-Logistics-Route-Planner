# 外部評価（2026-08-05）への対応記録

外部評価（総合 45/100・PoC 段階・本番導入不可）の内容をコード・リポジトリ・
GitHub 実測と突き合わせ、優先度の高い指摘に対応した記録です。

## 1. 検証結果のまとめ

### 評価時点と現状の差分

評価は commit `538bcbe`（2026-08-05 時点の main）を対象としています。その
後の作業ツリーで以下はすでに実装済みです（コミット前・本番デプロイ前）。

| 評価の指摘 | 評価時点 | 現在の実装 |
|---|---|---|
| DB 未実装・プロセス内辞書 | 正しい | SQLAlchemy（SQLite/PostgreSQL）＋ Alembic 14 テーブル |
| 監査は最後の 1 イベントのみ | 正しい | `audit_logs` テーブルへ永続化 |
| 認証・RBAC なし | 正しい | OIDC/Entra ID JWT 検証＋ API キー fallback＋ 5 ロール |
| 外部 API 未接続 | 正しい | アダプタ層実装済み（OSM/xROAD/PLATEAU/KSJ はスタブ） |
| バックアップ・監視・障害対応なし | 正しい | docs 6 点で手順・設定を整備 |

### 今も有効な指摘（未対応の残課題）

- 実道路ネットワークによるルート探索なし（`generate_routes()` は直線距離×
  固定係数の疑似経路）
- リスク地物は `sample_overlay_features()` によるサンプル生成
- ナレッジ検索は決定論的キーワード応答（AI ではない）
- 確認・承認・差戻しワークフロー未実装
- PDF／Excel 帳票未実装（Markdown／CSV のみ）
- 実ブラウザ E2E 未実施（Chromium が SIGTRAP で起動しない環境のため jsdom
  ハーネスで代替）
- 外部 API の timeout／retry／circuit breaker／キャッシュ未実装
- 本番公開時の TLS・リバースプロキシ・Access/VPN は未設定（設計・文書のみ）

### 評価内容の訂正・補足

- **CI 状態**：評価時「combined status 取得不可」とありましたが、GitHub の
  run 一覧を実測したところ commit `538bcbe` の直近実行はすべて `success`
  （quality／package／dependency-audit）です。
- **テスト件数**：現状は Python 21 件＋ Node.js 5 件（jsdom ハーネス）。README／
  RELEASE_READINESS／state.json はこの数値に統一済みです。
- **Dependabot ラベル**：`.github/dependabot.yml` にはラベル定義がありますが、
  リポジトリに `dependencies`／`ci`／`security` ラベルが存在せず、既存 PR に
  付いていませんでした。ラベルを新規作成し、open 中の Actions 更新 PR 4 件
  （#13, #15, #16, #17）へ付与しました。
- **SECURITY.md**：評価時点のまま「永続化なし・エンタープライズ認証なし」と
  記述されていたため、現状（永続化・OIDC・監査ログ・サンプルモード本番利用
  禁止）へ更新しました。

## 2. 今回の対応（P0 優先）

### サンプル表示の常時明示（評価「今すぐ」1 件目）

- UI 全画面の上部帯とサイドバーに「【PoC・サンプル】本番利用禁止」を常時表示
- Markdown 帳票の冒頭に本番利用禁止の注意書き、CSV 帳票に `sample_notice` 列を追加
- `/api/health` に `sample_mode`・`sample_data_notice`、ナレッジ応答に
  `sample_data_notice` を追加
- `PRODUCTION_MODE=1` で文言を切り替え可能（実データ連携完了前に有効化しない
  ことを README・SECURITY.md に明記）

### 監査ヘッダー偽装の排除（評価「今すぐ」5 件目）

- API キー認証時に `x-user-id`／`x-user-role` ヘッダーを信用しないよう変更
- 本人識別はデプロイ設定 `APP_API_KEY_USER_ID`／`APP_API_KEY_USER_ROLE`
  （デフォルト `api-key-operator`／`planner`）から生成
- 未認証操作は `anonymous` として記録
- 偽装ヘッダーを送っても無視されることをテストで固定（`tests/test_auth.py`）

### systemd パスの修正（評価「低」1 件目）

- ユニットテンプレートを旧パスから現在のリポジトリパスへ修正し、`%h` を使用
- 実インストール済みユニット（`~/.config/systemd/user/`）も更新して
  `daemon-reload`・再有効化し、`http://127.0.0.1:18017/api/health` が 200 で
  稼働することを確認

### 文書・記録の整合

- README：サンプル明示・認証方式・テスト件数を更新
- RELEASE_READINESS：評価日現在の状態へ更新（サンプルモード本番利用禁止を明記）
- SECURITY.md：現状の構成とセキュリティ方針へ更新
- state.json：テスト件数（21＋5）と最終セッション記録を更新
- docs（backup-restore / monitoring / deployment）：リポジトリパスを実パスへ統一

## 3. 検証に使った実測値

| 項目 | 結果 |
|---|---|
| `pytest -q` | 21 passed（API 3 / 認証 3 / リスク 3 / 帳票 4 / ナレッジ 8） |
| `node tests/js/route_screen.test.mjs` | 5 passed |
| `ruff check app tests` | passed |
| GitHub Actions（`538bcbe` 直近 run） | すべて success |
| systemd（18017） | active・`/api/health` 200 |

## 4. 次フェーズの推奨着手順

評価の「最初の 1 スプリント」に沿い、以下を順に進めます。

1. PostgreSQL／PostGIS への切り替えと migration 本番適用
2. Entra ID テナント設定とロール別 API・UI テスト
3. 実ルーティング 1 系統（pgRouting または商用 Routing API）
4. OSM 実データを 1 地域だけ取り込み、橋梁・トンネル・学校を抽出
5. 確認・承認・差戻しと監査ログ検索 UI
6. 検証用現場 1 件での入力→PDF 出力 E2E

## 5. 残っている主な未対応事項

- 実ルート探索・実地物抽出（Phase 1 の中核）
- 確認・承認・差戻しワークフロー
- PDF／Excel 正式出力
- 実ブラウザ E2E・UAT（3 現場 3 車種）
- 外部 API 障害制御（timeout・retry・cache・失敗表示）
- rate limit・TLS・Access/VPN の本番適用
- 監査ログ検索・エクスポート UI
- xROAD・国土数値情報・PLATEAU 実連携（Phase 2）

---

## 6. 第 1 スプリント（2026-08-05 実施）の対応結果

評価の「次に着手すべき具体作業」6 項目を実装しました。

| # | 項目 | 結果 |
|---|---|---|
| 1 | PostgreSQL／PostGIS と migration | Alembic に PostGIS extension migration（`9f5c4e3b2a10`）を追加。docker-compose に `postgis/postgis:16-3.4` を同梱し `DATABASE_URL` 接続・`alembic upgrade head` 手順を整備。SQLite では migration がスキップされることをテストで確認 |
| 2 | Entra ID 認証と 4 ロール最小 RBAC | ロールを `admin` / `planner` / `site_user` / `viewer` に整理し、案件作成・ルート生成・評価・提出・差戻しは planner 以上、承認・監査ログは admin、リスク確認は site_user 以上に制限。`/api/me` を追加。権限制御はテストで固定 |
| 3 | 実ルーティング 1 系統 | OSRM アダプタを実装（`ROUTING_PROVIDER=osrm`、`OSRM_URL` 切替可）。実測で東京駅→日本橋の実道路ルート 1.5km を取得。失敗時はサンプルへフォールバックし API 応答に `mode`／`notes` を付与 |
| 4 | OSM 実データ取込（1 地域） | Overpass アダプタを実装（`OSM_OVERPASS_ENABLED=1`）。東京駅 500m 圏で実測 430 件（橋梁・トンネル・学校・病院）を取得。出典 URL・属性・取得日時・品質ランク C を保持し 6 時間キャッシュ。利用規約遵守のため本番は自前ホスト推奨を明記 |
| 5 | 確認・承認・差戻しと監査ログ | リスク確認（`confirmed` / `needs_review` / `not_applicable`）、案件提出（`review_required`）、承認（`reviewed`）、差戻し（`change_requested`）API を実装。すべて `audit_logs` に記録し、`GET /api/admin/audit-logs`（admin）で閲覧可能 |
| 6 | 架空現場で入力→PDF 出力の E2E | reportlab による PDF 帳票（`format=pdf`）を実装し、API レベル E2E（案件入力→ルート生成→評価→確認→提出→承認→PDF 取得）をテスト化。実ブラウザ E2E は Chromium 起動不可環境のため引き続き Playwright 未実施 |

### 追加で実施した対応

- バックアップ・監視スクリプトをリポジトリに追加：`scripts/backup_db.sh`（SQLite / pg_dump）、`scripts/restore_db.sh`、`scripts/monitor.sh`（実動作確認済み）
- `update_route` のリスク再保存時に評価結果の risk ID を保持するよう修正（同一セッションの stale リスク対策として `expire_all()` を追加）
- README・RELEASE_READINESS・state.json・operations/deployment/backup-restore/monitoring を実装内容へ同期

### 検証結果（このスプリント）

| 項目 | 結果 |
|---|---|
| `pytest -q` | 32 passed |
| `node tests/js/route_screen.test.mjs` | 5 passed |
| `ruff check .` | passed |
| OSRM 実測 | 東京駅→日本橋 1.5km・3 分（実道路ネットワーク） |
| Overpass 実測 | 東京駅 500m 圏で 430 件の実地物 |
| `alembic upgrade head` | state.db を `9f5c4e3b2a10` へ適用済み |
| backup / monitor | バックアップ作成成功・health 200 |

### 残課題（次スプリント以降）

- xROAD・国土数値情報・PLATEAU の実連携（アダプタはスタブのまま）
- Excel 帳票・実ブラウザ E2E・UAT（3 現場 3 車種）
- 商用 Routing API（HERE 等）または pgRouting への切替、規制属性の反映
- 監査ログ検索・エクスポート UI、承認フローの UI 実装
- TLS・rate limit・Access/VPN の本番適用
