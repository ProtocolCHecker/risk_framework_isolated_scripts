import requests
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
import numpy as np
import time

# Compound v3 Markets by Chain
GRAPH_API_KEY = "db5921ae7c7116289958d028661c86b3"

MARKETS = {
    "Ethereum": {
        "rpc": "https://lb.drpc.live/ethereum/AtiZvaKOcUmKq-AbTta3bRaREdpZbjkR8LQrEklbR4ac",
        "markets": {
            "USDC": "0xc3d688B66703497DAA19211EEdff47f25384cdc3",
            "USDT": "0x3Afdc9BCA9213A35503b077a6072F3D0d5AB0840",
            "WETH": "0xA17581A9E3356d9A858b789D68B4d866e593aE94"
        },
        "subgraph": f"https://gateway.thegraph.com/api/{GRAPH_API_KEY}/subgraphs/id/5nwMCSHaTqG3Kd2gHznbTXEnZ9QNWsssQfbHhDqQSQFp"
    },
    "Base": {
        "rpc": "https://lb.drpc.live/base/AtiZvaKOcUmKq-AbTta3bRaREdpZbjkR8LQrEklbR4ac",
        "markets": {
            "USDC": "0xb125E6687d4313864e53df431d5425969c15Eb2F",
            "WETH": "0x46e6b214b524310239732D51387075E0e70970bf"
        },
        "subgraph": f"https://gateway.thegraph.com/api/{GRAPH_API_KEY}/subgraphs/id/2hcXhs36pTBDVUmk5K2Zkr6N4UYGwaHuco2a6jyTsijo"
    },
    "Arbitrum": {
        "rpc": "https://lb.drpc.live/arbitrum/AtiZvaKOcUmKq-AbTta3bRaREdpZbjkR8LQrEklbR4ac",
        "markets": {
            "USDC": "0x9c4ec768c28520B50860ea7a15bd7213a9fF58bf",
            "USDT": "0xd98Be00b5D27fc98112BdE293e487f8D4cA57d07",
            "WETH": "0x6f7D514bbD4aFf3BcD1140B7344b32f063dEe486"
        },
        "subgraph": f"https://gateway.thegraph.com/api/{GRAPH_API_KEY}/subgraphs/id/Ff7ha9ELmpmg81D6nYxy4t8aGP26dPztqD1LDJNPqjLS"
    }
}

MULTICALL3 = "0xcA11bde05977b3631167028862bE2a173976CA11"

# Comet ABI (minimal)
COMET_ABI = [
    {"inputs": [], "name": "totalsBasic", "outputs": [{"type": "uint64"}, {"type": "uint64"}, {"type": "uint64"}, {"type": "uint64"}, {"type": "uint104", "name": "totalSupplyBase"}, {"type": "uint104", "name": "totalBorrowBase"}, {"type": "uint40"}, {"type": "uint8"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "getUtilization", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"type": "uint256"}], "name": "getSupplyRate", "outputs": [{"type": "uint64"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"type": "uint256"}], "name": "getBorrowRate", "outputs": [{"type": "uint64"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"type": "address"}], "name": "getAssetInfoByAddress", "outputs": [{"components": [{"type": "uint8", "name": "offset"}, {"type": "address", "name": "asset"}, {"type": "address", "name": "priceFeed"}, {"type": "uint128", "name": "scale"}, {"type": "uint128", "name": "borrowCollateralFactor"}, {"type": "uint128", "name": "liquidateCollateralFactor"}, {"type": "uint128", "name": "liquidationFactor"}, {"type": "uint128", "name": "supplyCap"}], "type": "tuple"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"type": "address"}], "name": "borrowBalanceOf", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"type": "address"}, {"type": "address"}], "name": "collateralBalanceOf", "outputs": [{"type": "uint128"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"type": "address"}], "name": "getPrice", "outputs": [{"type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "baseToken", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "decimals", "outputs": [{"type": "uint8"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"type": "address"}], "name": "totalsCollateral", "outputs": [{"type": "uint128", "name": "totalSupplyAsset"}, {"type": "uint128", "name": "_reserved"}], "stateMutability": "view", "type": "function"}
]

ERC20_ABI = [
    {"inputs": [], "name": "decimals", "outputs": [{"type": "uint8"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "symbol", "outputs": [{"type": "string"}], "stateMutability": "view", "type": "function"}
]

MULTICALL3_ABI = [
    {"inputs": [{"components": [{"name": "target", "type": "address"}, {"name": "callData", "type": "bytes"}], "name": "calls", "type": "tuple[]"}], "name": "aggregate", "outputs": [{"name": "blockNumber", "type": "uint256"}, {"name": "returnData", "type": "bytes[]"}], "stateMutability": "payable", "type": "function"}
]

def fetch_positions_from_subgraph(subgraph_url, comet_address, limit=100):
    """Fetch positions (borrowers) from The Graph - Compound V3 schema"""
    query = """
    query GetTopBorrowers($market: String!, $first: Int!) {
        positions(
            where: { 
                market: $market, 
                accounting_: { basePrincipal_lt: "0" } 
            }
            first: $first
            orderBy: accounting__basePrincipal
            orderDirection: asc
        ) {
            id
            account {
                id
            }
            accounting {
                basePrincipal
                baseBalance
                baseBalanceUsd
                collateralBalanceUsd
            }
        }
    }
    """
    
    try:
        response = requests.post(
            subgraph_url,
            json={
                "query": query, 
                "variables": {
                    "market": comet_address.lower(),
                    "first": limit
                }
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"    ⚠️  HTTP {response.status_code}: {response.text[:200]}")
            return []
        
        data = response.json()
        
        if 'errors' in data:
            print(f"    ⚠️  GraphQL errors: {data['errors']}")
            return []
        
        positions = data.get('data', {}).get('positions', [])
        
        if not positions:
            print(f"    ℹ️  No positions found in subgraph")
            return []
        
        # Extract borrower addresses and convert to checksum format
        borrowers = [
            Web3.to_checksum_address(pos['account']['id'])
            for pos in positions 
            if pos.get('accounting', {}).get('baseBalanceUsd') is not None
        ]
        
        print(f"    ✓ Found {len(borrowers)} borrowers in subgraph")
        return borrowers
        
    except Exception as e:
        print(f"    ⚠️  Error: {e}")
        return []



def analyze_compound_market(collateral_address, chain_name, chain_config):
    """Analyze Compound v3 market for a specific collateral. Returns dict with all metrics."""
    print(f"\n{'='*70}")
    print(f"🔍 Analyzing {chain_name} - Compound v3")
    print(f"{'='*70}\n")

    result = {
        "chain": chain_name,
        "protocol": "Compound V3",
        "collateral_address": collateral_address,
        "status": "error",
        "error": None,
        "markets": []
    }

    try:
        # Setup Web3
        w3 = Web3(Web3.HTTPProvider(chain_config['rpc']))
        if chain_name in ["Base", "Arbitrum"]:
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        # Get collateral token info
        collateral_token = w3.eth.contract(address=collateral_address, abi=ERC20_ABI)
        collateral_symbol = collateral_token.functions.symbol().call()
        collateral_decimals = collateral_token.functions.decimals().call()

        result["collateral_symbol"] = collateral_symbol
        result["collateral_decimals"] = collateral_decimals

        print(f"📊 Collateral: {collateral_symbol}")

        # Check each market
        for market_name, comet_address in chain_config['markets'].items():
            print(f"\n--- {market_name} Market ---")

            market_result = {
                "market_name": market_name,
                "comet_address": comet_address,
                "supported": False
            }

            comet = w3.eth.contract(address=comet_address, abi=COMET_ABI)

            # Check if collateral is supported
            try:
                asset_info = comet.functions.getAssetInfoByAddress(collateral_address).call()
                market_result["supported"] = True
            except:
                print(f"  ⚠️  {collateral_symbol} not supported in {market_name} market")
                result["markets"].append(market_result)
                continue

            # Get base token info
            base_token_address = comet.functions.baseToken().call()
            base_token = w3.eth.contract(address=base_token_address, abi=ERC20_ABI)
            base_symbol = base_token.functions.symbol().call()
            base_decimals = comet.functions.decimals().call()

            # Market data
            totals = comet.functions.totalsBasic().call()
            total_supply = totals[4] / (10 ** base_decimals)
            total_borrow = totals[5] / (10 ** base_decimals)

            utilization = comet.functions.getUtilization().call() / 1e18 * 100
            supply_rate = comet.functions.getSupplyRate(int(utilization * 1e16)).call() / 1e18 * 100
            borrow_rate = comet.functions.getBorrowRate(int(utilization * 1e16)).call() / 1e18 * 100

            # Collateral factors
            borrow_cf = asset_info[4] / 1e18 * 100  # borrowCollateralFactor = LTV
            liquidate_cf = asset_info[5] / 1e18 * 100  # liquidateCollateralFactor
            liquidation_factor = asset_info[6] / 1e18  # Used in HF calculation
            supply_cap = asset_info[7] / (10 ** collateral_decimals)  # Supply cap

            # Get total collateral supplied
            collateral_totals = comet.functions.totalsCollateral(collateral_address).call()
            total_collateral_supplied = collateral_totals[0] / (10 ** collateral_decimals)

            # Store market overview
            market_result["base_asset"] = base_symbol
            market_result["market_overview"] = {
                "total_supply": total_supply,
                "total_borrow": total_borrow,
                "supply_apy": supply_rate,
                "borrow_apy": borrow_rate,
                "utilization": utilization
            }
            market_result["collateral_info"] = {
                "total_supplied": total_collateral_supplied,
                "supply_cap": supply_cap,
                "cap_utilization": (total_collateral_supplied/supply_cap*100) if supply_cap > 0 else 0,
                "ltv": borrow_cf,
                "liquidation_cf": liquidate_cf
            }

            print(f"\n  📈 Market Overview:")
            print(f"    Base Asset:            {base_symbol}")
            print(f"    Total Supply:          {total_supply:,.2f} {base_symbol}")
            print(f"    Total Borrow:          {total_borrow:,.2f} {base_symbol}")
            print(f"    Supply APY:            {supply_rate:.2f}%")
            print(f"    Borrow APY:            {borrow_rate:.2f}%")
            print(f"    Utilization:           {utilization:.2f}%")

            print(f"\n  💰 {collateral_symbol} Collateral:")
            print(f"    Total Supplied:        {total_collateral_supplied:,.4f} {collateral_symbol}")
            print(f"    Supply Cap:            {supply_cap:,.4f} {collateral_symbol}")
            print(f"    Cap Utilization:       {(total_collateral_supplied/supply_cap*100) if supply_cap > 0 else 0:.2f}%")
            print(f"    LTV:                   {borrow_cf:.0f}%")
            print(f"    Liquidation CF:        {liquidate_cf:.0f}%")

            # Skip CLR if no collateral supplied
            if total_collateral_supplied == 0:
                print(f"\n  ℹ️  No {collateral_symbol} collateral supplied - skipping CLR")
                market_result["clr"] = {"error": "No collateral supplied"}
                result["markets"].append(market_result)
                continue

            # CLR Calculation
            print(f"\n  ⚠️  Calculating CLR...")

            # Fetch borrowers from subgraph
            borrowers = fetch_positions_from_subgraph(
                chain_config['subgraph'],
                comet_address,
                limit=100
            )

            if not borrowers:
                print(f"    ⚠️  No borrower data from subgraph - CLR unavailable")
                market_result["clr"] = {"error": "No borrower data from subgraph"}
                result["markets"].append(market_result)
                continue

            print(f"    Fetching data for {len(borrowers)} borrowers...")

            # Get prices
            collateral_price = comet.functions.getPrice(asset_info[2]).call() / 1e8  # Price feed returns 8 decimals

            # Batch call via Multicall3
            multicall = w3.eth.contract(address=MULTICALL3, abi=MULTICALL3_ABI)

            calls = []
            for borrower in borrowers:
                # borrowBalanceOf
                calls.append((comet.address, comet.encode_abi('borrowBalanceOf', [borrower])))
                # collateralBalanceOf
                calls.append((comet.address, comet.encode_abi('collateralBalanceOf', [borrower, collateral_address])))

            _, multicall_results = multicall.functions.aggregate(calls).call()

            # Decode and calculate health factors
            risk_buckets = {
                "critical": [],
                "high_risk": [],
                "at_risk": [],
                "moderate": [],
                "safe": []
            }

            total_debt_analyzed = 0
            debt_at_risk = 0

            for i in range(0, len(multicall_results), 2):
                borrow_balance = w3.codec.decode(['uint256'], multicall_results[i])[0] / (10 ** base_decimals)
                collateral_balance = w3.codec.decode(['uint128'], multicall_results[i+1])[0] / (10 ** collateral_decimals)

                if borrow_balance == 0 or collateral_balance == 0:
                    continue

                # Health Factor = (Collateral USD × Liquidation Factor) / Borrowed USD
                collateral_usd = collateral_balance * collateral_price
                hf = (collateral_usd * liquidation_factor) / borrow_balance if borrow_balance > 0 else float('inf')

                total_debt_analyzed += borrow_balance

                if hf < 1.0:
                    risk_buckets["critical"].append({"address": borrowers[i//2], "health_factor": hf, "debt": borrow_balance})
                    debt_at_risk += borrow_balance
                elif hf < 1.05:
                    risk_buckets["high_risk"].append({"address": borrowers[i//2], "health_factor": hf, "debt": borrow_balance})
                    debt_at_risk += borrow_balance
                elif hf < 1.1:
                    risk_buckets["at_risk"].append({"address": borrowers[i//2], "health_factor": hf, "debt": borrow_balance})
                    debt_at_risk += borrow_balance
                elif hf < 1.25:
                    risk_buckets["moderate"].append({"address": borrowers[i//2], "health_factor": hf, "debt": borrow_balance})
                else:
                    risk_buckets["safe"].append({"address": borrowers[i//2], "health_factor": hf, "debt": borrow_balance})

            total_positions = sum(len(v) for v in risk_buckets.values())
            at_risk_count = len(risk_buckets["critical"]) + len(risk_buckets["high_risk"]) + len(risk_buckets["at_risk"])

            clr_count = (at_risk_count / total_positions * 100) if total_positions > 0 else 0
            clr_value = (debt_at_risk / total_debt_analyzed * 100) if total_debt_analyzed > 0 else 0

            # Store CLR in result
            market_result["clr"] = {
                "clr_by_count": clr_count,
                "clr_by_value": clr_value,
                "positions_analyzed": total_positions,
                "debt_analyzed": total_debt_analyzed,
                "debt_at_risk": debt_at_risk,
                "risk_distribution": {
                    "critical": len(risk_buckets["critical"]),
                    "high_risk": len(risk_buckets["high_risk"]),
                    "at_risk": len(risk_buckets["at_risk"]),
                    "moderate": len(risk_buckets["moderate"]),
                    "safe": len(risk_buckets["safe"])
                }
            }

            print(f"\n    Health Factor Distribution:")
            bucket_labels = {
                "critical": "Critical (HF < 1.0)",
                "high_risk": "High Risk (1.0 ≤ HF < 1.05)",
                "at_risk": "At Risk (1.05 ≤ HF < 1.1)",
                "moderate": "Moderate (1.1 ≤ HF < 1.25)",
                "safe": "Safe (HF ≥ 1.25)"
            }
            for bucket_key, positions in risk_buckets.items():
                count = len(positions)
                pct = (count / total_positions * 100) if total_positions > 0 else 0
                print(f"      {bucket_labels[bucket_key]}: {count} positions ({pct:.1f}%)")

            print(f"\n    CLR (by count):        {clr_count:.2f}%")
            print(f"    CLR (by value):        {clr_value:.2f}%")
            print(f"    Positions Analyzed:    {total_positions}")
            print(f"    Debt Analyzed:         {total_debt_analyzed:,.2f} {base_symbol}")

            result["markets"].append(market_result)

        result["status"] = "success"
        return result

    except Exception as e:
        print(f"❌ Error: {e}")
        result["error"] = str(e)
        return result

if __name__ == "__main__":
    import json

    # Token-independent: just change this address
    collateral_token = "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf"  # cbBTC

    all_results = []
    for chain_name, config in MARKETS.items():
        result = analyze_compound_market(collateral_token, chain_name, config)
        if result:
            all_results.append(result)
        print()

    # Print JSON summary
    print("\n" + "="*70)
    print("JSON OUTPUT:")
    print("="*70)
    print(json.dumps(all_results, indent=2, default=str))