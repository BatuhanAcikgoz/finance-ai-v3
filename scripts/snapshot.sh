#!/usr/bin/env bash
# Snapshot the running stack's relevant signals for a status dump.
set -uo pipefail

API=${API:-http://localhost:8000}
DASH=${DASH:-http://localhost:8080}

echo "================ STACK SNAPSHOT $(date +%H:%M:%S) ================"
echo ""
echo "[containers]"
docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep -E "finance-ai|^(NAMES)" | head -10 || echo "(docker ps failed)"
echo ""
echo "[api-gateway]"
for path in "/health" "/health/ready" "/v1/market/symbols" "/v1/decisions/recent" "/v1/alerts/"; do
  code=$(curl -so/dev/null -w '%{http_code}' --max-time 3 "$API$path" 2>/dev/null || echo "ERR")
  printf '  %-30s  %s\n' "$path" "$code"
done

echo ""
echo "[dashboard]"
for path in "/" "/decisions.html" "/decision-detail.html?id=foo" "/portfolio.html" "/alerts.html" "/system-health.html"; do
  code=$(curl -so/dev/null -w '%{http_code}' --max-time 3 "$DASH$path" 2>/dev/null || echo "ERR")
  size=$(curl -so/dev/null -w '%{size_download}' --max-time 3 "$DASH$path" 2>/dev/null || echo "0")
  printf '  %-30s  %s  %sb\n' "$path" "$code" "$size"
done

echo ""
echo "[postgres tables]"
docker exec finance-ai-postgres psql -U finance_ai_v3 -d finance_ai_v3 -At 2>/dev/null -c "
  SELECT 'market_data.tickers', count(*) FROM market_data.tickers UNION ALL
  SELECT 'market_data.bars',   count(*) FROM market_data.bars   UNION ALL
  SELECT 'decision.decisions', count(*) FROM decision.decisions UNION ALL
  SELECT 'notification.alerts',count(*) FROM notification.alerts;" | sed 's/^/  /'

echo ""
echo "[worker log tails]"
for svc in kap-collector technical-analysis decision-engine report-generator; do
  echo "  --- $svc ---"
  docker logs "finance-ai-${svc}" --tail 3 2>&1 | sed 's/^/    /'
done

echo ""
echo "================================================================="
