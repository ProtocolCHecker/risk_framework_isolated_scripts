# Development Guide

> Generated: 2026-01-22 | DeFi Risk Assessment Framework

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.13+ | Tested with 3.13.1 |
| pip | Latest | Package manager |
| Git | Any | Version control |

## Quick Start

### 1. Clone & Setup Environment

```bash
# Navigate to project
cd risk_framework_isolated_scripts

# Create virtual environment (if not exists)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
.\venv\Scripts\activate   # Windows
```

### 2. Install Dependencies

```bash
pip install streamlit pandas numpy web3 requests plotly pydantic aiohttp beautifulsoup4 pyarrow
```

**Key Dependencies:**

| Package | Version | Purpose |
|---------|---------|---------|
| streamlit | 1.53.0 | Web dashboard framework |
| web3 | 7.14.0 | Ethereum RPC interactions |
| pandas | 2.3.3 | Data manipulation |
| numpy | 2.4.1 | Numerical computations |
| plotly | 6.5.2 | Interactive visualizations |
| requests | 2.32.5 | HTTP client for APIs |
| pydantic | 2.12.5 | Data validation |
| aiohttp | 3.13.3 | Async HTTP requests |
| beautifulsoup4 | 4.14.3 | HTML parsing |
| pyarrow | 23.0.0 | Data serialization |

### 3. Run the Dashboard

```bash
streamlit run streamlit_app.py
```

The dashboard will open at `http://localhost:8501`

### 4. Alternative: CLI Runner

```bash
python risk_framework.py
```

Follow the interactive prompts to run specific analyses.

## Environment Variables

No environment variables are required for basic operation. API keys are embedded in the source files:

| Service | Location | Notes |
|---------|----------|-------|
| dRPC | Various `*.py` files | RPC endpoints for Ethereum, Base, Arbitrum |
| The Graph | Config JSON files | Subgraph IDs for DEX data |
| CoinGecko | `price_risk.py` | Free tier, no key required |
| Blockscout | Various `*.py` files | Public API, no key required |

## Configuration Files

To analyze a new asset, create a JSON config file based on existing templates:

```bash
# Copy an existing template
cp example_wsteth_config.json my_asset_config.json

# Edit the configuration
# Then load it in the Streamlit dashboard
```

**Config Structure:**
- `asset_name`, `asset_symbol`, `asset_type` - Basic metadata
- `token_addresses` - Multi-chain addresses
- `lending_configs` - Aave/Compound market configs
- `dex_pools` - DEX pool addresses
- `proof_of_reserve` - Reserve verification settings
- `oracle_lag` - Chainlink price feed addresses
- `audit_data` - Security audit information
- `multisig_configs` - Governance structure

## Development Workflow

### Adding a New Data Fetcher

1. Create a new Python file (e.g., `new_protocol.py`)
2. Implement the analysis function following existing patterns:
   ```python
   def analyze_new_protocol(config: dict) -> dict:
       """Fetch and analyze data from NewProtocol."""
       # Implement data fetching logic
       return {"metric1": value1, "metric2": value2}
   ```
3. Import in `streamlit_app.py`
4. Add a new tab or integrate into existing tabs

### Modifying Scoring Thresholds

1. Edit `thresholds.py` to adjust threshold values
2. Each threshold includes:
   - `value` - The numeric threshold
   - `score` - Score assigned at this threshold
   - `justification` - Why this threshold was chosen

### Adding a New Risk Category

1. Add category definition in `thresholds.py`
2. Add category weight in `CATEGORY_WEIGHTS`
3. Implement scoring logic in `asset_score.py`
4. Update `streamlit_app.py` to display new metrics

## Testing

Currently no automated tests. Manual testing workflow:

1. Load a known-good config (e.g., `example_wsteth_config.json`)
2. Verify all tabs load without errors
3. Spot-check metrics against on-chain data
4. Use verification scripts for data accuracy:
   ```bash
   python uniswap_check.py
   python curve_check.py
   python pancakeswap_check.py
   ```

## Common Issues

### RPC Rate Limits

If you see RPC errors, the public endpoints may be rate-limited. Solutions:
- Wait and retry
- Use your own RPC endpoints (edit URLs in source files)
- Reduce concurrent requests

### The Graph API Limits

Subgraph queries have rate limits. If you hit them:
- Add delays between requests
- Use a paid The Graph API key

### Module Import Errors

If imports fail, ensure you're in the activated virtual environment:
```bash
source venv/bin/activate
python -c "import streamlit; print('OK')"
```

## Project Structure Reference

```
├── streamlit_app.py      # Main entry point
├── asset_score.py        # Scoring logic
├── thresholds.py         # Threshold definitions
├── primary_checks.py     # Qualification checks
├── [protocol]_data.py    # Data fetchers
├── [protocol]_check.py   # Data verification
└── example_*.json        # Config templates
```

## Deployment

No deployment configuration exists. For production deployment:

1. **Streamlit Cloud** (recommended for quick deployment)
   - Push to GitHub
   - Connect to Streamlit Cloud
   - Configure secrets for API keys

2. **Docker** (not yet configured)
   - Would need Dockerfile creation
   - Consider multi-stage build for smaller image

3. **Self-hosted**
   - Run behind nginx/Apache reverse proxy
   - Use `streamlit run --server.port 80`
