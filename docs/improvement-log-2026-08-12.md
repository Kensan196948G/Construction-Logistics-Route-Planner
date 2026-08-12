# 改善台帳（2026-08-12）

| # | 重要度 | 分類 | 改善内容 | 理由 | 対象者 | 効果 | 難易度 | 概算工数 | 状態 | 検証 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 重大 | セキュリティ | 本番モード（PRODUCTION_MODE=1）で認証未設定時は全保護 API を 503 で拒否（フェイルクローズ） | 認証未設定時に誰でも planner 権限で操作できる fail-open を放置すると権限逸脱 | 全利用者 | 権限逸脱・データ改ざん防止 | 低 | 0.5h | 完了 | tests/test_auth.py・test_api.py、実機 503 確認 |
| 2 | 重大 | セキュリティ | API キー比較を hmac.compare_digest に変更（タイミング攻撃対策） | 文字列比較はタイミング差分でキー推定の余地 | 全利用者 | 認証情報保護 | 低 | 0.2h | 完了 | tests/test_auth.py |
| 3 | 重大 | セキュリティ | Entra JWKS キャッシュに TTL を追加し、kid 不一致時は 1 回再取得 | キーローテーション後に全トークン検証が失敗し続ける障害 | 全利用者 | 認証可用性・セキュリティ | 中 | 1h | 完了 | tests/test_auth.py（OIDC 誤設定）、コードレビュー |
| 4 | 重大 | データ保全 | リスク確認ステータスを再評価時に引き継ぐ（コメントも追記） | 再評価で risks を全削除すると確認履歴が消失 | 現場・技術者 | 確認記録の消失防止・監査保全 | 中 | 2h | 完了 | tests/test_workflow.py、実機スモーク |
| 5 | 重大 | データ保全 | ルート再生成の世代管理（generation 列・移行追加）。一覧/帳票は最新世代のみ | 再生成のたびに重複ルートが増え、帳票が肥大化 | 技術者 | データ品質・帳票整合 | 中 | 2h | 完了 | tests/test_workflow.py、alembic upgrade 成功、実機スモーク |
| 6 | 高 | データ保全 | 搬入条件（日付/時間帯/休日/夜間）と回避条件を DB 永続化＋作成者 owner_user_id 記録 | API では受けるが保存されないデータ消失 | 技術者・監査 | 入力データ保全・監査性 | 中 | 2.5h | 完了 | tests/test_persistence.py |
| 7 | 高 | セキュリティ | 全レスポンスにセキュリティヘッダー（CSP 含む）を付与 | XSS・クリックジャッキング・MIME スニッフィング対策 | 全利用者 | Web 攻撃面の縮小 | 低 | 0.5h | 完了 | tests/test_api.py、実機ヘッダー確認 |
| 8 | 高 | セキュリティ | ナレッジ検索（公開 API）に IP あたり 30 回/分のレートリミット | 未認証エンドポイントの濫用 | 全利用者 | リソース保護 | 低 | 0.5h | 完了 | tests/test_api.py（429 確認） |
| 9 | 高 | データ品質 | CSV エクスポートの数式インジェクション対策（= + - @ 前置きを ' で中和） | Excel 等で開いた際の数式実行リスク | 全利用者 | セキュリティ・データ品質 | 低 | 0.5h | 完了 | tests/test_reporting.py |
| 10 | 高 | セキュリティ | Entra ID 有効時に ENTRA_CLIENT_ID 欠落なら 503 で停止 | 誤設定のサイレントダウングレード防止 | IT/DX | 認証方式の予期せぬ切替防止 | 低 | 0.3h | 完了 | tests/test_auth.py |
| 11 | 高 | 可用性 | /api/health に DB 接続状態と dialect を追加（1.5s タイムアウト） | HEALTHCHECK で DB 断を検知できない | IT/DX | 監視精度向上 | 低 | 0.5h | 完了 | tests/test_persistence.py、実機確認 |
| 12 | 高 | 監査 | 監査ログ CSV エクスポート（admin のみ・CSV 安全化済み）を追加 | 監査ログの持ち出し・BI 連携手段がない | IT/DX・監査 | 監査実務の効率化 | 中 | 1h | 完了 | tests/test_persistence.py |
| 13 | 高 | 構成 | Cloudflare Worker の BACKEND_ORIGIN 既定値を空に変更し、未設定時は 502。CORS は許可オリジンのみエコー。x-user-id/x-user-role ヘッダー許可を削除 | localhost へのプロキシは必ず失敗する誤設定。CORS の不整合 | IT/DX | 本番公開経路の誤動作防止 | 低 | 1h | 完了 | node --check、wrangler 設定レビュー |
| 14 | 高 | UI/UX | ダッシュボードの案件選択→ルート生成・評価→地図→確認→提出/承認→レポート DL を実 API に接続 | 主要フローがデモのまま | 技術者・現場 | 業務フロー実用化 | 中 | 3h | 完了 | tests/js（13 件）、node --check |
| 15 | 中 | UI/UX | リスクレベル exclusion_consideration の表示対応と API 確認ステータス（confirmed/needs_review）の表示・登録対応 | バックエンドの値と UI の値が不一致 | 技術者 | 表示・操作の正しさ | 低 | 0.5h | 完了 | tests/js |
| 16 | 中 | UI/UX | システム画面の API キー接続テスト（/api/me）と保存（sessionStorage）を実装 | テスト/保存が偽実装だった | IT/DX | 設定の実効性 | 中 | 1h | 完了 | tests/js |
| 17 | 中 | データ品質 | レポート出力前に未評価ルートを評価・永続化 | 帳票と DB の評価状態が不一致 | 技術者 | 帳票整合 | 低 | 0.3h | 完了 | tests/test_persistence.py |
| 18 | 中 | 性能 | FK 参照インデックス 12 本を移行で追加 | 一覧・監査・リスク取得のテーブルフルスキャン回避 | 全利用者 | 応答性能 | 低 | 0.5h | 完了 | alembic upgrade 成功 |
| 19 | 中 | 運用 | .opencode/ を Git 管理対象外に変更（.gitignore） | ローカルツール状態の混入防止 | IT/DX | リポジトリ衛生 | 低 | 0.1h | 完了 | git status |
| 20 | 中 | 文書 | README/SECURITY/RELEASE_READINESS/state.json を実装と整合（ロール数 4、テスト 46+13、本番モード説明、Worker 設定） | 文書と実装の乖離 | 全員 | 運用・監査の正確性 | 低 | 1.5h | 完了 | レビュー |
| 21 | 中 | CI | 失敗済み stale Dependabot PR（actions/checkout@7.0.1、setup-python@7.0.0）をクローズ | 存在しないバージョンへの更新は CI を壊すだけ | IT/DX | CI 状態の正常化 | 低 | 0.2h | 完了 | gh pr checks |
| 22 | 中 | 監視 | docs/monitoring.md にレートリミット・セキュリティヘッダーの確認項目を追記 | 監視項目の抜け | IT/DX | 運用品質 | 低 | 0.3h | 完了 | レビュー |

## 残課題（未実施・ブロック）

| # | 内容 | 理由/状態 | 推奨時期 |
|---|---|---|---|
| R1 | Cloudflare 実デプロイ（Pages/Worker/ドメイン/Access） | CLOUDFLARE_API_TOKEN・ACCOUNT_ID 未取得 | 3 か月以内 |
| R2 | Neon PostgreSQL 本番プロビジョニングと移行 | Neon API キー未取得 | 3 か月以内 |
| R3 | Entra ID テナント設定（アプリ登録・roles クレーム・グループ同期） | テナント設定待ち | 3 か月以内 |
| R4 | xROAD/KSJ/PLATEAU 実連携（API キー・契約） | 契約/キー待ち | 6〜12 か月 |
| R5 | 実ブラウザ E2E（Playwright） | 実行環境で Chromium が SIGTRAP 終了するため jsdom で代替中 | 3 か月以内 |
| R6 | オフサイトバックアップ・復旧訓練 | 対象ストレージ未決定 | 3 か月以内 |
| R7 | Excel 帳票・監査ログ検索 UI・プロジェクト編集/削除・検索/ページング | 未着手（Phase 1） | 3 か月以内 |
| R8 | 通知（Teams/メール）・監視アラート実配信 | 未着手（Phase 3） | 6〜12 か月 |
| R9 | モバイル PWA・オフライン | 未着手（Phase 3） | 6〜12 か月 |
| R10 | 型検査（mypy/pyright）導入 | 未着手 | 6 か月以内 |
| R11 | AI（RAG・引用・人間承認・利用量上限・監査） | 設計のみ（Phase 3） | 6〜12 か月 |
| R12 | 本番利用禁止表示の解除判断 | 実データ連携完了後の判定が必要 | 実データ後 |
