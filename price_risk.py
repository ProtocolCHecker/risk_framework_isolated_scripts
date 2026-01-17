import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def get_coingecko_data(coin_id, days=365):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {'vs_currency': 'usd', 'days': days}
    response = requests.get(url, params=params)
    data = response.json()
    prices = [item[1] for item in data['prices']]
    timestamps = [item[0] for item in data['prices']]
    return timestamps, prices

def calculate_peg_deviation(token_prices, underlying_prices):
    token_prices = np.array(token_prices)
    underlying_prices = np.array(underlying_prices)
    
    # Calculate deviation as percentage
    deviation = ((token_prices - underlying_prices) / underlying_prices) * 100
    
    return {
        'Mean Deviation': f"{np.mean(deviation):.4f}%",
        'Max Deviation': f"{np.max(deviation):.4f}%",
        'Min Deviation': f"{np.min(deviation):.4f}%",
        'Std Dev of Deviation': f"{np.std(deviation):.4f}%",
        'Current Deviation': f"{deviation[-1]:.4f}%"
    }

def calculate_metrics(prices):
    prices = np.array(prices)
    returns = np.diff(prices) / prices[:-1]
    
    # Annualized Volatility
    volatility = np.std(returns) * np.sqrt(365)
    
    # VaR (Value at Risk)
    var_95 = np.percentile(returns, 5)
    var_99 = np.percentile(returns, 1)
    
    # CVaR (Conditional Value at Risk)
    cvar_95 = returns[returns <= var_95].mean()
    cvar_99 = returns[returns <= var_99].mean()
    
    return {
        'Annualized Volatility': f"{volatility:.2%}",
        'VaR 95%': f"{var_95:.2%}",
        'VaR 99%': f"{var_99:.2%}",
        'CVaR 95%': f"{cvar_95:.2%}",
        'CVaR 99%': f"{cvar_99:.2%}"
    }

if __name__ == "__main__":
    token_id = input("Enter token CoinGecko ID (e.g., tether, dai): ").strip()
    underlying_id = input("Enter underlying asset CoinGecko ID (e.g., bitcoin, ethereum, usd-coin): ").strip()
    
    print(f"\nFetching data for {token_id}...")
    token_timestamps, token_prices = get_coingecko_data(token_id)
    
    print(f"Fetching data for {underlying_id}...")
    underlying_timestamps, underlying_prices = get_coingecko_data(underlying_id)
    
    # Ensure both have the same length
    min_len = min(len(token_prices), len(underlying_prices))
    token_prices = token_prices[:min_len]
    underlying_prices = underlying_prices[:min_len]
    
    print(f"\nCalculating peg deviation metrics...")
    peg_metrics = calculate_peg_deviation(token_prices, underlying_prices)
    
    print("\n=== Peg Deviation Metrics ===")
    for key, value in peg_metrics.items():
        print(f"{key}: {value}")
    
    print(f"\nCalculating risk metrics for {token_id} ({len(token_prices)} data points)...\n")
    metrics = calculate_metrics(token_prices)
    
    print("=== Risk Metrics ===")
    for key, value in metrics.items():
        print(f"{key}: {value}")