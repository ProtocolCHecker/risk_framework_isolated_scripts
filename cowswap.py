#!/usr/bin/env python3
"""
CowSwap Slippage Calculator
Calculates slippage across different trade sizes for any token pair
"""

import requests
from typing import Dict, List, Optional

# API Configuration
COWSWAP_API = {
    "ethereum": "https://api.cow.fi/mainnet/api/v1",
    "base": "https://api.cow.fi/base/api/v1",
}


def get_quote(
    network: str,
    sell_token: str,
    buy_token: str,
    sell_amount: int
) -> Dict:
    """Fetch quote from CowSwap API"""
    url = f"{COWSWAP_API[network]}/quote"
    payload = {
        "sellToken": sell_token,
        "buyToken": buy_token,
        "sellAmountBeforeFee": str(sell_amount),
        "kind": "sell",
        "from": "0x0000000000000000000000000000000000000001",
        "priceQuality": "verified",
    }
    
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()


def usd_to_atomic_units(
    usd_amount: float,
    token_price_usd: float,
    decimals: int
) -> int:
    """Convert USD to atomic units of any token"""
    token_amount = usd_amount / token_price_usd
    return int(token_amount * 10**decimals)


def calculate_effective_price(
    buy_amount: int,
    sell_amount: int,
    fee_amount: int
) -> float:
    """Calculate effective price after fees"""
    sell_after_fee = sell_amount - fee_amount
    return buy_amount / sell_after_fee if sell_after_fee > 0 else 0


def calculate_slippage(
    network: str,
    sell_token: str,
    buy_token: str,
    sell_token_decimals: int,
    buy_token_decimals: int,
    sell_token_price_usd: float,
    trade_sizes_usd: Optional[List[int]] = None,
    baseline_index: int = 1,
    sell_token_symbol: str = "SELL",
    buy_token_symbol: str = "BUY"
) -> Dict:
    """
    Calculate slippage for different trade sizes on any token pair.
    Returns dict with all slippage data.

    Args:
        network: "ethereum" or "base"
        sell_token: Address of token to sell
        buy_token: Address of token to buy
        sell_token_decimals: Decimals of sell token
        buy_token_decimals: Decimals of buy token
        sell_token_price_usd: Current USD price of sell token
        trade_sizes_usd: List of trade sizes in USD (optional)
        baseline_index: Index of trade size to use as baseline (default: 1 = 2nd smallest)
        sell_token_symbol: Symbol for display (optional)
        buy_token_symbol: Symbol for display (optional)
    """
    if trade_sizes_usd is None:
        trade_sizes_usd = [1_000, 10_000, 50_000, 100_000, 500_000, 1_000_000]

    output = {
        "protocol": "CowSwap",
        "network": network,
        "sell_token": sell_token,
        "buy_token": buy_token,
        "sell_token_symbol": sell_token_symbol,
        "buy_token_symbol": buy_token_symbol,
        "sell_token_price_usd": sell_token_price_usd,
        "status": "error",
        "error": None,
        "quotes": [],
        "slippage_analysis": []
    }

    print(f"CowSwap Slippage Analysis ({network.upper()})")
    print(f"Pair: {sell_token_symbol} → {buy_token_symbol}")
    print(f"{sell_token_symbol} Price: ${sell_token_price_usd:,.2f}")
    print("=" * 70)

    results = []

    # Get quotes for all trade sizes
    for usd_size in trade_sizes_usd:
        sell_amount = usd_to_atomic_units(
            usd_size,
            sell_token_price_usd,
            sell_token_decimals
        )

        try:
            quote = get_quote(network, sell_token, buy_token, sell_amount)
            buy_amount = int(quote["quote"]["buyAmount"])
            fee_amount = int(quote["quote"]["feeAmount"])

            effective_price = calculate_effective_price(buy_amount, sell_amount, fee_amount)

            results.append({
                "size_usd": usd_size,
                "sell_amount": sell_amount,
                "buy_amount": buy_amount,
                "fee_amount": fee_amount,
                "effective_price": effective_price,
            })

            print(f"${usd_size:>7,} | Fetched quote successfully")

        except Exception as e:
            print(f"${usd_size:>7,} | Error: {e}")
            output["error"] = str(e)
            return output

    # Use specified baseline
    baseline_price = results[baseline_index]["effective_price"]
    output["baseline_size_usd"] = results[baseline_index]["size_usd"]
    output["baseline_price"] = baseline_price

    print("\n" + "=" * 70)
    print(f"{'Trade Size':>12} | {'Effective Price':>15} | {'Slippage %':>12}")
    print("=" * 70)

    for i, result in enumerate(results):
        slippage_pct = ((baseline_price - result["effective_price"]) / baseline_price) * 100
        is_baseline = i == baseline_index
        marker = " (baseline)" if is_baseline else ""

        result["slippage_pct"] = slippage_pct
        result["is_baseline"] = is_baseline
        output["slippage_analysis"].append(result)

        print(f"${result['size_usd']:>10,} | {result['effective_price']:>15.6f} | "
              f"{slippage_pct:>11.4f}%{marker}")

    print("=" * 70)

    output["quotes"] = results
    output["status"] = "success"
    return output


if __name__ == "__main__":
    import json

    # Example: cbBTC -> USDC on Ethereum
    result = calculate_slippage(
        network="ethereum",
        sell_token="0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",  # cbBTC
        buy_token="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",   # USDC
        sell_token_decimals=8,
        buy_token_decimals=6,
        sell_token_price_usd=100_000,  # cbBTC price
        sell_token_symbol="cbBTC",
        buy_token_symbol="USDC"
    )

    # Print JSON summary
    print("\n" + "="*70)
    print("JSON OUTPUT:")
    print("="*70)
    print(json.dumps(result, indent=2, default=str))
    