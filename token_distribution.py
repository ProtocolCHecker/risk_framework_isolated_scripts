import requests
import numpy as np
import time

# Ankr API Configuration
ANKR_API_KEY = "e8bf3173e4e6b30a96ea14c4c84afac697441d8a280563b3ea8e82ad23641605"
ANKR_URL = f"https://rpc.ankr.com/multichain/{ANKR_API_KEY}"

# Chain to Ankr blockchain mapping
ANKR_CHAINS = {
    "ethereum": "eth",
    "base": "base",
    "arbitrum": "arbitrum",
    "polygon": "polygon",
    "bsc": "bsc",
    "avalanche": "avalanche",
    "optimism": "optimism",
}


def gini(amounts):
    sorted_amounts = np.sort(amounts)
    n = len(amounts)
    index = np.arange(1, n + 1)
    return (2 * np.sum(index * sorted_amounts)) / (n * np.sum(sorted_amounts)) - (n + 1) / n


def get_ankr_holders(token_address, chain_name, max_holders=200, decimals=18):
    """Get token holders using Ankr API"""
    holders = []
    page_token = None
    ankr_chain = ANKR_CHAINS.get(chain_name.lower())

    if not ankr_chain:
        print(f"  Ankr does not support chain: {chain_name}")
        return []

    while len(holders) < max_holders:
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "ankr_getTokenHolders",
                "params": {
                    "blockchain": ankr_chain,
                    "contractAddress": token_address,
                    "pageSize": min(200, max_holders - len(holders))
                },
                "id": 1
            }

            if page_token:
                payload["params"]["pageToken"] = page_token

            response = requests.post(ANKR_URL, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                print(f"  Ankr error: {data['error'].get('message', 'Unknown error')}")
                break

            result = data.get("result", {})
            holder_list = result.get("holders", [])

            if not holder_list:
                break

            for holder in holder_list:
                address = holder.get("holderAddress", "")
                balance = float(holder.get("balance", 0))
                holders.append((address, balance))

            page_token = result.get("nextPageToken")
            print(f"  Fetched {len(holders)} holders via Ankr...", end="\r")

            if not page_token or len(holders) >= max_holders:
                break

            time.sleep(0.3)

        except Exception as e:
            print(f"  Ankr error: {e}")
            break

    print(f"  Total holders fetched via Ankr: {len(holders)}")
    return holders[:max_holders]


def get_evm_holders(token_address, blockscout_url, max_holders=200, decimals=8):
    holders = []
    url = f"{blockscout_url}/api/v2/tokens/{token_address}/holders"
    divisor = 10 ** decimals

    while url and len(holders) < max_holders:
        try:
            # Increased timeout to 30 seconds
            r = requests.get(url, timeout=30).json()
            items = r.get('items', [])
            holders.extend([(h['address']['hash'], float(h['value']) / divisor) for h in items])
            
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

def analyze_token(token_address, chain_name, blockscout_url=None, use_ankr=False, decimals=8) -> dict:
    """
    Analyze token distribution. Returns dict with metrics.

    Args:
        token_address: Token contract address
        chain_name: Name of the chain (Ethereum, Base, Arbitrum, Solana, etc.)
        blockscout_url: Blockscout API URL (optional for EVM chains)
        use_ankr: Force using Ankr API instead of Blockscout
        decimals: Token decimals (default 8 for cbBTC-like tokens)
    """
    print(f"\nAnalyzing {chain_name}...", flush=True)

    result = {
        "chain": chain_name,
        "token_address": token_address,
        "status": "error",
        "error": None,
        "data_source": None
    }

    holders = []

    # Determine which API to use
    if chain_name.lower() == "solana":
        holders = get_solana_holders(token_address)
        result["data_source"] = "Helius"
    elif use_ankr or chain_name.lower() in ["arbitrum"]:
        # Use Ankr for Arbitrum (Blockscout often down) or if explicitly requested
        print(f"  Using Ankr API...")
        holders = get_ankr_holders(token_address, chain_name, decimals=decimals)
        result["data_source"] = "Ankr"
    elif blockscout_url:
        # Try Blockscout first
        holders = get_evm_holders(token_address, blockscout_url, decimals=decimals)
        result["data_source"] = "Blockscout"

        # Fallback to Ankr if Blockscout fails
        if not holders and chain_name.lower() in ANKR_CHAINS:
            print(f"  Blockscout failed, trying Ankr as fallback...")
            holders = get_ankr_holders(token_address, chain_name, decimals=decimals)
            result["data_source"] = "Ankr (fallback)"

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