import requests
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
import numpy as np
import time

# Chain configurations
CHAINS = {
    "Ethereum": {
        "rpc": "https://lb.drpc.live/ethereum/AtiZvaKOcUmKq-AbTta3bRaREdpZbjkR8LQrEklbR4ac",
        "pool": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
        "blockscout": "https://eth.blockscout.com"
    },
    "Base": {
        "rpc": "https://lb.drpc.live/base/AtiZvaKOcUmKq-AbTta3bRaREdpZbjkR8LQrEklbR4ac",
        "pool": "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5",
        "blockscout": "https://base.blockscout.com"
    },
    "Arbitrum": {
        "rpc": "https://lb.drpc.live/arbitrum/AtiZvaKOcUmKq-AbTta3bRaREdpZbjkR8LQrEklbR4ac",
        "pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
        "blockscout": "https://arbitrum.blockscout.com"
    }
}

MULTICALL3 = "0xcA11bde05977b3631167028862bE2a173976CA11"

# Minimal ABIs
POOL_ABI = [
    {"inputs": [{"name": "asset", "type": "address"}], "name": "getReserveData", "outputs": [{"components": [{"name": "configuration", "type": "uint256"}, {"name": "liquidityIndex", "type": "uint128"}, {"name": "currentLiquidityRate", "type": "uint128"}, {"name": "variableBorrowIndex", "type": "uint128"}, {"name": "currentVariableBorrowRate", "type": "uint128"}, {"name": "currentStableBorrowRate", "type": "uint128"}, {"name": "lastUpdateTimestamp", "type": "uint40"}, {"name": "id", "type": "uint16"}, {"name": "aTokenAddress", "type": "address"}, {"name": "stableDebtTokenAddress", "type": "address"}, {"name": "variableDebtTokenAddress", "type": "address"}, {"name": "interestRateStrategyAddress", "type": "address"}, {"name": "accruedToTreasury", "type": "uint128"}, {"name": "unbacked", "type": "uint128"}, {"name": "isolationModeTotalDebt", "type": "uint128"}], "type": "tuple"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "asset", "type": "address"}], "name": "getConfiguration", "outputs": [{"components": [{"name": "data", "type": "uint256"}], "type": "tuple"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "user", "type": "address"}], "name": "getUserAccountData", "outputs": [{"name": "totalCollateralBase", "type": "uint256"}, {"name": "totalDebtBase", "type": "uint256"}, {"name": "availableBorrowsBase", "type": "uint256"}, {"name": "currentLiquidationThreshold", "type": "uint256"}, {"name": "ltv", "type": "uint256"}, {"name": "healthFactor", "type": "uint256"}], "stateMutability": "view", "type": "function"}
]

ERC20_ABI = [
    {"inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "stateMutability": "view", "type": "function"}
]

MULTICALL3_ABI = [
    {"inputs": [{"components": [{"name": "target", "type": "address"}, {"name": "callData", "type": "bytes"}], "name": "calls", "type": "tuple[]"}], "name": "aggregate", "outputs": [{"name": "blockNumber", "type": "uint256"}, {"name": "returnData", "type": "bytes[]"}], "stateMutability": "payable", "type": "function"}
]

def get_holders_blockscout(token_address, blockscout_url, max_holders=200):
    """Fetch token holders from Blockscout"""
    holders = []
    url = f"{blockscout_url}/api/v2/tokens/{token_address}/holders"
    
    while url and len(holders) < max_holders:
        try:
            r = requests.get(url, timeout=30).json()
            items = r.get('items', [])
            holders.extend([(h['address']['hash'], float(h['value'])) for h in items])
            
            if len(holders) >= max_holders:
                break
            
            next_params = r.get('next_page_params')
            url = f"{blockscout_url}/api/v2/tokens/{token_address}/holders?" + requests.compat.urlencode(next_params) if next_params else None
            time.sleep(0.3)
        except Exception as e:
            print(f"  ⚠️  Blockscout error: {e}")
            break
    
    return holders[:max_holders]

def decode_ltv_liquidation(config_data):
    """Decode LTV and liquidation threshold from configuration bitmap"""
    ltv = (config_data & 0xFFFF) / 100  # First 16 bits
    liquidation_threshold = ((config_data >> 16) & 0xFFFF) / 100  # Next 16 bits
    return ltv, liquidation_threshold

def analyze_aave_market(token_address, chain_name, chain_config):
    """Complete AAVE market analysis for any token"""
    print(f"\n{'='*70}")
    print(f"🔍 Analyzing {chain_name} - AAVE V3")
    print(f"{'='*70}\n")
    
    try:
        # Setup Web3
        w3 = Web3(Web3.HTTPProvider(chain_config['rpc']))
        if chain_name in ["Base", "Arbitrum"]:
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        
        pool = w3.eth.contract(address=chain_config['pool'], abi=POOL_ABI)
        
        # Get reserve data
        print("📊 Fetching reserve data...")
        reserve_data = pool.functions.getReserveData(token_address).call()
        config = pool.functions.getConfiguration(token_address).call()
        
        atoken_address = reserve_data[8]
        debt_token_address = reserve_data[10]
        
        # Get token contracts and decimals
        underlying_token = w3.eth.contract(address=token_address, abi=ERC20_ABI)
        atoken = w3.eth.contract(address=atoken_address, abi=ERC20_ABI)
        debt_token = w3.eth.contract(address=debt_token_address, abi=ERC20_ABI)
        
        # Fetch decimals and symbol
        decimals = underlying_token.functions.decimals().call()
        symbol = underlying_token.functions.symbol().call()
        decimals_divisor = 10 ** decimals
        
        print(f"  Token: {symbol} ({decimals} decimals)")
        
        # Basic metrics
        total_supply = atoken.functions.totalSupply().call() / decimals_divisor
        total_borrow = debt_token.functions.totalSupply().call() / decimals_divisor
        
        supply_apy = (reserve_data[2] / 1e27) * 100  # liquidityRate
        borrow_apy = (reserve_data[4] / 1e27) * 100  # variableBorrowRate
        
        ltv, liquidation_threshold = decode_ltv_liquidation(config[0])
        
        utilization = (total_borrow / total_supply * 100) if total_supply > 0 else 0
        
        # Display basic metrics
        print(f"\n📈 Market Overview:")
        print(f"  Total Supply:          {total_supply:,.4f} {symbol}")
        print(f"  Total Borrow:          {total_borrow:,.4f} {symbol}")
        print(f"  Supply APY:            {supply_apy:.2f}%")
        print(f"  Borrow APY:            {borrow_apy:.2f}%")
        print(f"  LTV:                   {ltv:.0f}%")
        print(f"  Liquidation Threshold: {liquidation_threshold:.0f}%")
        print(f"  Utilization Rate:      {utilization:.2f}%")
        
        # RLR Calculation
        print(f"\n🔄 Calculating RLR (Recursive Lending Ratio)...")
        suppliers = get_holders_blockscout(atoken_address, chain_config['blockscout'])
        borrowers = get_holders_blockscout(debt_token_address, chain_config['blockscout'])
        
        if not suppliers or not borrowers:
            print("  ⚠️  Insufficient holder data for RLR")
            return
        
        # Create dictionaries for fast lookup
        supplier_dict = {addr.lower(): amt / decimals_divisor for addr, amt in suppliers}
        borrower_dict = {addr.lower(): amt / decimals_divisor for addr, amt in borrowers}
        
        # Find loopers (overlap addresses)
        supplier_addrs = set(supplier_dict.keys())
        borrower_addrs = set(borrower_dict.keys())
        loopers = supplier_addrs & borrower_addrs
        
        # Calculate looper details
        looper_details = []
        for addr in loopers:
            user_supply = supplier_dict[addr]
            user_borrow = borrower_dict[addr]
            
            # Skip if supply <= borrow (invalid leverage)
            if user_supply <= user_borrow:
                continue
            
            leverage = user_supply / (user_supply - user_borrow)
            looper_details.append({
                "address": addr,
                "supply": user_supply,
                "borrow": user_borrow,
                "leverage": leverage
            })
        
        # Sort by leverage descending
        looper_details.sort(key=lambda x: x['leverage'], reverse=True)
        
        # Calculate statistics
        if looper_details:
            leverages = [l['leverage'] for l in looper_details]
            leverage_avg = np.mean(leverages)
            leverage_max = np.max(leverages)
            leverage_min = np.min(leverages)
        else:
            leverage_avg = leverage_max = leverage_min = 0
        
        # Calculate total looped borrow
        looped_borrow = sum(l['borrow'] for l in looper_details)
        
        rlr_supply = (looped_borrow / total_supply * 100) if total_supply > 0 else 0
        rlr_borrow = (looped_borrow / total_borrow * 100) if total_borrow > 0 else 0
        
        print(f"  Loopers Detected:      {len(looper_details)} addresses")
        print(f"  Looped Borrow:         {looped_borrow:,.4f} {symbol}")
        print(f"  RLR (Supply-based):    {rlr_supply:.2f}%")
        print(f"  RLR (Borrow-based):    {rlr_borrow:.2f}%")
        
        print(f"\n  📊 Looper Leverage Statistics:")
        print(f"  Average Leverage:      {leverage_avg:.2f}x")
        print(f"  Max Leverage:          {leverage_max:.2f}x")
        print(f"  Min Leverage:          {leverage_min:.2f}x")
        
        print(f"\n  🔝 Top 10 Loopers by Leverage:")
        for i, looper in enumerate(looper_details[:10], 1):
            print(f"    {i}. {looper['address'][:10]}...{looper['address'][-8:]}")
            print(f"       Supply: {looper['supply']:,.4f} {symbol} | Borrow: {looper['borrow']:,.4f} {symbol} | Leverage: {looper['leverage']:.2f}x")
        
        # CLR Calculation
        print(f"\n⚠️  Calculating CLR (Cascade Liquidation Risk)...")
        
        borrower_list = [addr for addr, _ in borrowers[:100]]  # Limit to 100 for speed
        
        # Batch call getUserAccountData via Multicall3
        multicall = w3.eth.contract(address=MULTICALL3, abi=MULTICALL3_ABI)
        
        calls = []
        for borrower in borrower_list:
            call_data = pool.encode_abi('getUserAccountData', [borrower])
            calls.append((pool.address, call_data))
        
        print(f"  Fetching health factors for {len(borrower_list)} borrowers...")
        _, results = multicall.functions.aggregate(calls).call()
        
        # Decode results
        risk_buckets = {
            "Critical (HF < 1.0)": [],
            "High Risk (1.0 ≤ HF < 1.05)": [],
            "At Risk (1.05 ≤ HF < 1.1)": [],
            "Moderate (1.1 ≤ HF < 1.25)": [],
            "Safe (HF ≥ 1.25)": []
        }
        
        total_debt_analyzed = 0
        debt_at_risk = 0
        
        for i, result in enumerate(results):
            decoded = w3.codec.decode(['uint256', 'uint256', 'uint256', 'uint256', 'uint256', 'uint256'], result)
            collateral, debt, _, _, _, health_factor = decoded
            
            if debt == 0:
                continue
            
            hf = health_factor / 1e18
            debt_usd = debt / 1e8  # AAVE uses 8 decimals for USD values
            total_debt_analyzed += debt_usd
            
            if hf < 1.0:
                risk_buckets["Critical (HF < 1.0)"].append((borrower_list[i], hf, debt_usd))
                debt_at_risk += debt_usd
            elif hf < 1.05:
                risk_buckets["High Risk (1.0 ≤ HF < 1.05)"].append((borrower_list[i], hf, debt_usd))
                debt_at_risk += debt_usd
            elif hf < 1.1:
                risk_buckets["At Risk (1.05 ≤ HF < 1.1)"].append((borrower_list[i], hf, debt_usd))
                debt_at_risk += debt_usd
            elif hf < 1.25:
                risk_buckets["Moderate (1.1 ≤ HF < 1.25)"].append((borrower_list[i], hf, debt_usd))
            else:
                risk_buckets["Safe (HF ≥ 1.25)"].append((borrower_list[i], hf, debt_usd))
        
        total_positions = sum(len(v) for v in risk_buckets.values())
        at_risk_count = len(risk_buckets["Critical (HF < 1.0)"]) + len(risk_buckets["High Risk (1.0 ≤ HF < 1.05)"]) + len(risk_buckets["At Risk (1.05 ≤ HF < 1.1)"])
        
        clr_count = (at_risk_count / total_positions * 100) if total_positions > 0 else 0
        clr_value = (debt_at_risk / total_debt_analyzed * 100) if total_debt_analyzed > 0 else 0
        
        print(f"\n  Health Factor Distribution:")
        for bucket, positions in risk_buckets.items():
            count = len(positions)
            pct = (count / total_positions * 100) if total_positions > 0 else 0
            print(f"    {bucket}: {count} positions ({pct:.1f}%)")
        
        print(f"\n  CLR (by count):        {clr_count:.2f}%")
        print(f"  CLR (by value):        {clr_value:.2f}%")
        print(f"  Positions Analyzed:    {total_positions}")
        print(f"  Debt Analyzed:         ${total_debt_analyzed:,.2f}")
        
    except Exception as e:
        print(f"❌ Error analyzing {chain_name}: {e}")

if __name__ == "__main__":
    # Example: cbBTC
    token_address = "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf"
    
    for chain_name, config in CHAINS.items():
        analyze_aave_market(token_address, chain_name, config)
        print()