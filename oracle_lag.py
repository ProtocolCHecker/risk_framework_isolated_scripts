# #!/usr/bin/env python3
# """
# Oracle Lag Calculator - Compare oracle update timestamps between two chains
# Calculates the time difference between oracle updates on different blockchains
# """

# from web3 import Web3
# from datetime import datetime
# import json

# # Configuration
# CONFIG = {
#     "chain_1": {
#         "name": "Ethereum",
#         "rpc": "https://lb.drpc.live/ethereum/AtiZvaKOcUmKq-AbTta3bRaREdpZbjkR8LQrEklbR4ac",
#         "oracle_address": "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419",  # ETH/USD Chainlink
#     },
#     "chain_2": {
#         "name": "Polygon",
#         "rpc": "https://lb.drpc.live/polygon/AtiZvaKOcUmKq-AbTta3bRaREdpZbjkR8LQrEklbR4ac",
#         "oracle_address": "0xAB594600376Ec9fD91F8e885dADF0CE036862dE0",  # MATIC/USD Chainlink
#     }
# }

# # Chainlink AggregatorV3 ABI (minimal)
# ORACLE_ABI = json.loads('''[
#     {
#         "inputs": [],
#         "name": "latestRoundData",
#         "outputs": [
#             {"name": "roundId", "type": "uint80"},
#             {"name": "answer", "type": "int256"},
#             {"name": "startedAt", "type": "uint256"},
#             {"name": "updatedAt", "type": "uint256"},
#             {"name": "answeredInRound", "type": "uint80"}
#         ],
#         "stateMutability": "view",
#         "type": "function"
#     }
# ]''')


# def get_oracle_data(rpc_url, oracle_address):
#     """Fetch latest oracle data from a chain"""
#     try:
#         w3 = Web3(Web3.HTTPProvider(rpc_url))
#         if not w3.is_connected():
#             raise ConnectionError(f"Failed to connect to {rpc_url}")
        
#         contract = w3.eth.contract(address=oracle_address, abi=ORACLE_ABI)
#         round_data = contract.functions.latestRoundData().call()
        
#         return {
#             "round_id": round_data[0],
#             "price": round_data[1],
#             "updated_at": round_data[3],
#             "timestamp": datetime.fromtimestamp(round_data[3])
#         }
#     except Exception as e:
#         print(f"Error fetching data: {e}")
#         return None


# def calculate_lag(chain1_data, chain2_data):
#     """Calculate time lag between two oracle updates"""
#     if not chain1_data or not chain2_data:
#         return None
    
#     lag_seconds = abs(chain1_data["updated_at"] - chain2_data["updated_at"])
#     return lag_seconds


# def main():
#     print("=" * 60)
#     print("ORACLE LAG CALCULATOR")
#     print("=" * 60)
    
#     # Fetch data from both chains
#     print(f"\nFetching data from {CONFIG['chain_1']['name']}...")
#     chain1_data = get_oracle_data(
#         CONFIG["chain_1"]["rpc"],
#         CONFIG["chain_1"]["oracle_address"]
#     )
    
#     print(f"Fetching data from {CONFIG['chain_2']['name']}...")
#     chain2_data = get_oracle_data(
#         CONFIG["chain_2"]["rpc"],
#         CONFIG["chain_2"]["oracle_address"]
#     )
    
#     # Display results
#     if chain1_data:
#         print(f"\n{CONFIG['chain_1']['name']} Oracle:")
#         print(f"  Last Update: {chain1_data['timestamp']}")
#         print(f"  Price: {chain1_data['price'] / 10**8:.2f} USD")
    
#     if chain2_data:
#         print(f"\n{CONFIG['chain_2']['name']} Oracle:")
#         print(f"  Last Update: {chain2_data['timestamp']}")
#         print(f"  Price: {chain2_data['price'] / 10**8:.2f} USD")
    
#     # Calculate lag
#     lag = calculate_lag(chain1_data, chain2_data)
#     if lag is not None:
#         print("\n" + "=" * 60)
#         print(f"ORACLE LAG: {lag} seconds ({lag/60:.2f} minutes)")
#         print("=" * 60)
        
#         # Determine which is ahead
#         if chain1_data["updated_at"] > chain2_data["updated_at"]:
#             print(f"{CONFIG['chain_1']['name']} is ahead by {lag} seconds")
#         else:
#             print(f"{CONFIG['chain_2']['name']} is ahead by {lag} seconds")


# if __name__ == "__main__":
#     main()


#!/usr/bin/env python3
"""
Oracle Lag Calculator - Compare oracle update timestamps between two chains
Calculates the time difference between oracle updates on different blockchains
"""

from web3 import Web3
from datetime import datetime
import json
import argparse
import sys

# Predefined popular chains with RPC endpoints
KNOWN_CHAINS = {
    "ethereum": {
        "name": "Ethereum",
        "rpc": "https://eth.llamarpc.com",
        "chain_id": 1
    },
    "polygon": {
        "name": "Polygon",
        "rpc": "https://polygon-rpc.com",
        "chain_id": 137
    },
    "arbitrum": {
        "name": "Arbitrum",
        "rpc": "https://arb1.arbitrum.io/rpc",
        "chain_id": 42161
    },
    "optimism": {
        "name": "Optimism",
        "rpc": "https://mainnet.optimism.io",
        "chain_id": 10
    },
    "avalanche": {
        "name": "Avalanche",
        "rpc": "https://api.avax.network/ext/bc/C/rpc",
        "chain_id": 43114
    },
    "bsc": {
        "name": "BSC",
        "rpc": "https://bsc-dataseed.binance.org",
        "chain_id": 56
    },
    "base": {
        "name": "Base",
        "rpc": "https://mainnet.base.org",
        "chain_id": 8453
    },
    "gnosis": {
        "name": "Gnosis",
        "rpc": "https://rpc.gnosischain.com",
        "chain_id": 100
    }
}

# Chainlink AggregatorV3 ABI (minimal)
ORACLE_ABI = json.loads('''[
    {
        "inputs": [],
        "name": "latestRoundData",
        "outputs": [
            {"name": "roundId", "type": "uint80"},
            {"name": "answer", "type": "int256"},
            {"name": "startedAt", "type": "uint256"},
            {"name": "updatedAt", "type": "uint256"},
            {"name": "answeredInRound", "type": "uint80"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]''')


def list_available_chains():
    """Display all available predefined chains"""
    print("\nAvailable chains:")
    print("-" * 60)
    for key, chain in KNOWN_CHAINS.items():
        print(f"  {key:15} - {chain['name']} (Chain ID: {chain['chain_id']})")
    print("-" * 60)


def get_chain_config(chain_input, custom_rpc=None):
    """Get chain configuration from user input"""
    chain_lower = chain_input.lower()
    
    if chain_lower in KNOWN_CHAINS:
        config = KNOWN_CHAINS[chain_lower].copy()
        if custom_rpc:
            config["rpc"] = custom_rpc
        return config
    else:
        # Custom chain - requires RPC
        if not custom_rpc:
            print(f"\nError: Unknown chain '{chain_input}'. Please provide a custom RPC endpoint.")
            print("Use --chain1-rpc or --chain2-rpc flag, or choose from known chains:")
            list_available_chains()
            return None
        
        return {
            "name": chain_input,
            "rpc": custom_rpc,
            "chain_id": None
        }


def interactive_mode():
    """Interactive mode for user input"""
    print("\n" + "=" * 60)
    print("ORACLE LAG CALCULATOR - Interactive Mode")
    print("=" * 60)
    
    list_available_chains()
    
    # Chain 1
    print("\n--- Chain 1 Configuration ---")
    chain1_name = input("Enter chain 1 name (or choose from above): ").strip()
    chain1_oracle = input("Enter oracle address for chain 1: ").strip()
    chain1_rpc = input("Custom RPC for chain 1 (press Enter to use default): ").strip() or None
    
    # Chain 2
    print("\n--- Chain 2 Configuration ---")
    chain2_name = input("Enter chain 2 name (or choose from above): ").strip()
    chain2_oracle = input("Enter oracle address for chain 2: ").strip()
    chain2_rpc = input("Custom RPC for chain 2 (press Enter to use default): ").strip() or None
    
    return {
        "chain1": {
            "name": chain1_name,
            "oracle": chain1_oracle,
            "rpc": chain1_rpc
        },
        "chain2": {
            "name": chain2_name,
            "oracle": chain2_oracle,
            "rpc": chain2_rpc
        }
    }


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Calculate oracle lag between two blockchain networks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python oracle_lag_calculator.py
  
  # Command line mode
  python oracle_lag_calculator.py \\
    --chain1 ethereum \\
    --oracle1 0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419 \\
    --chain2 polygon \\
    --oracle2 0xAB594600376Ec9fD91F8e885dADF0CE036862dE0
  
  # With custom RPC
  python oracle_lag_calculator.py \\
    --chain1 ethereum \\
    --oracle1 0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419 \\
    --chain1-rpc https://custom-rpc.com \\
    --chain2 polygon \\
    --oracle2 0xAB594600376Ec9fD91F8e885dADF0CE036862dE0
        """
    )
    
    parser.add_argument("--list-chains", action="store_true",
                       help="List all available predefined chains")
    parser.add_argument("--chain1", type=str,
                       help="First chain name (e.g., ethereum, polygon)")
    parser.add_argument("--oracle1", type=str,
                       help="Oracle address on chain 1")
    parser.add_argument("--chain1-rpc", type=str,
                       help="Custom RPC endpoint for chain 1")
    parser.add_argument("--chain2", type=str,
                       help="Second chain name")
    parser.add_argument("--oracle2", type=str,
                       help="Oracle address on chain 2")
    parser.add_argument("--chain2-rpc", type=str,
                       help="Custom RPC endpoint for chain 2")
    
    return parser.parse_args()



def get_oracle_data(rpc_url, oracle_address):
    """Fetch latest oracle data from a chain"""
    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            raise ConnectionError(f"Failed to connect to {rpc_url}")
        
        contract = w3.eth.contract(address=oracle_address, abi=ORACLE_ABI)
        round_data = contract.functions.latestRoundData().call()
        
        return {
            "round_id": round_data[0],
            "price": round_data[1],
            "updated_at": round_data[3],
            "timestamp": datetime.fromtimestamp(round_data[3])
        }
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None


def calculate_lag(chain1_data, chain2_data):
    """Calculate time lag between two oracle updates"""
    if not chain1_data or not chain2_data:
        return None
    
    lag_seconds = abs(chain1_data["updated_at"] - chain2_data["updated_at"])
    return lag_seconds


def main():
    args = parse_arguments()
    
    # Handle --list-chains flag
    if args.list_chains:
        list_available_chains()
        return
    
    # Determine mode: command line or interactive
    if args.chain1 and args.oracle1 and args.chain2 and args.oracle2:
        # Command line mode
        chain1_config = get_chain_config(args.chain1, args.chain1_rpc)
        chain2_config = get_chain_config(args.chain2, args.chain2_rpc)
        
        if not chain1_config or not chain2_config:
            sys.exit(1)
        
        chain1_oracle = args.oracle1
        chain2_oracle = args.oracle2
        
    else:
        # Interactive mode
        if args.chain1 or args.oracle1 or args.chain2 or args.oracle2:
            print("\nError: Please provide all required arguments or none for interactive mode.")
            print("Required: --chain1, --oracle1, --chain2, --oracle2")
            print("\nRun with --help for usage information")
            sys.exit(1)
        
        user_input = interactive_mode()
        
        chain1_config = get_chain_config(user_input["chain1"]["name"], user_input["chain1"]["rpc"])
        chain2_config = get_chain_config(user_input["chain2"]["name"], user_input["chain2"]["rpc"])
        
        if not chain1_config or not chain2_config:
            sys.exit(1)
        
        chain1_oracle = user_input["chain1"]["oracle"]
        chain2_oracle = user_input["chain2"]["oracle"]
    
    # Display configuration
    print("\n" + "=" * 60)
    print("ORACLE LAG CALCULATOR")
    print("=" * 60)
    print(f"\nChain 1: {chain1_config['name']}")
    print(f"  RPC: {chain1_config['rpc']}")
    print(f"  Oracle: {chain1_oracle}")
    print(f"\nChain 2: {chain2_config['name']}")
    print(f"  RPC: {chain2_config['rpc']}")
    print(f"  Oracle: {chain2_oracle}")
    
    # Fetch data from both chains
    print(f"\n{'─' * 60}")
    print(f"Fetching data from {chain1_config['name']}...")
    chain1_data = get_oracle_data(chain1_config["rpc"], chain1_oracle)
    
    print(f"Fetching data from {chain2_config['name']}...")
    chain2_data = get_oracle_data(chain2_config["rpc"], chain2_oracle)
    
    # Display results
    if chain1_data:
        print(f"\n{chain1_config['name']} Oracle:")
        print(f"  Round ID: {chain1_data['round_id']}")
        print(f"  Last Update: {chain1_data['timestamp']}")
        print(f"  Unix Timestamp: {chain1_data['updated_at']}")
        print(f"  Price: {chain1_data['price'] / 10**8:.8f}")
    else:
        print(f"\n⚠️  Failed to fetch data from {chain1_config['name']}")
    
    if chain2_data:
        print(f"\n{chain2_config['name']} Oracle:")
        print(f"  Round ID: {chain2_data['round_id']}")
        print(f"  Last Update: {chain2_data['timestamp']}")
        print(f"  Unix Timestamp: {chain2_data['updated_at']}")
        print(f"  Price: {chain2_data['price'] / 10**8:.8f}")
    else:
        print(f"\n⚠️  Failed to fetch data from {chain2_config['name']}")
    
    # Calculate lag
    lag = calculate_lag(chain1_data, chain2_data)
    if lag is not None:
        print("\n" + "=" * 60)
        print(f"ORACLE LAG: {lag} seconds ({lag/60:.2f} minutes)")
        print("=" * 60)
        
        # Determine which is ahead
        if chain1_data["updated_at"] > chain2_data["updated_at"]:
            print(f"✓ {chain1_config['name']} is ahead by {lag} seconds")
        elif chain1_data["updated_at"] < chain2_data["updated_at"]:
            print(f"✓ {chain2_config['name']} is ahead by {lag} seconds")
        else:
            print("✓ Both oracles are synchronized!")
        
        print("=" * 60)
    else:
        print("\n⚠️  Unable to calculate lag due to missing data")
        sys.exit(1)


if __name__ == "__main__":
    main()