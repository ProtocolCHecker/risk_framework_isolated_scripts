"""
Asset Configuration Validator.

Checks each asset config JSON against fetcher requirements.
"""

import json
import os
import glob
from typing import Dict, List, Tuple

# Fetcher requirements
FETCHER_REQUIREMENTS = {
    "oracle": {
        "description": "Oracle freshness metrics",
        "required_any": [
            ["oracles"],
            ["oracle_freshness", "price_feeds"]
        ],
        "also_needs": ["rpc_urls"]
    },
    "reserve": {
        "description": "Proof of Reserve / backing ratio",
        "required_any": [
            ["proof_of_reserve"]
        ],
        "por_types": ["chainlink_por", "fractional", "fractional_reserve", "nav_based", "liquid_staking", "apostro_scraper"]
    },
    "liquidity": {
        "description": "Slippage and TVL metrics",
        "required_any": [
            ["dex_pools"]
        ],
        "also_needs_any": [
            ["coingecko_id"],
            ["price_risk", "token_coingecko_id"]
        ]
    },
    "lending": {
        "description": "CLR, RLR, utilization metrics",
        "required_any": [
            ["lending_markets"],
            ["lending_configs"]
        ]
    },
    "distribution": {
        "description": "HHI, Gini, concentration metrics",
        "required_any": [
            ["chains"],
            ["token_addresses"]
        ],
        "also_needs": ["blockscout_apis"]
    },
    "market": {
        "description": "Volatility, VaR, peg deviation",
        "required_any": [
            ["coingecko_id"],
            ["price_risk", "token_coingecko_id"]
        ]
    }
}


def get_nested(config: Dict, keys: List[str]):
    """Get nested value from config."""
    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value


def check_fetcher_requirements(config: Dict, fetcher: str) -> Tuple[bool, str, List[str]]:
    """
    Check if config meets fetcher requirements.

    Returns:
        Tuple of (passes, status, issues)
    """
    req = FETCHER_REQUIREMENTS[fetcher]
    issues = []

    # Check required_any
    has_required = False
    for path in req.get("required_any", []):
        value = get_nested(config, path)
        if value is not None and value != [] and value != {}:
            has_required = True
            break

    if not has_required:
        paths_str = " OR ".join([".".join(p) for p in req["required_any"]])
        issues.append(f"Missing: {paths_str}")
        return False, "MISSING", issues

    # Check also_needs (all required)
    for key in req.get("also_needs", []):
        if key not in config or not config[key]:
            issues.append(f"Missing dependency: {key}")

    # Check also_needs_any (at least one)
    also_needs_any = req.get("also_needs_any", [])
    if also_needs_any:
        has_any = False
        for path in also_needs_any:
            value = get_nested(config, path)
            if value is not None:
                has_any = True
                break
        if not has_any:
            paths_str = " OR ".join([".".join(p) for p in also_needs_any])
            issues.append(f"Missing: {paths_str}")

    # Special check for reserve fetcher - check por type
    if fetcher == "reserve":
        por = config.get("proof_of_reserve", {})
        por_type = por.get("type") or por.get("verification_type")
        if por_type and por_type not in req.get("por_types", []):
            issues.append(f"Unknown PoR type: {por_type}")

    # Special check for liquidity - need token info in dex_pools
    if fetcher == "liquidity":
        dex_pools = config.get("dex_pools", [])
        if isinstance(dex_pools, list):
            for i, pool in enumerate(dex_pools):
                has_sell = pool.get("token_address") or pool.get("sell_token")
                has_buy = pool.get("quote_token") or pool.get("buy_token")
                if not has_sell:
                    # Check if token_addresses can provide it
                    chain = pool.get("chain")
                    token_addr = next(
                        (ta.get("address") for ta in config.get("token_addresses", []) if ta.get("chain") == chain),
                        None
                    )
                    if not token_addr:
                        issues.append(f"dex_pools[{i}] ({pool.get('pool_name', 'unknown')}): missing token_address")
                if not has_buy:
                    issues.append(f"dex_pools[{i}] ({pool.get('pool_name', 'unknown')}): missing quote_token")

    if issues:
        return True, "PARTIAL", issues
    return True, "OK", []


def validate_config(config: Dict) -> Dict:
    """Validate a single config against all fetchers."""
    symbol = config.get("asset_symbol", "UNKNOWN")
    results = {
        "asset_symbol": symbol,
        "asset_name": config.get("asset_name", ""),
        "fetchers": {}
    }

    for fetcher in FETCHER_REQUIREMENTS:
        passes, status, issues = check_fetcher_requirements(config, fetcher)
        results["fetchers"][fetcher] = {
            "status": status,
            "passes": passes,
            "issues": issues
        }

    return results


def print_validation_report(results: List[Dict]):
    """Print formatted validation report."""
    print("\n" + "=" * 100)
    print("ASSET CONFIGURATION VALIDATION REPORT")
    print("=" * 100)

    # Summary table
    print("\n{:<12} {:<10} {:<10} {:<10} {:<10} {:<10} {:<10}".format(
        "Asset", "Oracle", "Reserve", "Liquidity", "Lending", "Distrib", "Market"
    ))
    print("-" * 80)

    for result in results:
        row = [result["asset_symbol"]]
        for fetcher in ["oracle", "reserve", "liquidity", "lending", "distribution", "market"]:
            status = result["fetchers"][fetcher]["status"]
            if status == "OK":
                row.append("✅")
            elif status == "PARTIAL":
                row.append("⚠️")
            else:
                row.append("❌")
        print("{:<12} {:<10} {:<10} {:<10} {:<10} {:<10} {:<10}".format(*row))

    # Detailed issues
    print("\n" + "=" * 100)
    print("DETAILED ISSUES")
    print("=" * 100)

    for result in results:
        has_issues = any(
            result["fetchers"][f]["issues"]
            for f in result["fetchers"]
        )
        if has_issues:
            print(f"\n{result['asset_symbol']} ({result['asset_name']})")
            print("-" * 60)
            for fetcher, data in result["fetchers"].items():
                if data["issues"]:
                    print(f"  {fetcher}:")
                    for issue in data["issues"]:
                        print(f"    - {issue}")

    # Statistics
    print("\n" + "=" * 100)
    print("STATISTICS")
    print("=" * 100)

    total = len(results)
    for fetcher in FETCHER_REQUIREMENTS:
        ok = sum(1 for r in results if r["fetchers"][fetcher]["status"] == "OK")
        partial = sum(1 for r in results if r["fetchers"][fetcher]["status"] == "PARTIAL")
        missing = sum(1 for r in results if r["fetchers"][fetcher]["status"] == "MISSING")
        print(f"{fetcher:<15}: {ok}/{total} OK, {partial} partial, {missing} missing")


def main():
    """Main validation function."""
    # Find config files
    script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_patterns = [
        os.path.join(script_dir, "example_*_config.json"),
        os.path.join(script_dir, "asset_configs", "*.json"),
    ]

    config_files = []
    for pattern in config_patterns:
        config_files.extend(glob.glob(pattern))

    # Remove test_config.json if present
    config_files = [f for f in config_files if "test_config" not in f]

    if not config_files:
        print("No config files found!")
        return

    print(f"Found {len(config_files)} config files:")
    for f in config_files:
        print(f"  - {os.path.basename(f)}")

    # Validate each config
    results = []
    for config_file in config_files:
        try:
            with open(config_file) as f:
                config = json.load(f)
            results.append(validate_config(config))
        except Exception as e:
            print(f"Error loading {config_file}: {e}")

    # Print report
    print_validation_report(results)


if __name__ == "__main__":
    main()
