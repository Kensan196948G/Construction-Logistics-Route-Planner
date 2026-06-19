# Construction Logistics Route Planner 詳細仕様設計書

## 建設資材・重機搬入ルート公開データ検討システム

| 項目 | 内容 |
|---|---|
| 文書種別 | 詳細仕様設計書 |
| プロジェクト名 | Construction Logistics Route Planner |
| リポジトリ名 | Construction-Logistics-Route-Planner |
| 対象 | Webアプリケーション、API、DB、地図・GIS処理、外部データ連携 |
| 基本方針 | 搬入ルートの初期検討支援。確定判定はしない |
| 初版 | 2026-06-19 |

---

## 1. システム全体像

Construction Logistics Route Planner は、資材・重機搬入ルートの候補生成、公開データ重ね合わせ、リスク抽出、追加確認事項の提示、搬入リスクメモ出力を行うWebアプリケーションである。

本システムは、以下の4層で構成する。

```text
[利用者]
  └─ Web UI
       └─ Backend API
            ├─ Routing Service Adapter
            ├─ Public Data Adapter
            ├─ Risk Evaluation Engine
            ├─ Report Generator
            └─ Database / Cache
```

---

## 2. 推奨技術スタック

## 2.1 フロントエンド

| 項目 | 推奨 |
|---|---|
| フレームワーク | React / Next.js |
| 言語 | TypeScript |
| 地図ライブラリ | MapLibre GL JS / Leaflet |
| UI | shadcn/ui または MUI |
| 状態管理 | TanStack Query / Zustand |
| 帳票表示 | Markdown Preview / HTML Preview |

## 2.2 バックエンド

| 項目 | 推奨 |
|---|---|
| フレームワーク | FastAPI または NestJS |
| 言語 | Python 3.12+ または TypeScript |
| GIS処理 | GeoPandas / Shapely / PostGIS |
| 非同期処理 | Celery / RQ / BullMQ |
| API形式 | REST API |
| 認証 | OIDC / Entra ID連携 |

## 2.3 データベース

| 項目 | 推奨 |
|---|---|
| DB | PostgreSQL |
| GIS拡張 | PostGIS |
| キャッシュ | Redis またはDBキャッシュテーブル |
| ファイル保管 | ローカル/SharePoint/Azure Blobを段階検討 |

## 2.4 ルート探索エンジン

| 用途 | 候補 | 備考 |
|---|---|---|
| 通常ルート候補 | OSRM | OSMベースで高速。車両制限判定は限定的 |
| 大型車・重機候補 | Valhalla / openrouteservice | 高さ・幅・重量等の条件対応を検討 |
| 将来 | 商用API | 精度・規制情報が必要な場合に検討 |

重要: MVPではルート候補生成に使うが、重量・高さ制限の最終判定には使わない。

---

## 3. 論理アーキテクチャ

```text
Web Browser
  |
  | HTTPS
  v
Frontend App
  |
  | REST API
  v
Backend API
  ├─ Auth Module
  ├─ Project Module
  ├─ Location Module
  ├─ Vehicle Condition Module
  ├─ Route Candidate Module
  ├─ Public Data Overlay Module
  ├─ Risk Evaluation Module
  ├─ Report Module
  ├─ Knowledge Module
  └─ Admin Module
       |
       v
PostgreSQL + PostGIS
       |
       +-- External APIs / Data Sources
```

---

## 4. 主要モジュール設計

## 4.1 Auth Module

### 目的

利用者認証、ロール判定、操作ログ記録の起点を担う。

### 機能

- Entra ID / OIDC 認証
- ロール取得
- セッション管理
- APIアクセス制御
- 操作ログへのユーザーID付与

### ロール

| ロール | 権限 |
|---|---|
| admin | 全機能 |
| dx_operator | データソース・ログ確認 |
| planner | 案件作成、評価、出力 |
| site_user | 閲覧、コメント、確認結果登録 |
| viewer | 閲覧のみ |

---

## 4.2 Project Module

### 目的

搬入ルート検討案件を管理する。

### 主な項目

- 案件ID
- 工事件名
- 現場名
- 発注者区分
- 担当部署
- 担当者
- 出発地
- 到着地
- 搬入予定日
- 搬入時間帯
- ステータス

### ステータス

| ステータス | 内容 |
|---|---|
| draft | 作成中 |
| evaluating | 評価中 |
| review_required | 追加確認中 |
| reviewed | 確認済み |
| archived | 保管 |

---

## 4.3 Location Module

### 目的

住所、緯度経度、地図クリックから地点情報を管理する。

### 機能

- 住所入力
- 緯度経度入力
- 地図クリック入力
- ジオコーディング
- 逆ジオコーディング
- 経由地管理
- 回避地点管理

### 入力バリデーション

| 項目 | ルール |
|---|---|
| 緯度 | -90〜90 |
| 経度 | -180〜180 |
| 住所 | 500文字以内 |
| 地点名 | 100文字以内 |
| 経由地 | 初期は最大10件 |

---

## 4.4 Vehicle Condition Module

### 目的

搬入車両・重機・積載条件を管理する。

### 項目

| 項目 | 型 | 必須 | 備考 |
|---|---|---|---|
| vehicle_type | enum | 必須 | 普通貨物、大型、トレーラー、重機回送等 |
| length_m | decimal | 任意 | 全長 |
| width_m | decimal | 任意 | 全幅 |
| height_m | decimal | 任意 | 全高 |
| gross_weight_t | decimal | 任意 | 総重量 |
| axle_weight_t | decimal | 任意 | 軸重 |
| cargo_type | text | 任意 | 資材・重機名 |
| special_vehicle_flag | boolean | 任意 | 特車該当可能性 |
| notes | text | 任意 | 補足 |

### 車両条件が未入力の場合

- ルート生成は可能とする。
- 高さ・重量・幅員に関する判定は「データ不足」または「追加確認」とする。

---

## 4.5 Route Candidate Module

### 目的

複数のルート候補を生成し、比較可能な形式で保存する。

### 候補生成タイプ

| タイプ | 内容 |
|---|---|
| shortest | 距離優先 |
| fastest | 時間優先 |
| arterial_priority | 幹線道路優先 |
| residential_avoid | 住宅地回避 |
| bridge_tunnel_caution | 橋梁・トンネル確認重視 |
| manual | 利用者指定・手動補正 |

### 処理フロー

```text
入力地点取得
  ↓
ルート探索API呼び出し
  ↓
候補ルートGeoJSON化
  ↓
距離・時間・道路種別を集計
  ↓
DB保存
  ↓
リスク評価キューへ投入
```

---

## 4.6 Public Data Overlay Module

### 目的

ルート周辺の公開データを取得し、GIS空間演算で注意箇所を抽出する。

### データ取得方式

| データ | 方式 | 保存方針 |
|---|---|---|
| OSM道路・POI | Overpass API / OSM抽出データ | キャッシュ保存 |
| xROAD | API/ダウンロード | 取得結果保存 |
| 国土数値情報 | ダウンロード/API | 定期取込 |
| PLATEAU | ダウンロード/API | 対象地域のみ取込 |
| 交通量 | API/CSV | 取得元別に保存 |

### 空間検索条件

| 対象 | 初期バッファ |
|---|---|
| ルート沿線施設 | 100m |
| 学校・病院 | 300m |
| 河川・浸水区域 | 100m〜500m |
| 橋梁・トンネル | ルート上または50m |
| 住宅地 | 100m |
| 交通量地点 | 500m |

---

## 4.7 Risk Evaluation Module

### 目的

ルートごとの注意点を抽出し、比較しやすいスコアとコメントを生成する。

### 評価結果区分

| 区分 | 説明 |
|---|---|
| candidate | 利用候補 |
| caution | 注意 |
| confirm_required | 要確認 |
| exclusion_candidate | 除外検討 |
| data_insufficient | データ不足 |

### スコア構成

```text
risk_score =
  road_condition_score
+ structure_score
+ traffic_score
+ surrounding_facility_score
+ disaster_score
+ data_quality_score
+ operation_score
```

### 初期重み

| 評価項目 | 重み |
|---|---:|
| 橋梁・トンネル・高さ重量確認 | 25 |
| 道路条件・狭隘性 | 20 |
| 交通量・混雑 | 15 |
| 周辺施設・近隣影響 | 15 |
| 災害・地形リスク | 10 |
| データ不足 | 10 |
| 運用面 | 5 |

### 判定ロジック例

| 条件 | 判定 |
|---|---|
| 車両高さあり + トンネル/アンダーパスあり + 高さ属性なし | 要確認 |
| 総重量あり + 橋梁あり + 耐荷重属性なし | 要確認 |
| 住宅地通過比率が高い | 注意 |
| 学校300m以内 + 登下校時間帯 | 注意 |
| 交通量多い区間 + 朝夕搬入 | 注意 |
| 主要属性が欠損 | データ不足 |
| 通行制限属性と車両条件が明らかに不整合 | 除外検討 |

### 注意

公開データに制限属性がない場合、「問題なし」とは扱わない。「制限情報未確認」として扱う。

---

## 4.8 Report Module

### 目的

検討結果を社内レビューや施工計画打合せに利用しやすい形式で出力する。

### 出力形式

| 形式 | 用途 |
|---|---|
| Markdown | GitHub/社内文書/ナレッジ化 |
| CSV | 一覧表・Excel加工 |
| HTML | レビュー表示 |
| PDF相当 | 将来対応 |
| GeoJSON | GIS再利用 |

### レポート構成

```text
1. 案件概要
2. 入力条件
3. 車両・搬入条件
4. ルート候補比較
5. 各ルート詳細
6. 注意箇所一覧
7. 追加確認事項
8. 確認先候補
9. 現地確認推奨事項
10. 免責・注意文
```

---

## 4.9 Knowledge Module

### 目的

検討履歴、確認結果、注意箇所を蓄積し、次回案件で再利用する。

### 機能

- 案件検索
- 地図範囲検索
- 類似ルート検索
- 注意地点登録
- 確認結果登録
- 協力会社コメント登録

---

## 5. 画面仕様

## 5.1 SCR-001 ダッシュボード

### 表示項目

- 最近の案件
- 要確認件数
- データソース接続状態
- 評価待ち件数
- 最近更新された注意地点

### 操作

- 案件新規作成
- 案件検索
- 管理画面へ遷移

---

## 5.2 SCR-002 案件作成画面

### 入力項目

| 項目 | 必須 | 備考 |
|---|---|---|
| 工事件名 | 必須 | 200文字以内 |
| 現場名 | 必須 | 200文字以内 |
| 発注者区分 | 任意 | 公共/民間/その他 |
| 担当者 | 必須 | 認証ユーザーを初期値 |
| 搬入目的 | 任意 | 資材搬入、重機搬入等 |
| 備考 | 任意 | 2000文字以内 |

---

## 5.3 SCR-003 地点・搬入条件入力画面

### 地点入力

- 出発地
- 到着地
- 経由地
- 回避地点
- 待機場所候補
- 転回場所候補

### 車両条件入力

- 車両種別
- 全長
- 全幅
- 全高
- 総重量
- 軸重
- 積載物
- 特殊車両該当可能性

---

## 5.4 SCR-004 ルート候補一覧画面

### 表示項目

| 項目 | 内容 |
|---|---|
| ルート名 | 候補A/B/C等 |
| 距離 | km |
| 想定時間 | 分 |
| 総合評価 | 利用候補/注意/要確認等 |
| 要確認件数 | 数値 |
| データ不足件数 | 数値 |
| 主な注意 | 上位3件 |

### 操作

- 地図で表示
- 詳細表示
- レポート対象に追加
- 除外理由登録

---

## 5.5 SCR-005 ルート地図画面

### 表示レイヤ

- ルート線
- 注意箇所ピン
- 橋梁・トンネル
- 学校・病院
- 交通量地点
- 災害リスク
- PLATEAU建物表示（将来）

### ピン種別

| 種別 | 表示 |
|---|---|
| bridge | 橋梁 |
| tunnel | トンネル |
| underpass | アンダーパス |
| school | 学校 |
| hospital | 病院 |
| narrow | 狭隘懸念 |
| traffic | 交通量注意 |
| disaster | 災害リスク |
| unknown | データ不足 |

---

## 5.6 SCR-006 注意箇所詳細画面

### 表示項目

- 注意箇所名
- 種別
- 位置
- 該当ルート
- 判定区分
- 根拠データ
- 取得日時
- 追加確認事項
- コメント
- 確認ステータス

### 確認ステータス

| ステータス | 内容 |
|---|---|
| unconfirmed | 未確認 |
| checking | 確認中 |
| confirmed_ok | 確認済み・懸念低 |
| confirmed_ng | 確認済み・懸念高 |
| not_applicable | 対象外 |

---

## 5.7 SCR-007 搬入リスクメモ画面

### 機能

- 自動生成メモ表示
- 手動追記
- 確認事項チェックリスト
- Markdown出力
- レビューコメント

---

## 5.8 SCR-008 管理画面

### 機能

- データソース一覧
- 接続テスト
- APIキー設定
- 評価ルール設定
- ユーザー権限確認
- 操作ログ検索

---

## 6. API設計

## 6.1 API一覧

| メソッド | パス | 内容 |
|---|---|---|
| GET | /api/health | ヘルスチェック |
| GET | /api/projects | 案件一覧 |
| POST | /api/projects | 案件作成 |
| GET | /api/projects/{project_id} | 案件詳細 |
| PUT | /api/projects/{project_id} | 案件更新 |
| DELETE | /api/projects/{project_id} | 案件削除/アーカイブ |
| POST | /api/projects/{project_id}/locations | 地点登録 |
| POST | /api/projects/{project_id}/vehicle | 車両条件登録 |
| POST | /api/projects/{project_id}/routes/generate | ルート候補生成 |
| GET | /api/projects/{project_id}/routes | ルート候補一覧 |
| GET | /api/routes/{route_id} | ルート詳細 |
| POST | /api/routes/{route_id}/evaluate | リスク評価実行 |
| GET | /api/routes/{route_id}/risks | リスク一覧 |
| POST | /api/risks/{risk_id}/comments | コメント登録 |
| PUT | /api/risks/{risk_id}/status | 確認ステータス更新 |
| GET | /api/projects/{project_id}/report | レポート生成 |
| GET | /api/admin/data-sources | データソース一覧 |
| POST | /api/admin/data-sources/{id}/test | 接続テスト |

---

## 6.2 ルート生成API

### POST /api/projects/{project_id}/routes/generate

#### Request

```json
{
  "route_types": ["shortest", "fastest", "arterial_priority", "residential_avoid"],
  "avoid_points": [
    { "lat": 35.0000, "lng": 139.0000, "radius_m": 300 }
  ],
  "via_points": [
    { "lat": 35.1000, "lng": 139.1000 }
  ]
}
```

#### Response

```json
{
  "project_id": "prj_001",
  "generated_count": 4,
  "routes": [
    {
      "route_id": "route_001",
      "name": "候補A 距離優先",
      "distance_km": 12.4,
      "duration_min": 34,
      "status": "evaluation_pending"
    }
  ]
}
```

---

## 6.3 リスク評価API

### POST /api/routes/{route_id}/evaluate

#### Request

```json
{
  "evaluation_profile": "default_heavy_vehicle_initial_check",
  "include_sources": ["osm", "xroad", "ksj", "plateau"],
  "buffer_m": 300
}
```

#### Response

```json
{
  "route_id": "route_001",
  "risk_score": 68,
  "risk_level": "confirm_required",
  "summary": "橋梁・学校近接・交通量注意区間があり、追加確認が必要です。",
  "risk_counts": {
    "caution": 5,
    "confirm_required": 3,
    "data_insufficient": 2
  }
}
```

---

## 6.4 レポート生成API

### GET /api/projects/{project_id}/report?format=markdown

#### Response

```json
{
  "project_id": "prj_001",
  "format": "markdown",
  "content": "# 搬入ルート初期検討メモ\n...",
  "generated_at": "2026-06-19T10:00:00+09:00"
}
```

---

## 7. データベース設計

## 7.1 ER概要

```text
users
  └─ projects
       ├─ project_locations
       ├─ vehicle_conditions
       ├─ route_candidates
       │    ├─ route_segments
       │    └─ route_risks
       │         └─ risk_comments
       ├─ reports
       └─ project_audit_logs

data_sources
  ├─ data_source_fetch_logs
  └─ public_geo_features

knowledge_points
```

---

## 7.2 テーブル定義

### users

| カラム | 型 | 内容 |
|---|---|---|
| id | uuid | ユーザーID |
| entra_object_id | varchar | Entra ID Object ID |
| display_name | varchar | 表示名 |
| email | varchar | メール |
| role | varchar | ロール |
| created_at | timestamp | 作成日時 |
| updated_at | timestamp | 更新日時 |

### projects

| カラム | 型 | 内容 |
|---|---|---|
| id | uuid | 案件ID |
| project_name | varchar | 工事件名 |
| site_name | varchar | 現場名 |
| client_type | varchar | 公共/民間/その他 |
| status | varchar | draft等 |
| owner_user_id | uuid | 担当者 |
| transport_purpose | varchar | 搬入目的 |
| planned_date | date | 搬入予定日 |
| planned_time_window | varchar | 搬入時間帯 |
| notes | text | 備考 |
| created_at | timestamp | 作成日時 |
| updated_at | timestamp | 更新日時 |

### project_locations

| カラム | 型 | 内容 |
|---|---|---|
| id | uuid | 地点ID |
| project_id | uuid | 案件ID |
| location_type | varchar | origin/destination/via/avoid/waiting/turning |
| name | varchar | 地点名 |
| address | text | 住所 |
| geom | geometry(Point, 4326) | 位置 |
| radius_m | integer | 回避半径等 |
| sort_order | integer | 順序 |

### vehicle_conditions

| カラム | 型 | 内容 |
|---|---|---|
| id | uuid | 車両条件ID |
| project_id | uuid | 案件ID |
| vehicle_type | varchar | 車両種別 |
| length_m | numeric | 全長 |
| width_m | numeric | 全幅 |
| height_m | numeric | 全高 |
| gross_weight_t | numeric | 総重量 |
| axle_weight_t | numeric | 軸重 |
| cargo_type | varchar | 積載物 |
| special_vehicle_flag | boolean | 特車該当可能性 |
| notes | text | 備考 |

### route_candidates

| カラム | 型 | 内容 |
|---|---|---|
| id | uuid | ルートID |
| project_id | uuid | 案件ID |
| route_name | varchar | ルート名 |
| route_type | varchar | shortest等 |
| distance_km | numeric | 距離 |
| duration_min | numeric | 想定時間 |
| geom | geometry(LineString, 4326) | ルート形状 |
| risk_score | integer | リスクスコア |
| risk_level | varchar | 評価区分 |
| evaluation_status | varchar | 評価状態 |
| data_quality_summary | jsonb | データ品質概要 |
| created_at | timestamp | 作成日時 |

### route_risks

| カラム | 型 | 内容 |
|---|---|---|
| id | uuid | リスクID |
| route_id | uuid | ルートID |
| risk_type | varchar | bridge/tunnel/school等 |
| risk_level | varchar | caution/confirm_required等 |
| title | varchar | タイトル |
| description | text | 説明 |
| source_name | varchar | データ出典 |
| source_rank | varchar | A/B/C/D/E |
| source_url | text | 出典URL |
| fetched_at | timestamp | 取得日時 |
| geom | geometry(Point/Polygon, 4326) | 位置 |
| confirmation_status | varchar | 未確認/確認済み等 |
| recommendation | text | 推奨確認事項 |

### risk_comments

| カラム | 型 | 内容 |
|---|---|---|
| id | uuid | コメントID |
| risk_id | uuid | リスクID |
| user_id | uuid | 登録者 |
| comment | text | コメント |
| confirmation_result | varchar | 確認結果 |
| created_at | timestamp | 登録日時 |

### data_sources

| カラム | 型 | 内容 |
|---|---|---|
| id | uuid | データソースID |
| name | varchar | 名称 |
| source_type | varchar | api/download/manual |
| base_url | text | URL |
| license | varchar | ライセンス |
| reliability_rank | varchar | A/B/C/D/E |
| update_frequency | varchar | 更新頻度 |
| enabled | boolean | 有効/無効 |
| last_checked_at | timestamp | 最終確認日時 |

### public_geo_features

| カラム | 型 | 内容 |
|---|---|---|
| id | uuid | 地物ID |
| data_source_id | uuid | データソースID |
| feature_type | varchar | school/bridge/river等 |
| name | varchar | 名称 |
| attributes | jsonb | 属性 |
| geom | geometry | 地物形状 |
| source_updated_at | timestamp | データ側更新日時 |
| fetched_at | timestamp | 取得日時 |

### reports

| カラム | 型 | 内容 |
|---|---|---|
| id | uuid | レポートID |
| project_id | uuid | 案件ID |
| report_type | varchar | route_comparison/risk_memo等 |
| format | varchar | markdown/csv/html/pdf |
| content | text | 本文 |
| file_path | text | ファイルパス |
| generated_by | uuid | 生成者 |
| generated_at | timestamp | 生成日時 |

---

## 8. データクレンジング設計

## 8.1 取込時処理

```text
データ取得
  ↓
文字コード統一
  ↓
座標系確認・WGS84変換
  ↓
ジオメトリ妥当性検証
  ↓
属性名正規化
  ↓
重複候補検出
  ↓
異常値検出
  ↓
信頼度ランク付与
  ↓
DB保存
```

## 8.2 欠損処理ルール

| 項目 | 処理 |
|---|---|
| 高さ制限なし | 「制限なし」と解釈しない。「情報なし」と扱う |
| 重量制限なし | 「通行可能」と解釈しない。「追加確認」と扱う |
| 道路幅員なし | 狭隘判定を保留し、現地確認推奨 |
| 更新日不明 | データ品質スコアを下げる |
| 出典不明 | 評価根拠に使わない |

## 8.3 重複統合ルール

- 同一名称かつ50m以内の施設は重複候補とする。
- 公的データとOSMが重複した場合、公的データを優先する。
- OSMにのみ存在する場合は、信頼度Cとして扱う。

---

## 9. リスク評価詳細設計

## 9.1 RiskRule構造

```json
{
  "rule_id": "RR-BRIDGE-001",
  "name": "橋梁重量確認",
  "target_feature": "bridge",
  "condition": {
    "vehicle.gross_weight_t": { "exists": true },
    "feature.max_weight_t": { "missing": true }
  },
  "risk_level": "confirm_required",
  "score": 25,
  "message": "橋梁を通過する可能性がありますが、公開データ上で重量制限を確認できません。道路管理者または現地資料で追加確認してください。"
}
```

## 9.2 代表ルール

| ルールID | 条件 | 判定 |
|---|---|---|
| RR-BRIDGE-001 | 橋梁あり、重量制限情報なし | 要確認 |
| RR-TUNNEL-001 | トンネル/アンダーパスあり、高さ情報なし | 要確認 |
| RR-HEIGHT-001 | 車両高さが入力済み、制限高さ情報が欠損 | データ不足 |
| RR-SCHOOL-001 | 学校300m以内、朝夕搬入 | 注意 |
| RR-HOSPITAL-001 | 病院300m以内 | 注意 |
| RR-RESIDENTIAL-001 | 住宅地通過比率が閾値以上 | 注意 |
| RR-TRAFFIC-001 | 交通量多い区間を通過 | 注意 |
| RR-DISASTER-001 | 浸水・土砂等のリスク区域近接 | 注意 |
| RR-OSM-QUALITY-001 | OSM属性欠損が多い | データ不足 |

---

## 10. バッチ・非同期処理設計

## 10.1 バッチ一覧

| ジョブID | ジョブ名 | 内容 | 頻度 |
|---|---|---|---|
| JOB-001 | データソース接続確認 | 外部APIの疎通確認 | 日次 |
| JOB-002 | 国土数値情報取込 | 対象データの更新確認・取込 | 月次/手動 |
| JOB-003 | OSMキャッシュ更新 | 対象地域のOSMデータ更新 | 週次/手動 |
| JOB-004 | xROADデータ確認 | 公開データ/API状態確認 | 日次/週次 |
| JOB-005 | レポート再生成 | データ更新後の再評価 | 手動 |
| JOB-006 | 古いキャッシュ削除 | キャッシュ期限切れ削除 | 日次 |

## 10.2 非同期処理

- ルート候補生成
- 公開データ重ね合わせ
- リスク評価
- レポート生成
- 大規模GISデータ取込

---

## 11. ログ設計

## 11.1 アプリケーションログ

| ログ | 内容 |
|---|---|
| access_log | APIアクセス |
| operation_log | ユーザー操作 |
| evaluation_log | 評価実行結果 |
| external_api_log | 外部API呼び出し |
| error_log | エラー詳細 |
| audit_log | 管理操作、評価ルール変更 |

## 11.2 操作ログ項目

| 項目 | 内容 |
|---|---|
| user_id | 操作者 |
| action | 操作内容 |
| target_type | project/route/risk/report等 |
| target_id | 対象ID |
| ip_address | 接続元IP |
| user_agent | ブラウザ情報 |
| created_at | 操作日時 |

---

## 12. セキュリティ設計

## 12.1 認証・認可

- Entra ID連携を推奨する。
- HENNGE ONE環境との整合性を確認する。
- APIは認証必須とする。
- ロールにより編集・出力・管理操作を制限する。

## 12.2 入力チェック

| 対象 | チェック |
|---|---|
| 住所・地点名 | 文字数、禁止文字 |
| 緯度経度 | 範囲チェック |
| 数値 | 高さ・重量・幅の範囲チェック |
| コメント | XSS対策、HTMLエスケープ |
| ファイル | 初期版ではアップロード原則なし |

## 12.3 外部APIキー管理

- APIキーは環境変数またはSecrets管理に保存する。
- フロントエンドへ直接露出しない。
- 管理画面ではマスク表示する。
- APIキー更新履歴を監査ログに記録する。

---

## 13. エラーハンドリング設計

| エラー | 表示方針 |
|---|---|
| ルート生成失敗 | 条件を変更して再実行する案内を表示 |
| 外部APIタイムアウト | 該当データを除外し、データ不足として評価 |
| データ取得制限 | キャッシュ利用または再試行案内 |
| GIS処理失敗 | 対象レイヤ名と失敗理由を表示 |
| 認証エラー | 再ログイン案内 |
| 権限エラー | 管理者へ問い合わせ案内 |

---

## 14. レポートテンプレート仕様

## 14.1 Markdownテンプレート

```markdown
# 搬入ルート初期検討メモ

## 1. 案件概要

- 工事件名:
- 現場名:
- 担当者:
- 作成日:

## 2. 搬入条件

- 出発地:
- 到着地:
- 車両種別:
- 全高:
- 総重量:
- 搬入時間帯:

## 3. ルート候補比較

| 候補 | 距離 | 時間 | 評価 | 要確認 | データ不足 | コメント |
|---|---:|---:|---|---:|---:|---|

## 4. 主な注意箇所

| No | 種別 | 場所 | 判定 | 確認事項 | 出典 |
|---:|---|---|---|---|---|

## 5. 追加確認事項

- 道路管理者確認:
- 警察協議:
- 協力会社確認:
- 現地踏査:

## 6. 注意文

本資料は公開データに基づく初期検討資料であり、通行可否を保証するものではありません。
```

---

## 15. ディレクトリ構成案

```text
Construction-Logistics-Route-Planner/
├─ README.md
├─ docs/
│  ├─ requirements.md
│  ├─ detailed-design.md
│  ├─ api-design.md
│  ├─ database-design.md
│  └─ operation-guide.md
├─ frontend/
│  ├─ src/
│  │  ├─ app/
│  │  ├─ components/
│  │  ├─ features/
│  │  ├─ hooks/
│  │  └─ lib/
├─ backend/
│  ├─ app/
│  │  ├─ api/
│  │  ├─ core/
│  │  ├─ modules/
│  │  ├─ services/
│  │  ├─ adapters/
│  │  ├─ models/
│  │  └─ schemas/
│  ├─ tests/
│  └─ pyproject.toml
├─ database/
│  ├─ migrations/
│  ├─ seed/
│  └─ postgis/
├─ data/
│  ├─ samples/
│  └─ schemas/
├─ scripts/
│  ├─ import_ksj.py
│  ├─ check_xroad.py
│  └─ refresh_osm_cache.py
├─ docker-compose.yml
└─ .env.example
```

---

## 16. 開発順序

## 16.1 Sprint 1: 基盤

- リポジトリ作成
- README整備
- Docker Compose作成
- PostgreSQL + PostGIS構築
- Backend API雛形
- Frontend雛形
- 地図表示確認

## 16.2 Sprint 2: 案件・地点・車両条件

- 案件CRUD
- 地点入力
- 車両条件入力
- DB保存
- 入力バリデーション

## 16.3 Sprint 3: ルート候補生成

- ルート探索アダプタ実装
- 複数候補生成
- GeoJSON保存
- ルート一覧表示
- 地図上のルート表示

## 16.4 Sprint 4: 公開データ重ね合わせ

- OSM/Overpass連携
- 国土数値情報サンプル取込
- 周辺施設抽出
- 橋梁・トンネル抽出
- 注意箇所ピン表示

## 16.5 Sprint 5: リスク評価・レポート

- リスクルール実装
- スコア算出
- 追加確認フラグ
- Markdownレポート生成
- CSV出力

## 16.6 Sprint 6: 運用・管理

- データソース管理
- 接続テスト
- 操作ログ
- 権限管理
- テスト整備

---

## 17. テスト設計

## 17.1 単体テスト

| 対象 | テスト内容 |
|---|---|
| 入力バリデーション | 数値範囲、必須、文字数 |
| ルート生成 | APIレスポンス変換、エラー処理 |
| GIS処理 | バッファ、交差、近接判定 |
| リスク評価 | ルール条件、スコア算出 |
| レポート生成 | Markdown/CSV形式 |

## 17.2 結合テスト

- 案件作成からレポート出力までの一連動作
- 外部API取得失敗時のデータ不足表示
- 地図上の注意箇所表示
- コメント登録・確認ステータス更新

## 17.3 UAT

| 利用者 | 確認内容 |
|---|---|
| 現場担当 | 入力しやすさ、表示の分かりやすさ |
| 施工計画担当 | 比較表とメモが実務に使えるか |
| IT・DX担当 | 運用負荷、ログ、障害時対応 |
| 安全管理担当 | 危険な断定表現がないか |

---

## 18. 画面文言ルール

## 18.1 使用してよい表現

- 初期検討結果
- 追加確認が必要です
- 公開データ上の注意箇所です
- 現地確認を推奨します
- 道路管理者等への確認を推奨します
- データ不足のため判断できません

## 18.2 使用しない表現

- 通行可能です
- このルートで確定です
- 問題ありません
- 許可不要です
- 安全です
- すべて確認済みです

---

## 19. 運用設計

## 19.1 データ更新運用

| データ | 更新方式 |
|---|---|
| OSM | 週次または手動更新 |
| xROAD | 日次接続確認、データ更新は公開状況に合わせる |
| 国土数値情報 | 月次または更新時手動 |
| PLATEAU | 対象地域追加時に手動取込 |
| 社内注意地点 | 利用者登録、管理者レビュー |

## 19.2 障害対応

| 障害 | 対応 |
|---|---|
| 外部API停止 | キャッシュ表示、データ不足扱い |
| DB障害 | バックアップから復旧 |
| 地図表示不可 | 一覧とレポートのみ利用可能にする |
| 認証障害 | 管理者向けにローカル緊急閲覧は原則設けない |

## 19.3 バックアップ

- PostgreSQLの日次バックアップ
- レポートファイルの世代管理
- 評価ルール変更前後のエクスポート
- データソース設定のバックアップ

---

## 20. MVP完了条件

- Web画面から案件を作成できる。
- 出発地・到着地・車両条件を入力できる。
- 3件以上のルート候補を表示できる。
- ルート上の橋梁・トンネル・学校・病院等を抽出できる。
- 「注意」「要確認」「データ不足」を表示できる。
- 搬入リスクメモをMarkdownで出力できる。
- 断定表現を使わず、追加確認前提のレポートになっている。
- データソース、取得日時、根拠を確認できる。

---

## 21. 将来拡張

| 拡張 | 内容 |
|---|---|
| 特車申請支援 | 申請に必要な確認項目の整理支援 |
| 現地踏査アプリ | スマートフォンで写真・コメント登録 |
| PLATEAU 3D表示 | 高架、周辺建物、搬入空間確認 |
| AIメモ生成 | 協議事項、ヒアリング項目の自動生成 |
| 気象・防災連携 | 搬入日の気象・河川・強風リスク連携 |
| 施工計画システム連携 | 工程・搬入日・作業計画との連携 |
| 協力会社ポータル | 協力会社コメント・実績登録 |
| 統合OS連携 | Construction Enterprise OSへの組込 |

---

## 22. 実装上の重要注意点

1. 高さ・重量・幅員のデータがない場合、絶対に「問題なし」と扱わない。
2. OpenStreetMapの属性は便利だが、公式な道路許認可情報ではない。
3. 商用ナビのような最短案内ではなく、施工計画向けの比較・注意喚起を重視する。
4. 評価スコアは順位付けの補助であり、最終判断ではない。
5. レポートには必ず注意文を入れる。
6. 発注者・道路管理者・警察・協力会社確認の履歴を残す。

---

## 23. 結論

本詳細仕様では、Construction Logistics Route Planner を「搬入ルート自動決定システム」ではなく、「搬入ルート初期検討・追加確認支援システム」として設計した。

MVPでは、ルート候補生成、公開データ重ね合わせ、注意箇所抽出、リスクメモ出力に集中する。これにより、施工計画担当者が最初の検討資料を短時間で作成でき、現地確認・道路管理者確認・協力会社確認へ進みやすくなる。

最初から完璧な特車判定を狙うと、開発も運用も重機級に重くなる。まずは「確認漏れを減らす軽快な相棒」として作るのがベストである。
