"""
Monitoring system configuration.

Database connection and other settings.
"""

import os

# Database configuration - uses existing Avantgarde RDS
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "avantgarde.czecagq2wers.eu-west-1.rds.amazonaws.com"),
    "database": os.getenv("DB_NAME", "avantgarde"),
    "user": os.getenv("DB_USER", "florian"),
    "password": os.getenv("DB_PASSWORD", "Dbeaverflo031299?"),
    "port": int(os.getenv("DB_PORT", 5432))
}

# Schema for risk monitoring tables
# NOTE: Using 'morpho' temporarily until admin creates 'risk_monitoring' schema
# All tables prefixed with 'rm_' to distinguish from existing morpho tables
SCHEMA_NAME = "morpho"
TABLE_PREFIX = "rm_"  # risk monitoring prefix

# Alert notification settings
ALERT_CONFIG = {
    "slack_webhook": os.getenv("SLACK_WEBHOOK_URL"),
    "discord_webhook": os.getenv("DISCORD_WEBHOOK_URL"),
    "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN"),
    "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID"),
}

# Metric frequency categories (in minutes)
FREQUENCY_CONFIG = {
    "critical": 5,      # PoR ratio, oracle freshness, peg deviation
    "high": 30,         # TVL, utilization, slippage
    "medium": 360,      # HHI, Gini, CLR, RLR, supply
    "daily": 1440,      # Volatility, VaR
}
