-- ============================================================================
-- Risk Monitoring Tables (in morpho schema with rm_ prefix)
-- NOTE: Using morpho schema temporarily until admin creates risk_monitoring schema
-- All tables prefixed with 'rm_' to distinguish from existing morpho tables
-- ============================================================================

-- ============================================================================
-- ASSET REGISTRY
-- Stores monitored assets with their full JSON configuration
-- ============================================================================

CREATE TABLE IF NOT EXISTS morpho.rm_asset_registry (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100),
    config JSONB NOT NULL,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE morpho.rm_asset_registry IS 'Registry of monitored assets with their configurations';
COMMENT ON COLUMN morpho.rm_asset_registry.config IS 'Full JSON configuration for the asset (same format as config files)';

-- ============================================================================
-- METRICS HISTORY
-- Stores all fetched metric values over time
-- ============================================================================

CREATE TABLE IF NOT EXISTS morpho.rm_metrics_history (
    id SERIAL PRIMARY KEY,
    asset_symbol VARCHAR(20) NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    value NUMERIC(20,8),
    chain VARCHAR(20),
    metadata JSONB,
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- Index for fast lookups by asset + metric + time
CREATE INDEX IF NOT EXISTS idx_rm_metrics_lookup
ON morpho.rm_metrics_history(asset_symbol, metric_name, recorded_at DESC);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_rm_metrics_time
ON morpho.rm_metrics_history(recorded_at DESC);

COMMENT ON TABLE morpho.rm_metrics_history IS 'Historical metric values for all monitored assets';
COMMENT ON COLUMN morpho.rm_metrics_history.metadata IS 'Additional context (pool address, market id, etc.)';

-- ============================================================================
-- ALERT THRESHOLDS
-- Configurable thresholds for each metric
-- ============================================================================

CREATE TABLE IF NOT EXISTS morpho.rm_alert_thresholds (
    id SERIAL PRIMARY KEY,
    asset_symbol VARCHAR(20),  -- NULL means applies to all assets
    metric_name VARCHAR(50) NOT NULL,
    operator VARCHAR(5) NOT NULL,  -- '<', '>', '<=', '>=', '='
    threshold_value NUMERIC(20,8) NOT NULL,
    severity VARCHAR(10) NOT NULL,  -- 'critical', 'warning', 'info'
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Unique constraint to prevent duplicate thresholds
CREATE UNIQUE INDEX IF NOT EXISTS idx_rm_threshold_unique
ON morpho.rm_alert_thresholds(
    COALESCE(asset_symbol, ''), metric_name, operator, threshold_value
);

COMMENT ON TABLE morpho.rm_alert_thresholds IS 'Alert threshold configuration per metric';
COMMENT ON COLUMN morpho.rm_alert_thresholds.asset_symbol IS 'NULL means threshold applies to all assets';

-- ============================================================================
-- ALERTS LOG
-- Records triggered alerts
-- ============================================================================

CREATE TABLE IF NOT EXISTS morpho.rm_alerts_log (
    id SERIAL PRIMARY KEY,
    asset_symbol VARCHAR(20) NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    value NUMERIC(20,8),
    threshold_value NUMERIC(20,8),
    operator VARCHAR(5),
    severity VARCHAR(10),
    message TEXT,
    notified BOOLEAN DEFAULT false,
    notification_channel VARCHAR(20),  -- 'discord', 'telegram', 'email'
    triggered_at TIMESTAMP DEFAULT NOW()
);

-- Index for recent alerts
CREATE INDEX IF NOT EXISTS idx_rm_alerts_recent
ON morpho.rm_alerts_log(triggered_at DESC);

-- Index for unnotified alerts
CREATE INDEX IF NOT EXISTS idx_rm_alerts_pending
ON morpho.rm_alerts_log(notified) WHERE notified = false;

COMMENT ON TABLE morpho.rm_alerts_log IS 'Log of all triggered alerts';

-- ============================================================================
-- SEED DEFAULT THRESHOLDS
-- Default alert thresholds based on risk framework
-- ============================================================================

INSERT INTO morpho.rm_alert_thresholds (asset_symbol, metric_name, operator, threshold_value, severity)
VALUES
    -- Critical thresholds (apply to all assets)
    (NULL, 'por_ratio', '<', 1.0, 'critical'),
    (NULL, 'por_ratio', '<', 0.99, 'critical'),
    (NULL, 'oracle_freshness_minutes', '>', 30, 'warning'),
    (NULL, 'oracle_freshness_minutes', '>', 60, 'critical'),
    (NULL, 'peg_deviation_pct', '>', 2.0, 'warning'),
    (NULL, 'peg_deviation_pct', '>', 5.0, 'critical'),

    -- High frequency thresholds
    (NULL, 'utilization_rate', '>', 95, 'critical'),
    (NULL, 'utilization_rate', '>', 90, 'warning'),
    (NULL, 'pool_tvl_usd', '<', 100000, 'warning'),
    (NULL, 'slippage_100k_pct', '>', 2.0, 'warning'),
    (NULL, 'slippage_100k_pct', '>', 5.0, 'critical'),

    -- Medium frequency thresholds
    (NULL, 'hhi', '>', 4000, 'warning'),
    (NULL, 'hhi', '>', 6000, 'critical'),
    (NULL, 'gini', '>', 0.8, 'warning'),
    (NULL, 'gini', '>', 0.9, 'critical'),
    (NULL, 'clr_pct', '>', 10, 'warning'),
    (NULL, 'clr_pct', '>', 20, 'critical'),
    (NULL, 'rlr_pct', '>', 20, 'warning'),
    (NULL, 'rlr_pct', '>', 35, 'critical')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- HELPER VIEWS
-- ============================================================================

-- Latest metric values per asset
CREATE OR REPLACE VIEW morpho.rm_latest_metrics AS
SELECT DISTINCT ON (asset_symbol, metric_name)
    asset_symbol,
    metric_name,
    value,
    chain,
    metadata,
    recorded_at
FROM morpho.rm_metrics_history
ORDER BY asset_symbol, metric_name, recorded_at DESC;

-- Active alerts (triggered in last 24 hours)
CREATE OR REPLACE VIEW morpho.rm_active_alerts AS
SELECT *
FROM morpho.rm_alerts_log
WHERE triggered_at > NOW() - INTERVAL '24 hours'
ORDER BY triggered_at DESC;

-- Asset health summary
CREATE OR REPLACE VIEW morpho.rm_asset_health AS
SELECT
    ar.symbol,
    ar.name,
    ar.enabled,
    COUNT(DISTINCT mh.metric_name) as metrics_tracked,
    MAX(mh.recorded_at) as last_update,
    COUNT(DISTINCT CASE WHEN al.severity = 'critical' THEN al.id END) as critical_alerts_24h,
    COUNT(DISTINCT CASE WHEN al.severity = 'warning' THEN al.id END) as warning_alerts_24h
FROM morpho.rm_asset_registry ar
LEFT JOIN morpho.rm_metrics_history mh ON ar.symbol = mh.asset_symbol
LEFT JOIN morpho.rm_alerts_log al ON ar.symbol = al.asset_symbol
    AND al.triggered_at > NOW() - INTERVAL '24 hours'
GROUP BY ar.symbol, ar.name, ar.enabled
ORDER BY ar.symbol;
