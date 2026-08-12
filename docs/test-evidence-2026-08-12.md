# テスト証跡（2026-08-12）

## 実行環境

- Python 3.12.3、Node.js 25.2.1、ruff 0.15.22、Linux（ローカル）
- 実行日時: 2026-08-12（日本時間）
- コミット: 作業ブランチ `improve/production-readiness-eval`（ベース: `7a6bd27`）

## 自動テスト結果

| ゲート | コマンド | 結果 | 件数 |
|---|---|---:|---|
| lint | `ruff check .` | PASS | 0 指摘 |
| 構文 | `python -m compileall -q app tests` | PASS | — |
| 単体/統合/API/E2E | `python -m pytest` | PASS | 46 |
| コードセキュリティ | `bandit -q -r app` | PASS | 0 |
| クライアント構文 | `node --check`（app.js/component.js/dc-runtime.js） | PASS | 3 |
| クライアント動作 | `node tests/js/route_screen.test.mjs` | PASS | 13 |
| wheel ビルド | `python -m build --wheel` | PASS | — |
| アセット同梱 | `python scripts/check_package_assets.py` | PASS | 9/9 |
| 依存脆弱性 | `pip-audit .` | PASS | 0 |
| マイグレーション | `alembic upgrade head`（SQLite） | PASS | 3 リビジョン適用 |

## 新規・更新テストの内容

| ファイル | 検証内容 |
|---|---|
| tests/test_auth.py | 本番フェイルクローズ（503）、API キー誤り（401）、OIDC 設定欠落（503）、タイミングセーフ比較の経路 |
| tests/test_api.py | セキュリティヘッダー、本番モードの未認証書き込み拒否、ナレッジ検索レートリミット（429） |
| tests/test_workflow.py | 再評価時の確認ステータス引き継ぎ、再生成時の最新世代のみ表示（重複なし） |
| tests/test_persistence.py | 搬入/回避条件の往復永続化、owner_user_id 記録、レポート自動評価の永続化、health の DB 状態、監査 CSV エクスポートの権限と形式 |
| tests/test_reporting.py | CSV 数式インジェクション中和（= + @） |
| tests/js/route_screen.test.mjs | 表示レベル対応、_geoInv 逆変換、confirmRisk の Authorization/body、testApi の /api/me 検証、未選択案件の DL エラー、submitProject |

## 実サーバースモーク（uvicorn + 一時 SQLite、ポート 18099）

| ステップ | 結果 |
|---|---|
| alembic upgrade head（generation 移行含む） | PASS |
| POST /api/projects（搬入・回避条件付き） | 201、条件の永続化確認 |
| POST /routes/generate | 200（4 候補） |
| POST /routes/{id}/evaluate | 200（リスク生成） |
| POST /risks/{id}/confirm | 200（confirmed） |
| 再評価後の確認ステータス | 引き継ぎ確認（1 件 confirmed） |
| 再生成後の一覧 | 最新世代のみ 4 件（重複なし） |
| GET /report?format=pdf | 200 application/pdf（%PDF ヘッダ確認） |
| GET /report?format=csv | 200（行・免責・サンプル注意含む） |
| セキュリティヘッダー | nosniff / DENY / no-referrer / CSP 付与確認 |
| GET /api/health | db.status=ok、dialect=sqlite |

## 実行できなかった検証（NOT RUN / BLOCKED）

| 項目 | 理由 |
|---|---|
| 実ブラウザ E2E・スクリーンショット | 環境で Chromium が SIGTRAP 即終了。jsdom ハーネスで代替 |
| Cloudflare 実デプロイ | CLOUDFLARE_API_TOKEN / ACCOUNT_ID 未取得 |
| Neon PostgreSQL 本番マイグレーション | Neon API キー未取得 |
| Entra ID 実トークン認証 | テナント設定未完了（JWT 検証ロジックは単体で検証） |
| 負荷・性能テスト（600 名想定） | 未実施 |
| バックアップ復旧訓練 | 未実施（スクリプト・手順は整備済み） |

## CI 状態

- 作業ブランチ PR の CI（quality / package / dependency-audit）: push 後に確認予定
- main 上の CI 直近実績: success（2026-08-10 の Dependabot Updates 実行含む）
- stale Dependabot PR #16（checkout@7.0.1）・#17（setup-python@7.0.0）は CI 失敗のためクローズ予定
