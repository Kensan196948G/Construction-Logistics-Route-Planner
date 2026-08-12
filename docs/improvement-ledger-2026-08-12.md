# 改善台帳（2026-08-12）

評価（docs/evaluation-report-2026-08-12.md）に基づき実施した改善と検証結果を記録する。

## 実装済み（Verify 済み）

| # | 改善 | 分類 | ファイル | 検証 |
|---|---|---|---|---|
| 1 | 配信条件・回避条件の永続化（delivery_date / time_window / holiday / night_delivery_allowed / avoid_conditions） | データ消失（重大） | app/db_models.py, app/repository.py, alembic/versions/b2c3d4e5f6a7_*.py | pytest tests/test_persistence.py::test_delivery_and_avoid_conditions_round_trip, API スモーク |
| 2 | 案件の所有者（owner_user_id）記録（クライアントヘッダー不使用） | 権限・監査 | app/repository.py, app/main.py | 回帰テストで DB 直接確認 |
| 3 | FK 参照・検索用インデックス 12 本 | 性能 | migration b2c3d4e5f6a7 | migration upgrade/downgrade テスト |
| 4 | /api/health の DB 接続状態（dialect・status・timeout 1.5s） | 監視 | app/main.py | pytest・curl |
| 5 | 監査ログ CSV エクスポート（admin 限定・CSV インジェクション対策） | 監査 | app/main.py | pytest test_audit_logs_csv_export_requires_admin_and_is_parseable |
| 6 | レポート取得時の未評価ルート自動評価を DB へ永続化 | データ整合 | app/main.py | pytest test_report_auto_evaluation_is_persisted |
| 7 | UI 中核フロー実機能化: 案件入力フォーム（名前・現場・担当・発注区分・地点/緯度経度・車両・搬入日・時間帯・夜間・回避・特車） | 機能完成度 | app/static/index.html, app/static/component.js | node tests 13件・構文チェック |
| 8 | 案件登録→ルート生成→自動評価→ルート画面表示（saveAndGenerate / generateAndEvaluate / regenRoutes） | 機能完成度 | component.js | node test saveAndGenerate |
| 9 | ルート実 geometry の地図描画（サンプル SVG パスと併用） | 地図 | component.js | node 構文・既存 test |
| 10 | リスク確認ステータス・コメントの API 連携（confirmRisk / submitRiskComment） | ワークフロー | component.js, index.html | node test confirmRisk |
| 11 | レポート形式切替・ダウンロード（markdown/csv/pdf）・PDF 案内 | 帳票 | component.js, index.html | node test downloadReport |
| 12 | 提出（レビュー依頼）・承認ボタンと API 連携 | ワークフロー | component.js, index.html | node test submitProject |
| 13 | ダッシュボード・管理画面の実データ表示（案件・データソース・監査ログ）と更新ボタン | 管理運用 | component.js, index.html, app.js | 実測（API 応答） |
| 14 | API キーの sessionStorage 保存と Authorization ヘッダ付与・/ api/me 接続テスト | 認証 UI | component.js | node test testApi |
| 15 | デモ/未対応の明示（経由地未対応・辞書サンプル・ZIP 次フェーズ・AI 表示の是正） | 誠実な表示 | index.html | 目視確認 |
| 16 | ヘッダーの動的表示（案件 ID・名称・状態・日時・利用者） | UX | component.js, index.html | 構文確認 |
| 17 | README・RELEASE_READINESS の実装との整合、評価書・台帳・証跡・CHANGELOG 追加 | 文書 | docs/*, README.md, RELEASE_READINESS.md | レビュー |
| 18 | state.json の検証結果・フェーズ更新 | 運用記録 | state.json | 記録 |
| 19 | サンプル地物の品質ランク E 化と sample フラグ付与（OSM/公的データを装わない） | データ品質 | app/risk_engine.py, app/adapters.py | pytest test_sample_features_are_ranked_estimated |
| 20 | include_sources による評価入力フィルタ（API 契約の実装） | 機能 | app/risk_engine.py | pytest test_include_sources_filters_evaluation_inputs |
| 21 | Overpass キャッシュの上限（256 エントリ） | 性能 | app/adapters.py | コードレビュー |
| 22 | monitor.sh の DB 状態チェック（/api/health db.status） | 監視 | scripts/monitor.sh | 実実行（バックアップ時 smoke） |
| 23 | 失敗済み stale Dependabot PR（checkout@7.0.1 / setup-python@7.0.0）をクローズ | CI | GitHub | gh pr checks / close |
| 24 | .opencode/ を Git 管理対象外化、Alembic モジュールの型ヒント近代化 | 保守性 | .gitignore, alembic/* | ruff・compileall |

## 先行作業の継承（2026-08-12 時点で作業ツリーにあった改善、本評価で検証）

| # | 改善 | 分類 | 検証 |
|---|---|---|---|
| A | JWKS キャッシュ TTL・スレッドロック・kid ミス時の再取得、OIDC 設定不備の fail-closed | セキュリティ | pytest・bandit |
| B | API キーの hmac 比較、PRODUCTION_MODE=1 で未設定時に fail-closed | 認証 | pytest test_auth |
| C | CSP・セキュリティヘッダ・ナレッジ検索レート制限（30回/分/IP） | セキュリティ | pytest |
| D | CSV 数式インジェクション対策 | セキュリティ | pytest test_reporting |
| E | ルート再生成の世代管理（履歴保全）と再評価時の確認状態引き継ぎ | データ整合 | pytest・migration |
| F | Cloudflare Worker の BACKEND_ORIGIN 検証・CORS 修正・wrangler の秘密値プレースホルダ削除 | セキュリティ | コードレビュー |

## 未実施（外部依存・承認待ち）

| 項目 | 理由 | 必要操作 |
|---|---|---|
| Entra ID テナント設定 | ENTRA_TENANT_ID / ENTRA_CLIENT_ID 未提供 | Azure/Entra でアプリ登録とロール付与 |
| Neon PostgreSQL 接続 | Neon API キー未提供 | Neon プロジェクト作成と DATABASE_URL 設定 |
| Cloudflare 本番デプロイ | CLOUDFLARE_API_TOKEN / ACCOUNT_ID 未提供 | scripts/deploy-cloudflare.sh 実行（本番承認後） |
| xROAD / PLATEAU / KSI 実連携 | API キー・利用契約未締結 | 各提供元との契約 |
| ブラウザ E2E | 本環境の Chromium が SIGTRAP で起動不能 | 別環境での Playwright 実行 |
| 本番デプロイ・マージ | CLAUDE.md の承認ゲート（マージ判定 Y/N） | ユーザー承認 |

## 完了基準の確認

| 基準 | 結果 |
|---|---|
| 重大リスクの解消または明示的な受容・課題化 | データ消失は修正。実データ未連携は「本番利用禁止」明示で受容・課題化 |
| 変更範囲の CI | ローカル品質ゲート全成功（49 pytest / 13 node / ruff / bandit / compile / build） |
| 主要テスト・ビルド | pytest 49 passed、Node 13 passed、wheel ビルド確認 |
| データ移行 | Alembic upgrade head 適用（state.db）・downgrade テスト |
| バックアップ・復旧 | backup_db.sh 実行確認（SQLite・7世代保持）。restore_db.sh を一時ディレクトリで実ドリル（復旧後 rows 1 / integrity ok / value original） |
| 検証環境の主要フロー | API スモーク（入力→生成→評価→Markdown/PDF→提出→RBAC 403）＋ systemd（18017）が新コードで稼働中（health ok / db.status ok / sample_mode） |
| 評価書・改善台帳・テスト証跡・運用手順・変更履歴・残課題 | 本ファイルと docs/evaluation-report-2026-08-12.md・docs/test-evidence-2026-08-12.md・docs/CHANGELOG.md に記録 |
