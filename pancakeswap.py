#!/usr/bin/env python3
"""
PancakeSwap V3 Pool Analyzer
Analyzes TVL, holder concentration (HHI), and LP distribution
"""

import requests
from collections import defaultdict
from typing import Dict, List, Tuple

# The Graph Subgraph IDs for PancakeSwap V3
PANCAKESWAP_SUBGRAPH_IDS = {
    "ethereum": "CJYGNhb7RvnhfBDjqpRnD3oxgyhibzc7fkAMa38YV3oS",
    "base": "BHWNsedAHtmTCzXxCCDfhPmm6iN9rxUhoRHdHKyujic3",
    "bsc": "78EUqzJmEVJsAKvWghn7qotf9LVGqcTQxJhT5z84ZmgJ",
    "arbitrum": "251MHFNN1rwjErXD2efWMpNS73SANZN8Ua192zw6iXve",
}

GRAPH_API_BASE = "https://gateway.thegraph.com/api"


class PancakeSwapV3Analyzer:
    def __init__(self, network: str, api_key: str = ""):
        """Initialize analyzer for specific network"""
        if network not in PANCAKESWAP_SUBGRAPH_IDS:
            raise ValueError(f"Network must be one of {list(PANCAKESWAP_SUBGRAPH_IDS.keys())}")
        
        self.network = network
        self.subgraph_id = PANCAKESWAP_SUBGRAPH_IDS[network]
        self.api_key = api_key
        self.endpoint = f"{GRAPH_API_BASE}/{api_key}/subgraphs/id/{self.subgraph_id}"
    
    def query_subgraph(self, query: str) -> dict:
        """Execute GraphQL query against The Graph"""
        response = requests.post(self.endpoint, json={"query": query})
        response.raise_for_status()
        return response.json()
    
    def get_pool_data(self, pool_address: str) -> dict:
        """Get pool information (TVL, token amounts, etc.)"""
        query = f"""
        {{
          pool(id: "{pool_address.lower()}") {{
            id
            token0 {{
              id
              symbol
              decimals
            }}
            token1 {{
              id
              symbol
              decimals
            }}
            totalValueLockedToken0
            totalValueLockedToken1
            totalValueLockedUSD
            liquidity
            feeTier
          }}
        }}
        """
        
        result = self.query_subgraph(query)
        return result.get("data", {}).get("pool")
    
    def get_all_positions(self, pool_address: str) -> List[dict]:
        """Fetch all LP positions for a pool (paginated)"""
        all_positions = []
        skip = 0
        batch_size = 1000
        
        while True:
            query = f"""
            {{
              positions(
                first: {batch_size}
                skip: {skip}
                where: {{pool: "{pool_address.lower()}", liquidity_gt: "0"}}
              ) {{
                id
                owner
                liquidity
              }}
            }}
            """
            
            result = self.query_subgraph(query)
            positions = result.get("data", {}).get("positions", [])
            
            if not positions:
                break
            
            all_positions.extend(positions)
            skip += batch_size
            
            print(f"  Fetched {len(all_positions)} positions...", end="\r")
        
        print(f"  Total positions fetched: {len(all_positions)}")
        return all_positions
    
    def calculate_metrics(self, positions: List[dict], pool_data: dict) -> dict:
        """Calculate HHI, concentration, and holder metrics"""
        # Aggregate liquidity by owner
        owner_liquidity = defaultdict(float)
        for pos in positions:
            owner = pos["owner"]
            liquidity = float(pos["liquidity"])
            owner_liquidity[owner] += liquidity
        
        # Calculate total liquidity and unique holders
        total_liquidity = sum(owner_liquidity.values())
        unique_holders = len(owner_liquidity)
        
        # Sort owners by liquidity (descending)
        sorted_owners = sorted(
            owner_liquidity.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Calculate market shares and HHI
        market_shares = []
        hhi = 0.0
        
        for owner, liquidity in sorted_owners:
            share_pct = (liquidity / total_liquidity) * 100
            market_shares.append((owner, liquidity, share_pct))
            hhi += share_pct ** 2
        
        # Top concentrations
        def get_top_concentration(n: int) -> float:
            return sum(share for _, _, share in market_shares[:n])
        
        return {
            "unique_holders": unique_holders,
            "total_liquidity": total_liquidity,
            "hhi": hhi,
            "top_1": get_top_concentration(1),
            "top_3": get_top_concentration(3),
            "top_5": get_top_concentration(5),
            "top_10": get_top_concentration(10),
            "top_lps": market_shares[:10],
        }
    
    def analyze_pool(self, pool_address: str) -> dict:
        """Complete pool analysis with formatted output. Returns dict with all metrics."""
        print(f"\n{'='*70}")
        print(f"PancakeSwap V3 Pool Analysis - {self.network.upper()}")
        print(f"{'='*70}")
        print(f"Pool Address: {pool_address}\n")

        result = {
            "protocol": "PancakeSwap V3",
            "network": self.network,
            "pool_address": pool_address,
            "status": "error",
            "error": None
        }

        # Get pool data
        print("Fetching pool data...")
        pool_data = self.get_pool_data(pool_address)

        if not pool_data:
            print(f"❌ Pool not found on {self.network}")
            result["error"] = f"Pool not found on {self.network}"
            return result

        # Display pool info
        token0 = pool_data["token0"]
        token1 = pool_data["token1"]

        result["pair"] = f"{token0['symbol']}/{token1['symbol']}"
        result["fee_tier"] = int(pool_data['feeTier']) / 10000
        result["tvl_usd"] = float(pool_data['totalValueLockedUSD'])

        print(f"\n📊 POOL INFO")
        print(f"{'─'*70}")
        print(f"Pair: {token0['symbol']}/{token1['symbol']}")
        print(f"Fee Tier: {int(pool_data['feeTier']) / 10000}%")
        print(f"TVL (USD): ${float(pool_data['totalValueLockedUSD']):,.2f}")

        # Token amounts
        token0_amount = float(pool_data['totalValueLockedToken0'])
        token1_amount = float(pool_data['totalValueLockedToken1'])

        result["token_amounts"] = [
            {"symbol": token0['symbol'], "amount": token0_amount},
            {"symbol": token1['symbol'], "amount": token1_amount}
        ]

        print(f"\n💰 TOKEN AMOUNTS")
        print(f"{'─'*70}")
        print(f"{token0['symbol']}: {token0_amount:,.4f}")
        print(f"{token1['symbol']}: {token1_amount:,.4f}")

        # Get positions
        print(f"\n🔍 Fetching LP positions...")
        positions = self.get_all_positions(pool_address)

        if not positions:
            print("❌ No active positions found")
            result["error"] = "No active positions found"
            return result

        # Calculate metrics
        print("\n📈 Calculating metrics...")
        metrics = self.calculate_metrics(positions, pool_data)

        # HHI interpretation
        if metrics['hhi'] < 1500:
            hhi_label = "Highly Competitive"
        elif metrics['hhi'] < 2500:
            hhi_label = "Moderately Competitive"
        else:
            hhi_label = "Highly Concentrated"

        result["concentration_metrics"] = {
            "unique_holders": metrics['unique_holders'],
            "hhi": metrics['hhi'],
            "hhi_category": hhi_label,
            "top_1_pct": metrics['top_1'],
            "top_3_pct": metrics['top_3'],
            "top_5_pct": metrics['top_5'],
            "top_10_pct": metrics['top_10']
        }

        result["top_lps"] = [
            {"address": owner, "share_pct": share}
            for owner, liquidity, share in metrics['top_lps']
        ]

        # Display concentration metrics
        print(f"\n🎯 CONCENTRATION METRICS")
        print(f"{'─'*70}")
        print(f"Unique Holders: {metrics['unique_holders']:,}")
        print(f"HHI (0-10,000): {metrics['hhi']:,.2f}")
        print(f"HHI Category: {hhi_label}")

        print(f"\n📊 LP CONCENTRATION")
        print(f"{'─'*70}")
        print(f"Top 1 LP:   {metrics['top_1']:.2f}%")
        print(f"Top 3 LPs:  {metrics['top_3']:.2f}%")
        print(f"Top 5 LPs:  {metrics['top_5']:.2f}%")
        print(f"Top 10 LPs: {metrics['top_10']:.2f}%")

        # Display top LPs
        print(f"\n🏆 TOP 10 LIQUIDITY PROVIDERS")
        print(f"{'─'*70}")
        print(f"{'Rank':<6} {'Address':<44} {'Share %':>10}")
        print(f"{'─'*70}")

        for i, (owner, liquidity, share) in enumerate(metrics['top_lps'], 1):
            print(f"{i:<6} {owner:<44} {share:>9.2f}%")

        print(f"\n{'='*70}\n")

        result["status"] = "success"
        return result


def main():
    """Example usage"""
    import json

    # Configuration
    NETWORK = "base"
    API_KEY = "db5921ae7c7116289958d028661c86b3"
    POOL_ADDRESS = "0xb94b22332ABf5f89877A14Cc88f2aBC48c34B3Df"

    # Create analyzer and run
    analyzer = PancakeSwapV3Analyzer(NETWORK, API_KEY)
    result = analyzer.analyze_pool(POOL_ADDRESS)

    # Print JSON summary
    print("\n" + "="*70)
    print("JSON OUTPUT:")
    print("="*70)
    print(json.dumps(result, indent=2, default=str))

    return result


if __name__ == "__main__":
    main()