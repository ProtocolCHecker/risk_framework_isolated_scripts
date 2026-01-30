# Risk Monitoring System - Deployment Guide

## Overview

This system monitors DeFi asset risk metrics on a scheduled basis and sends alerts to Telegram when thresholds are breached.

**Key Features:**
- Fetches 22 risk metrics across 6 categories
- Stores metrics in PostgreSQL (existing RDS instance)
- Triggers alerts based on configurable thresholds
- Sends notifications via Telegram

**Tested Assets:** WBTC, wstETH, cbBTC, RLP, cUSD

---

## Verification Status

| Component | Status | Notes |
|-----------|--------|-------|
| Fetchers (6) | ✅ Tested | oracle, reserve, liquidity, lending, distribution, market |
| Database | ✅ Tested | Connection, inserts, queries all working |
| Alerts | ✅ Tested | Threshold checking and logging verified |
| Dispatcher | ✅ Tested | All 4 frequencies collecting metrics |
| Registry | ✅ Tested | 5 assets registered and retrieved |
| Telegram | ✅ Tested | Alerts sent successfully |
| Handlers | ⚠️ Partial | Logic tested, Lambda deploy pending |
| Slack | ⏭️ Skipped | No admin access |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     CloudWatch Events (Schedules)                    │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐ │
│   │ 5 min   │  │ 30 min  │  │ 6 hour  │  │ 24 hour │  │  5 min   │ │
│   └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬─────┘ │
└────────┼────────────┼───────────┼───────────┼─────────────┼────────┘
         ▼            ▼           ▼           ▼             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Lambda Functions                              │
│                                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐│
│  │ critical │ │   high   │ │  medium  │ │  daily   │ │notification││
│  │ handler  │ │ handler  │ │ handler  │ │ handler  │ │  handler   ││
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬──────┘│
└───────┼────────────┼────────────┼────────────┼─────────────┼───────┘
        │            │            │            │             │
        ▼            ▼            ▼            ▼             │
┌─────────────────────────────────────────────────────────┐ │
│                  Fetchers (Data Collection)              │ │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │ │
│  │ Oracle │ │Reserve │ │Liquidty│ │Lending │ │ Market │ │ │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ │ │
└─────────────────────────┬───────────────────────────────┘ │
                          ▼                                 │
┌─────────────────────────────────────────────────────────┐ │
│              PostgreSQL (morpho schema)                  │ │
│  ┌─────────────┐ ┌─────────────┐ ┌───────────────────┐  │ │
│  │ rm_metrics  │ │rm_alerts_log│ │rm_alert_thresholds│  │ │
│  └─────────────┘ └─────────────┘ └───────────────────┘  │ │
└─────────────────────────────────────────────────────────┘ │
                                                            │
┌───────────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────┐
│                    Telegram API                          │
│              (Alert Notifications)                       │
└─────────────────────────────────────────────────────────┘
```

---

## Lambda Functions

| Function Name | Schedule | Timeout | Memory | Metrics |
|---------------|----------|---------|--------|---------|
| `risk-monitoring-critical` | Every 5 min | 180s | 512MB | PoR ratio, oracle freshness, peg deviation |
| `risk-monitoring-high` | Every 30 min | 300s | 1024MB | Pool TVL, utilization, slippage |
| `risk-monitoring-medium` | Every 6 hours | 600s | 1024MB | HHI, Gini, CLR, RLR, supply |
| `risk-monitoring-daily` | Every 24 hours | 600s | 512MB | Volatility, VaR, CVaR |
| `risk-monitoring-notifications` | Every 5 min | 60s | 256MB | Process pending alerts |

**Handler paths:**
```
handlers/critical_handler.handler
handlers/high_handler.handler
handlers/medium_handler.handler
handlers/daily_handler.handler
handlers/notification_handler.handler
```

---

## Database Schema

All tables are in the `morpho` schema with `rm_` prefix.

### Tables Overview

| Table | Purpose |
|-------|---------|
| `rm_metrics_history` | All collected metrics (time series) |
| `rm_latest_metrics` | Most recent value per metric |
| `rm_alerts_log` | Triggered alerts history |
| `rm_alert_thresholds` | Configurable thresholds |
| `rm_asset_registry` | Asset configurations |
| `rm_asset_health` | Asset health scores |
| `rm_active_alerts` | Currently active (unresolved) alerts |

### rm_metrics_history
Stores all collected metrics.

```sql
CREATE TABLE morpho.rm_metrics_history (
    id SERIAL PRIMARY KEY,
    asset_symbol VARCHAR(20) NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    value NUMERIC NOT NULL,
    chain VARCHAR(20),
    metadata JSONB,
    recorded_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_rm_metrics_asset_time ON morpho.rm_metrics_history(asset_symbol, recorded_at DESC);
CREATE INDEX idx_rm_metrics_name_time ON morpho.rm_metrics_history(metric_name, recorded_at DESC);
```

### rm_alerts_log
Logs triggered alerts.

```sql
CREATE TABLE morpho.rm_alerts_log (
    id SERIAL PRIMARY KEY,
    asset_symbol VARCHAR(20) NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    value NUMERIC NOT NULL,
    threshold_value NUMERIC NOT NULL,
    operator VARCHAR(5) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT,
    chain VARCHAR(20),
    notified BOOLEAN DEFAULT FALSE,
    notification_channel VARCHAR(20),
    triggered_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_rm_alerts_notified ON morpho.rm_alerts_log(notified, severity);
```

### rm_alert_thresholds
Configurable alert thresholds.

```sql
CREATE TABLE morpho.rm_alert_thresholds (
    id SERIAL PRIMARY KEY,
    asset_symbol VARCHAR(20),  -- NULL = global (all assets)
    metric_name VARCHAR(50) NOT NULL,
    operator VARCHAR(5) NOT NULL,  -- '<', '>', '<=', '>='
    threshold_value NUMERIC NOT NULL,
    severity VARCHAR(20) NOT NULL,  -- 'critical', 'warning', 'info'
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Pre-populated thresholds:** 40 thresholds based on scoring framework (14 critical, 15 warning, 11 info).

---

## Supported Verification Types

### Reserve (Proof of Reserve)
| Type | Description | Example Asset |
|------|-------------|---------------|
| `chainlink_por` | Chainlink PoR feeds | WBTC, cbBTC |
| `liquid_staking` | LST backing ratio | wstETH, rETH |
| `fractional` | Fractional reserve | cUSD |
| `nav_based` | NAV oracle-based | - |
| `apostro_scraper` | Resolv dashboard + NAV oracle | RLP |

### Config Format Compatibility
Fetchers support both formats:
- **New format**: Lists (`token_addresses`, `dex_pools`, `lending_configs`, `price_feeds`)
- **Legacy format**: Dicts (`chains`, `oracles`, `lending_markets`)

---

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_HOST` | RDS PostgreSQL endpoint | `avantgarde.xxx.eu-west-1.rds.amazonaws.com` |
| `DB_NAME` | Database name | `avantgarde` |
| `DB_USER` | Database username | `florian` |
| `DB_PASSWORD` | Database password | `***` |
| `DB_PORT` | Database port | `5432` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token | `8244407314:AAEvEWGNEDQ5...` |
| `TELEGRAM_CHAT_ID` | Telegram channel/group ID | `-1003789839646` |

---

## VPC Configuration

Lambda functions need VPC access to reach RDS.

**Required:**
- Subnet IDs in the same VPC as RDS (at least 2 for HA)
- Security Group that allows outbound to RDS on port 5432
- NAT Gateway for external API calls (CoinGecko, aggregators, RPCs)

---

## Deployment

### Option 1: SAM CLI (Recommended)

```bash
cd monitoring/deploy

# First time - guided setup
sam build -t template.yaml
sam deploy --guided

# Subsequent deployments
sam build && sam deploy
```

### Option 2: Manual Lambda Setup

1. **Create Lambda Layer** with dependencies:
   ```bash
   pip install -r deploy/requirements.txt -t python/lib/python3.11/site-packages/
   zip -r layer.zip python/
   # Upload as Lambda Layer
   ```

2. **Create Lambda Functions** (5 total):
   - Runtime: Python 3.11
   - Handler: `handlers/{name}_handler.handler`
   - Add Layer from step 1
   - Configure VPC, environment variables

3. **Create CloudWatch Events Rules**:
   - `rate(5 minutes)` → critical_handler, notification_handler
   - `rate(30 minutes)` → high_handler
   - `rate(6 hours)` → medium_handler
   - `rate(1 day)` → daily_handler

---

## Monitoring & Troubleshooting

### View Logs

```bash
# Critical handler logs
aws logs tail /aws/lambda/risk-monitoring-critical-production --follow

# Filter errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/risk-monitoring-critical-production \
  --filter-pattern "ERROR"
```

### Manual Invocation

```bash
# Test critical handler
aws lambda invoke \
  --function-name risk-monitoring-critical-production \
  --payload '{}' \
  response.json

cat response.json
```

### Expected Response

```json
{
  "statusCode": 200,
  "body": {
    "handler": "critical",
    "status": "success",
    "dispatch_result": {
      "assets_processed": 5,
      "metrics_collected": 22,
      "alerts_triggered": 0,
      "errors": []
    },
    "duration_ms": 45000
  }
}
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `Connection timed out` | Lambda can't reach RDS | Check VPC config, security groups |
| `No module named 'psycopg2'` | Missing Layer | Add Lambda Layer with dependencies |
| `Telegram send failed` | Invalid token/chat ID | Verify env vars, bot permissions |
| `No metrics collected` | API rate limits | Check CloudWatch logs for specific errors |

---

## File Structure

```
monitoring/
├── config/
│   └── settings.py          # DB config, alert settings
├── core/
│   ├── db.py                 # Database connection, queries
│   ├── registry.py           # Asset config loader
│   ├── alerts.py             # Threshold checking, logging
│   └── dispatcher.py         # Routes to fetchers by frequency
├── fetchers/
│   ├── oracle.py             # Oracle freshness metrics
│   ├── reserve.py            # PoR/backing ratio
│   ├── liquidity.py          # Slippage, TVL
│   ├── lending.py            # CLR, RLR, utilization
│   ├── distribution.py       # HHI, Gini, concentration
│   └── market.py             # Volatility, VaR, peg deviation
├── handlers/
│   ├── critical_handler.py   # 5 min frequency
│   ├── high_handler.py       # 30 min frequency
│   ├── medium_handler.py     # 6 hour frequency
│   ├── daily_handler.py      # 24 hour frequency
│   └── notification_handler.py
├── notifications/
│   ├── telegram.py           # Telegram Bot API
│   └── slack.py              # Slack webhooks (optional)
├── scripts/
│   ├── populate_thresholds.py  # Insert alert thresholds
│   ├── validate_configs.py     # Validate asset configs
│   └── test_all_fetchers.py    # Test fetchers against all configs
└── deploy/
    ├── template.yaml         # SAM/CloudFormation template
    ├── samconfig.toml        # SAM CLI config
    ├── requirements.txt      # Lambda dependencies
    └── deploy.sh             # Deployment script
```

---

## Quick Start Checklist

- [ ] Verify RDS is accessible from Lambda VPC
- [ ] Create/verify database tables exist
- [ ] Run `populate_thresholds.py` to insert alert thresholds
- [ ] Set environment variables (DB + Telegram)
- [ ] Deploy Lambda functions with SAM or manually
- [ ] Create CloudWatch Events schedules
- [ ] Test with manual Lambda invocation
- [ ] Verify Telegram alerts are received

---

## Contact

For questions about the monitoring logic or metrics, contact the Risk team.
For deployment/infrastructure issues, check CloudWatch logs first.
