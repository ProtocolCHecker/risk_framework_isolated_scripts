import requests
import numpy as np
import time

def gini(amounts):
    sorted_amounts = np.sort(amounts)
    n = len(amounts)
    index = np.arange(1, n + 1)
    return (2 * np.sum(index * sorted_amounts)) / (n * np.sum(sorted_amounts)) - (n + 1) / n

def get_evm_holders(token_address, blockscout_url, max_holders=200):
    holders = []
    url = f"{blockscout_url}/api/v2/tokens/{token_address}/holders"
    
    while url and len(holders) < max_holders:
        try:
            # Increased timeout to 30 seconds
            r = requests.get(url, timeout=30).json()
            items = r.get('items', [])
            holders.extend([(h['address']['hash'], float(h['value']) / 1e8) for h in items])
            
            if len(holders) >= max_holders:
                break
                
            next_params = r.get('next_page_params')
            url = f"{blockscout_url}/api/v2/tokens/{token_address}/holders?" + requests.compat.urlencode(next_params) if next_params else None
            
            time.sleep(0.5)  # Small delay between requests
            
        except requests.exceptions.Timeout:
            print(f"Timeout - try using Basescan API instead for Base")
            break
        except Exception as e:
            print(f"Error: {e}")
            break
    
    return holders[:max_holders]

def get_solana_holders(token_address, max_holders=200):
    holders = []
    cursor = None
    helius_key = "5167631c-772f-49bb-ab19-fe8553e4e6dc"
    
    while len(holders) < max_holders:
        try:
            params = {"limit": min(1000, max_holders - len(holders)), "mint": token_address}
            if cursor:
                params["cursor"] = cursor
            
            r = requests.post(
                f"https://mainnet.helius-rpc.com/?api-key={helius_key}",
                json={"jsonrpc": "2.0", "id": 1, "method": "getTokenAccounts", "params": params},
                timeout=30
            ).json()
            
            result = r.get('result', {})
            accounts = result.get('token_accounts', [])
            
            if not accounts:
                break
            
            # Group by owner and sum amounts (one owner can have multiple token accounts)
            owner_balances = {}
            for acc in accounts:
                owner = acc['owner']
                amount = float(acc.get('amount', 0)) / 1e8
                owner_balances[owner] = owner_balances.get(owner, 0) + amount
            
            holders.extend(list(owner_balances.items()))
            cursor = result.get('cursor')
            
            if not cursor or len(holders) >= max_holders:
                break
                
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error: {e}")
            break
    
    return holders[:max_holders]

def analyze_token(token_address, chain_name, blockscout_url=None) -> dict:
    """Analyze token distribution. Returns dict with metrics."""
    print(f"\nAnalyzing {chain_name}...", flush=True)

    result = {
        "chain": chain_name,
        "token_address": token_address,
        "status": "error",
        "error": None
    }

    holders = get_evm_holders(token_address, blockscout_url) if blockscout_url else get_solana_holders(token_address)

    if not holders:
        print(f"No data for {chain_name}\n")
        result["error"] = "No holder data"
        return result

    holders.sort(key=lambda x: x[1], reverse=True)
    balances = np.array([h[1] for h in holders])
    total = balances.sum()

    gini_coeff = gini(balances)
    top_10_concentration = balances[:10].sum() / total * 100
    top_50_concentration = balances[:50].sum() / total * 100

    result["metrics"] = {
        "holders_analyzed": len(holders),
        "total_supply": float(total),
        "gini_coefficient": float(gini_coeff),
        "top_10_concentration_pct": float(top_10_concentration),
        "top_50_concentration_pct": float(top_50_concentration)
    }

    result["top_holders"] = [
        {"address": addr, "balance": float(bal)}
        for addr, bal in holders[:10]
    ]

    print(f"\n{'='*60}")
    print(f"{chain_name} - Token Distribution")
    print(f"{'='*60}")
    print(f"Holders Analyzed: {len(holders)}")
    print(f"Gini Coefficient: {gini_coeff:.4f}")
    print(f"Top 10 Concentration: {top_10_concentration:.2f}%")
    print(f"Top 50 Concentration: {top_50_concentration:.2f}%")
    print(f"{'='*60}\n")

    result["status"] = "success"
    return result

if __name__ == "__main__":
    import json

    addr = "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf"

    all_results = []
    all_results.append(analyze_token(addr, "Ethereum", "https://eth.blockscout.com"))
    all_results.append(analyze_token(addr, "Base", "https://base.blockscout.com"))
    all_results.append(analyze_token(addr, "Arbitrum", "https://arbitrum.blockscout.com"))
    all_results.append(analyze_token("cbbtcf3aa214zXHbiAZQwf4122FBYbraNdFqgw4iMij", "Solana"))

    # Print JSON summary
    print("\n" + "="*70)
    print("JSON OUTPUT:")
    print("="*70)
    print(json.dumps(all_results, indent=2, default=str))