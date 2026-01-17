#!/usr/bin/env python3
"""Uniswap V3 Data Accuracy Verification Script"""

import requests
from web3 import Web3
from typing import Dict, List

# Configuration
SUBGRAPH_IDS = {
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
    "ethereum": "https://lb.drpc.live/ethereum/AtiZvaKOcUmKq-AbTta3bRaREdpZbjkR8LQrEklbR4ac",
    "base": "https://lb.drpc.live/base/AtiZvaKOcUmKq-AbTta3bRaREdpZbjkR8LQrEklbR4ac",
    "arbitrum": "https://lb.drpc.live/arbitrum/AtiZvaKOcUmKq-AbTta3bRaREdpZbjkR8LQrEklbR4ac"
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


def verify_uniswap_v3_accuracy(chain: str, pool_address: str, top_n: int = 10):
    """Verify Uniswap V3 data accuracy for a specific pool"""
    pool_address = pool_address.lower()
    w3 = Web3(Web3.HTTPProvider(RPC_URLS[chain]))
    
    print(f"\n{'='*80}")
    print(f"Verifying Uniswap V3 Pool on {chain.upper()}")
    print(f"Pool: {pool_address}")
    print(f"{'='*80}\n")

    # 1. Get total liquidity from subgraph
    url = f"https://gateway.thegraph.com/api/{GRAPH_API_KEY}/subgraphs/id/{SUBGRAPH_IDS[chain]}"
    query = """query($pool: String!) { pool(id: $pool) { liquidity } }"""
    resp = requests.post(url, json={"query": query, "variables": {"pool": pool_address}})
    subgraph_total = int(resp.json()["data"]["pool"]["liquidity"])

    # 2. Get total liquidity on-chain
    pool = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=POOL_ABI)
    onchain_total = pool.functions.liquidity().call()

    total_deviation = abs(subgraph_total - onchain_total) / onchain_total * 100
    print(f"Total Liquidity - Subgraph: {subgraph_total:,} | On-chain: {onchain_total:,} | Deviation: {total_deviation:.4f}%")

    # 3. Get top positions from subgraph
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
    positions = resp.json()["data"]["positions"]

    # 4. Verify each position on-chain
    nft_manager = w3.eth.contract(address=Web3.to_checksum_address(NONFUNGIBLE_POSITION_MANAGER[chain]), abi=NFT_ABI)
    matched = 0

    print(f"\n{'Token ID':<12} {'Subgraph Liq':>18} {'On-chain Liq':>18} {'Dev %':>10} {'Match':>8}")
    print("-" * 80)

    for pos in positions:
        token_id = int(pos["id"].split("#")[1]) if "#" in pos["id"] else int(pos["id"])
        subgraph_liq = int(pos["liquidity"])
        subgraph_owner = pos["owner"].lower()

        # On-chain verification
        onchain_data = nft_manager.functions.positions(token_id).call()
        onchain_liq = onchain_data[7]  # liquidity at index 7
        onchain_owner = nft_manager.functions.ownerOf(token_id).call().lower()

        # Compare
        deviation = abs(subgraph_liq - onchain_liq) / onchain_liq * 100 if onchain_liq > 0 else 100
        owner_match = subgraph_owner == onchain_owner
        liq_match = deviation <= 1.0  # 1% tolerance
        is_verified = owner_match and liq_match

        if is_verified:
            matched += 1

        print(f"{token_id:<12} {subgraph_liq:>18,} {onchain_liq:>18,} {deviation:>9.4f}% {'✓' if is_verified else '✗':>8}")

    # 5. Calculate accuracy score
    accuracy = matched / len(positions) * 100 if positions else 0
    status = "VERIFIED" if accuracy == 100 else "PARTIAL" if accuracy >= 50 else "FAILED"
    
    print(f"\n{'='*80}")
    print(f"RESULTS: {status}")
    print(f"Accuracy Score: {accuracy:.1f}% ({matched}/{len(positions)} positions matched)")
    print(f"{'='*80}\n")

    return {"accuracy": accuracy, "total_deviation": total_deviation, "matched": matched}


if __name__ == "__main__":
    # Example usage - replace with your pool address and chain
    CHAIN = "base"
    POOL_ADDRESS = "0x8c7080564b5a792a33ef2fd473fba6364d5495e5"  # Base cbBTC/WETH
    
    result = verify_uniswap_v3_accuracy(CHAIN, POOL_ADDRESS, top_n=3)