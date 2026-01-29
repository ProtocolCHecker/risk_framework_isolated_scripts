# Risk Monitoring System - AWS Deployment

## Overview

This deploys the Risk Monitoring System as AWS Lambda functions with CloudWatch Events triggers.

## Architecture

```
CloudWatch Events (Schedules)
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│                    Lambda Functions                      │
│                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │  Critical   │  │    High     │  │     Medium      │  │
│  │  (5 min)    │  │  (30 min)   │  │    (6 hr)       │  │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘  │
│         │                │                   │           │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌────────┴────────┐  │
│  │   Daily     │  │ Notification│  │                 │  │
│  │  (24 hr)    │  │  (5 min)    │  │                 │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│                 RDS PostgreSQL (morpho)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ rm_metrics   │  │ rm_alerts    │  │ rm_thresholds│   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│                     Telegram API                         │
│                   (Alert Notifications)                  │
└─────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **SAM CLI** installed: `pip install aws-sam-cli`
3. **Docker** installed (for building Lambda layers)
4. **VPC Configuration** for RDS access:
   - Subnet IDs in the same VPC as your RDS
   - Security Group allowing Lambda to connect to RDS (port 5432)

## Deployment

### First-Time Deployment

Run guided deployment to configure parameters:

```bash
cd monitoring/deploy
./deploy.sh --guided
```

You'll be prompted for:
- `DatabaseHost`: Your RDS endpoint
- `DatabaseName`: `morpho`
- `DatabaseUser`: Database username
- `DatabasePassword`: Database password
- `TelegramBotToken`: Bot token from @BotFather
- `TelegramChatId`: Channel/group ID for alerts
- `VpcSubnetIds`: Comma-separated subnet IDs
- `VpcSecurityGroupIds`: Security group ID

### Subsequent Deployments

```bash
./deploy.sh production
# or
./deploy.sh staging
```

## Lambda Functions

| Function | Frequency | Metrics | Timeout | Memory |
|----------|-----------|---------|---------|--------|
| critical | 5 min | PoR ratio, oracle freshness, peg deviation | 180s | 512MB |
| high | 30 min | TVL, utilization, slippage | 300s | 1024MB |
| medium | 6 hr | HHI, Gini, CLR, RLR | 600s | 1024MB |
| daily | 24 hr | Volatility, VaR, CVaR | 600s | 512MB |
| notification | 5 min | Process pending alerts | 60s | 256MB |

## Environment Variables

All functions share these environment variables:

| Variable | Description |
|----------|-------------|
| `ENVIRONMENT` | `production` or `staging` |
| `DB_HOST` | RDS PostgreSQL endpoint |
| `DB_NAME` | Database name |
| `DB_USER` | Database username |
| `DB_PASSWORD` | Database password |
| `DB_PORT` | `5432` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token |
| `TELEGRAM_CHAT_ID` | Telegram chat/channel ID |

## Monitoring

### View Logs

```bash
# Critical function logs
aws logs tail /aws/lambda/risk-monitoring-critical-production --follow

# All functions
aws logs tail /aws/lambda/risk-monitoring-high-production --follow
aws logs tail /aws/lambda/risk-monitoring-medium-production --follow
aws logs tail /aws/lambda/risk-monitoring-daily-production --follow
aws logs tail /aws/lambda/risk-monitoring-notifications-production --follow
```

### Manual Invocation

```bash
# Invoke critical handler
aws lambda invoke \
  --function-name risk-monitoring-critical-production \
  --payload '{}' \
  output.json

cat output.json
```

### CloudWatch Metrics

Monitor in CloudWatch:
- Invocation count
- Duration
- Errors
- Throttles

## Troubleshooting

### Lambda can't connect to RDS

1. Verify VPC subnet IDs are correct
2. Ensure Security Group allows inbound on port 5432 from Lambda
3. Check RDS is in the same VPC

### Telegram notifications not sending

1. Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are correct
2. Ensure bot is added to the channel/group
3. Check CloudWatch logs for error messages

### Function timeout

1. Increase `Timeout` in template.yaml
2. Consider increasing `MemorySize` (more memory = more CPU)
3. Check if specific asset configs are causing slow fetches

## Cost Estimate

Based on default configuration:

| Resource | Monthly Estimate |
|----------|------------------|
| Lambda (Critical, 5min) | ~8,640 invocations |
| Lambda (High, 30min) | ~1,440 invocations |
| Lambda (Medium, 6hr) | ~120 invocations |
| Lambda (Daily, 24hr) | ~30 invocations |
| Lambda (Notifications, 5min) | ~8,640 invocations |
| CloudWatch Logs | Based on retention |

Total Lambda compute depends on execution duration and memory.
