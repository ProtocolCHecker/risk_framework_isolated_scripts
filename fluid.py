#!/usr/bin/env python3
"""
Fluid DEX Pool Analyzer v5.0 - Refactored for Streamlit Integration
Analyzes Fluid DEX pools with LP concentration metrics
"""

import requests
from web3 import Web3
from datetime import datetime
import time

# ============================================================================
# CONSTANTS
# ============================================================================

COINGECKO_API = "https://api.coingecko.com/api/v3"

# Fluid protocol resolver address (same across all Fluid pools on Ethereum)
FLUID_RESOLVER_ADDRESS = "0x05Bd8269A20C472b148246De20E6852091BF16Ff"

# ============================================================================
# ABIs
# ============================================================================

FLUID_RESOLVER_ABI = [
    {
        "inputs": [{"name": "dex_", "type": "address"}],
        "name": "getDexCollateralReserves",
        "outputs": [{
            "components": [
                {"name": "token0RealReserves", "type": "uint256"},
                {"name": "token1RealReserves", "type": "uint256"},
                {"name": "token0ImaginaryReserves", "type": "uint256"},
                {"name": "token1ImaginaryReserves", "type": "uint256"}
            ],
            "name": "reserves_",
            "type": "tuple"
        }],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "dex_", "type": "address"}],
        "name": "getDexDebtReserves",
        "outputs": [{
            "components": [
                {"name": "token0Debt", "type": "uint256"},
                {"name": "token0RealReserves", "type": "uint256"},
                {"name": "token0ImaginaryReserves", "type": "uint256"},
                {"name": "token1Debt", "type": "uint256"},
                {"name": "token1RealReserves", "type": "uint256"},
                {"name": "token1ImaginaryReserves", "type": "uint256"}
            ],
            "name": "reserves_",
            "type": "tuple"
        }],
        "stateMutability": "view",
        "type": "function"
    }
]

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_token_prices(token_ids: list) -> dict:
    """Get token prices from CoinGecko for multiple tokens."""
    prices = {}
    try:
        ids_str = ",".join(token_ids)
        url = f"{COINGECKO_API}/simple/price"
        params = {
            "ids": ids_str,
            "vs_currencies": "usd"
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        for token_id in token_ids:
            if token_id in data:
                prices[token_id] = data[token_id].get("usd", 0)
            else:
                prices[token_id] = 0
    except Exception as e:
        print(f"Error fetching prices: {e}")
        for token_id in token_ids:
            prices[token_id] = 0

    return prices


def get_fluid_pool_reserves(w3: Web3, pool_address: str, resolver_address: str, token0_decimals: int = 18, token1_decimals: int = 6) -> dict:
    """Get pool reserves from Fluid DexReservesResolver."""
    resolver = w3.eth.contract(
        address=Web3.to_checksum_address(resolver_address),
        abi=FLUID_RESOLVER_ABI
    )
    pool_addr = Web3.to_checksum_address(pool_address)

    # Get collateral reserves
    collateral = resolver.functions.getDexCollateralReserves(pool_addr).call()

    # Get debt reserves
    debt = resolver.functions.getDexDebtReserves(pool_addr).call()

    # Total reserves = collateral real + debt real
    token0_total = collateral[0] + debt[1]
    token1_total = collateral[1] + debt[4]

    return {
        "token0": token0_total / (10 ** token0_decimals),
        "token1": token1_total / (10 ** token1_decimals)
    }


def get_lp_holders_blockscout(blockscout_api: str, lp_token_address: str, lp_decimals: int = 18) -> dict:
    """Get LP token holders from Blockscout API (supports v1 and v2)."""
    holders = {}

    # Detect API version based on URL
    is_v2 = "/v2" in blockscout_api or blockscout_api.endswith("/api/v2")

    if is_v2:
        # V2 API: /api/v2/tokens/{address}/holders
        base_url = blockscout_api.rstrip("/")
        if not base_url.endswith("/v2"):
            base_url = base_url.rsplit("/api", 1)[0] + "/api/v2"

        url = f"{base_url}/tokens/{lp_token_address}/holders"
        next_page_params = None

        while True:
            try:
                if next_page_params:
                    response = requests.get(url, params=next_page_params, timeout=15)
                else:
                    response = requests.get(url, timeout=15)

                data = response.json()
                items = data.get("items", [])

                if not items:
                    break

                for holder in items:
                    addr_info = holder.get("address", {})
                    address = addr_info.get("hash") if isinstance(addr_info, dict) else holder.get("address")
                    balance = int(holder.get("value", 0))

                    if address and balance > 0:
                        holders[address.lower()] = balance / (10 ** lp_decimals)

                # Check for next page
                next_page = data.get("next_page_params")
                if not next_page:
                    break
                next_page_params = next_page
                time.sleep(0.2)

            except Exception as e:
                print(f"Error fetching holders (v2): {e}")
                break
    else:
        # V1 API: /api?module=token&action=getTokenHolders
        page = 1
        while True:
            try:
                params = {
                    "module": "token",
                    "action": "getTokenHolders",
                    "contractaddress": lp_token_address,
                    "page": page,
                    "offset": 100
                }

                response = requests.get(blockscout_api, params=params, timeout=15)
                data = response.json()

                if not data.get("result"):
                    break
                if data.get("message") not in ["OK", None] and data.get("status") != "1":
                    break

                for holder in data["result"]:
                    address = holder.get("address")
                    balance = int(holder.get("value", 0))

                    if balance > 0:
                        holders[address.lower()] = balance / (10 ** lp_decimals)

                if len(data["result"]) < 100:
                    break

                page += 1
                time.sleep(0.2)

            except Exception as e:
                print(f"Error fetching holders (v1, page {page}): {e}")
                break

    return holders


def calculate_concentration(holders: dict) -> dict:
    """Calculate LP concentration metrics."""
    if not holders:
        return {
            "unique_holders": 0,
            "top_5_pct": 0,
            "top_10_pct": 0,
            "hhi": 0,
            "hhi_category": "Unknown",
            "sorted_holders": []
        }

    sorted_holders = sorted(holders.items(), key=lambda x: x[1], reverse=True)
    total_supply = sum(holders.values())

    # Top 5 concentration
    top_5_amount = sum([balance for _, balance in sorted_holders[:5]])
    top_5_pct = (top_5_amount / total_supply * 100) if total_supply > 0 else 0

    # Top 10 concentration
    top_10_amount = sum([balance for _, balance in sorted_holders[:10]])
    top_10_pct = (top_10_amount / total_supply * 100) if total_supply > 0 else 0

    # HHI
    hhi = sum([(balance / total_supply) ** 2 for balance in holders.values()]) * 10000 if total_supply > 0 else 0

    # HHI category
    if hhi < 1500:
        hhi_category = "Highly Competitive"
    elif hhi < 2500:
        hhi_category = "Moderately Competitive"
    else:
        hhi_category = "Highly Concentrated"

    return {
        "unique_holders": len(holders),
        "top_5_pct": top_5_pct,
        "top_10_pct": top_10_pct,
        "hhi": hhi,
        "hhi_category": hhi_category,
        "sorted_holders": sorted_holders[:10],
        "total_supply": total_supply
    }


# ============================================================================
# MAIN ANALYZER FUNCTION
# ============================================================================

def analyze_fluid_pool(
    pool_address: str,
    lp_token_address: str,
    pool_name: str,
    chain: str,
    rpc_url: str,
    blockscout_api: str,
    token0_coingecko_id: str = None,
    token1_coingecko_id: str = "usd-coin",
    token0_decimals: int = 18,
    token1_decimals: int = 6,
    lp_decimals: int = 18,
    fee_tier: float = 0.05,
    resolver_address: str = None
) -> dict:
    """
    Analyze a Fluid DEX pool.

    Args:
        pool_address: Fluid pool contract address
        lp_token_address: Smart Lending LP token address
        pool_name: Pool name (e.g., "RLP/USDC")
        chain: Chain name (e.g., "ethereum")
        rpc_url: RPC URL for the chain
        blockscout_api: Blockscout API URL for LP holder queries
        token0_coingecko_id: CoinGecko ID for token0 (optional)
        token1_coingecko_id: CoinGecko ID for token1 (default: "usd-coin")
        token0_decimals: Decimals for token0 (default: 18)
        token1_decimals: Decimals for token1 (default: 6 for USDC)
        lp_decimals: Decimals for LP token (default: 18)
        fee_tier: Pool fee tier in percent (default: 0.05)
        resolver_address: Fluid resolver address (default: Ethereum mainnet)

    Returns:
        dict with pool analysis matching Uniswap/Curve format
    """
    result = {
        "protocol": "Fluid",
        "network": chain,
        "chain": chain,
        "pool_address": pool_address,
        "pool_name": pool_name,
        "status": "error",
        "error": None
    }

    # Use default resolver if not provided
    if not resolver_address:
        resolver_address = FLUID_RESOLVER_ADDRESS

    try:
        # Initialize Web3
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            result["error"] = f"Failed to connect to RPC: {rpc_url}"
            return result

        print(f"\n{'='*70}")
        print(f"Fluid DEX Pool Analysis - {chain.upper()}")
        print(f"{'='*70}")
        print(f"Pool: {pool_name}")
        print(f"Address: {pool_address}\n")

        # Get pool reserves
        print("Fetching reserves...")
        reserves = get_fluid_pool_reserves(
            w3, pool_address, resolver_address,
            token0_decimals, token1_decimals
        )

        # Get token prices
        print("Fetching prices...")
        token_ids = []
        if token0_coingecko_id:
            token_ids.append(token0_coingecko_id)
        if token1_coingecko_id:
            token_ids.append(token1_coingecko_id)

        prices = get_token_prices(token_ids) if token_ids else {}

        token0_price = prices.get(token0_coingecko_id, 0) if token0_coingecko_id else 0
        token1_price = prices.get(token1_coingecko_id, 1) if token1_coingecko_id else 1  # Default to 1 for stablecoins

        # Calculate TVL
        token0_tvl = reserves["token0"] * token0_price
        token1_tvl = reserves["token1"] * token1_price
        total_tvl = token0_tvl + token1_tvl

        # Parse token symbols from pool name
        tokens = pool_name.split("/")
        token0_symbol = tokens[0] if len(tokens) > 0 else "Token0"
        token1_symbol = tokens[1] if len(tokens) > 1 else "Token1"

        result["pair"] = pool_name
        result["fee_tier"] = fee_tier
        result["tvl_usd"] = total_tvl
        result["token_amounts"] = [
            {"symbol": token0_symbol, "amount": reserves["token0"], "tvl_usd": token0_tvl},
            {"symbol": token1_symbol, "amount": reserves["token1"], "tvl_usd": token1_tvl}
        ]

        print(f"TVL: ${total_tvl:,.2f}")

        # Get LP holders
        print("Fetching LP holders from Blockscout...")
        holders = get_lp_holders_blockscout(blockscout_api, lp_token_address, lp_decimals)

        # Calculate concentration
        concentration = calculate_concentration(holders)

        result["concentration_metrics"] = {
            "unique_holders": concentration["unique_holders"],
            "hhi": concentration["hhi"],
            "hhi_category": concentration["hhi_category"],
            "top_5_pct": concentration["top_5_pct"],
            "top_10_pct": concentration["top_10_pct"]
        }

        # Format top LPs
        total_supply = concentration.get("total_supply", 1)
        result["top_lps"] = [
            {
                "address": address,
                "balance": balance,
                "share_pct": (balance / total_supply * 100) if total_supply > 0 else 0
            }
            for address, balance in concentration["sorted_holders"]
        ]

        print(f"LP Holders: {concentration['unique_holders']}")
        print(f"HHI: {concentration['hhi']:,.2f} ({concentration['hhi_category']})")
        print(f"Top 5 Concentration: {concentration['top_5_pct']:.2f}%")

        result["status"] = "success"
        print(f"\n{'='*70}\n")

    except Exception as e:
        result["error"] = str(e)
        print(f"Error analyzing Fluid pool: {e}")

    return result


# ============================================================================
# CLI FOR TESTING
# ============================================================================

if __name__ == "__main__":
    # Test with RLP-USDC pool
    result = analyze_fluid_pool(
        pool_address="0x50faCbcfBf9352523F82C67832E6d3D7Ce731D4c",
        lp_token_address="0x10705D774fBE0a3802d7a915E23F6f2c109Fd77f",
        pool_name="RLP/USDC",
        chain="ethereum",
        rpc_url="https://lb.drpc.live/ethereum/AtiZvaKOcUmKq-AbTta3bRagNNpNbjkR8LQsEklbR4ac",
        blockscout_api="https://eth.blockscout.com/api",
        token0_coingecko_id="resolv-liquidity-provider-token",
        token1_coingecko_id="usd-coin",
        token0_decimals=18,
        token1_decimals=6
    )

    print("\n--- Result Dict ---")
    print(f"Status: {result['status']}")
    print(f"TVL: ${result.get('tvl_usd', 0):,.2f}")
    print(f"HHI: {result.get('concentration_metrics', {}).get('hhi', 0):,.2f}")
    if result.get("error"):
        print(f"Error: {result['error']}")
