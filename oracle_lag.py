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

# Chainlink AggregatorV3 ABI (minimal) + fallback for adapters
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
    },
    {
        "inputs": [],
        "name": "latestAnswer",
        "outputs": [{"name": "", "type": "int256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "lastPrice",
        "outputs": [
            {"name": "price", "type": "uint256"},
            {"name": "timestamp", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
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
    """Fetch latest oracle data from a chain.

    Tries methods in order:
    1. latestRoundData() - standard Chainlink AggregatorV3
    2. lastPrice() - RLP Fundamental Oracle (returns price, timestamp)
    3. latestAnswer() - adapters without timestamp (uses current time as proxy)
    """
    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            raise ConnectionError(f"Failed to connect to {rpc_url}")

        contract = w3.eth.contract(address=oracle_address, abi=ORACLE_ABI)

        # Try latestRoundData first (standard Chainlink feeds)
        try:
            round_data = contract.functions.latestRoundData().call()
            return {
                "round_id": round_data[0],
                "price": round_data[1],
                "updated_at": round_data[3],
                "timestamp": datetime.fromtimestamp(round_data[3])
            }
        except Exception:
            pass

        # Fallback to lastPrice() for RLP Fundamental Oracle
        try:
            last_price_data = contract.functions.lastPrice().call()
            price = last_price_data[0]
            timestamp = last_price_data[1]
            return {
                "round_id": 0,  # Not available for this oracle type
                "price": price,
                "updated_at": timestamp,
                "timestamp": datetime.fromtimestamp(timestamp),
                "oracle_type": "lastPrice"
            }
        except Exception:
            pass

        # Final fallback to latestAnswer() for adapters (no timestamp available)
        try:
            import time
            answer = contract.functions.latestAnswer().call()
            current_time = int(time.time())
            return {
                "round_id": 0,  # Not available for adapters
                "price": answer,
                "updated_at": current_time,  # Use current time as proxy
                "timestamp": datetime.fromtimestamp(current_time),
                "is_adapter": True  # Flag that this is an adapter without timestamp
            }
        except Exception as e:
            print(f"All oracle methods failed: {e}")
            return None

    except Exception as e:
        print(f"Error fetching data: {e}")
        return None


def calculate_oracle_freshness(updated_at_timestamp: int) -> dict:
    """
    Calculate how fresh an oracle is based on last update time.

    Formula: Freshness (hours) = (Current Time - Last Oracle Update Time) / 3600

    Args:
        updated_at_timestamp: Unix timestamp of last oracle update

    Returns:
        dict with freshness metrics
    """
    import time
    current_time = time.time()
    seconds_since_update = current_time - updated_at_timestamp

    return {
        "seconds_since_update": seconds_since_update,
        "minutes_since_update": seconds_since_update / 60,
        "hours_since_update": seconds_since_update / 3600,
        "last_update_timestamp": updated_at_timestamp,
        "last_update_datetime": datetime.fromtimestamp(updated_at_timestamp).isoformat()
    }


def get_oracle_freshness(
    oracle_addresses: list,
    chain_name: str = "ethereum",
    custom_rpc: str = None
) -> dict:
    """
    Get oracle freshness for one or more Chainlink price feeds on a chain.

    Args:
        oracle_addresses: List of Chainlink price feed addresses
        chain_name: Chain name (ethereum, base, arbitrum, etc.)
        custom_rpc: Optional custom RPC URL

    Returns:
        dict with freshness data for each oracle and aggregate metrics
    """
    import time

    result = {
        "protocol": "Oracle Freshness",
        "chain": chain_name,
        "status": "error",
        "oracles": [],
        "aggregate": {}
    }

    chain_config = get_chain_config(chain_name, custom_rpc)
    if not chain_config:
        result["error"] = f"Unknown chain: {chain_name}"
        return result

    print(f"\n{'='*60}")
    print(f"ORACLE FRESHNESS CHECK - {chain_config['name']}")
    print(f"{'='*60}")

    freshness_values = []

    for oracle_address in oracle_addresses:
        print(f"\nChecking oracle: {oracle_address[:10]}...{oracle_address[-8:]}")

        oracle_data = get_oracle_data(chain_config["rpc"], oracle_address)

        if oracle_data:
            freshness = calculate_oracle_freshness(oracle_data["updated_at"])

            oracle_result = {
                "address": oracle_address,
                "price": oracle_data["price"] / 10**8,
                "round_id": oracle_data["round_id"],
                **freshness
            }
            result["oracles"].append(oracle_result)
            freshness_values.append(freshness["minutes_since_update"])

            print(f"  Price: {oracle_data['price'] / 10**8:.8f}")
            print(f"  Last Update: {freshness['last_update_datetime']}")
            print(f"  Freshness: {freshness['minutes_since_update']:.2f} minutes ({freshness['hours_since_update']:.2f} hours)")
        else:
            result["oracles"].append({
                "address": oracle_address,
                "error": "Failed to fetch data"
            })
            print(f"  ⚠️  Failed to fetch data")

    # Calculate aggregate metrics
    if freshness_values:
        result["aggregate"] = {
            "min_freshness_minutes": min(freshness_values),
            "max_freshness_minutes": max(freshness_values),
            "avg_freshness_minutes": sum(freshness_values) / len(freshness_values),
            "oracles_checked": len(freshness_values)
        }

        print(f"\n{'─'*60}")
        print(f"AGGREGATE METRICS")
        print(f"  Freshest Oracle: {result['aggregate']['min_freshness_minutes']:.2f} minutes")
        print(f"  Stalest Oracle: {result['aggregate']['max_freshness_minutes']:.2f} minutes")
        print(f"  Average Freshness: {result['aggregate']['avg_freshness_minutes']:.2f} minutes")

        result["status"] = "success"
    else:
        result["error"] = "No oracle data retrieved"

    print(f"{'='*60}\n")
    return result


def get_cross_chain_oracle_freshness(
    chain_oracles: list
) -> dict:
    """
    Get oracle freshness across multiple chains and calculate cross-chain lag.

    Args:
        chain_oracles: List of dicts with keys: chain, oracle_address, rpc (optional)

    Returns:
        dict with per-chain freshness and cross-chain lag
    """
    result = {
        "protocol": "Cross-Chain Oracle Freshness",
        "status": "error",
        "chains": [],
        "cross_chain_lag": {}
    }

    print(f"\n{'='*60}")
    print(f"CROSS-CHAIN ORACLE FRESHNESS")
    print(f"{'='*60}")

    all_update_times = []

    for chain_oracle in chain_oracles:
        chain_name = chain_oracle.get("chain", "unknown")
        oracle_address = chain_oracle.get("oracle_address")
        custom_rpc = chain_oracle.get("rpc")

        chain_config = get_chain_config(chain_name, custom_rpc)
        if not chain_config:
            result["chains"].append({
                "chain": chain_name,
                "error": f"Unknown chain: {chain_name}"
            })
            continue

        print(f"\n{chain_config['name']}:")
        oracle_data = get_oracle_data(chain_config["rpc"], oracle_address)

        if oracle_data:
            freshness = calculate_oracle_freshness(oracle_data["updated_at"])

            chain_result = {
                "chain": chain_config["name"],
                "oracle_address": oracle_address,
                "price": oracle_data["price"] / 10**8,
                **freshness
            }
            result["chains"].append(chain_result)
            all_update_times.append({
                "chain": chain_config["name"],
                "updated_at": oracle_data["updated_at"]
            })

            print(f"  Oracle: {oracle_address[:10]}...{oracle_address[-8:]}")
            print(f"  Price: {oracle_data['price'] / 10**8:.8f}")
            print(f"  Freshness: {freshness['minutes_since_update']:.2f} minutes")
        else:
            result["chains"].append({
                "chain": chain_config["name"],
                "oracle_address": oracle_address,
                "error": "Failed to fetch data"
            })
            print(f"  ⚠️  Failed to fetch data")

    # Calculate cross-chain lag
    if len(all_update_times) >= 2:
        sorted_times = sorted(all_update_times, key=lambda x: x["updated_at"], reverse=True)
        newest = sorted_times[0]
        oldest = sorted_times[-1]

        lag_seconds = newest["updated_at"] - oldest["updated_at"]

        result["cross_chain_lag"] = {
            "lag_seconds": lag_seconds,
            "lag_minutes": lag_seconds / 60,
            "newest_chain": newest["chain"],
            "oldest_chain": oldest["chain"]
        }

        print(f"\n{'─'*60}")
        print(f"CROSS-CHAIN LAG")
        print(f"  Lag: {lag_seconds} seconds ({lag_seconds/60:.2f} minutes)")
        print(f"  Newest: {newest['chain']}")
        print(f"  Oldest: {oldest['chain']}")

        result["status"] = "success"
    elif len(all_update_times) == 1:
        result["cross_chain_lag"] = {"error": "Only one chain available, cannot calculate lag"}
        result["status"] = "partial"
    else:
        result["error"] = "No oracle data retrieved from any chain"

    print(f"{'='*60}\n")
    return result


def calculate_lag(chain1_data, chain2_data):
    """Calculate time lag between two oracle updates"""
    if not chain1_data or not chain2_data:
        return None

    lag_seconds = abs(chain1_data["updated_at"] - chain2_data["updated_at"])
    return lag_seconds


def analyze_oracle_lag(
    chain1_name: str,
    oracle1_address: str,
    chain2_name: str,
    oracle2_address: str,
    chain1_rpc: str = None,
    chain2_rpc: str = None
) -> dict:
    """
    Compare oracle update timestamps between two chains.
    Returns dict with lag analysis.
    """
    result = {
        "protocol": "Oracle Lag Calculator",
        "status": "error",
        "error": None,
        "chain1": {"name": chain1_name, "oracle": oracle1_address},
        "chain2": {"name": chain2_name, "oracle": oracle2_address}
    }

    # Get chain configs
    chain1_config = get_chain_config(chain1_name, chain1_rpc)
    chain2_config = get_chain_config(chain2_name, chain2_rpc)

    if not chain1_config or not chain2_config:
        result["error"] = "Invalid chain configuration"
        return result

    result["chain1"]["rpc"] = chain1_config["rpc"]
    result["chain2"]["rpc"] = chain2_config["rpc"]

    print(f"\n{'='*60}")
    print("ORACLE LAG CALCULATOR")
    print(f"{'='*60}")
    print(f"\nChain 1: {chain1_config['name']}")
    print(f"  Oracle: {oracle1_address}")
    print(f"\nChain 2: {chain2_config['name']}")
    print(f"  Oracle: {oracle2_address}")

    # Fetch data from both chains
    print(f"\n{'─'*60}")
    print(f"Fetching data from {chain1_config['name']}...")
    chain1_data = get_oracle_data(chain1_config["rpc"], oracle1_address)

    print(f"Fetching data from {chain2_config['name']}...")
    chain2_data = get_oracle_data(chain2_config["rpc"], oracle2_address)

    # Store oracle data in result
    if chain1_data:
        result["chain1"]["data"] = {
            "round_id": chain1_data["round_id"],
            "price": chain1_data["price"] / 10**8,
            "updated_at": chain1_data["updated_at"],
            "timestamp": str(chain1_data["timestamp"])
        }
        print(f"\n{chain1_config['name']} Oracle:")
        print(f"  Round ID: {chain1_data['round_id']}")
        print(f"  Last Update: {chain1_data['timestamp']}")
        print(f"  Price: {chain1_data['price'] / 10**8:.8f}")
    else:
        print(f"\n⚠️  Failed to fetch data from {chain1_config['name']}")
        result["chain1"]["data"] = None

    if chain2_data:
        result["chain2"]["data"] = {
            "round_id": chain2_data["round_id"],
            "price": chain2_data["price"] / 10**8,
            "updated_at": chain2_data["updated_at"],
            "timestamp": str(chain2_data["timestamp"])
        }
        print(f"\n{chain2_config['name']} Oracle:")
        print(f"  Round ID: {chain2_data['round_id']}")
        print(f"  Last Update: {chain2_data['timestamp']}")
        print(f"  Price: {chain2_data['price'] / 10**8:.8f}")
    else:
        print(f"\n⚠️  Failed to fetch data from {chain2_config['name']}")
        result["chain2"]["data"] = None

    # Calculate lag
    lag = calculate_lag(chain1_data, chain2_data)
    if lag is not None:
        result["lag_seconds"] = lag
        result["lag_minutes"] = lag / 60

        if chain1_data["updated_at"] > chain2_data["updated_at"]:
            result["ahead_chain"] = chain1_config["name"]
        elif chain1_data["updated_at"] < chain2_data["updated_at"]:
            result["ahead_chain"] = chain2_config["name"]
        else:
            result["ahead_chain"] = "synchronized"

        print("\n" + "=" * 60)
        print(f"ORACLE LAG: {lag} seconds ({lag/60:.2f} minutes)")
        print("=" * 60)

        if result["ahead_chain"] == "synchronized":
            print("✓ Both oracles are synchronized!")
        else:
            print(f"✓ {result['ahead_chain']} is ahead by {lag} seconds")
        print("=" * 60)

        result["status"] = "success"
    else:
        print("\n⚠️  Unable to calculate lag due to missing data")
        result["error"] = "Unable to calculate lag due to missing data"

    return result


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