# 統合評価・実装報告（2026-08-14）— MVP operable sprint

## 1. エグゼクティブサマリ

| 項目 | 内容 |
|---|---|
| 対象 | Construction Logistics Route Planner（建設資材・重機搬入ルート初期検討支援 MVP） |
| ブランチ | `feat/mvp-crud-excel-search`（ベース: main `8dfc4fc`） |
| 目的 | 企画・評価で終わらせず、主要ユースケースを実操作・評価できる MVP を完成し、関係者レビュー用 URL を用意する |
| 総合判定 | **GO（MVP/Prototype として操作・評価可能）** |
| 完了基準 | P0=0、主要 P1 解消、ダミーデータ投入・保持、UI/API/DB 整合、テスト/CI 成功、文書整合 |

本番運用（本番デプロイ・本番 DB migration・本番 Secrets 変更・実データ投入）は対象外として実施していない。

## 2. Monitor / Assessment の要点

2026-08-12 の評価（18カテゴリ平均 59.0）を引き継ぎ、実コード・実 DB・稼働中サーバー・GitHub・Cloudflare を再監査した。

### 検出した問題（重要度順）

| # | 問題 | 重大度 | 対処 |
|---|---|---|---|
| 1 | 実ブラウザで全画面が白紙になる既存バグ（`renderVals` 内で `fmt` を宣言前に参照する TDZ ReferenceError。jsdom ハーネスでは発見不能） | **P0（主要操作不能）** | 宣言順を修正＋「renderVals が 9 画面すべてで throw しない」回帰テスト＋Firefox 実ブラウザ E2E で恒久検証 |
| 2 | 案件の編集・削除が未実装（Issue #23） | P1 | `PATCH` / `DELETE`（論理削除）+ UI + テスト |
| 3 | 案件一覧の検索・ページングがない | P1 | `q` / `status` / `limit` / `offset` + `risk_summary` + UI |
| 4 | Excel 帳票がない（Markdown/CSV/PDF のみ） | P1 | `format=xlsx`（openpyxl・4シート・注入対策）+ UI |
| 5 | 監査ログ検索 UI がない（API は表示のみ） | P2 | API フィルタ + 管理画面の検索・CSV エクスポート |
| 6 | 施設辞書画面がハードコードのサンプルで DB と無関係 | P2 | `GET /api/facilities` + DB 連携（読取り専用） |
| 7 | 評価可能な架空ダミーデータが体系化されていない | P1（ユーザー要件） | `scripts/seed_demo.py`（冪等・`seed-` 接頭辞・参照整合性付き） |
| 8 | ブラウザ E2E 未実施（Chromium SIGTRAP） | P1（Issue #22） | Playwright + **Firefox headless** で実現し CI に組込み |
| 9 | ダッシュボード KPI がページ内件数ベース | P2 | `GET /api/projects/stats` を追加し全件ベースに変更 |
| 10 | 編集済みの成功通知が案件画面に出ない | P3 | 案件画面に `apiNotice` 表示を追加 |

### セキュリティ監査（P0/P1 なし）

- 秘密スキャン: コミット済みファイル・Git 履歴に実秘密値・接続文字列・PII なし（テスト用の架空値のみ）。
- `bandit` 0 件、`pip-audit .`（プロジェクト依存）「No known vulnerabilities found」。
- 認証フェイルクローズ・タイミングセーフ比較・セキュリティヘッダー・レート制限・CSV/Excel 注入対策は維持・拡張。
- PoC 限定の `POC_ANONYMOUS_ROLE` を追加（既定 `planner`）。`PRODUCTION_MODE=1` では無効。

## 3. 実装内容

### Backend

- `PATCH /api/projects/{id}`: `ProjectUpdate`（全フィールド任意）。draft/evaluating/change_requested のみ編集可（それ以外は 409）。監査 `project_updated`。
- `DELETE /api/projects/{id}`: `archived` への論理削除。履歴・ルート・リスク・帳票・監査ログは保持。監査 `project_archived`。
- `GET /api/projects`: `{items,total,limit,offset}` + `q`（案件名/現場名/担当者）・`status` フィルタ + `risk_summary`（最新世代の候補・要確認・データ不足）。
- `GET /api/projects/stats`: ステータス別件数（KPI）。
- `GET /api/admin/audit-logs`: `q` / `action` / `user_id` / `limit` / `offset`。CSV エクスポートは既存を維持。
- `GET /api/projects/{id}/report?format=xlsx`: openpyxl 4 シート。`_csv_safe` で数式注入中和。依存に `openpyxl>=3.1` を追加。
- `GET /api/facilities`: `knowledge_points` の読取り専用一覧。
- `POC_ANONYMOUS_ROLE`: PoC 限定の匿名ロール切替（不正値は `planner` にフォールバック）。

### Frontend（9画面 SPA）

- ダッシュボード: 検索ボックス・ステータスフィルタチップ・ページング・行ごとの編集/保管、実 KPI。
- 案件画面: 編集モード（既存案件の読込み→PATCH）、保存のみ／更新して再評価、キャンセル、成功通知。
- レポート画面: Excel ボタンと xlsx ダウンロード（blob・正しい MIME）。
- 管理画面: 監査ログの絞り込みと CSV エクスポート。
- 施設辞書画面: DB 連携表示（登録機能は次フェーズと明示）。
- ヘッダーに PoC ロール表示（`/api/me`）。

### ダミーデータ（`scripts/seed_demo.py`）

冪等（`seed-` 接頭辞の行のみ毎回入れ替え）。架空の人物名・会社・住所・座標のみ使用。

| テーブル | 件数 | 内容 |
|---|---:|---|
| users | 4 | admin / planner / site_user / viewer（メールは `@example.jp`） |
| projects | 8 | draft〜archived の全ステータスを網羅 |
| route_candidates / segments / risks | 32 / 60 / 140 | 最新世代、確認ステータス・コメント付き |
| reports | 16 | Markdown / CSV |
| data_sources | 5 | OSM・xROAD・KSJ・PLATEAU・交通量サンプル |
| knowledge_points | 8 | 施設辞書（橋梁〜交通量） |
| audit_logs | 8+ | 案件作成等 |

`state.db`（ローカル検証環境）に投入済みで保持している。再生成は `python scripts/seed_demo.py` のみ。

## 4. 検証結果（すべて実測）

| ゲート | コマンド | 結果 |
|---|---|---|
| lint | `ruff check .` | PASS（0 指摘） |
| 構文 | `python -m compileall app tests scripts` | PASS |
| Python テスト | `pytest -q` | **59 passed**（新規: 案件CRUD・検索/ページング・Excel・監査フィルタ・PoCロール 12 件） |
| コードセキュリティ | `bandit -q -r app` | PASS（0 件） |
| クライアント構文 | `node --check` ×3 | PASS |
| クライアント動作 | `node tests/js/route_screen.test.mjs` | **18 passed**（新規: envelope/search/edit/delete/xlsx 等 5 件＋renderVals 白紙回帰） |
| 実ブラウザ E2E | Playwright + Firefox headless | **8 passed**（ダッシュボード→検索→ルート生成→ナレッジ→施設辞書→監査CSV→編集→論理削除） |
| wheel/アセット | `python -m build --wheel` + `check_package_assets.py` | PASS（9/9 同梱） |
| 依存脆弱性 | `pip-audit .` | PASS（No known vulnerabilities） |
| 実サーバースモーク | systemd `18017` 再起動後 | health ok / db ok / PATCH / DELETE / xlsx / 検索 / 監査 / 施設辞書を curl で確認 |
| DB 整合性 | `PRAGMA integrity_check` / `foreign_key_check` | ok / 違反なし |

## 5. 公開 URL（Cloudflare）

- MVP/Prototype: `https://route-planner-mvp.mirai-dx-platform.com`（Cloudflare Tunnel `route-planner-mvp` → ローカル systemd `18017`。TLS は Cloudflare で終端）。
- 本番（予約）: `https://route-planner.mirai-dx-platform.com`（DNS 予約のみ。本番デプロイは対象外のため未配信）。

## 6. 残バックログ（P1 以下・本番対象外を除く）

| 優先度 | 項目 | 備考 |
|---|---|---|
| P1 | Neon PostgreSQL 本番プロビジョニング（#19） | Neon API キーにプロジェクトなし（確認済み）。本番 DB 操作は今回対象外 |
| P1 | Entra ID テナント設定（#20） | ENTRA_TENANT_ID / CLIENT_ID 未提供。ロジックとフェイルクローズは実装済み |
| P1 | 本番 URL への実配信（#21） | 本番デプロイ対象外。Tunnel/DNS の仕組みは MVP で検証済み |
| P2 | xROAD / KSJ / PLATEAU 実連携（#24） | API キー・契約待ち。アダプタ層は実装済み |
| P2 | バックアップのオフサイト保管と定期訓練（#25） | ローカル 7 世代バックアップ＋復旧ドリルは実施済み |
| P2 | 経由地・回避エリア指定、案件複製 | モデル（`AvoidPoint` / `avoid_points`）は既存 |
| P2 | モバイル最適化・PWA、通知（メール/Teams） | 現場利用前提。設計はロードマップ参照 |
| P2 | アクセシビリティ強化（ARIA・キーボード・コントラストの体系検証） | ラベル・focus 保持は実装済み |
| P3 | 施設辞書の登録/編集 UI、データソース管理 UI、型検査（mypy/pyright） | — |

## 7. MVP/Prototype 判定

**GO**。主要ユースケース（案件の登録・編集・論理削除・検索・一覧、ルート生成・評価・確認、提出・承認、Markdown/CSV/Excel/PDF 帳票、ナレッジ検索、施設辞書、RBAC、監査ログの検索・エクスポート）が、有効な架空ダミーデータを保持した状態で UI/API/DB にわたり実動作する。P0=0、主要 P1 は解消または管理可能なバックログ化済み。本番運用化は対象外として実施していない。
