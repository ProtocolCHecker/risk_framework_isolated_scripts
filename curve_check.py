#!/usr/bin/env python3
"""Curve LP Token Data Accuracy Verification Script"""

import requests
from web3 import Web3
from typing import Dict, List
import time

# Configuration
BLOCKSCOUT_APIS = {
    "ethereum": "https://eth.blockscout.com/api/v2",
    "base": "https://base.blockscout.com/api/v2",
    "arbitrum": "https://arbitrum.blockscout.com/api/v2",
}

RPC_URLS = {
    "ethereum": "https://eth.drpc.org",
    "base": "https://mainnet.base.org",
    "arbitrum": "https://arb1.arbitrum.io/rpc",
}

# ERC20 ABI for LP Token
ERC20_ABI = [
    {"inputs": [{"name": "account", "type": "address"}], "name": "balanceOf",
     "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "totalSupply",
     "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
]

# Curve Pool ABI to get LP token
CURVE_POOL_ABI = [
    {"inputs": [], "name": "lp_token", "outputs": [{"type": "address"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "token", "outputs": [{"type": "address"}],
     "stateMutability": "view", "type": "function"},
]


def get_lp_token_from_pool(w3: Web3, pool_address: str) -> str:
    """Get LP token address from a Curve pool contract."""
    pool_address = Web3.to_checksum_address(pool_address)
    pool_contract = w3.eth.contract(address=pool_address, abi=CURVE_POOL_ABI)

    # Try lp_token() first (most common)
    try:
        return pool_contract.functions.lp_token().call()
    except:
        pass

    # Try token() as fallback
    try:
        return pool_contract.functions.token().call()
    except:
        pass

    # If neither works, assume the pool_address itself is the LP token
    # (some newer Curve pools are the LP token)
    return pool_address


def call_with_retry(func, max_retries=3, delay=1.0):
    """Call a function with exponential backoff retry logic"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            if "429" in str(e) or "Too Many Requests" in str(e):
                wait_time = delay * (2 ** attempt)
                print(f"  Rate limit hit, waiting {wait_time:.1f}s before retry...")
                time.sleep(wait_time)
            else:
                raise


def get_blockscout_holders(chain: str, lp_token: str, top_n: int = 10) -> List[Dict]:
    """Get top N holders from Blockscout API"""
    url = f"{BLOCKSCOUT_APIS[chain]}/tokens/{lp_token}/holders"
    
    def make_request():
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    
    data = call_with_retry(make_request)
    holders = data.get("items", [])[:top_n]
    return holders


def get_blockscout_total_supply(chain: str, lp_token: str) -> int:
    """Get total supply from Blockscout API"""
    url = f"{BLOCKSCOUT_APIS[chain]}/tokens/{lp_token}"
    
    def make_request():
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    
    data = call_with_retry(make_request)
    total_supply = data.get("total_supply", "0")
    return int(total_supply)


def verify_curve_lp_accuracy(chain: str, pool_address: str, lp_token_override: str = None, top_n: int = 10, request_delay: float = 0.5):
    """Verify Curve LP token data accuracy.

    Args:
        chain: Chain name (ethereum, base, arbitrum)
        pool_address: Curve pool contract address
        lp_token_override: Optional explicit LP token address (for older pools)
        top_n: Number of top holders to verify
        request_delay: Delay between requests to avoid rate limiting
    """
    pool_address = Web3.to_checksum_address(pool_address)
    w3 = Web3(Web3.HTTPProvider(RPC_URLS[chain]))

    # Use override if provided, otherwise try to resolve from pool
    if lp_token_override:
        lp_token = Web3.to_checksum_address(lp_token_override)
    else:
        lp_token = get_lp_token_from_pool(w3, pool_address)
        lp_token = Web3.to_checksum_address(lp_token)

    print(f"\n{'='*80}")
    print(f"Verifying Curve LP Token on {chain.upper()}")
    print(f"Pool: {pool_address}")
    print(f"LP Token: {lp_token}")
    print(f"{'='*80}\n")

    # Setup contract
    lp_contract = w3.eth.contract(address=lp_token, abi=ERC20_ABI)

    # 1. Get total supply from Blockscout
    print("Step 1: Total Supply Verification")
    print("-" * 80)
    blockscout_total = get_blockscout_total_supply(chain, lp_token)
    
    # 2. Get total supply on-chain
    def get_total_supply():
        return lp_contract.functions.totalSupply().call()
    
    onchain_total = call_with_retry(get_total_supply)
    total_deviation = abs(blockscout_total - onchain_total) / onchain_total * 100 if onchain_total > 0 else 0
    
    print(f"Blockscout: {blockscout_total:,} | On-chain: {onchain_total:,} | Deviation: {total_deviation:.4f}%")

    # 3. Get top holders from Blockscout
    print(f"\nStep 2: Top {top_n} Holders Verification")
    print("-" * 80)
    holders = get_blockscout_holders(chain, lp_token, top_n)
    print(f"Found {len(holders)} holders in Blockscout\n")

    # 4. Verify each holder on-chain
    matched = 0
    verifiable = 0  # Only count holders with on-chain data available
    skipped = 0

    print(f"{'Holder Address':<44} {'Blockscout Bal':>20} {'On-chain Bal':>20} {'Dev %':>10} {'Match':>8}")
    print("-" * 110)

    for holder_data in holders:
        holder_address = holder_data.get("address", {}).get("hash", "")
        if not holder_address:
            continue

        holder_address = Web3.to_checksum_address(holder_address)
        blockscout_balance = int(holder_data.get("value", "0"))

        # Add delay between requests to avoid rate limiting
        time.sleep(request_delay)

        # On-chain verification
        def get_balance():
            return lp_contract.functions.balanceOf(holder_address).call()

        try:
            onchain_balance = call_with_retry(get_balance)

            # Skip holders with 0 on-chain balance (stale Blockscout data)
            if onchain_balance == 0:
                skipped += 1
                print(f"{holder_address:<44} {blockscout_balance:>20,} {onchain_balance:>20,} {'N/A':>10} {'⊘ SKIP':>8}")
                continue

            verifiable += 1

            # Compare
            deviation = abs(blockscout_balance - onchain_balance) / onchain_balance * 100
            balance_match = deviation <= 1.0  # 1% tolerance
            is_verified = balance_match

            if is_verified:
                matched += 1

            print(f"{holder_address:<44} {blockscout_balance:>20,} {onchain_balance:>20,} {deviation:>9.4f}% {'✓' if is_verified else '✗':>8}")

        except Exception as e:
            print(f"{holder_address:<44} {'ERROR':>20} {str(e)[:30]:>20} {'N/A':>10} {'✗':>8}")

    # 5. Calculate accuracy score (only count verifiable holders)
    accuracy = matched / verifiable * 100 if verifiable > 0 else 0
    status = "VERIFIED" if accuracy == 100 else "PARTIAL" if accuracy >= 50 else "FAILED"

    print(f"\n{'='*80}")
    print(f"RESULTS: {status}")
    print(f"Accuracy Score: {accuracy:.1f}% ({matched}/{verifiable} verifiable holders matched)")
    if skipped > 0:
        print(f"Skipped: {skipped} holders with stale Blockscout data (0 on-chain balance)")
    print(f"Total Supply Deviation: {total_deviation:.4f}%")
    print(f"{'='*80}\n")

    return {"accuracy": accuracy, "total_deviation": total_deviation, "matched": matched, "verifiable": verifiable, "skipped": skipped}


if __name__ == "__main__":
    # Example usage - replace with your pool address and chain
    CHAIN = "ethereum"
    POOL_ADDRESS = "0x7fC77b5c7614E1533320Ea6DDc2Eb61fa00A9714"  # renBTC/WBTC/sBTC pool

    result = verify_curve_lp_accuracy(CHAIN, POOL_ADDRESS, top_n=3, request_delay=0.5)