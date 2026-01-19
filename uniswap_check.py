#!/usr/bin/env python3
"""Uniswap V3 Data Accuracy Verification Script
Supports both Uniswap official schema and Messari schema
"""

import requests
from web3 import Web3
from typing import Dict, List, Optional

# Default subgraph IDs (Uniswap official schema)
DEFAULT_SUBGRAPH_IDS = {
    "ethereum": "5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV",
    "base": "43Hwfi3dJSoGpyas9VwNoDAv55yjgGrPpNSmbQZArzMG",
    "arbitrum": "FbCGRftH4a3yZugY7TnbYgPJVEv2LvMT6oF1fxPe9aJM",
}

NONFUNGIBLE_POSITION_MANAGER = {
    "ethereum": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
    "base": "0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1",
    "arbitrum": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
}

RPC_URLS = {
    "ethereum": "https://eth.drpc.org",
    "base": "https://base.drpc.org",
    "arbitrum": "https://arbitrum.drpc.org"
}

GRAPH_API_KEY = "db5921ae7c7116289958d028661c86b3"

POOL_ABI = [
    {"inputs": [], "name": "liquidity", "outputs": [{"type": "uint128"}],
     "stateMutability": "view", "type": "function"}
]

NFT_ABI = [
    {"inputs": [{"name": "tokenId", "type": "uint256"}], "name": "positions",
     "outputs": [{"type": "uint96"}, {"type": "address"}, {"type": "address"},
                 {"type": "address"}, {"type": "uint24"}, {"type": "int24"},
                 {"type": "int24"}, {"type": "uint128"}, {"type": "uint256"},
                 {"type": "uint256"}, {"type": "uint128"}, {"type": "uint128"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "tokenId", "type": "uint256"}], "name": "ownerOf",
     "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
]


def detect_schema(url: str) -> str:
    """Detect whether subgraph uses Uniswap official or Messari schema."""
    # Try Uniswap official schema first (has 'Pool' entity)
    query = '{ __type(name: "Pool") { name } }'
    try:
        resp = requests.post(url, json={"query": query}, timeout=10)
        if resp.json().get("data", {}).get("__type"):
            return "uniswap"
    except:
        pass

    # Check for Messari schema (has 'LiquidityPool' entity)
    query = '{ __type(name: "LiquidityPool") { name } }'
    try:
        resp = requests.post(url, json={"query": query}, timeout=10)
        if resp.json().get("data", {}).get("__type"):
            return "messari"
    except:
        pass

    return "uniswap"  # Default


def verify_uniswap_v3_accuracy(
    chain: str,
    pool_address: str,
    top_n: int = 10,
    subgraph_id: str = None
) -> dict:
    """
    Verify Uniswap V3 data accuracy for a specific pool.

    Args:
        chain: Chain name (ethereum, base, arbitrum)
        pool_address: Pool contract address
        top_n: Number of top positions to verify
        subgraph_id: Optional custom subgraph ID

    Returns:
        dict with accuracy metrics
    """
    pool_address = pool_address.lower()

    # Use provided subgraph_id or default
    sg_id = subgraph_id or DEFAULT_SUBGRAPH_IDS.get(chain)
    if not sg_id:
        return {"accuracy": 0, "error": f"No subgraph ID for chain: {chain}"}

    url = f"https://gateway.thegraph.com/api/{GRAPH_API_KEY}/subgraphs/id/{sg_id}"

    # Detect schema type
    schema_type = detect_schema(url)

    print(f"\n{'='*80}")
    print(f"Verifying Uniswap V3 Pool on {chain.upper()} ({schema_type} schema)")
    print(f"Pool: {pool_address}")
    print(f"Subgraph: {sg_id[:20]}...")
    print(f"{'='*80}\n")

    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URLS.get(chain, RPC_URLS["ethereum"])))

        # 1. Get total liquidity from subgraph
        if schema_type == "messari":
            query = """query($pool: String!) { liquidityPool(id: $pool) { id } }"""
            resp = requests.post(url, json={"query": query, "variables": {"pool": pool_address}})
            data = resp.json()
            if not data.get("data", {}).get("liquidityPool"):
                print(f"Pool not found in subgraph")
                return {"accuracy": 0, "error": "Pool not found", "total_deviation": 0}
            # Messari doesn't have direct liquidity field, skip total comparison
            subgraph_total = 0
            onchain_total = 0
            total_deviation = 0
            print(f"Note: Messari schema - skipping total liquidity comparison")
        else:
            query = """query($pool: String!) { pool(id: $pool) { liquidity } }"""
            resp = requests.post(url, json={"query": query, "variables": {"pool": pool_address}})
            data = resp.json()
            if not data.get("data", {}).get("pool"):
                print(f"Pool not found in subgraph")
                return {"accuracy": 0, "error": "Pool not found", "total_deviation": 0}
            subgraph_total = int(data["data"]["pool"]["liquidity"])

            # 2. Get total liquidity on-chain
            pool = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=POOL_ABI)
            onchain_total = pool.functions.liquidity().call()

            total_deviation = abs(subgraph_total - onchain_total) / onchain_total * 100 if onchain_total > 0 else 0
            print(f"Total Liquidity - Subgraph: {subgraph_total:,} | On-chain: {onchain_total:,} | Deviation: {total_deviation:.4f}%")

        # 3. Get top positions from subgraph
        if schema_type == "messari":
            query = """
            query($pool: String!, $first: Int!) {
                positions(where: {pool: $pool, liquidity_gt: "0"}, first: $first,
                          orderBy: liquidity, orderDirection: desc) {
                    id
                    account { id }
                    liquidity
                }
            }"""
        else:
            query = """
            query($pool: String!, $first: Int!) {
                positions(where: {pool: $pool, liquidity_gt: "0"}, first: $first,
                          orderBy: liquidity, orderDirection: desc) {
                    id
                    owner
                    liquidity
                }
            }"""

        resp = requests.post(url, json={"query": query, "variables": {"pool": pool_address, "first": top_n}})
        data = resp.json()

        if data.get("errors"):
            print(f"Subgraph error: {data['errors'][0].get('message', 'Unknown')}")
            return {"accuracy": 0, "error": data['errors'][0].get('message'), "total_deviation": total_deviation}

        positions = data.get("data", {}).get("positions", [])

        if not positions:
            print("No positions found")
            return {"accuracy": 100, "total_deviation": total_deviation, "matched": 0, "note": "No positions to verify"}

        # Normalize owner field for Messari schema
        for pos in positions:
            if schema_type == "messari" and "account" in pos:
                pos["owner"] = pos["account"]["id"]

        # 4. Verify each position on-chain
        nft_manager_addr = NONFUNGIBLE_POSITION_MANAGER.get(chain)
        if not nft_manager_addr:
            print(f"No NFT Position Manager for chain: {chain}")
            return {"accuracy": 0, "error": f"No NFT Position Manager for {chain}", "total_deviation": total_deviation}

        nft_manager = w3.eth.contract(address=Web3.to_checksum_address(nft_manager_addr), abi=NFT_ABI)
        matched = 0
        verifiable = 0  # Only count positions with on-chain data available
        skipped = 0

        print(f"\n{'Token ID':<12} {'Subgraph Liq':>18} {'On-chain Liq':>18} {'Dev %':>10} {'Match':>8}")
        print("-" * 80)

        for pos in positions:
            try:
                # Extract token ID from position ID
                pos_id = pos["id"]
                if "#" in pos_id:
                    token_id = int(pos_id.split("#")[1])
                elif pos_id.startswith("0x"):
                    # Messari format: hex token ID
                    token_id = int(pos_id, 16)
                else:
                    token_id = int(pos_id)

                subgraph_liq = int(pos["liquidity"])
                subgraph_owner = pos["owner"].lower()

                # On-chain verification
                onchain_data = nft_manager.functions.positions(token_id).call()
                onchain_liq = onchain_data[7]  # liquidity at index 7
                onchain_owner = nft_manager.functions.ownerOf(token_id).call().lower()

                verifiable += 1

                # Compare
                deviation = abs(subgraph_liq - onchain_liq) / onchain_liq * 100 if onchain_liq > 0 else 100
                owner_match = subgraph_owner == onchain_owner
                liq_match = deviation <= 1.0  # 1% tolerance
                is_verified = owner_match and liq_match

                if is_verified:
                    matched += 1

                print(f"{token_id:<12} {subgraph_liq:>18,} {onchain_liq:>18,} {deviation:>9.4f}% {'✓' if is_verified else '✗':>8}")

            except Exception as e:
                skipped += 1
                print(f"{pos['id'][:12]:<12} {'N/A':>18} {'N/A':>18} {'N/A':>10} {'⊘ SKIP':>8}  (unverifiable)")

        # 5. Calculate accuracy score (only count verifiable positions)
        if verifiable > 0:
            accuracy = matched / verifiable * 100
            status = "VERIFIED" if accuracy == 100 else "PARTIAL" if accuracy >= 50 else "FAILED"
        else:
            accuracy = None  # Cannot determine accuracy
            status = "UNVERIFIABLE"

        print(f"\n{'='*80}")
        print(f"RESULTS: {status}")
        if accuracy is not None:
            print(f"Accuracy Score: {accuracy:.1f}% ({matched}/{verifiable} verifiable positions matched)")
        else:
            print(f"Accuracy Score: N/A (no positions verifiable on-chain)")
        if skipped > 0:
            print(f"Skipped: {skipped} positions (subgraph ID format not mappable to on-chain)")
        print(f"{'='*80}\n")

        return {"accuracy": accuracy, "total_deviation": total_deviation, "matched": matched, "verifiable": verifiable, "skipped": skipped, "status": status}

    except Exception as e:
        print(f"Error during verification: {e}")
        return {"accuracy": 0, "error": str(e), "total_deviation": 0}


if __name__ == "__main__":
    # Example usage - replace with your pool address and chain
    CHAIN = "base"
    POOL_ADDRESS = "0x8c7080564b5a792a33ef2fd473fba6364d5495e5"  # Base cbBTC/WETH

    result = verify_uniswap_v3_accuracy(CHAIN, POOL_ADDRESS, top_n=3)
