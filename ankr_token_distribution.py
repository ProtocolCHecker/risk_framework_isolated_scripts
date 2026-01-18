import requests

# ============================================================================
# CONFIGURATION - Add your Ankr API key here
# Get free key at: https://www.ankr.com/rpc/
# ============================================================================
ANKR_API_KEY = "e8bf3173e4e6b30a96ea14c4c84afac697441d8a280563b3ea8e82ad23641605"  # Replace with your actual API key
ANKR_URL = f"https://rpc.ankr.com/multichain/{ANKR_API_KEY}"

# Token contract address (ARB token on Arbitrum)
TOKEN_ADDRESS = "0x912CE59144191C1204E64559FE8253a0e49E6548"
BLOCKCHAIN = "arbitrum"

def get_token_holders(contract_address, page_size=100, page_token=None):
    """Get token holders with balances"""
    
    payload = {
        "jsonrpc": "2.0",
        "method": "ankr_getTokenHolders",
        "params": {
            "blockchain": BLOCKCHAIN,
            "contractAddress": contract_address,
            "pageSize": page_size
        },
        "id": 1
    }
    
    if page_token:
        payload["params"]["pageToken"] = page_token
    
    try:
        response = requests.post(ANKR_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            print(f"❌ Error: {data['error'].get('message', 'Unknown error')}")
            return None
        
        result = data.get("result", {})
        holders = result.get("holders", [])
        total_count = result.get("holdersCount", 0)
        next_token = result.get("nextPageToken")
        
        print(f"📊 Total Holders: {total_count:,}")
        print(f"📄 Page Size: {len(holders)} holders\n")
        
        # Display holders
        for i, holder in enumerate(holders, 1):
            address = holder.get("holderAddress", "N/A")
            balance = float(holder.get("balance", 0))
            balance_usd = float(holder.get("balanceUsd", 0))
            
            print(f"{i:3d}. {address}")
            print(f"     Balance: {balance:,.2f} tokens (${balance_usd:,.2f})\n")
        
        return {
            "holders": holders,
            "total_count": total_count,
            "next_token": next_token
        }
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        if "403" in str(e):
            print("💡 Make sure your API key is correct")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    print("="*70)
    print("ANKR API - ARBITRUM TOKEN HOLDERS")
    print("="*70)
    print(f"Token: {TOKEN_ADDRESS}")
    print(f"Chain: {BLOCKCHAIN.upper()}\n")
    
    get_token_holders(TOKEN_ADDRESS, page_size=500)
    
    print("\n" + "="*70)
