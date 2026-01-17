"""
Slippage Cross-Verification Across DEX Aggregators
Compares quotes from 5 aggregators to find median slippage
"""

import requests
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

# API Configuration
API_KEYS = {
    "1inch": "0oMzoh4kEXyjaZO6SKWjbPQIv2lb78jA",
    "0x": "2f6515bf-7bed-4e07-8058-792cdb570d05",
}

# Chain mappings
CHAIN_MAP = {
    "ethereum": {"cowswap": "mainnet", "1inch": 1, "0x": 1, "kyber": "ethereum", "odos": 1},
    "base": {"cowswap": "base", "1inch": 8453, "0x": 8453, "kyber": "base", "odos": 8453},
}


def usd_to_atomic_units(usd_amount: float, token_price_usd: float, decimals: int) -> int:
    """Convert USD to atomic units"""
    token_amount = usd_amount / token_price_usd
    return int(token_amount * 10**decimals)


def get_cowswap_quote(chain: str, sell_token: str, buy_token: str, sell_amount: int) -> Optional[int]:
    """Get quote from CowSwap"""
    try:
        url = f"https://api.cow.fi/{CHAIN_MAP[chain]['cowswap']}/api/v1/quote"
        payload = {
            "sellToken": sell_token,
            "buyToken": buy_token,
            "sellAmountBeforeFee": str(sell_amount),
            "kind": "sell",
            "from": "0x0000000000000000000000000000000000000001",
            "priceQuality": "verified",
        }
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return int(resp.json()["quote"]["buyAmount"])
    except Exception as e:
        print(f"  CowSwap error: {e}")
        return None


def get_1inch_quote(chain: str, sell_token: str, buy_token: str, sell_amount: int) -> Optional[int]:
    """Get quote from 1inch"""
    try:
        chain_id = CHAIN_MAP[chain]["1inch"]
        url = f"https://api.1inch.dev/swap/v6.0/{chain_id}/quote"
        params = {
            "src": sell_token,
            "dst": buy_token,
            "amount": str(sell_amount),
        }
        headers = {"Authorization": f"Bearer {API_KEYS['1inch']}"}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        return int(resp.json()["dstAmount"])
    except Exception as e:
        print(f"  1inch error: {e}")
        return None


def get_0x_quote(chain: str, sell_token: str, buy_token: str, sell_amount: int) -> Optional[int]:
    """Get quote from 0x"""
    try:
        url = "https://api.0x.org/swap/permit2/quote"
        params = {
            "chainId": CHAIN_MAP[chain]["0x"],
            "sellToken": sell_token,
            "buyToken": buy_token,
            "sellAmount": str(sell_amount),
            "taker": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
        }
        headers = {
            "0x-api-key": API_KEYS["0x"],
            "0x-version": "v2",
        }
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        return int(resp.json().get("buyAmount", 0))
    except Exception as e:
        print(f"  0x error: {e}")
        return None


def get_kyberswap_quote(chain: str, sell_token: str, buy_token: str, sell_amount: int) -> Optional[int]:
    """Get quote from KyberSwap"""
    try:
        chain_name = CHAIN_MAP[chain]["kyber"]
        url = f"https://aggregator-api.kyberswap.com/{chain_name}/api/v1/routes"
        params = {
            "tokenIn": sell_token,
            "tokenOut": buy_token,
            "amountIn": str(sell_amount),
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()["data"]
        return int(data["routeSummary"]["amountOut"])
    except Exception as e:
        print(f"  KyberSwap error: {e}")
        return None


def get_odos_quote(chain: str, sell_token: str, buy_token: str, sell_amount: int) -> Optional[int]:
    """Get quote from Odos"""
    try:
        url = "https://api.odos.xyz/sor/quote/v2"
        payload = {
            "chainId": CHAIN_MAP[chain]["odos"],
            "inputTokens": [{"tokenAddress": sell_token, "amount": str(sell_amount)}],
            "outputTokens": [{"tokenAddress": buy_token, "proportion": 1}],
            "userAddr": "0x0000000000000000000000000000000000000001",
        }
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return int(resp.json()["outAmounts"][0])
    except Exception as e:
        print(f"  Odos error: {e}")
        return None


def fetch_all_quotes(
    chain: str,
    sell_token: str,
    buy_token: str,
    sell_amount: int
) -> Dict[str, Optional[int]]:
    """Fetch quotes from all aggregators in parallel"""
    aggregators = {
        "CowSwap": lambda: get_cowswap_quote(chain, sell_token, buy_token, sell_amount),
        "1inch": lambda: get_1inch_quote(chain, sell_token, buy_token, sell_amount),
        "0x": lambda: get_0x_quote(chain, sell_token, buy_token, sell_amount),
        "KyberSwap": lambda: get_kyberswap_quote(chain, sell_token, buy_token, sell_amount),
        "Odos": lambda: get_odos_quote(chain, sell_token, buy_token, sell_amount),
    }
    
    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(func): name for name, func in aggregators.items()}
        for future in as_completed(futures):
            name = futures[future]
            results[name] = future.result()
    
    return results


def cross_verify_slippage(
    chain: str,
    sell_token: str,
    buy_token: str,
    sell_token_decimals: int,
    sell_token_price_usd: float,
    trade_sizes_usd: Optional[List[int]] = None,
    sell_token_symbol: str = "SELL",
    buy_token_symbol: str = "BUY"
):
    """
    Cross-verify slippage across multiple aggregators
    
    Args:
        chain: "ethereum" or "base"
        sell_token: Address of token to sell
        buy_token: Address of token to buy
        sell_token_decimals: Decimals of sell token
        sell_token_price_usd: Current USD price of sell token
        trade_sizes_usd: List of trade sizes in USD (default: [100K, 500K])
        sell_token_symbol: Symbol for display
        buy_token_symbol: Symbol for display
    """
    if trade_sizes_usd is None:
        trade_sizes_usd = [100_000, 500_000]
    
    print(f"Slippage Cross-Verification ({chain.upper()})")
    print(f"Pair: {sell_token_symbol} → {buy_token_symbol}")
    print(f"{sell_token_symbol} Price: ${sell_token_price_usd:,.2f}")
    print("=" * 90)
    
    for usd_size in trade_sizes_usd:
        sell_amount = usd_to_atomic_units(usd_size, sell_token_price_usd, sell_token_decimals)
        
        print(f"\nTrade Size: ${usd_size:,}")
        print("-" * 90)
        print("Fetching quotes from all aggregators...")
        
        quotes = fetch_all_quotes(chain, sell_token, buy_token, sell_amount)
        
        # Filter successful quotes
        successful_quotes = {k: v for k, v in quotes.items() if v is not None}
        
        if not successful_quotes:
            print("❌ No successful quotes received")
            continue
        
        # Find best quote
        best_aggregator = max(successful_quotes, key=successful_quotes.get)
        best_buy_amount = successful_quotes[best_aggregator]
        
        # Calculate slippage for each aggregator
        slippages = []
        print(f"\n{'Aggregator':<12} | {'Buy Amount':>20} | {'Slippage %':>12} | {'Status':>8}")
        print("-" * 90)
        
        for agg in ["CowSwap", "1inch", "0x", "KyberSwap", "Odos"]:
            buy_amount = quotes.get(agg)
            
            if buy_amount is None:
                print(f"{agg:<12} | {'N/A':>20} | {'N/A':>12} | {'Failed':>8}")
            else:
                slippage_pct = ((best_buy_amount - buy_amount) / best_buy_amount) * 100
                slippages.append(slippage_pct)
                
                is_best = agg == best_aggregator
                status = "BEST ⭐" if is_best else "OK"
                
                print(f"{agg:<12} | {buy_amount:>20,} | {slippage_pct:>11.4f}% | {status:>8}")
        
        # Calculate median slippage
        if slippages:
            median_slippage = statistics.median(slippages)
            print("-" * 90)
            print(f"Median Slippage: {median_slippage:.4f}%")
            print(f"Successful Quotes: {len(successful_quotes)}/5")
    
    print("=" * 90)


if __name__ == "__main__":
    # Example: cbBTC -> USDC on Ethereum
    cross_verify_slippage(
        chain="ethereum",
        sell_token="0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",  # cbBTC
        buy_token="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",   # USDC
        sell_token_decimals=8,
        sell_token_price_usd=100_000,
        trade_sizes_usd=[100_000, 500_000],
        sell_token_symbol="cbBTC",
        buy_token_symbol="USDC"
    )