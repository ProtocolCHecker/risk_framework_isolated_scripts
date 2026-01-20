from web3 import Web3
import json
import numpy as np
import requests

# =============================================================================
# ABIs
# =============================================================================

# Chainlink Price Feed ABI (for Chainlink PoR)
CHAINLINK_ABI = json.loads('[{"inputs":[],"name":"latestRoundData","outputs":[{"internalType":"uint80","name":"roundId","type":"uint80"},{"internalType":"int256","name":"answer","type":"int256"},{"internalType":"uint256","name":"startedAt","type":"uint256"},{"internalType":"uint256","name":"updatedAt","type":"uint256"},{"internalType":"uint80","name":"answeredInRound","type":"uint80"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"}]')

# Standard ERC20 Token ABI
TOKEN_ABI = json.loads('[{"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"}]')

# Lido stETH ABI (for liquid staking verification)
LIDO_ABI = json.loads('''[
    {"inputs":[],"name":"getTotalPooledEther","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"getTotalShares","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"getBeaconStat","outputs":[{"internalType":"uint256","name":"depositedValidators","type":"uint256"},{"internalType":"uint256","name":"beaconValidators","type":"uint256"},{"internalType":"uint256","name":"beaconBalance","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"getBufferedEther","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"_sharesAmount","type":"uint256"}],"name":"getPooledEthByShares","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}
]''')

# wstETH ABI (for wrapped staked ETH)
WSTETH_ABI = json.loads('''[
    {"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"stEthPerToken","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[],"name":"tokensPerStEth","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"uint256","name":"_wstETHAmount","type":"uint256"}],"name":"getStETHByWstETH","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}
]''')

# =============================================================================
# RPC Configuration
# =============================================================================

RPCS = {
    "ethereum": "https://eth.drpc.org",
    "base": "https://base.drpc.org",
    "arbitrum": "https://arbitrum.drpc.org",
    "optimism": "https://optimism.drpc.org",
    "polygon": "https://polygon.drpc.org"
}

HELIUS_KEY = "5167631c-772f-49bb-ab19-fe8553e4e6dc"

# =============================================================================
# Protocol-specific contract addresses
# =============================================================================

LIQUID_STAKING_CONTRACTS = {
    "lido": {
        "ethereum": {
            "steth": "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84",
            "wsteth": "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0"
        }
    }
    # Future: Add rocketpool, coinbase, etc.
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_web3(chain: str, rpc_urls: dict = None) -> Web3:
    """Get Web3 instance for a chain."""
    if rpc_urls and chain in rpc_urls:
        rpc_url = rpc_urls[chain]
    else:
        rpc_url = RPCS.get(chain)

    if not rpc_url:
        raise ValueError(f"No RPC URL for chain: {chain}")

    return Web3(Web3.HTTPProvider(rpc_url))


def get_reserves(w3, por_address):
    """Get reserves from Chainlink PoR feed."""
    contract = w3.eth.contract(address=por_address, abi=CHAINLINK_ABI)
    round_data = contract.functions.latestRoundData().call()
    decimals = contract.functions.decimals().call()
    reserves = round_data[1] / (10 ** decimals)
    return reserves


def get_evm_supply(w3, token_address):
    """Get ERC20 token total supply."""
    contract = w3.eth.contract(address=token_address, abi=TOKEN_ABI)
    supply = contract.functions.totalSupply().call()
    decimals = contract.functions.decimals().call()
    return supply / (10 ** decimals)


def get_solana_supply(token_address):
    """Get Solana token total supply."""
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
    """Calculate reserve ratio and score."""
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


# =============================================================================
# Chainlink Proof of Reserve (for wrapped assets like cbBTC)
# =============================================================================

def analyze_chainlink_por(
    evm_chains: list = None,
    solana_token: str = None,
    rpc_urls: dict = None,
    por_scope: str = "global"
) -> dict:
    """
    Analyze proof of reserves using Chainlink PoR feeds.

    Used for wrapped assets like cbBTC that have Chainlink PoR feeds.

    Args:
        evm_chains: List of dicts with keys: name, por (PoR address), token (token address)
        solana_token: Optional Solana token address
        rpc_urls: Optional custom RPC URLs
        por_scope: "global" = PoR covers all chains (compare median PoR vs total supply)
                   "per_chain" = PoR covers only its chain (compare PoR vs supply from chains with PoR only)

    Returns:
        dict with reserve analysis
    """
    result = {
        "verification_type": "chainlink_por",
        "protocol": "chainlink",
        "status": "error",
        "error": None,
        "chain_data": [],
        "reserves": {},
        "supply": {},
        "por_scope": por_scope
    }

    if not evm_chains:
        evm_chains = []

    reserve_values = []
    total_supply = 0
    supply_from_por_chains = 0  # Track supply only from chains that have PoR

    # Collect reserves from each PoR feed
    for chain in evm_chains:
        chain_result = {"name": chain["name"], "por_address": chain.get("por"), "token_address": chain.get("token")}
        has_por = bool(chain.get("por"))

        try:
            w3 = get_web3(chain["name"], rpc_urls)

            if has_por:
                reserves = get_reserves(w3, chain["por"])
                reserve_values.append(reserves)
                chain_result["reserves"] = reserves
                print(f"\n{chain['name'].upper()} Reserves: {reserves:.8f}")

            if chain.get("token"):
                supply = get_evm_supply(w3, chain["token"])
                total_supply += supply
                chain_result["supply"] = supply
                print(f"{chain['name'].upper()} Supply: {supply:.8f}")

                # Track supply from chains with PoR for per_chain scope
                if has_por:
                    supply_from_por_chains += supply

        except Exception as e:
            chain_result["error"] = str(e)
            print(f"Error on {chain['name']}: {e}")

        result["chain_data"].append(chain_result)

    # Add Solana supply (only for global scope, as Solana has no PoR feed)
    if solana_token:
        try:
            solana_supply = get_solana_supply(solana_token)
            total_supply += solana_supply
            result["supply"]["solana"] = solana_supply
            print(f"SOLANA Supply: {solana_supply:.8f}")
        except Exception as e:
            result["supply"]["solana_error"] = str(e)

    # Take median of reserves
    median_reserves = np.median(reserve_values) if reserve_values else 0
    result["reserves"]["median"] = median_reserves
    result["reserves"]["all_values"] = reserve_values
    print(f"\nMedian Reserves: {median_reserves:.8f}")

    # Determine effective supply based on por_scope
    if por_scope == "per_chain":
        effective_supply = supply_from_por_chains
        print(f"PoR Scope: per_chain - using supply from chains with PoR only: {effective_supply:.8f}")
    else:
        effective_supply = total_supply
        print(f"PoR Scope: global - using total supply from all chains: {effective_supply:.8f}")

    result["supply"]["effective"] = effective_supply
    result["supply"]["total"] = total_supply
    result["supply"]["from_por_chains"] = supply_from_por_chains

    # Calculate metrics
    print("\n" + "="*50)
    metrics = calculate_reserve_ratio(median_reserves, effective_supply)
    result["metrics"] = metrics

    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"{key}: {value:.8f}")
        else:
            print(f"{key}: {value}")

    result["status"] = "success"
    return result


# =============================================================================
# Liquid Staking Verification (for LSTs like wstETH, rETH)
# =============================================================================

def analyze_lido_reserve(
    chain: str = "ethereum",
    rpc_urls: dict = None,
    contracts: dict = None
) -> dict:
    """
    Analyze Lido stETH/wstETH collateralization.

    stETH is always 1:1 backed by design (totalSupply == getTotalPooledEther).
    This function verifies this and provides component breakdown.

    Args:
        chain: Chain to query (default: ethereum)
        rpc_urls: Optional custom RPC URLs
        contracts: Optional contract addresses override

    Returns:
        dict with reserve analysis and component breakdown
    """
    result = {
        "verification_type": "liquid_staking",
        "protocol": "lido",
        "status": "error",
        "error": None,
        "chain_data": [],
        "components": {}
    }

    try:
        w3 = get_web3(chain, rpc_urls)

        # Get contract addresses
        if contracts:
            steth_address = contracts.get("steth") or contracts.get("staking_contract")
            wsteth_address = contracts.get("wsteth") or contracts.get("wrapped_token")
        else:
            lido_contracts = LIQUID_STAKING_CONTRACTS.get("lido", {}).get(chain, {})
            steth_address = lido_contracts.get("steth")
            wsteth_address = lido_contracts.get("wsteth")

        if not steth_address:
            raise ValueError(f"No Lido stETH contract found for chain: {chain}")

        # Initialize contracts
        steth_contract = w3.eth.contract(
            address=Web3.to_checksum_address(steth_address),
            abi=LIDO_ABI
        )

        print(f"\n{'='*60}")
        print(f"LIDO RESERVE VERIFICATION - {chain.upper()}")
        print(f"{'='*60}")

        # Query stETH contract
        total_pooled_ether = steth_contract.functions.getTotalPooledEther().call()
        total_supply = steth_contract.functions.totalSupply().call()
        total_shares = steth_contract.functions.getTotalShares().call()
        buffered_ether = steth_contract.functions.getBufferedEther().call()

        # Get beacon chain stats
        beacon_stat = steth_contract.functions.getBeaconStat().call()
        deposited_validators = beacon_stat[0]
        beacon_validators = beacon_stat[1]
        beacon_balance = beacon_stat[2]

        # Convert to ETH (from wei)
        total_pooled_eth = total_pooled_ether / 1e18
        total_supply_eth = total_supply / 1e18
        buffered_eth = buffered_ether / 1e18
        beacon_balance_eth = beacon_balance / 1e18

        # Calculate transient balance (validators deposited but not yet active)
        transient_validators = deposited_validators - beacon_validators
        transient_balance_eth = transient_validators * 32  # Each validator = 32 ETH

        # Print component breakdown
        print(f"\nstETH Total Supply: {total_supply_eth:,.4f} ETH")
        print(f"Total Pooled Ether: {total_pooled_eth:,.4f} ETH")
        print(f"\nComponent Breakdown:")
        print(f"  Beacon Balance: {beacon_balance_eth:,.4f} ETH ({beacon_validators} validators)")
        print(f"  Buffered Ether: {buffered_eth:,.4f} ETH")
        print(f"  Transient Balance: {transient_balance_eth:,.4f} ETH ({transient_validators} validators in transit)")

        # Backing ratio (should be 1.0 by design)
        backing_ratio = total_pooled_eth / total_supply_eth if total_supply_eth > 0 else 0
        print(f"\nBacking Ratio: {backing_ratio:.6f} ({backing_ratio * 100:.4f}%)")

        # Store components
        result["components"] = {
            "total_pooled_ether": total_pooled_eth,
            "total_supply": total_supply_eth,
            "total_shares": total_shares / 1e18,
            "beacon_balance": beacon_balance_eth,
            "buffered_ether": buffered_eth,
            "transient_balance": transient_balance_eth,
            "deposited_validators": deposited_validators,
            "beacon_validators": beacon_validators,
            "transient_validators": transient_validators
        }

        # Query wstETH if available
        wsteth_data = {}
        if wsteth_address:
            try:
                wsteth_contract = w3.eth.contract(
                    address=Web3.to_checksum_address(wsteth_address),
                    abi=WSTETH_ABI
                )

                wsteth_supply = wsteth_contract.functions.totalSupply().call()
                steth_per_token = wsteth_contract.functions.stEthPerToken().call()

                wsteth_supply_tokens = wsteth_supply / 1e18
                steth_per_wsteth = steth_per_token / 1e18
                wsteth_backing_in_steth = wsteth_supply_tokens * steth_per_wsteth

                print(f"\nwstETH Data:")
                print(f"  wstETH Total Supply: {wsteth_supply_tokens:,.4f} wstETH")
                print(f"  stETH per wstETH: {steth_per_wsteth:.6f}")
                print(f"  wstETH backing in stETH: {wsteth_backing_in_steth:,.4f} stETH")

                wsteth_data = {
                    "wsteth_supply": wsteth_supply_tokens,
                    "steth_per_wsteth": steth_per_wsteth,
                    "wsteth_backing_in_steth": wsteth_backing_in_steth
                }
                result["components"]["wsteth"] = wsteth_data

            except Exception as e:
                print(f"  wstETH query failed: {e}")

        # Chain data for compatibility
        result["chain_data"].append({
            "name": chain,
            "supply": total_supply_eth,
            "reserves": total_pooled_eth
        })

        # Calculate metrics (same format as Chainlink PoR)
        result["metrics"] = calculate_reserve_ratio(total_pooled_eth, total_supply_eth)

        print(f"\n{'='*60}")
        print(f"VERIFICATION COMPLETE")
        print(f"  Status: {'FULLY BACKED' if backing_ratio >= 1.0 else 'UNDERCOLLATERALIZED'}")
        print(f"  Score: {result['metrics']['score']:.1f}/100")
        print(f"{'='*60}\n")

        result["status"] = "success"

    except Exception as e:
        result["error"] = str(e)
        print(f"Error analyzing Lido reserve: {e}")

    return result


def analyze_liquid_staking_reserve(
    protocol: str,
    chain: str = "ethereum",
    rpc_urls: dict = None,
    contracts: dict = None
) -> dict:
    """
    Route to appropriate liquid staking protocol handler.

    Args:
        protocol: Protocol name (lido, rocketpool, coinbase, etc.)
        chain: Chain to query
        rpc_urls: Optional custom RPC URLs
        contracts: Optional contract addresses

    Returns:
        dict with reserve analysis
    """
    protocol = protocol.lower()

    if protocol == "lido":
        return analyze_lido_reserve(chain, rpc_urls, contracts)
    else:
        # Future: Add rocketpool, coinbase, etc.
        return {
            "verification_type": "liquid_staking",
            "protocol": protocol,
            "status": "error",
            "error": f"Unsupported liquid staking protocol: {protocol}",
            "metrics": calculate_reserve_ratio(0, 0)
        }


# =============================================================================
# Main Dispatcher Function
# =============================================================================

def analyze_proof_of_reserve(
    # Legacy parameters (for backward compatibility)
    evm_chains: list = None,
    solana_token: str = None,
    # New config-based approach
    config: dict = None
) -> dict:
    """
    Analyze proof of reserves - agnostic dispatcher.

    Supports multiple verification types:
    - chainlink_por: For wrapped assets with Chainlink PoR feeds (cbBTC, WBTC)
    - liquid_staking: For LSTs (wstETH, rETH, cbETH)

    Args:
        evm_chains: Legacy - list of chain configs for Chainlink PoR
        solana_token: Legacy - Solana token address
        config: Full proof_of_reserve config from JSON

    Returns:
        dict with reserve analysis (unified format)
    """
    # If config provided, use new approach
    if config:
        verification_type = config.get("verification_type", "chainlink_por")
        rpc_urls = config.get("rpc_urls")

        if verification_type == "liquid_staking":
            protocol = config.get("protocol", "lido")
            chain = config.get("chain", "ethereum")
            contracts = config.get("contracts", {})

            return analyze_liquid_staking_reserve(
                protocol=protocol,
                chain=chain,
                rpc_urls=rpc_urls,
                contracts=contracts
            )

        elif verification_type == "chainlink_por":
            return analyze_chainlink_por(
                evm_chains=config.get("evm_chains", []),
                solana_token=config.get("solana_token"),
                rpc_urls=rpc_urls,
                por_scope=config.get("por_scope", "global")
            )

        else:
            return {
                "verification_type": verification_type,
                "status": "error",
                "error": f"Unknown verification type: {verification_type}",
                "metrics": calculate_reserve_ratio(0, 0)
            }

    # Legacy mode: assume Chainlink PoR
    return analyze_chainlink_por(
        evm_chains=evm_chains,
        solana_token=solana_token
    )


# =============================================================================
# CLI for testing
# =============================================================================

if __name__ == "__main__":
    print("Proof of Reserve Analyzer")
    print("=" * 50)

    mode = input("Select mode:\n1. Chainlink PoR (wrapped assets)\n2. Liquid Staking (LSTs)\nChoice [1/2]: ").strip()

    if mode == "2":
        # Liquid staking mode
        protocol = input("Protocol (lido/rocketpool) [lido]: ").strip() or "lido"
        chain = input("Chain [ethereum]: ").strip() or "ethereum"

        result = analyze_liquid_staking_reserve(protocol=protocol, chain=chain)

        if result["status"] == "success":
            print("\n" + "="*50)
            print("RESULT SUMMARY")
            print("="*50)
            metrics = result.get("metrics", {})
            print(f"Reserve Ratio: {metrics.get('reserve_ratio', 0)*100:.4f}%")
            print(f"Is Fully Backed: {metrics.get('is_fully_backed', False)}")
            print(f"Score: {metrics.get('score', 0):.1f}/100")
    else:
        # Chainlink PoR mode
        evm_chains = []

        for chain_name in ["ethereum", "base", "arbitrum"]:
            print(f"\n{chain_name.upper()}:")
            por = input("  Chainlink PoR address (press Enter to skip): ").strip()
            token = input("  Token address (press Enter to skip): ").strip()

            if por or token:
                evm_chains.append({
                    "name": chain_name,
                    "por": por if por else None,
                    "token": token if token else None
                })

        print("\nSOLANA:")
        solana_token = input("  Token address (press Enter to skip): ").strip()

        result = analyze_chainlink_por(
            evm_chains=evm_chains,
            solana_token=solana_token if solana_token else None
        )
