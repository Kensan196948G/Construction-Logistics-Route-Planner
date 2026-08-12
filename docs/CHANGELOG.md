# 変更履歴

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
- テスト: 46 Python + 13 Node（永続化・RBAC・監査 CSV・saveAndGenerate・submitProject 等を追加）
- 文書: 評価報告書・改善台帳・テスト証跡・CHANGELOG 追加、README/RELEASE_READINESS 整合

### 先行作業の継承（2026-08-12 作業ツリー）
- JWKS キャッシュ TTL・ロック、OIDC fail-closed、API キー hmac 比較、PRODUCTION_MODE fail-closed
- CSP・セキュリティヘッダ、ナレッジ検索レート制限
- CSV 数式インジェクション対策
- ルート再生成の世代管理と確認状態引き継ぎ
- Cloudflare Worker の BACKEND_ORIGIN 検証・CORS 修正、wrangler 秘密値プレースホルダ削除

## 2026-08-05 — リリース準備（既存記録）

- SQLAlchemy 永続化・Alembic・OIDC/API キー認証・RBAC・監査ログ・アダプタ層・OSRM/Overpass・PDF・backup/monitor/restore・運用文書 6 点（詳細は RELEASE_READINESS.md）
