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
| 単体/統合/API/E2E | `python -m pytest` | PASS | 49 |
| コードセキュリティ | `bandit -q -r app` | PASS | 0 |
| クライアント構文 | `node --check`（app.js/component.js/dc-runtime.js） | PASS | 3 |
| クライアント動作 | `node tests/js/route_screen.test.mjs` | PASS | 13 |
| wheel ビルド | `python -m build --wheel` | PASS | — |
| アセット同梱 | `python scripts/check_package_assets.py` | PASS | 9/9 |
| 依存脆弱性 | `pip-audit .` | PASS | 0 |
| マイグレーション | `alembic upgrade head`（SQLite） | PASS | 4 リビジョン適用（initial / postgis / generation / delivery+indexes） |

## 新規・更新テストの内容

| ファイル | 検証内容 |
|---|---|
| tests/test_auth.py | 本番フェイルクローズ（503）、API キー誤り（401）、OIDC 設定欠落（503）、タイミングセーフ比較の経路 |
| tests/test_api.py | セキュリティヘッダー、本番モードの未認証書き込み拒否、ナレッジ検索レートリミット（429） |
| tests/test_workflow.py | 再評価時の確認ステータス引き継ぎ、再生成時の最新世代のみ表示（重複なし） |
| tests/test_persistence.py | 搬入/回避条件の往復永続化、owner_user_id 記録、レポート自動評価の永続化、health の DB 状態、監査 CSV エクスポートの権限と形式 |
| tests/test_reporting.py | CSV 数式インジェクション中和（= + @） |
| tests/test_adapters.py | サンプル地物の品質ランク E・sample フラグ（実データと区別） |
| tests/test_risk_engine.py | include_sources による評価対象フィルタ、サンプルランク E |
| tests/test_api.py | feature なしリスク（高さ・重量未入力）の DB ラウンドトリップ（500 回帰防止） |
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

## 復旧ドリル（実スクリプトによる検証）

`scripts/restore_db.sh` を一時ディレクトリで実行（本番 state.db は非破壊）:

| 手順 | 結果 |
|---|---|
| 検証用 state.db 作成（1 行）→ バックアップ（gzip）→ 2 行目を追記 | before restore rows: 2 |
| `restore_db.sh <backup.gz>` 実行 | `[OK] SQLite restored to ...` |
| 復旧後の行数・整合性・値 | rows: 1 / integrity: ok / value: original |

## 実 DB（state.db）のマイグレーション適用状況

- `alembic current`: `b2c3d4e5f6a7 (head)`（2 本の新リビジョン適用済み）
- `PRAGMA integrity_check`: `ok`
- 適用前に `scripts/backup_db.sh` でバックアップ取得（`state_20260812_194107.db.gz`）

## 検証環境（systemd）の稼働状況

- `construction-logistics-route-planner.service`: active（2026-08-12 19:26 再起動、新コード反映）
- `http://127.0.0.1:18017/api/health`: status=ok、db.status=ok、sample_mode=true
| POST /routes/generate（buffer_m=500） | 200（取得半径パラメータの実接続） |
| POST /routes/{id}/evaluate（include_sources=["osm"]） | 200（指定ソースのみ評価、feature なしリスク 2 件 feature:null） |
| GET /api/routes/{id}（車両諸元未入力案件） | 200（featureless リスク 500 の回帰確認） |

## 実行できなかった検証（NOT RUN / BLOCKED）

| 項目 | 理由 |
|---|---|
| 実ブラウザ E2E・スクリーンショット | 環境で Chromium が SIGTRAP 即終了。jsdom ハーネスで代替 |
| Cloudflare 実デプロイ | CLOUDFLARE_API_TOKEN / ACCOUNT_ID 未取得 |
| Neon PostgreSQL 本番マイグレーション | Neon API キー未取得 |
| Entra ID 実トークン認証 | テナント設定未完了（JWT 検証ロジックは単体で検証） |
| 負荷・性能テスト（600 名想定） | 未実施 |
| バックアップ復旧訓練 | 実スクリプトでの復旧ドリルは実施済み（一時ディレクトリ）。本番データでの復旧は本番移行時 |

## CI 状態

- 作業ブランチ PR #18 の CI: **quality（lint/compile/pytest/bandit/node）・package・dependency-audit すべて成功**（2026-08-12 実測、run 31587672250）
- main 上の CI 直近実績: success（2026-08-10 の Dependabot Updates 実行含む）
- stale Dependabot PR #16（checkout@7.0.1）・#17（setup-python@7.0.0）は CI 失敗のためクローズ予定
