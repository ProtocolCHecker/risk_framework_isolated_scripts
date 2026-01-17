#!/usr/bin/env python3
"""
Curve Finance Pool Analyzer
Analyzes TVL, holder concentration (HHI), and LP distribution
"""

import requests
from collections import defaultdict
from typing import Dict, List, Tuple

# API endpoints
CURVE_API_BASE = "https://api.curve.finance/v1/getPools"
BLOCKSCOUT_API_BASE = {
    "ethereum": "https://eth.blockscout.com/api/v2",
    "base": "https://base.blockscout.com/api/v2",
    "arbitrum": "https://arbitrum.blockscout.com/api/v2"
}


class CurveFinanceAnalyzer:
    def __init__(self, network: str):
        """Initialize analyzer for specific network"""
        if network not in BLOCKSCOUT_API_BASE:
            raise ValueError(f"Network must be one of {list(BLOCKSCOUT_API_BASE.keys())}")
        
        self.network = network
        self.blockscout_api = BLOCKSCOUT_API_BASE[network]
        self.curve_api = CURVE_API_BASE
    
    def get_pool_data(self, pool_address: str) -> dict:
        """Get pool information from Curve API"""
        # Try different pool types
        pool_types = ["factory-stable-ng", "factory-crypto", "main"]
        
        for pool_type in pool_types:
            try:
                url = f"{self.curve_api}/{self.network}/{pool_type}"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                # Search for pool in response
                if "data" in data and "poolData" in data["data"]:
                    for pool in data["data"]["poolData"]:
                        if pool.get("address", "").lower() == pool_address.lower():
                            return pool
            except Exception as e:
                continue
        
        return None
    
    def get_all_holders(self, lp_token_address: str) -> List[dict]:
        """Fetch all LP token holders from Blockscout"""
        url = f"{self.blockscout_api}/tokens/{lp_token_address}/holders"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            holders = data.get("items", [])
            print(f"  Total holders fetched: {len(holders)}")
            return holders
            
        except Exception as e:
            print(f"\n  Error fetching holders: {e}")
            return []
    
    def calculate_metrics(self, holders: List[dict]) -> dict:
        """Calculate HHI, concentration, and holder metrics"""
        if not holders:
            return None
        
        # Extract balances with addresses
        holder_data = []
        for h in holders:
            address = h.get("address", {}).get("hash", "Unknown")
            value = int(h.get("value", "0"))
            holder_data.append((address, value))
        
        # Sort by balance (descending)
        holder_data.sort(key=lambda x: x[1], reverse=True)
        
        balances = [bal for _, bal in holder_data]
        total_supply = sum(balances)
        
        if total_supply == 0:
            return None
        
        # Calculate market shares and HHI
        market_shares = []
        hhi = 0.0
        
        for address, balance in holder_data:
            share_pct = (balance / total_supply) * 100
            market_shares.append((address, balance, share_pct))
            hhi += share_pct ** 2
        
        # Top concentrations
        def get_top_concentration(n: int) -> float:
            return sum(balances[:n]) / total_supply * 100 if total_supply else 0
        
        return {
            "unique_holders": len(holders),
            "total_supply": total_supply,
            "hhi": hhi,
            "top_1": get_top_concentration(1),
            "top_3": get_top_concentration(3),
            "top_5": get_top_concentration(5),
            "top_10": get_top_concentration(10),
            "top_lps": market_shares[:10],
        }
    
    def analyze_pool(self, pool_address: str) -> None:
        """Complete pool analysis with formatted output"""
        print(f"\n{'='*70}")
        print(f"Curve Finance Pool Analysis - {self.network.upper()}")
        print(f"{'='*70}")
        print(f"Pool Address: {pool_address}\n")
        
        # Get pool data
        print("Fetching pool data from Curve API...")
        pool_data = self.get_pool_data(pool_address)
        
        if not pool_data:
            print(f"❌ Pool not found on {self.network}")
            return
        
        # Display pool info
        pool_name = pool_data.get("name", "Unknown")
        coins = pool_data.get("coins", [])
        tvl = float(pool_data.get("usdTotal", 0))
        
        print(f"\n📊 POOL INFO")
        print(f"{'─'*70}")
        print(f"Pool: {pool_name}")
        
        # Token symbols
        token_symbols = [coin.get("symbol", "?") for coin in coins]
        print(f"Pair: {'/'.join(token_symbols)}")
        print(f"TVL (USD): ${tvl:,.2f}")
        
        # Token amounts
        print(f"\n💰 TOKEN AMOUNTS")
        print(f"{'─'*70}")
        for coin in coins:
            symbol = coin.get("symbol", "Unknown")
            balance = float(coin.get("poolBalance", 0))
            decimals = int(coin.get("decimals", 18))
            actual_balance = balance / (10 ** decimals)
            print(f"{symbol}: {actual_balance:,.4f}")
        
        # Get holders
        print(f"\n🔍 Fetching LP token holders from Blockscout...")
        lp_token_address = pool_data.get("lpTokenAddress", pool_address)
        holders = self.get_all_holders(lp_token_address)
        
        if not holders:
            print("❌ No holders found")
            return
        
        # Calculate metrics
        print("\n📈 Calculating metrics...")
        metrics = self.calculate_metrics(holders)
        
        if not metrics:
            print("❌ Failed to calculate metrics")
            return
        
        # Display concentration metrics
        print(f"\n🎯 CONCENTRATION METRICS")
        print(f"{'─'*70}")
        print(f"Unique Holders: {metrics['unique_holders']:,}")
        print(f"HHI (0-10,000): {metrics['hhi']:,.2f}")
        
        # HHI interpretation
        if metrics['hhi'] < 1500:
            hhi_label = "Highly Competitive"
        elif metrics['hhi'] < 2500:
            hhi_label = "Moderately Competitive"
        else:
            hhi_label = "Highly Concentrated"
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
        
        for i, (address, balance, share) in enumerate(metrics['top_lps'], 1):
            print(f"{i:<6} {address:<44} {share:>9.2f}%")
        
        print(f"\n{'='*70}\n")


def main():
    """Example usage"""
    # Configuration
    NETWORK = "ethereum"
    POOL_ADDRESS = "0x839d6bDeDFF886404A6d7a788ef241e4e28F4802"
    
    # Create analyzer and run
    analyzer = CurveFinanceAnalyzer(NETWORK)
    analyzer.analyze_pool(POOL_ADDRESS)


if __name__ == "__main__":
    main()