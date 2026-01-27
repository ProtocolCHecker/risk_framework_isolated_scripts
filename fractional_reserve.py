"""
Fractional Reserve Verification Module.

Provides proof-of-reserve verification for PSM (Peg Stability Module) style
stablecoins like cUSD that use fractional reserve backing with lending.

Key features:
- Query vault for total supplies and borrows per backing asset
- Calculate backing ratio (reserves vs supply)
- Calculate utilization (borrowed vs deposited)
- Detect risk conditions (undercollateralization, high utilization, concentration)
- Query oracle for price/peg verification
"""

import time
from typing import Dict, Any, List, Tuple, Optional, TYPE_CHECKING

# Lazy import web3 to allow pure calculation functions to be used without web3 installed
if TYPE_CHECKING:
    from web3 import Web3


# =============================================================================
# ABI DEFINITIONS
# =============================================================================

# ERC20 totalSupply ABI
TOTAL_SUPPLY_ABI = [
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Vault totalSupplies(asset) and totalBorrows(asset) ABI
VAULT_ABI = [
    {
        "inputs": [{"name": "asset", "type": "address"}],
        "name": "totalSupplies",
        "outputs": [{"type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "asset", "type": "address"}],
        "name": "totalBorrows",
        "outputs": [{"type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Chainlink-compatible oracle ABI
ORACLE_ABI = [
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
        "name": "decimals",
        "outputs": [{"type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    }
]


# =============================================================================
# CALCULATION FUNCTIONS
# =============================================================================

def calculate_backing_ratio(total_reserves: float, total_supply: float) -> float:
    """
    Calculate the backing ratio as a percentage.

    Args:
        total_reserves: Total value of reserve assets (in USD or token units)
        total_supply: Total supply of the stablecoin

    Returns:
        Backing ratio as percentage (100.0 = fully backed)
    """
    if total_supply <= 0:
        return 100.0  # No tokens to back

    return (total_reserves / total_supply) * 100.0


def calculate_utilization(total_borrows: float, total_supplies: float) -> float:
    """
    Calculate utilization rate as a percentage.

    Args:
        total_borrows: Total amount borrowed
        total_supplies: Total amount deposited/supplied

    Returns:
        Utilization as percentage (0-100+)
    """
    if total_supplies <= 0:
        return 0.0

    return (total_borrows / total_supplies) * 100.0


def calculate_asset_allocations(assets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Calculate allocation percentage for each asset.

    Args:
        assets: List of assets with 'symbol' and 'total_supplies' fields

    Returns:
        List of assets with added 'allocation_pct' field
    """
    if not assets:
        return []

    total = sum(a.get("total_supplies", 0) for a in assets)

    if total <= 0:
        # Return assets with 0% allocation
        return [
            {**a, "allocation_pct": 0.0}
            for a in assets
        ]

    return [
        {**a, "allocation_pct": (a.get("total_supplies", 0) / total) * 100.0}
        for a in assets
    ]


def is_price_depegged(price: float, threshold_pct: float = 1.0) -> bool:
    """
    Check if price has deviated from $1 peg beyond threshold.

    Args:
        price: Current price in USD
        threshold_pct: Maximum allowed deviation percentage

    Returns:
        True if depegged (beyond threshold), False if within peg
    """
    deviation_pct = abs(price - 1.0) * 100.0
    return deviation_pct > threshold_pct


def is_oracle_stale(staleness_seconds: int, max_staleness_seconds: int) -> bool:
    """
    Check if oracle data is stale.

    Args:
        staleness_seconds: Seconds since last oracle update
        max_staleness_seconds: Maximum allowed staleness

    Returns:
        True if stale, False if fresh
    """
    return staleness_seconds > max_staleness_seconds


def calculate_risk_flags(data: Dict[str, Any], thresholds: Dict[str, Any]) -> List[str]:
    """
    Generate risk flags based on current state and thresholds.

    Args:
        data: Current reserve data including:
            - backing_ratio_pct
            - overall_utilization_pct
            - oracle_staleness_seconds
            - asset_allocations (list with allocation_pct)
        thresholds: Risk thresholds including:
            - min_backing_ratio_pct
            - max_utilization_pct
            - max_single_asset_pct
            - max_staleness_seconds

    Returns:
        List of risk flag strings
    """
    flags = []

    # Check undercollateralization
    backing_ratio = data.get("backing_ratio_pct", 100.0)
    min_backing = thresholds.get("min_backing_ratio_pct", 100)
    if backing_ratio < min_backing:
        flags.append("UNDERCOLLATERALIZED")

    # Check high utilization
    utilization = data.get("overall_utilization_pct", 0.0)
    max_utilization = thresholds.get("max_utilization_pct", 80)
    if utilization > max_utilization:
        flags.append("HIGH_UTILIZATION")

    # Check concentration risk
    max_single_asset = thresholds.get("max_single_asset_pct", 50)
    for asset in data.get("asset_allocations", []):
        if asset.get("allocation_pct", 0) > max_single_asset:
            flags.append("CONCENTRATION_RISK")
            break  # Only add once

    # Check oracle staleness
    staleness = data.get("oracle_staleness_seconds", 0)
    max_staleness = thresholds.get("max_staleness_seconds", 3600)
    if staleness > max_staleness:
        flags.append("ORACLE_STALE")

    return flags


# =============================================================================
# WEB3 QUERY FUNCTIONS
# =============================================================================

def query_total_supply(w3: "Web3", vault_address: str, decimals: int) -> float:
    """
    Query total supply of the stablecoin from vault/token contract.

    Args:
        w3: Web3 instance
        vault_address: Address of vault/token contract
        decimals: Token decimals

    Returns:
        Total supply as float
    """
    from web3 import Web3 as Web3Lib
    contract = w3.eth.contract(
        address=Web3Lib.to_checksum_address(vault_address),
        abi=TOTAL_SUPPLY_ABI
    )
    raw_supply = contract.functions.totalSupply().call()
    return raw_supply / (10 ** decimals)


def query_asset_supplies(
    w3: "Web3",
    vault_address: str,
    asset_address: str,
    decimals: int
) -> float:
    """
    Query total supplies for a specific asset in the vault.

    Args:
        w3: Web3 instance
        vault_address: Address of vault contract
        asset_address: Address of the backing asset
        decimals: Asset decimals

    Returns:
        Total supplies as float
    """
    from web3 import Web3 as Web3Lib
    contract = w3.eth.contract(
        address=Web3Lib.to_checksum_address(vault_address),
        abi=VAULT_ABI
    )
    raw_supplies = contract.functions.totalSupplies(
        Web3Lib.to_checksum_address(asset_address)
    ).call()
    return raw_supplies / (10 ** decimals)


def query_asset_borrows(
    w3: "Web3",
    vault_address: str,
    asset_address: str,
    decimals: int
) -> float:
    """
    Query total borrows for a specific asset in the vault.

    Args:
        w3: Web3 instance
        vault_address: Address of vault contract
        asset_address: Address of the backing asset
        decimals: Asset decimals

    Returns:
        Total borrows as float
    """
    from web3 import Web3 as Web3Lib
    contract = w3.eth.contract(
        address=Web3Lib.to_checksum_address(vault_address),
        abi=VAULT_ABI
    )
    raw_borrows = contract.functions.totalBorrows(
        Web3Lib.to_checksum_address(asset_address)
    ).call()
    return raw_borrows / (10 ** decimals)


def query_oracle_price(
    w3: "Web3",
    oracle_address: str,
    decimals: int
) -> Tuple[float, int]:
    """
    Query price and timestamp from Chainlink-compatible oracle.

    Args:
        w3: Web3 instance
        oracle_address: Address of oracle contract
        decimals: Oracle decimals

    Returns:
        Tuple of (price, timestamp)
    """
    from web3 import Web3 as Web3Lib
    contract = w3.eth.contract(
        address=Web3Lib.to_checksum_address(oracle_address),
        abi=ORACLE_ABI
    )
    round_data = contract.functions.latestRoundData().call()
    # round_data = (roundId, answer, startedAt, updatedAt, answeredInRound)
    price = round_data[1] / (10 ** decimals)
    timestamp = round_data[3]  # updatedAt
    return price, timestamp


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_config(config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate fractional reserve configuration.

    Args:
        config: Configuration dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ["vault_address", "chain", "backing_assets"]

    for field in required_fields:
        if field not in config:
            return False, f"Missing required field: {field}"

    if not config.get("vault_address"):
        return False, "vault_address cannot be empty"

    if not config.get("backing_assets"):
        return False, "backing_assets cannot be empty"

    # Validate each backing asset
    for asset in config.get("backing_assets", []):
        if not asset.get("address"):
            return False, f"backing_assets: missing address for {asset.get('symbol', 'unknown')}"
        if "decimals" not in asset:
            return False, f"backing_assets: missing decimals for {asset.get('symbol', 'unknown')}"

    return True, None


# =============================================================================
# MAIN FETCHER FUNCTION
# =============================================================================

def fetch_fractional_reserve_data(
    config: Dict[str, Any],
    rpc_urls: Dict[str, str]
) -> Dict[str, Any]:
    """
    Fetch comprehensive fractional reserve data.

    This is the main entry point for fractional reserve verification.
    It queries the vault contract for supplies/borrows, the oracle for price,
    and calculates all relevant metrics and risk flags.

    Args:
        config: Proof of reserve configuration containing:
            - vault_address: Address of the vault/token contract
            - chain: Chain name (e.g., "ethereum")
            - backing_assets: List of backing asset configs
            - price_oracle: Oracle configuration (optional)
            - risk_thresholds: Risk threshold configuration (optional)
        rpc_urls: Dictionary mapping chain names to RPC URLs

    Returns:
        Dictionary containing:
            - status: "success" or "error"
            - total_supply: Total stablecoin supply
            - backing_assets: List of asset data with supplies/borrows
            - total_reserves_usd: Total reserve value
            - total_borrows_usd: Total borrowed amount
            - available_liquidity_usd: Available for withdrawal
            - backing_ratio_pct: Reserves / Supply * 100
            - overall_utilization_pct: Borrows / Supplies * 100
            - oracle_price: Current oracle price
            - oracle_timestamp: Last oracle update timestamp
            - is_fully_backed: True if backing_ratio >= 100%
            - risk_flags: List of detected risks
            - error: Error message if status is "error"
    """
    result = {
        "status": "error",
        "total_supply": 0.0,
        "backing_assets": [],
        "total_reserves_usd": 0.0,
        "total_borrows_usd": 0.0,
        "available_liquidity_usd": 0.0,
        "backing_ratio_pct": 0.0,
        "overall_utilization_pct": 0.0,
        "oracle_price": None,
        "oracle_timestamp": None,
        "is_fully_backed": False,
        "risk_flags": [],
        "error": None
    }

    # Validate configuration
    is_valid, error = validate_config(config)
    if not is_valid:
        result["error"] = f"Invalid configuration: {error}"
        return result

    # Get chain and RPC URL
    chain = config.get("chain", "ethereum").lower()
    rpc_url = rpc_urls.get(chain)

    if not rpc_url:
        result["error"] = f"No RPC URL configured for chain: {chain}"
        return result

    # Connect to Web3
    try:
        from web3 import Web3 as Web3Lib
        w3 = Web3Lib(Web3Lib.HTTPProvider(rpc_url))
        if not w3.is_connected():
            result["error"] = f"Failed to connect to RPC: {rpc_url}"
            return result
    except Exception as e:
        result["error"] = f"Web3 connection error: {str(e)}"
        return result

    vault_address = config.get("vault_address")
    token_decimals = config.get("token_decimals", 18)

    # Query total supply
    try:
        result["total_supply"] = query_total_supply(w3, vault_address, token_decimals)
    except Exception as e:
        result["error"] = f"Failed to query total supply: {str(e)}"
        return result

    # Query each backing asset
    total_supplies = 0.0
    total_borrows = 0.0
    asset_results = []

    for asset_config in config.get("backing_assets", []):
        symbol = asset_config.get("symbol", "UNKNOWN")
        address = asset_config.get("address")
        decimals = asset_config.get("decimals", 18)

        try:
            supplies = query_asset_supplies(w3, vault_address, address, decimals)
            borrows = query_asset_borrows(w3, vault_address, address, decimals)

            utilization = calculate_utilization(borrows, supplies)

            asset_data = {
                "symbol": symbol,
                "address": address,
                "total_supplies": supplies,
                "total_borrows": borrows,
                "utilization_pct": round(utilization, 2)
            }

            asset_results.append(asset_data)
            total_supplies += supplies
            total_borrows += borrows

        except Exception as e:
            # Log error but continue with other assets
            print(f"Warning: Failed to query asset {symbol}: {str(e)}")
            asset_results.append({
                "symbol": symbol,
                "address": address,
                "total_supplies": 0.0,
                "total_borrows": 0.0,
                "utilization_pct": 0.0,
                "error": str(e)
            })

    # Calculate allocations
    asset_results = calculate_asset_allocations(asset_results)
    result["backing_assets"] = asset_results

    # Calculate totals
    result["total_reserves_usd"] = total_supplies
    result["total_borrows_usd"] = total_borrows
    result["available_liquidity_usd"] = total_supplies - total_borrows

    # Calculate backing ratio and utilization
    result["backing_ratio_pct"] = round(
        calculate_backing_ratio(total_supplies, result["total_supply"]),
        2
    )
    result["overall_utilization_pct"] = round(
        calculate_utilization(total_borrows, total_supplies),
        2
    )
    result["is_fully_backed"] = result["backing_ratio_pct"] >= 100.0

    # Query oracle price (optional)
    oracle_config = config.get("price_oracle", {})
    oracle_address = oracle_config.get("address")
    oracle_staleness_seconds = 0

    if oracle_address:
        try:
            oracle_decimals = oracle_config.get("decimals", 8)
            price, timestamp = query_oracle_price(w3, oracle_address, oracle_decimals)
            result["oracle_price"] = round(price, 6)
            result["oracle_timestamp"] = timestamp
            oracle_staleness_seconds = int(time.time()) - timestamp
        except Exception as e:
            print(f"Warning: Failed to query oracle: {str(e)}")
            result["oracle_price"] = None
            result["oracle_timestamp"] = None
            oracle_staleness_seconds = 999999  # Treat as very stale

    # Calculate risk flags
    risk_thresholds = config.get("risk_thresholds", {})
    default_thresholds = {
        "min_backing_ratio_pct": 100,
        "max_utilization_pct": 80,
        "max_single_asset_pct": 50,
        "max_staleness_seconds": oracle_config.get("max_staleness_seconds", 3600)
    }
    thresholds = {**default_thresholds, **risk_thresholds}

    risk_data = {
        "backing_ratio_pct": result["backing_ratio_pct"],
        "overall_utilization_pct": result["overall_utilization_pct"],
        "oracle_staleness_seconds": oracle_staleness_seconds,
        "asset_allocations": [
            {"symbol": a["symbol"], "allocation_pct": a.get("allocation_pct", 0)}
            for a in asset_results
        ]
    }

    result["risk_flags"] = calculate_risk_flags(risk_data, thresholds)

    # Mark as success
    result["status"] = "success"
    result["error"] = None

    return result
