"""
JSON Configuration Schema for Risk Framework.

This schema defines all inputs required for:
1. Quantitative data fetching (addresses, chains, API identifiers)
2. Qualitative risk assessment (audit data, governance, custody)
3. Scoring configuration (asset metadata, role weights)

Usage:
- User provides JSON file or fills form in Streamlit
- Data adapter validates against this schema
- Scripts are called with extracted parameters
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json


# =============================================================================
# SCHEMA DEFINITIONS
# =============================================================================

# Supported chains for quantitative scripts
SUPPORTED_CHAINS = ["ethereum", "base", "arbitrum", "polygon", "optimism", "avalanche", "bsc", "gnosis"]

# Supported custody models
CUSTODY_MODELS = ["decentralized", "regulated_insured", "regulated", "unregulated", "unknown"]

# Supported blacklist control types
BLACKLIST_CONTROLS = ["none", "governance", "multisig", "eoa"]

# Supported asset types
ASSET_TYPES = ["wrapped_btc", "wrapped_eth", "stablecoin", "lst", "lrt", "synthetic", "native", "other"]


@dataclass
class ChainAddress:
    """Address on a specific chain."""
    chain: str
    address: str


@dataclass
class AuditData:
    """Security audit information."""
    auditor: str
    date: str  # YYYY-MM format
    issues: Dict[str, int] = field(default_factory=lambda: {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0
    })


@dataclass
class Incident:
    """Security incident record."""
    description: str
    days_ago: int
    funds_lost: float = 0.0
    funds_lost_pct: float = 0.0


@dataclass
class MultisigConfig:
    """Multisig/admin role configuration."""
    role_name: str
    is_multisig: bool
    is_eoa: bool = False
    threshold: int = 1
    owners_count: int = 1


@dataclass
class LendingProtocolConfig:
    """Configuration for a lending protocol analysis."""
    protocol: str  # "aave" or "compound"
    chain: str
    token_address: str


@dataclass
class DexPoolConfig:
    """Configuration for a DEX pool analysis."""
    protocol: str  # "uniswap", "curve", "pancakeswap"
    chain: str
    pool_address: str


@dataclass
class ProofOfReserveConfig:
    """Configuration for Proof of Reserve analysis."""
    evm_chains: List[Dict[str, str]]  # [{"name": "ethereum", "por": "0x...", "token": "0x..."}]
    solana_token: Optional[str] = None


@dataclass
class PriceRiskConfig:
    """Configuration for price risk analysis (CoinGecko)."""
    token_coingecko_id: str
    underlying_coingecko_id: str


@dataclass
class OracleLagConfig:
    """Configuration for oracle lag calculation (PoR feeds)."""
    por_feed_1: ChainAddress
    por_feed_2: ChainAddress


@dataclass
class OracleFreshnessConfig:
    """Configuration for oracle freshness calculation (Price feeds)."""
    price_feeds: List[ChainAddress]


# =============================================================================
# MAIN CONFIGURATION SCHEMA
# =============================================================================

@dataclass
class AssetRiskConfig:
    """
    Complete configuration for asset risk analysis.

    This is the main schema that the Streamlit app will use.
    All fields map directly to script inputs or scoring requirements.
    """

    # =========================================================================
    # SECTION 1: Asset Metadata (Required)
    # =========================================================================
    asset_name: str
    asset_symbol: str
    asset_type: str = "other"  # One of ASSET_TYPES
    underlying: Optional[str] = None  # e.g., "BTC", "ETH", "USD"

    # =========================================================================
    # SECTION 2: Token Addresses (Required for quantitative analysis)
    # =========================================================================
    # Primary token address on each chain where it exists
    token_addresses: List[ChainAddress] = field(default_factory=list)

    # =========================================================================
    # SECTION 3: Lending Protocol Configurations
    # =========================================================================
    lending_configs: List[LendingProtocolConfig] = field(default_factory=list)

    # =========================================================================
    # SECTION 4: DEX Pool Configurations
    # =========================================================================
    dex_pools: List[DexPoolConfig] = field(default_factory=list)

    # =========================================================================
    # SECTION 5: Proof of Reserve Configuration
    # =========================================================================
    proof_of_reserve: Optional[ProofOfReserveConfig] = None

    # =========================================================================
    # SECTION 6: Price Risk Configuration (CoinGecko IDs)
    # =========================================================================
    price_risk: Optional[PriceRiskConfig] = None

    # =========================================================================
    # SECTION 7: Oracle Configuration
    # =========================================================================
    oracle_lag: Optional[OracleLagConfig] = None
    oracle_freshness: Optional[OracleFreshnessConfig] = None

    # =========================================================================
    # SECTION 8: Smart Contract Risk (Qualitative)
    # =========================================================================
    audit_data: Optional[AuditData] = None
    deployment_date: Optional[str] = None  # ISO format: YYYY-MM-DD
    incidents: List[Incident] = field(default_factory=list)

    # =========================================================================
    # SECTION 9: Counterparty Risk (Qualitative)
    # =========================================================================
    multisig_configs: List[MultisigConfig] = field(default_factory=list)
    has_timelock: bool = False
    timelock_hours: float = 0.0
    custody_model: str = "unknown"  # One of CUSTODY_MODELS
    has_blacklist: bool = False
    blacklist_control: str = "none"  # One of BLACKLIST_CONTROLS

    # Optional: Custom role weights for scoring
    critical_roles: List[str] = field(default_factory=lambda: ["owner", "admin"])
    role_weights: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssetRiskConfig":
        """Create from dictionary (e.g., loaded from JSON)."""
        # Handle nested dataclasses
        if "token_addresses" in data:
            data["token_addresses"] = [
                ChainAddress(**addr) if isinstance(addr, dict) else addr
                for addr in data["token_addresses"]
            ]

        if "lending_configs" in data:
            data["lending_configs"] = [
                LendingProtocolConfig(**cfg) if isinstance(cfg, dict) else cfg
                for cfg in data["lending_configs"]
            ]

        if "dex_pools" in data:
            data["dex_pools"] = [
                DexPoolConfig(**pool) if isinstance(pool, dict) else pool
                for pool in data["dex_pools"]
            ]

        if "proof_of_reserve" in data and data["proof_of_reserve"]:
            data["proof_of_reserve"] = ProofOfReserveConfig(**data["proof_of_reserve"])

        if "price_risk" in data and data["price_risk"]:
            data["price_risk"] = PriceRiskConfig(**data["price_risk"])

        if "oracle_lag" in data and data["oracle_lag"]:
            ol = data["oracle_lag"]
            data["oracle_lag"] = OracleLagConfig(
                por_feed_1=ChainAddress(**ol["por_feed_1"]) if isinstance(ol["por_feed_1"], dict) else ol["por_feed_1"],
                por_feed_2=ChainAddress(**ol["por_feed_2"]) if isinstance(ol["por_feed_2"], dict) else ol["por_feed_2"],
            )

        if "oracle_freshness" in data and data["oracle_freshness"]:
            of = data["oracle_freshness"]
            data["oracle_freshness"] = OracleFreshnessConfig(
                price_feeds=[ChainAddress(**pf) if isinstance(pf, dict) else pf for pf in of["price_feeds"]]
            )

        if "audit_data" in data and data["audit_data"]:
            data["audit_data"] = AuditData(**data["audit_data"])

        if "incidents" in data:
            data["incidents"] = [
                Incident(**inc) if isinstance(inc, dict) else inc
                for inc in data["incidents"]
            ]

        if "multisig_configs" in data:
            data["multisig_configs"] = [
                MultisigConfig(**cfg) if isinstance(cfg, dict) else cfg
                for cfg in data["multisig_configs"]
            ]

        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "AssetRiskConfig":
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_json_file(cls, file_path: str) -> "AssetRiskConfig":
        """Create from JSON file."""
        with open(file_path, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)


# =============================================================================
# VALIDATION
# =============================================================================

def validate_config(config: AssetRiskConfig) -> Dict[str, Any]:
    """
    Validate configuration and return validation results.

    Returns:
        Dict with:
        - is_valid: bool
        - errors: List of error messages
        - warnings: List of warning messages
        - completeness: Dict showing which sections are complete
    """
    errors = []
    warnings = []
    completeness = {}

    # Required fields
    if not config.asset_name:
        errors.append("asset_name is required")
    if not config.asset_symbol:
        errors.append("asset_symbol is required")

    # Asset type validation
    if config.asset_type not in ASSET_TYPES:
        errors.append(f"asset_type must be one of: {ASSET_TYPES}")

    # Token addresses
    completeness["token_addresses"] = len(config.token_addresses) > 0
    if not completeness["token_addresses"]:
        warnings.append("No token addresses provided - quantitative analysis will be limited")
    else:
        for addr in config.token_addresses:
            if addr.chain not in SUPPORTED_CHAINS:
                errors.append(f"Unsupported chain: {addr.chain}. Must be one of: {SUPPORTED_CHAINS}")

    # Lending configs
    completeness["lending_configs"] = len(config.lending_configs) > 0
    for cfg in config.lending_configs:
        if cfg.protocol not in ["aave", "compound"]:
            errors.append(f"Unsupported lending protocol: {cfg.protocol}. Must be 'aave' or 'compound'")

    # DEX pools
    completeness["dex_pools"] = len(config.dex_pools) > 0
    for pool in config.dex_pools:
        if pool.protocol not in ["uniswap", "curve", "pancakeswap"]:
            errors.append(f"Unsupported DEX protocol: {pool.protocol}")

    # Proof of Reserve
    completeness["proof_of_reserve"] = config.proof_of_reserve is not None

    # Price Risk
    completeness["price_risk"] = config.price_risk is not None
    if config.price_risk:
        if not config.price_risk.token_coingecko_id:
            errors.append("price_risk.token_coingecko_id is required when price_risk is provided")
        if not config.price_risk.underlying_coingecko_id:
            errors.append("price_risk.underlying_coingecko_id is required when price_risk is provided")

    # Oracle configs
    completeness["oracle_lag"] = config.oracle_lag is not None
    completeness["oracle_freshness"] = config.oracle_freshness is not None

    # Audit data
    completeness["audit_data"] = config.audit_data is not None
    if not completeness["audit_data"]:
        warnings.append("No audit_data provided - Smart Contract Risk score will be penalized")

    # Custody model validation
    if config.custody_model not in CUSTODY_MODELS:
        errors.append(f"custody_model must be one of: {CUSTODY_MODELS}")

    # Blacklist control validation
    if config.blacklist_control not in BLACKLIST_CONTROLS:
        errors.append(f"blacklist_control must be one of: {BLACKLIST_CONTROLS}")

    # Multisig configs
    completeness["multisig_configs"] = len(config.multisig_configs) > 0
    if not completeness["multisig_configs"]:
        warnings.append("No multisig_configs provided - Counterparty Risk assessment may be incomplete")

    # Deployment date
    completeness["deployment_date"] = config.deployment_date is not None
    if config.deployment_date:
        try:
            datetime.fromisoformat(config.deployment_date)
        except ValueError:
            errors.append("deployment_date must be in ISO format (YYYY-MM-DD)")

    # Calculate overall completeness
    total_sections = len(completeness)
    complete_sections = sum(1 for v in completeness.values() if v)
    completeness_pct = (complete_sections / total_sections) * 100 if total_sections > 0 else 0

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "completeness": completeness,
        "completeness_pct": round(completeness_pct, 1),
    }


# =============================================================================
# EXAMPLE CONFIGURATION
# =============================================================================

def get_example_config() -> AssetRiskConfig:
    """
    Get an example configuration for cbBTC.
    This serves as a template and documentation.
    """
    return AssetRiskConfig(
        # Asset Metadata
        asset_name="Coinbase Wrapped BTC",
        asset_symbol="cbBTC",
        asset_type="wrapped_btc",
        underlying="BTC",

        # Token Addresses
        token_addresses=[
            ChainAddress(chain="ethereum", address="0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf"),
            ChainAddress(chain="base", address="0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf"),
            ChainAddress(chain="arbitrum", address="0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf"),
        ],

        # Lending Protocols
        lending_configs=[
            LendingProtocolConfig(protocol="aave", chain="ethereum", token_address="0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf"),
            LendingProtocolConfig(protocol="aave", chain="base", token_address="0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf"),
            LendingProtocolConfig(protocol="compound", chain="ethereum", token_address="0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf"),
        ],

        # DEX Pools
        dex_pools=[
            DexPoolConfig(protocol="uniswap", chain="ethereum", pool_address="0xe8f7c89c5efa061e340f2d2f206ec78fd8f7e124"),
            DexPoolConfig(protocol="curve", chain="ethereum", pool_address="0x839d6bDeDFF886404A6d7a788ef241e4e28F4802"),
        ],

        # Proof of Reserve
        proof_of_reserve=ProofOfReserveConfig(
            evm_chains=[
                {"name": "ethereum", "por": "0x...", "token": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf"},
                {"name": "base", "por": "0x...", "token": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf"},
            ],
            solana_token=None
        ),

        # Price Risk (CoinGecko)
        price_risk=PriceRiskConfig(
            token_coingecko_id="coinbase-wrapped-btc",
            underlying_coingecko_id="bitcoin"
        ),

        # Oracle Configuration
        oracle_lag=OracleLagConfig(
            por_feed_1=ChainAddress(chain="ethereum", address="0x..."),
            por_feed_2=ChainAddress(chain="base", address="0x..."),
        ),
        oracle_freshness=OracleFreshnessConfig(
            price_feeds=[
                ChainAddress(chain="ethereum", address="0xF4030086522a5bEEa4988F8cA5B36dbC97BeE88c"),  # BTC/USD
                ChainAddress(chain="base", address="0x64c911996D3c6aC71E9b8Bd5f54b7F2f24DBc6FF"),      # BTC/USD on Base
            ]
        ),

        # Smart Contract Risk (Qualitative)
        audit_data=AuditData(
            auditor="OpenZeppelin",
            date="2024-06",
            issues={"critical": 0, "high": 0, "medium": 1, "low": 3}
        ),
        deployment_date="2024-09-12",
        incidents=[],

        # Counterparty Risk (Qualitative)
        multisig_configs=[
            MultisigConfig(role_name="owner", is_multisig=True, threshold=3, owners_count=5),
            MultisigConfig(role_name="minter", is_multisig=True, threshold=2, owners_count=3),
        ],
        has_timelock=True,
        timelock_hours=24.0,
        custody_model="regulated_insured",
        has_blacklist=True,
        blacklist_control="multisig",

        # Role configuration
        critical_roles=["owner", "minter"],
        role_weights={"owner": 5, "minter": 4},
    )


# =============================================================================
# JSON SCHEMA EXPORT (for external validation/documentation)
# =============================================================================

JSON_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Asset Risk Configuration",
    "description": "Configuration schema for the Risk Framework Streamlit app",
    "type": "object",
    "required": ["asset_name", "asset_symbol"],
    "properties": {
        "asset_name": {
            "type": "string",
            "description": "Full name of the asset (e.g., 'Coinbase Wrapped BTC')"
        },
        "asset_symbol": {
            "type": "string",
            "description": "Token symbol (e.g., 'cbBTC')"
        },
        "asset_type": {
            "type": "string",
            "enum": ASSET_TYPES,
            "default": "other",
            "description": "Type of asset for scoring context"
        },
        "underlying": {
            "type": ["string", "null"],
            "description": "Underlying asset symbol if applicable (e.g., 'BTC', 'ETH')"
        },
        "token_addresses": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["chain", "address"],
                "properties": {
                    "chain": {"type": "string", "enum": SUPPORTED_CHAINS},
                    "address": {"type": "string", "pattern": "^0x[a-fA-F0-9]{40}$"}
                }
            },
            "description": "Token contract addresses on each chain"
        },
        "lending_configs": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["protocol", "chain", "token_address"],
                "properties": {
                    "protocol": {"type": "string", "enum": ["aave", "compound"]},
                    "chain": {"type": "string", "enum": SUPPORTED_CHAINS},
                    "token_address": {"type": "string"}
                }
            },
            "description": "Lending protocol configurations for RLR/CLR analysis"
        },
        "dex_pools": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["protocol", "chain", "pool_address"],
                "properties": {
                    "protocol": {"type": "string", "enum": ["uniswap", "curve", "pancakeswap"]},
                    "chain": {"type": "string", "enum": SUPPORTED_CHAINS},
                    "pool_address": {"type": "string"}
                }
            },
            "description": "DEX pool configurations for HHI/concentration analysis"
        },
        "proof_of_reserve": {
            "type": ["object", "null"],
            "properties": {
                "evm_chains": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "por": {"type": "string", "description": "Chainlink PoR feed address"},
                            "token": {"type": "string", "description": "Token address for supply"}
                        }
                    }
                },
                "solana_token": {"type": ["string", "null"]}
            },
            "description": "Proof of Reserve configuration"
        },
        "price_risk": {
            "type": ["object", "null"],
            "properties": {
                "token_coingecko_id": {"type": "string"},
                "underlying_coingecko_id": {"type": "string"}
            },
            "description": "CoinGecko IDs for price risk analysis"
        },
        "oracle_lag": {
            "type": ["object", "null"],
            "description": "PoR feed addresses for cross-chain lag calculation"
        },
        "oracle_freshness": {
            "type": ["object", "null"],
            "description": "Price feed addresses for freshness calculation"
        },
        "audit_data": {
            "type": ["object", "null"],
            "properties": {
                "auditor": {"type": "string"},
                "date": {"type": "string", "pattern": "^\\d{4}-\\d{2}$"},
                "issues": {
                    "type": "object",
                    "properties": {
                        "critical": {"type": "integer", "minimum": 0},
                        "high": {"type": "integer", "minimum": 0},
                        "medium": {"type": "integer", "minimum": 0},
                        "low": {"type": "integer", "minimum": 0}
                    }
                }
            },
            "description": "Security audit information"
        },
        "deployment_date": {
            "type": ["string", "null"],
            "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
            "description": "Contract deployment date (YYYY-MM-DD)"
        },
        "incidents": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "days_ago": {"type": "integer"},
                    "funds_lost": {"type": "number"},
                    "funds_lost_pct": {"type": "number"}
                }
            }
        },
        "multisig_configs": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["role_name", "is_multisig"],
                "properties": {
                    "role_name": {"type": "string"},
                    "is_multisig": {"type": "boolean"},
                    "is_eoa": {"type": "boolean"},
                    "threshold": {"type": "integer", "minimum": 1},
                    "owners_count": {"type": "integer", "minimum": 1}
                }
            },
            "description": "Admin role configurations"
        },
        "has_timelock": {"type": "boolean", "default": False},
        "timelock_hours": {"type": "number", "minimum": 0, "default": 0},
        "custody_model": {
            "type": "string",
            "enum": CUSTODY_MODELS,
            "default": "unknown"
        },
        "has_blacklist": {"type": "boolean", "default": False},
        "blacklist_control": {
            "type": "string",
            "enum": BLACKLIST_CONTROLS,
            "default": "none"
        },
        "critical_roles": {
            "type": "array",
            "items": {"type": "string"},
            "default": ["owner", "admin"]
        },
        "role_weights": {
            "type": "object",
            "additionalProperties": {"type": "integer"}
        }
    }
}


if __name__ == "__main__":
    # Generate example config and validate
    example = get_example_config()

    print("=" * 70)
    print("EXAMPLE CONFIGURATION (cbBTC)")
    print("=" * 70)
    print(example.to_json())

    print("\n" + "=" * 70)
    print("VALIDATION RESULTS")
    print("=" * 70)
    validation = validate_config(example)
    print(json.dumps(validation, indent=2))

    print("\n" + "=" * 70)
    print("JSON SCHEMA")
    print("=" * 70)
    print(json.dumps(JSON_SCHEMA, indent=2))
