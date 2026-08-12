# 監視・アラート設定文書 (Monitoring & Alerting)

## ヘルスチェックエンドポイント

### エンドポイント

```
GET /api/health
```

### 正常レスポンス

```json
{
  "status": "ok",
  "service": "construction-logistics-route-planner",
  "version": "0.1.0",
  "disclaimer": "本システムは..."
}
```

### 監视频度

| 経路 | 方法 | 間隔 |
|---|---|---|
| Docker コンテナ | ビルトイン `HEALTHCHECK`（`Dockerfile:23-24`） | 30 秒 |
| systemd サービス | `systemctl --user status`（`Restart=on-failure` が有効） | プロセス監視（即時） |
| 外部監視 | cron + curl スクリプト | 5 分 |
| CI 監視 | GitHub Actions CI（push 時実行） | コミット毎 |

---

## 主要監視メトリクス

### アプリケーションメトリクス

| メトリクス | 取得方法 | 正常範囲 | 警告閾値 | 危険閾値 |
|---|---|---|---|---|
| `/api/health` 応答時間 | `curl -w` で計測 | < 50ms | > 200ms | > 1s |
| `/api/health` ステータスコード | curl exit code | 200 | 継続的 4xx | 5xx |
| DB ファイルサイズ | `stat -c%s state.db` | < 100MB | > 500MB | > 1GB |
| DB 接続状態 | `sqlite3 state.db "PRAGMA integrity_check;"` | `ok` | — | `ok` 以外 |
| `/api/projects` 応答時間 | API 計測 | < 500ms | > 2s | > 5s |
| API エラーレート | journalctl 集計 | 0% | > 1% | > 5% |
| 同時接続数 | `ss -tnp \| grep :18017 \| wc -l` | < 10 | > 50 | > 100 |

### システムメトリクス

| メトリクス | 取得方法 | 正常範囲 | 警告閾値 | 危険閾値 |
|---|---|---|---|---|
| CPU 使用率 | `ps aux \| grep uvicorn` | < 10% | > 50% | > 80% |
| メモリ使用量 | `ps -o rss= -p <pid>` | < 500MB | > 1GB | > 2GB |
| ディスク使用率 | `df -h /` | < 70% | > 85% | > 95% |
| プロセス生存 | `pgrep -f uvicorn` | 1 以上 | — | 0（停止中） |

---

## アラート閾値

### アラートレベル定義

| レベル | 意味 | 通知方法 | 対応期限 |
|---|---|---|---|
| CRITICAL | サービス停止中 | 即時 Slack / メール | 15 分以内に着手 |
| WARNING | 性能劣化・リソース逼迫 | Slack | 1 時間以内に調査 |
| INFO | 傾向検知 | ダッシュボードのみ | 次回定例 |

### アラートルール一覧

| ルール | 条件 | レベル | 説明 |
|---|---|---|---|
| `health-check-failure` | `/api/health` が連続 3 回 200 以外 | CRITICAL | サービス停止の可能性 |
| `health-check-slow` | 応答時間 > 1s が 5 分継続 | WARNING | 性能劣化 |
| `db-integrity-fail` | `PRAGMA integrity_check` が `ok` 以外 | CRITICAL | DB 破損（データ損失リスク） |
| `db-size-warning` | `state.db` が 500MB 超過 | WARNING | DB 肥大化 |
| `db-size-critical` | `state.db` が 1GB 超過 | CRITICAL | ディスク逼迫リスク |
| `disk-space-warning` | ディスク使用率 85% 超 | WARNING | 空き容量不足 |
| `disk-space-critical` | ディスク使用率 95% 超 | CRITICAL | 書き込み不能リスク |
| `process-down` | uvicorn プロセス不在 | CRITICAL | サービス停止 |
| `api-error-rate` | 直近 5 分のエラー率 5% 超 | WARNING | API 品質劣化 |
| `backup-failure` | バックアップスクリプト終了コード != 0 | WARNING | バックアップ未取得 |

---

## 監視スクリプト

### 統合ヘルスチェックスクリプト

リポジトリの `scripts/monitor.sh` が正規の監視スクリプトです
（`MONITOR_BASE_URL` で対象 URL を変更可能。既定 `http://127.0.0.1:18017`）。
以下は同等機能の参考実装です。

```bash
#!/bin/bash
# 統合ヘルスチェックスクリプト
# 正規版: scripts/monitor.sh
# cron: */5 * * * * /home/kensan/scripts/monitor.sh

set -euo pipefail

PROJECT_DIR="/home/kensan/Projects/Mirai-DX-Project/Construction-Logistics-Route-Planner"
LOG_DIR="$PROJECT_DIR/backups/monitor"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date -Iseconds)
LOG_FILE="$LOG_DIR/monitor_$(date +%Y%m%d).log"
ALERT_FILE="$LOG_DIR/alerts_$(date +%Y%m%d).log"

check_health() {
    local url="$1"
    local name="$2"
    local start end code

    start=$(date +%s%N)
    code=$(curl -sf -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")
    end=$(date +%s%N)
    local elapsed_ms=$(( (end - start) / 1000000 ))

    if [ "$code" != "200" ]; then
        echo "[CRITICAL] $TIMESTAMP: $name health check FAILED (HTTP $code, ${elapsed_ms}ms)" | tee -a "$ALERT_FILE"
        return 1
    elif [ "$elapsed_ms" -gt 1000 ]; then
        echo "[WARNING] $TIMESTAMP: $name health check SLOW (HTTP $code, ${elapsed_ms}ms)" | tee -a "$ALERT_FILE"
        return 0
    fi
    echo "[OK] $TIMESTAMP: $name health check OK (${elapsed_ms}ms)"
    return 0
}

check_db() {
    local db_file="$PROJECT_DIR/state.db"

    if [ ! -f "$db_file" ]; then
        echo "[CRITICAL] $TIMESTAMP: DB file not found: $db_file" | tee -a "$ALERT_FILE"
        return 1
    fi

    local integrity
    integrity=$(sqlite3 "$db_file" "PRAGMA integrity_check;" 2>/dev/null || echo "ERROR")
    if [ "$integrity" != "ok" ]; then
        echo "[CRITICAL] $TIMESTAMP: DB integrity check FAILED: $integrity" | tee -a "$ALERT_FILE"
        return 1
    fi

    local size_bytes
    size_bytes=$(stat -c%s "$db_file")
    local size_mb=$(( size_bytes / 1024 / 1024 ))

    if [ "$size_mb" -gt 1000 ]; then
        echo "[CRITICAL] $TIMESTAMP: DB size critical: ${size_mb}MB (>1GB)" | tee -a "$ALERT_FILE"
    elif [ "$size_mb" -gt 500 ]; then
        echo "[WARNING] $TIMESTAMP: DB size warning: ${size_mb}MB (>500MB)" | tee -a "$ALERT_FILE"
    else
        echo "[OK] $TIMESTAMP: DB OK (${size_mb}MB, integrity ok)"
    fi
}

check_process() {
    if ! pgrep -f "uvicorn app.main:app" > /dev/null; then
        echo "[CRITICAL] $TIMESTAMP: uvicorn process NOT running" | tee -a "$ALERT_FILE"
        return 1
    fi
    echo "[OK] $TIMESTAMP: uvicorn process running"
    return 0
}

check_disk() {
    local usage
    usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$usage" -gt 95 ]; then
        echo "[CRITICAL] $TIMESTAMP: Disk usage critical: ${usage}%" | tee -a "$ALERT_FILE"
    elif [ "$usage" -gt 85 ]; then
        echo "[WARNING] $TIMESTAMP: Disk usage warning: ${usage}%" | tee -a "$ALERT_FILE"
    else
        echo "[OK] $TIMESTAMP: Disk usage OK (${usage}%)"
    fi
}

# 全チェック実行（結果をログに追記）
{
    echo "=== Monitor Run: $TIMESTAMP ==="
    check_health "http://127.0.0.1:18017/api/health" "systemd"
    check_health "http://127.0.0.1:28080/api/health" "Docker" 2>/dev/null || echo "[INFO] $TIMESTAMP: Docker not running (expected if not in use)"
    check_db
    check_process
    check_disk
    echo ""
} >> "$LOG_FILE"
```

### cron 登録

```bash
# 5 分間隔で監視
crontab -e
# 以下を追加:
*/5 * * * * /home/kensan/scripts/monitor.sh
```

---

## ログ集約

### ログの種類と場所

| ログ種別 | 場所 | 取得方法 |
|---|---|---|
| アプリケーションログ (systemd) | journald | `journalctl --user -u construction-logistics-route-planner.service` |
| アプリケーションログ (Docker) | Docker stdout | `docker compose logs` |
| アクセスログ | uvicorn 標準出力（上記に統合） | 同上 |
| 監査ログ (`audit_logs` テーブル) | `state.db` 内 | SQLite クエリ |
| バックアップログ | `backups/backup.log` | ファイル読み取り |
| 監視ログ | `backups/monitor/` | ファイル読み取り |
| アラートログ | `backups/monitor/alerts_YYYYMMDD.log` | ファイル読み取り |

### ログローテーション

```bash
# journald はデフォルトで自動ローテーションされる

# 監視ログの手動ローテーション（月次）
# 設置先: /etc/cron.monthly/rotate-monitor-logs または crontab
find /home/kensan/Projects/Mirai-DX-Project/Construction-Logistics-Route-Planner/backups/monitor/ \
  -name "monitor_*.log" -mtime +90 -delete
find /home/kensan/Projects/Mirai-DX-Project/Construction-Logistics-Route-Planner/backups/monitor/ \
  -name "alerts_*.log" -mtime +90 -delete
```

### アラート発生時のログ確認

```bash
# 本日のアラート確認
cat backups/monitor/alerts_$(date +%Y%m%d).log

# CRITICAL のみ抽出
grep "CRITICAL" backups/monitor/alerts_$(date +%Y%m%d).log

# エラー発生時刻付近のアプリケーションログ
journalctl --user -u construction-logistics-route-planner.service \
  --since "2026-07-18 10:00" --until "2026-07-18 11:00"
```

---

## ダッシュボード設定ガイド

### 簡易ダッシュボード（cron + HTML レポート）

現在の MVP フェーズでは Grafana 等の本格的なダッシュボードは導入していません。以下の簡易的な方法で監視状況を可視化できます。

#### ステータスページ生成スクリプト

```bash
#!/bin/bash
# 簡易ステータスダッシュボード生成
# 設置先: /home/kensan/scripts/gen-dashboard.sh

OUTPUT_DIR="/home/kensan/Projects/Mirai-DX-Project/Construction-Logistics-Route-Planner/backups/monitor"
OUTPUT_FILE="$OUTPUT_DIR/status.html"

HEALTH_SYSTEMD=$(curl -sf -o /dev/null -w "%{http_code}" http://127.0.0.1:18017/api/health 2>/dev/null || echo "000")
HEALTH_DOCKER=$(curl -sf -o /dev/null -w "%{http_code}" http://127.0.0.1:28080/api/health 2>/dev/null || echo "000")
DB_SIZE=$(stat -c%s state.db 2>/dev/null | awk '{printf "%.1f MB", $1/1024/1024}')
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}')
UPTIME=$(systemctl --user show construction-logistics-route-planner.service -p ActiveEnterTimestamp 2>/dev/null | cut -d= -f2)

cat > "$OUTPUT_FILE" <<EOF
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="utf-8"><title>Route Planner Status</title>
<style>
body { font-family: monospace; max-width: 800px; margin: 2em auto; padding: 0 1em; background: #1a1a2e; color: #eee; }
h1 { border-bottom: 2px solid #e94560; padding-bottom: .5em; }
table { width: 100%; border-collapse: collapse; margin: 1em 0; }
th, td { padding: .75em; text-align: left; border-bottom: 1px solid #333; }
th { background: #16213e; }
.ok { color: #0f0; }
.down { color: #e94560; }
.warn { color: #f0a500; }
</style></head>
<body>
<h1>Route Planner Status - $(date)</h1>
<table>
<tr><th>項目</th><th>状態</th><th>詳細</th></tr>
<tr><td>systemd (18017)</td>
<td class="$([ "$HEALTH_SYSTEMD" = "200" ] && echo "ok" || echo "down")">$([ "$HEALTH_SYSTEMD" = "200" ] && echo "OK" || echo "DOWN ($HEALTH_SYSTEMD)")</td>
<td>起動時刻: ${UPTIME:-N/A}</td></tr>
<tr><td>Docker (28080)</td>
<td class="$([ "$HEALTH_DOCKER" = "200" ] && echo "ok" || echo "warn")">$([ "$HEALTH_DOCKER" = "200" ] && echo "OK" || echo "N/A ($HEALTH_DOCKER)")</td>
<td>使用時のみ起動</td></tr>
<tr><td>DB size</td>
<td>$DB_SIZE</td><td></td></tr>
<tr><td>Disk usage</td>
<td class="$([ "${DISK_USAGE%\%}" -gt 85 ] && echo "warn" || echo "ok")">$DISK_USAGE</td><td></td></tr>
</table>
<p style="color:#666;font-size:.8em">Generated: $(date -Iseconds)</p>
</body></html>
EOF

echo "Dashboard generated: $OUTPUT_FILE"
```

### 将来の拡張案（フェーズ 3-4）

| ツール | 用途 | 優先度 |
|---|---|---|
| Prometheus + Grafana | メトリクス収集・可視化 | 中 |
| Sentry | エラー追跡・通知 | 高 |
| Uptime Kuma | 外部ヘルスチェック監視 | 高 |
| Loki + Grafana | ログ集約・検索 | 中 |
| Slack Webhook | アラート通知 | 高 |

### アラート通知の将来設定（例: Slack）

```bash
#!/bin/bash
# Slack 通知関数（将来実装用スケルトン）
notify_slack() {
    local webhook_url="$SLACK_WEBHOOK_URL"
    local level="$1"
    local message="$2"

    local color
    case "$level" in
        CRITICAL) color="#e94560" ;;
        WARNING)  color="#f0a500" ;;
        *)        color="#36a64f" ;;
    esac

    curl -sf -X POST "$webhook_url" \
        -H "Content-Type: application/json" \
        -d "{
            \"attachments\": [{
                \"color\": \"$color\",
                \"title\": \"[$level] Route Planner Alert\",
                \"text\": \"$message\",
                \"footer\": \"Route Planner Monitor\"
            }]
        }" || echo "Failed to send Slack notification" >&2
}
```
