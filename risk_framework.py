#!/usr/bin/env python3
"""
Risk Framework - Unified Runner
Runs all risk analysis scripts based on configuration and returns aggregated JSON results.
"""

import json
import argparse
from datetime import datetime
from typing import Dict, Any, Optional

# Import all analysis modules
from aave_data import analyze_aave_market, CHAINS as AAVE_CHAINS
from compound import analyze_compound_market, MARKETS as COMPOUND_MARKETS
from cowswap import calculate_slippage as cowswap_slippage
from curve import CurveFinanceAnalyzer
from oracle_lag import analyze_oracle_lag
from pancakeswap import PancakeSwapV3Analyzer
from proof_of_reserve import analyze_proof_of_reserve
from slippage_check import cross_verify_slippage
from token_distribution import analyze_token
from uniswap import UniswapV3Analyzer
from price_risk import get_coingecko_data, calculate_peg_deviation, calculate_metrics

# Verification scripts (already return JSON)
from curve_check import verify_curve_lp_accuracy
from pancakeswap_check import verify_pancakeswap_v3_accuracy
from uniswap_check import verify_uniswap_v3_accuracy


def run_aave_analysis(config: Dict) -> list:
    """Run AAVE analysis for specified token across chains."""
    results = []
    token_address = config.get("token_address")
    chains = config.get("chains", ["Ethereum", "Base", "Arbitrum"])

    for chain_name in chains:
        if chain_name in AAVE_CHAINS:
            try:
                result = analyze_aave_market(token_address, chain_name, AAVE_CHAINS[chain_name])
                if result:
                    results.append(result)
            except Exception as e:
                results.append({"chain": chain_name, "protocol": "AAVE V3", "status": "error", "error": str(e)})

    return results


def run_compound_analysis(config: Dict) -> list:
    """Run Compound analysis for specified collateral across chains."""
    results = []
    token_address = config.get("token_address")
    chains = config.get("chains", ["Ethereum", "Base", "Arbitrum"])

    for chain_name in chains:
        if chain_name in COMPOUND_MARKETS:
            try:
                result = analyze_compound_market(token_address, chain_name, COMPOUND_MARKETS[chain_name])
                if result:
                    results.append(result)
            except Exception as e:
                results.append({"chain": chain_name, "protocol": "Compound V3", "status": "error", "error": str(e)})

    return results


def run_cowswap_slippage(config: Dict) -> Dict:
    """Run CowSwap slippage analysis."""
    try:
        return cowswap_slippage(
            network=config.get("network", "ethereum"),
            sell_token=config["sell_token"],
            buy_token=config["buy_token"],
            sell_token_decimals=config["sell_token_decimals"],
            buy_token_decimals=config.get("buy_token_decimals", 6),
            sell_token_price_usd=config["sell_token_price_usd"],
            trade_sizes_usd=config.get("trade_sizes_usd"),
            sell_token_symbol=config.get("sell_token_symbol", "SELL"),
            buy_token_symbol=config.get("buy_token_symbol", "BUY")
        )
    except Exception as e:
        return {"protocol": "CowSwap", "status": "error", "error": str(e)}


def run_slippage_check(config: Dict) -> Dict:
    """Run cross-aggregator slippage verification."""
    try:
        return cross_verify_slippage(
            chain=config.get("chain", "ethereum"),
            sell_token=config["sell_token"],
            buy_token=config["buy_token"],
            sell_token_decimals=config["sell_token_decimals"],
            sell_token_price_usd=config["sell_token_price_usd"],
            trade_sizes_usd=config.get("trade_sizes_usd"),
            sell_token_symbol=config.get("sell_token_symbol", "SELL"),
            buy_token_symbol=config.get("buy_token_symbol", "BUY")
        )
    except Exception as e:
        return {"protocol": "Slippage Cross-Verification", "status": "error", "error": str(e)}


def run_curve_analysis(config: Dict) -> Dict:
    """Run Curve pool analysis."""
    try:
        analyzer = CurveFinanceAnalyzer(config.get("network", "ethereum"))
        return analyzer.analyze_pool(config["pool_address"])
    except Exception as e:
        return {"protocol": "Curve Finance", "status": "error", "error": str(e)}


def run_uniswap_analysis(config: Dict) -> Dict:
    """Run Uniswap V3 pool analysis."""
    try:
        analyzer = UniswapV3Analyzer(
            config.get("network", "ethereum"),
            config.get("api_key", "")
        )
        return analyzer.analyze_pool(config["pool_address"])
    except Exception as e:
        return {"protocol": "Uniswap V3", "status": "error", "error": str(e)}


def run_pancakeswap_analysis(config: Dict) -> Dict:
    """Run PancakeSwap V3 pool analysis."""
    try:
        analyzer = PancakeSwapV3Analyzer(
            config.get("network", "base"),
            config.get("api_key", "")
        )
        return analyzer.analyze_pool(config["pool_address"])
    except Exception as e:
        return {"protocol": "PancakeSwap V3", "status": "error", "error": str(e)}


def run_oracle_lag(config: Dict) -> Dict:
    """Run oracle lag analysis."""
    try:
        return analyze_oracle_lag(
            chain1_name=config["chain1"],
            oracle1_address=config["oracle1"],
            chain2_name=config["chain2"],
            oracle2_address=config["oracle2"],
            chain1_rpc=config.get("chain1_rpc"),
            chain2_rpc=config.get("chain2_rpc")
        )
    except Exception as e:
        return {"protocol": "Oracle Lag Calculator", "status": "error", "error": str(e)}


def run_proof_of_reserve(config: Dict) -> Dict:
    """Run proof of reserve analysis."""
    try:
        return analyze_proof_of_reserve(
            evm_chains=config.get("evm_chains", []),
            solana_token=config.get("solana_token")
        )
    except Exception as e:
        return {"protocol": "Proof of Reserve", "status": "error", "error": str(e)}


def run_token_distribution(config: Dict) -> list:
    """Run token distribution analysis across chains."""
    results = []
    token_address = config.get("token_address")
    chains = config.get("chains", [])

    for chain_config in chains:
        try:
            result = analyze_token(
                token_address=chain_config.get("token_address", token_address),
                chain_name=chain_config["name"],
                blockscout_url=chain_config.get("blockscout_url")
            )
            if result:
                results.append(result)
        except Exception as e:
            results.append({"chain": chain_config["name"], "status": "error", "error": str(e)})

    return results


def run_price_risk(config: Dict) -> Dict:
    """Run price risk analysis using CoinGecko data."""
    try:
        token_id = config["token_id"]
        underlying_id = config["underlying_id"]
        days = config.get("days", 365)

        _, token_prices = get_coingecko_data(token_id, days)
        _, underlying_prices = get_coingecko_data(underlying_id, days)

        # Align lengths
        min_len = min(len(token_prices), len(underlying_prices))
        token_prices = token_prices[:min_len]
        underlying_prices = underlying_prices[:min_len]

        peg_metrics = calculate_peg_deviation(token_prices, underlying_prices)
        risk_metrics = calculate_metrics(token_prices)

        return {
            "protocol": "Price Risk Analysis",
            "token_id": token_id,
            "underlying_id": underlying_id,
            "data_points": min_len,
            "peg_deviation": peg_metrics,
            "risk_metrics": risk_metrics,
            "status": "success"
        }
    except Exception as e:
        return {"protocol": "Price Risk Analysis", "status": "error", "error": str(e)}


def run_verification(config: Dict) -> list:
    """Run data verification checks."""
    results = []

    # Uniswap verification
    if "uniswap" in config:
        for pool_config in config["uniswap"]:
            try:
                result = verify_uniswap_v3_accuracy(
                    chain=pool_config["chain"],
                    pool_address=pool_config["pool_address"],
                    top_n=pool_config.get("top_n", 10)
                )
                result["verification_type"] = "Uniswap V3"
                results.append(result)
            except Exception as e:
                results.append({"verification_type": "Uniswap V3", "status": "error", "error": str(e)})

    # PancakeSwap verification
    if "pancakeswap" in config:
        for pool_config in config["pancakeswap"]:
            try:
                result = verify_pancakeswap_v3_accuracy(
                    chain=pool_config["chain"],
                    pool_address=pool_config["pool_address"],
                    top_n=pool_config.get("top_n", 10)
                )
                result["verification_type"] = "PancakeSwap V3"
                results.append(result)
            except Exception as e:
                results.append({"verification_type": "PancakeSwap V3", "status": "error", "error": str(e)})

    # Curve verification
    if "curve" in config:
        for pool_config in config["curve"]:
            try:
                result = verify_curve_lp_accuracy(
                    chain=pool_config["chain"],
                    lp_token=pool_config["lp_token"],
                    top_n=pool_config.get("top_n", 10)
                )
                result["verification_type"] = "Curve"
                results.append(result)
            except Exception as e:
                results.append({"verification_type": "Curve", "status": "error", "error": str(e)})

    return results


def run_risk_framework(config: Dict) -> Dict:
    """
    Run the complete risk framework based on configuration.

    Args:
        config: Dict with module configurations. Each module is optional.
            - aave: {token_address, chains[]}
            - compound: {token_address, chains[]}
            - cowswap: {network, sell_token, buy_token, ...}
            - slippage: {chain, sell_token, buy_token, ...}
            - curve: {network, pool_address}
            - uniswap: {network, pool_address, api_key}
            - pancakeswap: {network, pool_address, api_key}
            - oracle_lag: {chain1, oracle1, chain2, oracle2}
            - proof_of_reserve: {evm_chains[], solana_token}
            - token_distribution: {token_address, chains[]}
            - price_risk: {token_id, underlying_id, days}
            - verification: {uniswap[], pancakeswap[], curve[]}

    Returns:
        Dict with aggregated results from all enabled modules.
    """
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "modules": {}
    }

    # Run each enabled module
    if "aave" in config:
        print("\n" + "="*80)
        print("RUNNING: AAVE V3 Analysis")
        print("="*80)
        results["modules"]["aave"] = run_aave_analysis(config["aave"])

    if "compound" in config:
        print("\n" + "="*80)
        print("RUNNING: Compound V3 Analysis")
        print("="*80)
        results["modules"]["compound"] = run_compound_analysis(config["compound"])

    if "cowswap" in config:
        print("\n" + "="*80)
        print("RUNNING: CowSwap Slippage Analysis")
        print("="*80)
        results["modules"]["cowswap"] = run_cowswap_slippage(config["cowswap"])

    if "slippage" in config:
        print("\n" + "="*80)
        print("RUNNING: Cross-Aggregator Slippage Verification")
        print("="*80)
        results["modules"]["slippage"] = run_slippage_check(config["slippage"])

    if "curve" in config:
        print("\n" + "="*80)
        print("RUNNING: Curve Pool Analysis")
        print("="*80)
        results["modules"]["curve"] = run_curve_analysis(config["curve"])

    if "uniswap" in config:
        print("\n" + "="*80)
        print("RUNNING: Uniswap V3 Pool Analysis")
        print("="*80)
        results["modules"]["uniswap"] = run_uniswap_analysis(config["uniswap"])

    if "pancakeswap" in config:
        print("\n" + "="*80)
        print("RUNNING: PancakeSwap V3 Pool Analysis")
        print("="*80)
        results["modules"]["pancakeswap"] = run_pancakeswap_analysis(config["pancakeswap"])

    if "oracle_lag" in config:
        print("\n" + "="*80)
        print("RUNNING: Oracle Lag Analysis")
        print("="*80)
        results["modules"]["oracle_lag"] = run_oracle_lag(config["oracle_lag"])

    if "proof_of_reserve" in config:
        print("\n" + "="*80)
        print("RUNNING: Proof of Reserve Analysis")
        print("="*80)
        results["modules"]["proof_of_reserve"] = run_proof_of_reserve(config["proof_of_reserve"])

    if "token_distribution" in config:
        print("\n" + "="*80)
        print("RUNNING: Token Distribution Analysis")
        print("="*80)
        results["modules"]["token_distribution"] = run_token_distribution(config["token_distribution"])

    if "price_risk" in config:
        print("\n" + "="*80)
        print("RUNNING: Price Risk Analysis")
        print("="*80)
        results["modules"]["price_risk"] = run_price_risk(config["price_risk"])

    if "verification" in config:
        print("\n" + "="*80)
        print("RUNNING: Data Verification")
        print("="*80)
        results["modules"]["verification"] = run_verification(config["verification"])

    return results


def main():
    parser = argparse.ArgumentParser(description="Risk Framework - Unified Runner")
    parser.add_argument("--config", "-c", type=str, help="Path to JSON config file")
    parser.add_argument("--output", "-o", type=str, help="Path to output JSON file")
    parser.add_argument("--example", action="store_true", help="Print example config and exit")

    args = parser.parse_args()

    if args.example:
        example_config = {
            "aave": {
                "token_address": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
                "chains": ["Ethereum", "Base", "Arbitrum"]
            },
            "compound": {
                "token_address": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
                "chains": ["Ethereum", "Base", "Arbitrum"]
            },
            "cowswap": {
                "network": "ethereum",
                "sell_token": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
                "buy_token": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "sell_token_decimals": 8,
                "buy_token_decimals": 6,
                "sell_token_price_usd": 100000,
                "sell_token_symbol": "cbBTC",
                "buy_token_symbol": "USDC",
                "trade_sizes_usd": [1000, 10000, 50000, 100000]
            },
            "slippage": {
                "chain": "ethereum",
                "sell_token": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
                "buy_token": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "sell_token_decimals": 8,
                "sell_token_price_usd": 100000,
                "sell_token_symbol": "cbBTC",
                "buy_token_symbol": "USDC",
                "trade_sizes_usd": [100000, 500000]
            },
            "uniswap": {
                "network": "ethereum",
                "pool_address": "0xe8f7c89c5efa061e340f2d2f206ec78fd8f7e124",
                "api_key": "your_graph_api_key"
            },
            "curve": {
                "network": "ethereum",
                "pool_address": "0x839d6bDeDFF886404A6d7a788ef241e4e28F4802"
            },
            "pancakeswap": {
                "network": "base",
                "pool_address": "0xb94b22332ABf5f89877A14Cc88f2aBC48c34B3Df",
                "api_key": "your_graph_api_key"
            },
            "oracle_lag": {
                "chain1": "ethereum",
                "oracle1": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",
                "chain2": "polygon",
                "oracle2": "0xAB594600376Ec9fD91F8e885dADF0CE036862dE0"
            },
            "proof_of_reserve": {
                "evm_chains": [
                    {"name": "ethereum", "por": "0xPOR_ADDRESS", "token": "0xTOKEN_ADDRESS"}
                ],
                "solana_token": "optional_solana_token_address"
            },
            "token_distribution": {
                "token_address": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
                "chains": [
                    {"name": "Ethereum", "blockscout_url": "https://eth.blockscout.com"},
                    {"name": "Base", "blockscout_url": "https://base.blockscout.com"},
                    {"name": "Solana", "token_address": "solana_token_address"}
                ]
            },
            "price_risk": {
                "token_id": "coinbase-wrapped-btc",
                "underlying_id": "bitcoin",
                "days": 365
            },
            "verification": {
                "uniswap": [
                    {"chain": "base", "pool_address": "0x8c7080564b5a792a33ef2fd473fba6364d5495e5", "top_n": 3}
                ]
            }
        }
        print(json.dumps(example_config, indent=2))
        return

    if not args.config:
        parser.print_help()
        return

    # Load config
    with open(args.config, 'r') as f:
        config = json.load(f)

    # Run framework
    results = run_risk_framework(config)

    # Output results
    output_json = json.dumps(results, indent=2, default=str)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output_json)
        print(f"\nResults written to: {args.output}")
    else:
        print("\n" + "="*80)
        print("FINAL JSON OUTPUT")
        print("="*80)
        print(output_json)


if __name__ == "__main__":
    main()
