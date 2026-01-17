from web3 import Web3
import json
import numpy as np
import requests

# Minimal ABI for required functions
CHAINLINK_ABI = json.loads('[{"inputs":[],"name":"latestRoundData","outputs":[{"internalType":"uint80","name":"roundId","type":"uint80"},{"internalType":"int256","name":"answer","type":"int256"},{"internalType":"uint256","name":"startedAt","type":"uint256"},{"internalType":"uint256","name":"updatedAt","type":"uint256"},{"internalType":"uint80","name":"answeredInRound","type":"uint80"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"}]')
TOKEN_ABI = json.loads('[{"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"}]')

# Hardcoded RPC URLs
RPCS = {
    "ethereum": "https://lb.drpc.live/ethereum/AtiZvaKOcUmKq-AbTta3bRaREdpZbjkR8LQrEklbR4ac",
    "base": "https://lb.drpc.live/base/AtiZvaKOcUmKq-AbTta3bRaREdpZbjkR8LQrEklbR4ac",
    "arbitrum": "https://lb.drpc.live/arbitrum/AtiZvaKOcUmKq-AbTta3bRaREdpZbjkR8LQrEklbR4ac"
}

HELIUS_KEY = "5167631c-772f-49bb-ab19-fe8553e4e6dc"

def get_reserves(w3, por_address):
    contract = w3.eth.contract(address=por_address, abi=CHAINLINK_ABI)
    round_data = contract.functions.latestRoundData().call()
    decimals = contract.functions.decimals().call()
    reserves = round_data[1] / (10 ** decimals)
    return reserves

def get_evm_supply(w3, token_address):
    contract = w3.eth.contract(address=token_address, abi=TOKEN_ABI)
    supply = contract.functions.totalSupply().call()
    decimals = contract.functions.decimals().call()
    return supply / (10 ** decimals)

def get_solana_supply(token_address):
    try:
        r = requests.post(
            f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenSupply",
                "params": [token_address]
            },
            timeout=30
        ).json()
        
        result = r.get('result', {})
        value = result.get('value', {})
        amount = float(value.get('amount', 0))
        decimals = int(value.get('decimals', 8))
        return amount / (10 ** decimals)
    except Exception as e:
        print(f"Error fetching Solana supply: {e}")
        return 0

def calculate_reserve_ratio(reserves, total_supply):
    ratio = reserves / total_supply if total_supply > 0 else 0
    
    if ratio >= 1.0:
        score = 95 + min(5, (ratio - 1.0) * 100)
    else:
        score = max(0, 95 - (1.0 - ratio) * 500)
    
    return {
        "reserves": reserves,
        "total_supply": total_supply,
        "reserve_ratio": ratio,
        "reserve_ratio_pct": ratio * 100,
        "surplus_deficit": reserves - total_supply,
        "is_fully_backed": reserves >= total_supply,
        "score": score
    }

if __name__ == "__main__":
    evm_chains = []
    
    for chain_name in ["ethereum", "base", "arbitrum"]:
        print(f"\n{chain_name.upper()}:")
        por = input("  Chainlink PoR address (press Enter to skip): ").strip()
        token = input("  Token address (press Enter to skip): ").strip()
        
        if por:
            evm_chains.append({
                "name": chain_name,
                "rpc": RPCS[chain_name],
                "por": por,
                "token": token
            })
    
    print("\nSOLANA:")
    solana_token = input("  Token address (press Enter to skip): ").strip()
    
    reserve_values = []
    total_supply = 0
    
    # Collect reserves from each PoR feed
    for chain in evm_chains:
        w3 = Web3(Web3.HTTPProvider(chain["rpc"]))
        reserves = get_reserves(w3, chain["por"])
        reserve_values.append(reserves)
        print(f"\n{chain['name'].upper()} Reserves: {reserves:.8f}")
    
    # Take median of reserves
    median_reserves = np.median(reserve_values) if reserve_values else 0
    print(f"\nMedian Reserves: {median_reserves:.8f}")
    
    # Sum EVM total supply
    for chain in evm_chains:
        if chain["token"]:
            w3 = Web3(Web3.HTTPProvider(chain["rpc"]))
            supply = get_evm_supply(w3, chain["token"])
            total_supply += supply
            print(f"{chain['name'].upper()} Supply: {supply:.8f}")
    
    # Add Solana supply
    if solana_token:
        solana_supply = get_solana_supply(solana_token)
        total_supply += solana_supply
        print(f"SOLANA Supply: {solana_supply:.8f}")
    
    # Calculate metrics
    print("\n" + "="*50)
    results = calculate_reserve_ratio(median_reserves, total_supply)
    
    for key, value in results.items():
        if isinstance(value, float):
            print(f"{key}: {value:.8f}")
        else:
            print(f"{key}: {value}")