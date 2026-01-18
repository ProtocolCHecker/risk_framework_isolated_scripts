#!/usr/bin/env python3
"""
Risk Framework - Unified Runner
Simple CLI to run all risk analysis scripts with minimal configuration.
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

# Verification scripts
from curve_check import verify_curve_lp_accuracy
from pancakeswap_check import verify_pancakeswap_v3_accuracy
from uniswap_check import verify_uniswap_v3_accuracy


def prompt_input(prompt: str, default: str = None, required: bool = True) -> str:
    """Get user input with optional default value."""
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "

    value = input(prompt).strip()

    if not value and default:
        return default
    if not value and required:
        print("This field is required!")
        return prompt_input(prompt, default, required)
    return value


def prompt_choice(prompt: str, options: list) -> str:
    """Present a menu of choices."""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")

    while True:
        choice = input("Enter number: ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass
        print("Invalid choice, try again.")


def run_interactive():
    """Run in interactive mode - prompts user for all inputs."""
    print("\n" + "="*70)
    print("RISK FRAMEWORK - Interactive Mode")
    print("="*70)

    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "modules": {}
    }

    modules = [
        "1. Token Distribution (holder concentration)",
        "2. AAVE V3 (lending metrics)",
        "3. Compound V3 (lending metrics)",
        "4. Uniswap V3 (LP concentration)",
        "5. PancakeSwap V3 (LP concentration)",
        "6. Curve Finance (LP concentration)",
        "7. CowSwap Slippage",
        "8. Cross-DEX Slippage",
        "9. Oracle Freshness & Lag (Price Feeds)",
        "10. Proof of Reserve",
        "11. Price Risk (peg deviation)",
        "12. Run ALL modules",
        "0. Exit"
    ]

    while True:
        print("\nAvailable Modules:")
        for m in modules:
            print(f"  {m}")

        choice = input("\nSelect module (number): ").strip()

        if choice == "0":
            break
        elif choice == "1":
            result = interactive_token_distribution()
            if result:
                results["modules"]["token_distribution"] = result
        elif choice == "2":
            result = interactive_aave()
            if result:
                results["modules"]["aave"] = result
        elif choice == "3":
            result = interactive_compound()
            if result:
                results["modules"]["compound"] = result
        elif choice == "4":
            result = interactive_uniswap()
            if result:
                results["modules"]["uniswap"] = result
        elif choice == "5":
            result = interactive_pancakeswap()
            if result:
                results["modules"]["pancakeswap"] = result
        elif choice == "6":
            result = interactive_curve()
            if result:
                results["modules"]["curve"] = result
        elif choice == "7":
            result = interactive_cowswap()
            if result:
                results["modules"]["cowswap"] = result
        elif choice == "8":
            result = interactive_slippage()
            if result:
                results["modules"]["slippage"] = result
        elif choice == "9":
            result = interactive_oracle_lag()
            if result:
                results["modules"]["oracle_lag"] = result
        elif choice == "10":
            result = interactive_proof_of_reserve()
            if result:
                results["modules"]["proof_of_reserve"] = result
        elif choice == "11":
            result = interactive_price_risk()
            if result:
                results["modules"]["price_risk"] = result
        elif choice == "12":
            print("\nRunning ALL modules requires a config file.")
            print("Use: python risk_framework.py --config your_config.json")
            continue
        else:
            print("Invalid choice")
            continue

        # Ask if user wants to continue
        cont = input("\nRun another module? (y/n): ").strip().lower()
        if cont != 'y':
            break

    # Output final results
    if results["modules"]:
        print("\n" + "="*70)
        print("FINAL JSON RESULTS")
        print("="*70)
        print(json.dumps(results, indent=2, default=str))

        save = input("\nSave to file? (y/n): ").strip().lower()
        if save == 'y':
            filename = input("Filename [results.json]: ").strip() or "results.json"
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"Saved to {filename}")

    return results


def interactive_token_distribution():
    """Interactive token distribution analysis."""
    print("\n--- Token Distribution Analysis ---")
    token = prompt_input("Token address")
    chain = prompt_choice("Select chain:", ["Ethereum", "Base", "Arbitrum", "Polygon", "Solana"])
    decimals = int(prompt_input("Token decimals", "8"))

    blockscout_urls = {
        "Ethereum": "https://eth.blockscout.com",
        "Base": "https://base.blockscout.com",
        "Arbitrum": "https://arbitrum.blockscout.com",
        "Polygon": "https://polygon.blockscout.com",
    }

    # Arbitrum uses Ankr by default (Blockscout often down)
    use_ankr = chain == "Arbitrum"
    if chain in ["Ethereum", "Base", "Polygon"]:
        use_ankr_choice = input("Use Ankr API instead of Blockscout? (y/n) [n]: ").strip().lower()
        use_ankr = use_ankr_choice == 'y'

    try:
        return analyze_token(
            token,
            chain,
            blockscout_urls.get(chain),
            use_ankr=use_ankr,
            decimals=decimals
        )
    except Exception as e:
        return {"status": "error", "error": str(e)}


def interactive_aave():
    """Interactive AAVE analysis."""
    print("\n--- AAVE V3 Analysis ---")
    token = prompt_input("Collateral token address")
    chain = prompt_choice("Select chain:", list(AAVE_CHAINS.keys()))

    try:
        return analyze_aave_market(token, chain, AAVE_CHAINS[chain])
    except Exception as e:
        return {"status": "error", "error": str(e)}


def interactive_compound():
    """Interactive Compound analysis."""
    print("\n--- Compound V3 Analysis ---")
    token = prompt_input("Collateral token address")
    chain = prompt_choice("Select chain:", list(COMPOUND_MARKETS.keys()))

    try:
        return analyze_compound_market(token, chain, COMPOUND_MARKETS[chain])
    except Exception as e:
        return {"status": "error", "error": str(e)}


def interactive_uniswap():
    """Interactive Uniswap V3 analysis."""
    print("\n--- Uniswap V3 Pool Analysis ---")
    pool = prompt_input("Pool address")
    network = prompt_choice("Select network:", ["ethereum", "base", "arbitrum"])
    api_key = prompt_input("The Graph API key", required=False)

    try:
        analyzer = UniswapV3Analyzer(network, api_key or "")
        return analyzer.analyze_pool(pool)
    except Exception as e:
        return {"status": "error", "error": str(e)}


def interactive_pancakeswap():
    """Interactive PancakeSwap V3 analysis."""
    print("\n--- PancakeSwap V3 Pool Analysis ---")
    pool = prompt_input("Pool address")
    network = prompt_choice("Select network:", ["ethereum", "base", "arbitrum", "bsc"])
    api_key = prompt_input("The Graph API key", required=False)

    try:
        analyzer = PancakeSwapV3Analyzer(network, api_key or "")
        return analyzer.analyze_pool(pool)
    except Exception as e:
        return {"status": "error", "error": str(e)}


def interactive_curve():
    """Interactive Curve analysis."""
    print("\n--- Curve Finance Pool Analysis ---")
    pool = prompt_input("Pool address")
    network = prompt_choice("Select network:", ["ethereum", "base", "arbitrum", "polygon"])

    try:
        analyzer = CurveFinanceAnalyzer(network)
        return analyzer.analyze_pool(pool)
    except Exception as e:
        return {"status": "error", "error": str(e)}


def interactive_cowswap():
    """Interactive CowSwap slippage analysis."""
    print("\n--- CowSwap Slippage Analysis ---")
    sell_token = prompt_input("Sell token address")
    buy_token = prompt_input("Buy token address")
    sell_decimals = int(prompt_input("Sell token decimals", "18"))
    buy_decimals = int(prompt_input("Buy token decimals", "6"))
    print("Enter CoinGecko ID for sell token (e.g., 'bitcoin', 'ethereum', 'coinbase-wrapped-btc')")
    coingecko_id = prompt_input("Sell token CoinGecko ID")
    network = prompt_choice("Select network:", ["ethereum", "arbitrum", "base"])

    try:
        return cowswap_slippage(
            network=network,
            sell_token=sell_token,
            buy_token=buy_token,
            sell_token_decimals=sell_decimals,
            buy_token_decimals=buy_decimals,
            sell_token_coingecko_id=coingecko_id
        )
    except Exception as e:
        return {"status": "error", "error": str(e)}


def interactive_slippage():
    """Interactive cross-DEX slippage analysis."""
    print("\n--- Cross-DEX Slippage Verification ---")
    sell_token = prompt_input("Sell token address")
    buy_token = prompt_input("Buy token address")
    sell_decimals = int(prompt_input("Sell token decimals", "18"))
    print("Enter CoinGecko ID for sell token (e.g., 'bitcoin', 'ethereum', 'coinbase-wrapped-btc')")
    coingecko_id = prompt_input("Sell token CoinGecko ID")
    chain = prompt_choice("Select chain:", ["ethereum", "arbitrum", "base"])

    try:
        return cross_verify_slippage(
            chain=chain,
            sell_token=sell_token,
            buy_token=buy_token,
            sell_token_decimals=sell_decimals,
            sell_token_coingecko_id=coingecko_id
        )
    except Exception as e:
        return {"status": "error", "error": str(e)}


def interactive_oracle_lag():
    """Interactive oracle lag and freshness analysis."""
    print("\n--- Oracle Lag & Freshness Analysis ---")
    print("This module calculates:")
    print("  1. Cross-chain LAG using Chainlink Proof of Reserve feeds")
    print("  2. Price FRESHNESS using Chainlink Price feeds\n")
    print("Find addresses at: https://data.chain.link/feeds\n")

    # Step 1: PoR feeds for cross-chain lag
    print("=" * 60)
    print("STEP 1: Proof of Reserve Feeds (for cross-chain lag)")
    print("=" * 60)
    chain1 = prompt_choice("Select chain 1:", ["ethereum", "polygon", "arbitrum", "base"])
    por1 = prompt_input(f"Chainlink PoR feed address on {chain1}")

    chain2 = prompt_choice("Select chain 2:", ["ethereum", "polygon", "arbitrum", "base"])
    por2 = prompt_input(f"Chainlink PoR feed address on {chain2}")

    # Step 2: Price feeds for freshness
    print("\n" + "=" * 60)
    print("STEP 2: Price Feeds (for freshness)")
    print("=" * 60)
    print("Example: BTC/USD on Ethereum = 0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c\n")

    price_feeds = []
    while True:
        price_chain = prompt_choice("Select chain for price feed:", ["ethereum", "polygon", "arbitrum", "base"])
        price_address = prompt_input(f"Chainlink Price feed address on {price_chain}")
        price_feeds.append({"chain": price_chain, "address": price_address})

        add_more = input("\nAdd another price feed? (y/n): ").strip().lower()
        if add_more != 'y':
            break

    try:
        from oracle_lag import analyze_oracle_lag, get_oracle_freshness

        # Calculate cross-chain lag using PoR feeds
        print("\n" + "=" * 70)
        print("CALCULATING CROSS-CHAIN LAG (using PoR feeds)")
        print("=" * 70)
        lag_result = analyze_oracle_lag(chain1, por1, chain2, por2)

        # Calculate price freshness using Price feeds
        print("\n" + "=" * 70)
        print("CALCULATING PRICE FRESHNESS (using Price feeds)")
        print("=" * 70)

        freshness_results = []
        for pf in price_feeds:
            freshness = get_oracle_freshness([pf["address"]], pf["chain"])
            freshness_min = freshness.get("oracles", [{}])[0].get("minutes_since_update") if freshness.get("oracles") else None
            freshness_results.append({
                "chain": pf["chain"],
                "price_feed": pf["address"],
                "freshness_minutes": freshness_min
            })

        # Combine results
        result = {
            "protocol": "Oracle Lag & Freshness",
            "status": "success",
            "cross_chain_lag": {
                "chain1": chain1,
                "chain2": chain2,
                "por_feed1": por1,
                "por_feed2": por2,
                "lag_seconds": lag_result.get("lag_seconds"),
                "lag_minutes": lag_result.get("lag_minutes"),
                "ahead_chain": lag_result.get("ahead_chain")
            },
            "price_freshness": freshness_results
        }

        # Print summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"\nCross-chain Lag (PoR): {result['cross_chain_lag']['lag_minutes']:.2f} minutes")
        print(f"  {result['cross_chain_lag']['ahead_chain']} is ahead")
        print(f"\nPrice Freshness:")
        for fr in freshness_results:
            if fr["freshness_minutes"] is not None:
                print(f"  {fr['chain']}: {fr['freshness_minutes']:.2f} minutes")
            else:
                print(f"  {fr['chain']}: Error fetching data")
        print("=" * 70)

        return result
    except Exception as e:
        return {"status": "error", "error": str(e)}


def interactive_proof_of_reserve():
    """Interactive proof of reserve analysis."""
    print("\n--- Proof of Reserve Analysis ---")
    print("Add chains where the token is deployed to compare total supply with reserves.")
    print("You can add multiple EVM chains and optionally Solana.\n")

    evm_chains = []
    available_chains = ["ethereum", "base", "arbitrum"]

    # First, get the PoR feed (usually on one chain like Ethereum)
    print("Step 1: Chainlink Proof of Reserve Feed")
    por_chain = prompt_choice("Chain with PoR feed:", available_chains)
    por_address = prompt_input("Proof of Reserve contract address")

    # Add this chain with PoR
    token_on_por_chain = prompt_input(f"Token address on {por_chain} (Enter to skip)", required=False)
    evm_chains.append({
        "name": por_chain,
        "por": por_address,
        "token": token_on_por_chain if token_on_por_chain else None
    })

    # Now add other chains for total supply
    print("\nStep 2: Add other chains where token is deployed (for total supply)")
    remaining_chains = [c for c in available_chains if c != por_chain]

    for chain in remaining_chains:
        add_chain = input(f"Add {chain}? (y/n): ").strip().lower()
        if add_chain == 'y':
            token_address = prompt_input(f"Token address on {chain}")
            evm_chains.append({
                "name": chain,
                "por": None,
                "token": token_address
            })

    # Solana
    print("\nStep 3: Solana (optional)")
    add_solana = input("Add Solana supply? (y/n): ").strip().lower()
    solana_token = None
    if add_solana == 'y':
        solana_token = prompt_input("Solana token address")

    print(f"\nAnalyzing {len(evm_chains)} EVM chain(s)" + (" + Solana" if solana_token else ""))

    try:
        return analyze_proof_of_reserve(evm_chains=evm_chains, solana_token=solana_token)
    except Exception as e:
        return {"status": "error", "error": str(e)}


def interactive_price_risk():
    """Interactive price risk analysis."""
    print("\n--- Price Risk Analysis ---")
    print("Uses CoinGecko IDs (e.g., 'bitcoin', 'ethereum', 'coinbase-wrapped-btc')")
    token_id = prompt_input("Token CoinGecko ID")
    underlying_id = prompt_input("Underlying asset CoinGecko ID")
    days = int(prompt_input("Days of history", "365"))

    try:
        print(f"\nFetching {token_id} price data...")
        _, token_prices = get_coingecko_data(token_id, days)
        print(f"Fetching {underlying_id} price data...")
        _, underlying_prices = get_coingecko_data(underlying_id, days)

        min_len = min(len(token_prices), len(underlying_prices))
        token_prices = token_prices[:min_len]
        underlying_prices = underlying_prices[:min_len]

        print(f"Analyzing {min_len} data points...")

        peg_metrics = calculate_peg_deviation(token_prices, underlying_prices)
        risk_metrics = calculate_metrics(token_prices)

        # Display results
        print(f"\n{'='*60}")
        print(f"Price Risk Analysis: {token_id} vs {underlying_id}")
        print(f"{'='*60}")

        print(f"\n📊 PEG DEVIATION METRICS")
        print(f"{'─'*60}")
        for key, value in peg_metrics.items():
            print(f"{key}: {value}")

        print(f"\n📈 RISK METRICS")
        print(f"{'─'*60}")
        for key, value in risk_metrics.items():
            print(f"{key}: {value}")

        print(f"{'='*60}\n")

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
        print(f"Error: {e}")
        return {"status": "error", "error": str(e)}


# CLI Direct Commands
def cmd_token(args):
    """Direct token distribution command."""
    try:
        result = analyze_token(args.address, args.chain, args.blockscout_url)
        print(json.dumps(result, indent=2, default=str))
        return result
    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error", "error": str(e)}


def cmd_aave(args):
    """Direct AAVE command."""
    if args.chain not in AAVE_CHAINS:
        print(f"Invalid chain. Available: {list(AAVE_CHAINS.keys())}")
        return
    try:
        result = analyze_aave_market(args.address, args.chain, AAVE_CHAINS[args.chain])
        print(json.dumps(result, indent=2, default=str))
        return result
    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error", "error": str(e)}


def cmd_compound(args):
    """Direct Compound command."""
    if args.chain not in COMPOUND_MARKETS:
        print(f"Invalid chain. Available: {list(COMPOUND_MARKETS.keys())}")
        return
    try:
        result = analyze_compound_market(args.address, args.chain, COMPOUND_MARKETS[args.chain])
        print(json.dumps(result, indent=2, default=str))
        return result
    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error", "error": str(e)}


def cmd_uniswap(args):
    """Direct Uniswap command."""
    try:
        analyzer = UniswapV3Analyzer(args.network, args.api_key or "")
        result = analyzer.analyze_pool(args.pool)
        print(json.dumps(result, indent=2, default=str))
        return result
    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error", "error": str(e)}


def cmd_pancakeswap(args):
    """Direct PancakeSwap command."""
    try:
        analyzer = PancakeSwapV3Analyzer(args.network, args.api_key or "")
        result = analyzer.analyze_pool(args.pool)
        print(json.dumps(result, indent=2, default=str))
        return result
    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error", "error": str(e)}


def cmd_curve(args):
    """Direct Curve command."""
    try:
        analyzer = CurveFinanceAnalyzer(args.network)
        result = analyzer.analyze_pool(args.pool)
        print(json.dumps(result, indent=2, default=str))
        return result
    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error", "error": str(e)}


def cmd_price(args):
    """Direct price risk command."""
    try:
        _, token_prices = get_coingecko_data(args.token, args.days)
        _, underlying_prices = get_coingecko_data(args.underlying, args.days)

        min_len = min(len(token_prices), len(underlying_prices))
        token_prices = token_prices[:min_len]
        underlying_prices = underlying_prices[:min_len]

        peg_metrics = calculate_peg_deviation(token_prices, underlying_prices)
        risk_metrics = calculate_metrics(token_prices)

        result = {
            "protocol": "Price Risk Analysis",
            "token_id": args.token,
            "underlying_id": args.underlying,
            "data_points": min_len,
            "peg_deviation": peg_metrics,
            "risk_metrics": risk_metrics,
            "status": "success"
        }
        print(json.dumps(result, indent=2, default=str))
        return result
    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error", "error": str(e)}


def run_from_config(config_path: str, output_path: str = None):
    """Run full framework from config file."""
    with open(config_path, 'r') as f:
        config = json.load(f)

    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "modules": {}
    }

    # Run each enabled module
    if "aave" in config:
        print("\n" + "="*70)
        print("RUNNING: AAVE V3 Analysis")
        print("="*70)
        cfg = config["aave"]
        token = cfg.get("token_address")
        chains = cfg.get("chains", list(AAVE_CHAINS.keys()))
        results["modules"]["aave"] = []
        for chain in chains:
            if chain in AAVE_CHAINS:
                try:
                    r = analyze_aave_market(token, chain, AAVE_CHAINS[chain])
                    if r:
                        results["modules"]["aave"].append(r)
                except Exception as e:
                    results["modules"]["aave"].append({"chain": chain, "error": str(e)})

    if "compound" in config:
        print("\n" + "="*70)
        print("RUNNING: Compound V3 Analysis")
        print("="*70)
        cfg = config["compound"]
        token = cfg.get("token_address")
        chains = cfg.get("chains", list(COMPOUND_MARKETS.keys()))
        results["modules"]["compound"] = []
        for chain in chains:
            if chain in COMPOUND_MARKETS:
                try:
                    r = analyze_compound_market(token, chain, COMPOUND_MARKETS[chain])
                    if r:
                        results["modules"]["compound"].append(r)
                except Exception as e:
                    results["modules"]["compound"].append({"chain": chain, "error": str(e)})

    if "uniswap" in config:
        print("\n" + "="*70)
        print("RUNNING: Uniswap V3 Analysis")
        print("="*70)
        cfg = config["uniswap"]
        try:
            analyzer = UniswapV3Analyzer(cfg.get("network", "ethereum"), cfg.get("api_key", ""))
            results["modules"]["uniswap"] = analyzer.analyze_pool(cfg["pool_address"])
        except Exception as e:
            results["modules"]["uniswap"] = {"error": str(e)}

    if "pancakeswap" in config:
        print("\n" + "="*70)
        print("RUNNING: PancakeSwap V3 Analysis")
        print("="*70)
        cfg = config["pancakeswap"]
        try:
            analyzer = PancakeSwapV3Analyzer(cfg.get("network", "base"), cfg.get("api_key", ""))
            results["modules"]["pancakeswap"] = analyzer.analyze_pool(cfg["pool_address"])
        except Exception as e:
            results["modules"]["pancakeswap"] = {"error": str(e)}

    if "curve" in config:
        print("\n" + "="*70)
        print("RUNNING: Curve Finance Analysis")
        print("="*70)
        cfg = config["curve"]
        try:
            analyzer = CurveFinanceAnalyzer(cfg.get("network", "ethereum"))
            results["modules"]["curve"] = analyzer.analyze_pool(cfg["pool_address"])
        except Exception as e:
            results["modules"]["curve"] = {"error": str(e)}

    if "token_distribution" in config:
        print("\n" + "="*70)
        print("RUNNING: Token Distribution Analysis")
        print("="*70)
        cfg = config["token_distribution"]
        token = cfg.get("token_address")
        results["modules"]["token_distribution"] = []
        for chain_cfg in cfg.get("chains", []):
            try:
                r = analyze_token(
                    chain_cfg.get("token_address", token),
                    chain_cfg["name"],
                    chain_cfg.get("blockscout_url")
                )
                if r:
                    results["modules"]["token_distribution"].append(r)
            except Exception as e:
                results["modules"]["token_distribution"].append({"chain": chain_cfg["name"], "error": str(e)})

    if "price_risk" in config:
        print("\n" + "="*70)
        print("RUNNING: Price Risk Analysis")
        print("="*70)
        cfg = config["price_risk"]
        try:
            _, token_prices = get_coingecko_data(cfg["token_id"], cfg.get("days", 365))
            _, underlying_prices = get_coingecko_data(cfg["underlying_id"], cfg.get("days", 365))
            min_len = min(len(token_prices), len(underlying_prices))
            peg = calculate_peg_deviation(token_prices[:min_len], underlying_prices[:min_len])
            risk = calculate_metrics(token_prices[:min_len])
            results["modules"]["price_risk"] = {
                "token_id": cfg["token_id"],
                "underlying_id": cfg["underlying_id"],
                "peg_deviation": peg,
                "risk_metrics": risk,
                "status": "success"
            }
        except Exception as e:
            results["modules"]["price_risk"] = {"error": str(e)}

    if "cowswap" in config:
        print("\n" + "="*70)
        print("RUNNING: CowSwap Slippage")
        print("="*70)
        cfg = config["cowswap"]
        try:
            results["modules"]["cowswap"] = cowswap_slippage(
                network=cfg.get("network", "ethereum"),
                sell_token=cfg["sell_token"],
                buy_token=cfg["buy_token"],
                sell_token_decimals=cfg["sell_token_decimals"],
                buy_token_decimals=cfg.get("buy_token_decimals", 6),
                sell_token_price_usd=cfg["sell_token_price_usd"],
                trade_sizes_usd=cfg.get("trade_sizes_usd"),
                sell_token_symbol=cfg.get("sell_token_symbol", "SELL"),
                buy_token_symbol=cfg.get("buy_token_symbol", "BUY")
            )
        except Exception as e:
            results["modules"]["cowswap"] = {"error": str(e)}

    if "slippage" in config:
        print("\n" + "="*70)
        print("RUNNING: Cross-DEX Slippage")
        print("="*70)
        cfg = config["slippage"]
        try:
            results["modules"]["slippage"] = cross_verify_slippage(
                chain=cfg.get("chain", "ethereum"),
                sell_token=cfg["sell_token"],
                buy_token=cfg["buy_token"],
                sell_token_decimals=cfg["sell_token_decimals"],
                sell_token_price_usd=cfg["sell_token_price_usd"],
                trade_sizes_usd=cfg.get("trade_sizes_usd"),
                sell_token_symbol=cfg.get("sell_token_symbol", "SELL"),
                buy_token_symbol=cfg.get("buy_token_symbol", "BUY")
            )
        except Exception as e:
            results["modules"]["slippage"] = {"error": str(e)}

    if "oracle_lag" in config:
        print("\n" + "="*70)
        print("RUNNING: Oracle Lag Analysis")
        print("="*70)
        cfg = config["oracle_lag"]
        try:
            results["modules"]["oracle_lag"] = analyze_oracle_lag(
                cfg["chain1"], cfg["oracle1"],
                cfg["chain2"], cfg["oracle2"],
                cfg.get("chain1_rpc"), cfg.get("chain2_rpc")
            )
        except Exception as e:
            results["modules"]["oracle_lag"] = {"error": str(e)}

    if "proof_of_reserve" in config:
        print("\n" + "="*70)
        print("RUNNING: Proof of Reserve")
        print("="*70)
        cfg = config["proof_of_reserve"]
        try:
            results["modules"]["proof_of_reserve"] = analyze_proof_of_reserve(
                evm_chains=cfg.get("evm_chains", []),
                solana_token=cfg.get("solana_token")
            )
        except Exception as e:
            results["modules"]["proof_of_reserve"] = {"error": str(e)}

    # Output
    output_json = json.dumps(results, indent=2, default=str)

    if output_path:
        with open(output_path, 'w') as f:
            f.write(output_json)
        print(f"\nResults saved to: {output_path}")
    else:
        print("\n" + "="*70)
        print("RESULTS")
        print("="*70)
        print(output_json)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Risk Framework - Run DeFi risk analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Interactive mode:
    python risk_framework.py

  From config file:
    python risk_framework.py --config config.json --output results.json

  Direct commands:
    python risk_framework.py token 0x1234... --chain Ethereum
    python risk_framework.py aave 0x1234... --chain Ethereum
    python risk_framework.py uniswap 0x1234... --network ethereum
    python risk_framework.py price coinbase-wrapped-btc bitcoin --days 365
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Direct module commands")

    # Token distribution
    p_token = subparsers.add_parser("token", help="Token distribution analysis")
    p_token.add_argument("address", help="Token contract address")
    p_token.add_argument("--chain", default="Ethereum", help="Chain name")
    p_token.add_argument("--blockscout-url", dest="blockscout_url", help="Blockscout API URL")
    p_token.set_defaults(func=cmd_token)

    # AAVE
    p_aave = subparsers.add_parser("aave", help="AAVE V3 collateral analysis")
    p_aave.add_argument("address", help="Collateral token address")
    p_aave.add_argument("--chain", default="Ethereum", help="Chain name")
    p_aave.set_defaults(func=cmd_aave)

    # Compound
    p_compound = subparsers.add_parser("compound", help="Compound V3 collateral analysis")
    p_compound.add_argument("address", help="Collateral token address")
    p_compound.add_argument("--chain", default="Ethereum", help="Chain name")
    p_compound.set_defaults(func=cmd_compound)

    # Uniswap
    p_uni = subparsers.add_parser("uniswap", help="Uniswap V3 pool analysis")
    p_uni.add_argument("pool", help="Pool address")
    p_uni.add_argument("--network", default="ethereum", help="Network (ethereum/base/arbitrum)")
    p_uni.add_argument("--api-key", dest="api_key", help="The Graph API key")
    p_uni.set_defaults(func=cmd_uniswap)

    # PancakeSwap
    p_pcs = subparsers.add_parser("pancakeswap", help="PancakeSwap V3 pool analysis")
    p_pcs.add_argument("pool", help="Pool address")
    p_pcs.add_argument("--network", default="base", help="Network")
    p_pcs.add_argument("--api-key", dest="api_key", help="The Graph API key")
    p_pcs.set_defaults(func=cmd_pancakeswap)

    # Curve
    p_curve = subparsers.add_parser("curve", help="Curve pool analysis")
    p_curve.add_argument("pool", help="Pool address")
    p_curve.add_argument("--network", default="ethereum", help="Network")
    p_curve.set_defaults(func=cmd_curve)

    # Price risk
    p_price = subparsers.add_parser("price", help="Price risk / peg deviation analysis")
    p_price.add_argument("token", help="Token CoinGecko ID")
    p_price.add_argument("underlying", help="Underlying asset CoinGecko ID")
    p_price.add_argument("--days", type=int, default=365, help="Days of history")
    p_price.set_defaults(func=cmd_price)

    # Config file mode
    parser.add_argument("--config", "-c", help="Run from JSON config file")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--example", action="store_true", help="Print example config")

    args = parser.parse_args()

    # Print example config
    if args.example:
        example = {
            "token_distribution": {
                "token_address": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
                "chains": [
                    {"name": "Ethereum", "blockscout_url": "https://eth.blockscout.com"}
                ]
            },
            "uniswap": {
                "pool_address": "0xe8f7c89c5efa061e340f2d2f206ec78fd8f7e124",
                "network": "ethereum",
                "api_key": "your_api_key"
            },
            "price_risk": {
                "token_id": "coinbase-wrapped-btc",
                "underlying_id": "bitcoin",
                "days": 365
            }
        }
        print(json.dumps(example, indent=2))
        return

    # Run from config file
    if args.config:
        run_from_config(args.config, args.output)
        return

    # Run subcommand
    if args.command:
        args.func(args)
        return

    # Default: interactive mode
    run_interactive()


if __name__ == "__main__":
    main()
