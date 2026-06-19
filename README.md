# Construction Logistics Route Planner

建設資材・重機搬入ルートの初期検討を支援する MVP です。公開データ連携前の段階として、入力条件から複数ルート候補、注意箇所、追加確認事項、Markdown/CSV レポートを生成します。

このシステムは通行可否、特殊車両通行許可、道路使用許可、道路占用許可、現地安全性を保証しません。最終判断には道路管理者、警察、発注者、協力会社、現地確認等による追加確認が必要です。

## 機能

- 案件、出発地、到着地、車両条件、搬入条件の入力
- 4 種類のルート候補生成
- 橋梁、トンネル、学校、病院、住宅地、交通量、災害リスク、OSM 属性不足の抽出
- 「注意」「要確認」「データ不足」「除外検討」の安全側評価
- Markdown/CSV レポート出力
- ローカル静的 UI
- API key 任意有効化による基本アクセス制御

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

既に FastAPI / pytest が入っている環境では、そのまま実行できます。

## 起動

```bash
uvicorn app.main:app --reload --port 8000
```

UI: http://127.0.0.1:8000/

API docs: http://127.0.0.1:8000/docs

既に `8000` が使われている場合は、任意の空きポートを指定します。

```bash
uvicorn app.main:app --port 8017
```

## API Key

社内評価環境などで簡易保護を有効にする場合は `APP_API_KEY` を設定します。

```bash
APP_API_KEY='change-me' uvicorn app.main:app --port 8000
```

設定時は `Authorization: Bearer change-me` が必要です。`/api/health` と静的 UI は対象外です。

## systemd 登録

この環境では user systemd service として登録済みです。

- Unit: `~/.config/systemd/user/construction-logistics-route-planner.service`
- URL: http://192.168.0.185:18017/
- Health: http://192.168.0.185:18017/api/health
- Bind: `0.0.0.0:18017`

```bash
systemctl --user status construction-logistics-route-planner.service
systemctl --user restart construction-logistics-route-planner.service
systemctl --user stop construction-logistics-route-planner.service
journalctl --user -u construction-logistics-route-planner.service -f
```

`loginctl enable-linger kensan` も有効化済みのため、ユーザーセッションがない状態でも起動対象になります。

## 検証

```bash
pytest
python3 -m compileall app tests
```

## MVP の制約

- 外部 GIS/API 連携は未接続です。評価根拠は deterministic sample overlay として生成されます。
- DB 永続化は未実装で、プロセス内メモリ保存です。
- Entra ID / OIDC、PostGIS、監査ログ永続化、実データキャッシュは次フェーズ対象です。
