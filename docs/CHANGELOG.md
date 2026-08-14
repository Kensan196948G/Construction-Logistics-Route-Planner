# 変更履歴

## 2026-08-14（追補）— ライトUI統一・本番ドメインの配信

- サイドバーとヘッダーをダーククロームからライトテーマへ統一（全体ライトモード）。
  Firefox E2E に computed style の回帰アサーションを追加
- 本番ドメイン `https://route-planner.mirai-dx-platform.com` の Cloudflare Tunnel
  （`route-planner`）を起動し、1033 エラーを解消。現状は MVP と同一の
  サンプルモードアプリを配信（本番運用化は対象外のまま）
- `deploy/cloudflared/*.example.yml` を追加（Tunnel 構成の再現用）

## 2026-08-14 — MVP operable sprint（CRUD・検索・Excel・E2E・デモ seed）

ブランチ: `feat/mvp-crud-excel-search`

### 修正・改善
- 案件管理: `PATCH /api/projects/{id}`（draft / evaluating / change_requested のみ）と
  `DELETE /api/projects/{id}`（論理削除＝`archived`。履歴・ルート・監査ログは保持）
- 一覧・検索: `GET /api/projects` を `{items,total,limit,offset}` 形式に拡張
  （`q` / `status` フィルタ）、`GET /api/projects/stats`、案件ごとの
  `risk_summary`（最新世代の候補/要確認/データ不足件数）
- Excel 帳票: `format=xlsx`（概要・ルート比較・注意箇所・免責の4シート、
  openpyxl、数式インジェクション中和）
- 監査: `GET /api/admin/audit-logs` に `q` / `action` / `user_id` / `offset` を追加。
  管理画面に検索・CSV エクスポート UI
- 施設辞書: `GET /api/facilities`（`knowledge_points` 読取り専用）を追加し、
  周辺施設辞書画面を DB 連携に変更
- ダミーデータ: `scripts/seed_demo.py`（冪等・`seed-` プレフィックス）。
  架空ユーザー4名・案件8件・ルート32候補・リスク140件・帳票・データソース5件・
  施設辞書8件・監査ログを参照整合性付きで投入
- UI: ダッシュボードの検索/フィルタ/ページング/編集/保管、Excel ダウンロード、
  監査ログ検索 UI、PoC ロール表示、編集モード、案件画面の成功通知表示。
  既存の `fmt` TDZ バグ（実ブラウザで全画面が白紙になる）を修正
- E2E: Playwright + Firefox headless の実ブラウザテスト8シナリオ
  （`tests/e2e/browser_smoke.mjs`）と CI `e2e` ジョブ。Chromium は本環境で
  SIGTRAP のため Firefox を使用
- 認証: PoC 限定の `POC_ANONYMOUS_ROLE`（既定 `planner`）を追加。
  本番フェイルクローズは不変
- テスト: Python 59 / Node 18 / ブラウザ 8。ruff・bandit・compileall・wheel・
  pip-audit すべて合格

## 2026-08-12 — 総合評価対応（改善スプリント）

ブランチ: `improve/production-readiness-eval`

### 修正・改善
- 配信条件・回避条件の永続化（新カラム 5 本 + JSON、Alembic migration `b2c3d4e5f6a7`）
- 案件所有者（owner_user_id）の記録、FK インデックス 12 本
- `/api/health` に DB 接続状態・dialect を追加（timeout 1.5s）
- `/api/admin/audit-logs/export`（admin 限定 CSV、CSV インジェクション対策）
- レポート取得時に未評価ルートを自動評価し DB へ永続化
- UI: 案件入力フォームの実装（工事件名・現場・担当・発注区分・地点/緯度経度・車両諸元・搬入日・時間帯・夜間・回避・特車）
- UI: 案件登録→ルート生成→自動評価→地図表示の一気通貫フロー
- UI: リスク確認ステータス・コメントの API 連携、レポート形式切替・ダウンロード（MD/CSV/PDF）
- UI: レビュー依頼（提出）・承認ボタン、ダッシュボード/管理画面の実データ表示
- UI: API キーの sessionStorage 保存と Authorization ヘッダ、/api/me 接続テスト
- UI: デモ・未対応項目の明示（経由地未対応、辞書サンプル、ZIP 次フェーズ、AI 表示是正）
- テスト: 49 Python + 13 Node（永続化・RBAC・監査 CSV・featureless リスク回帰・include_sources・saveAndGenerate・submitProject 等を追加）
- 文書: 評価報告書・改善台帳・テスト証跡・CHANGELOG 追加、README/RELEASE_READINESS 整合
- 修正: 認証済みユーザーの users テーブル upsert（ensure_user）で PostgreSQL の owner_user_id FK 制約違反を解消。SQLite テストも PRAGMA foreign_keys=ON で同等検証

### 先行作業の継承（2026-08-12 作業ツリー）
- JWKS キャッシュ TTL・ロック、OIDC fail-closed、API キー hmac 比較、PRODUCTION_MODE fail-closed
- CSP・セキュリティヘッダ、ナレッジ検索レート制限
- CSV 数式インジェクション対策
- ルート再生成の世代管理と確認状態引き継ぎ
- Cloudflare Worker の BACKEND_ORIGIN 検証・CORS 修正、wrangler 秘密値プレースホルダ削除

## 2026-08-05 — リリース準備（既存記録）

- SQLAlchemy 永続化・Alembic・OIDC/API キー認証・RBAC・監査ログ・アダプタ層・OSRM/Overpass・PDF・backup/monitor/restore・運用文書 6 点（詳細は RELEASE_READINESS.md）
