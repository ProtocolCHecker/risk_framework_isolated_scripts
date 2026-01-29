"""
Asset Registry - Manages monitored assets and their configurations.

Provides CRUD operations for assets stored in the database.
"""

import json
from typing import List, Dict, Any, Optional
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import SCHEMA_NAME, TABLE_PREFIX
from core.db import get_connection, execute_query, table_name


class AssetRegistry:
    """
    Manages the asset registry for monitoring.

    Assets are stored in the database with their full JSON configuration,
    allowing the dispatcher to determine which metrics to fetch.
    """

    @staticmethod
    def add_asset(symbol: str, name: str, config: dict, enabled: bool = True) -> int:
        """
        Add a new asset to the registry.

        Args:
            symbol: Asset symbol (e.g., 'RLP', 'wstETH')
            name: Full asset name
            config: Full JSON configuration dict
            enabled: Whether monitoring is enabled

        Returns:
            Inserted asset ID
        """
        query = f"""
            INSERT INTO {table_name('asset_registry')} (symbol, name, config, enabled)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (symbol) DO UPDATE SET
                name = EXCLUDED.name,
                config = EXCLUDED.config,
                enabled = EXCLUDED.enabled,
                updated_at = NOW()
            RETURNING id
        """
        config_json = json.dumps(config)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (symbol, name, config_json, enabled))
                row_id = cur.fetchone()[0]
                conn.commit()
                return row_id

    @staticmethod
    def add_asset_from_file(file_path: str, enabled: bool = True) -> int:
        """
        Add an asset from a JSON config file.

        Args:
            file_path: Path to JSON config file
            enabled: Whether monitoring is enabled

        Returns:
            Inserted asset ID
        """
        with open(file_path, 'r') as f:
            config = json.load(f)

        symbol = config.get('asset_symbol', Path(file_path).stem)
        name = config.get('asset_name', symbol)

        return AssetRegistry.add_asset(symbol, name, config, enabled)

    @staticmethod
    def get_asset(symbol: str) -> Optional[Dict]:
        """
        Get an asset by symbol.

        Args:
            symbol: Asset symbol

        Returns:
            Asset dict with config, or None if not found
        """
        query = f"""
            SELECT id, symbol, name, config, enabled, created_at, updated_at
            FROM {table_name('asset_registry')}
            WHERE symbol = %s
        """
        results = execute_query(query, (symbol,))
        if results:
            result = results[0]
            # Parse JSON config
            if isinstance(result['config'], str):
                result['config'] = json.loads(result['config'])
            return result
        return None

    @staticmethod
    def get_all_assets(enabled_only: bool = True) -> List[Dict]:
        """
        Get all registered assets.

        Args:
            enabled_only: If True, only return enabled assets

        Returns:
            List of asset dicts
        """
        query = f"""
            SELECT id, symbol, name, config, enabled, created_at, updated_at
            FROM {table_name('asset_registry')}
        """
        if enabled_only:
            query += " WHERE enabled = true"
        query += " ORDER BY symbol"

        results = execute_query(query)
        for result in results:
            if isinstance(result['config'], str):
                result['config'] = json.loads(result['config'])
        return results

    @staticmethod
    def update_asset(symbol: str, config: dict = None, enabled: bool = None) -> bool:
        """
        Update an asset's configuration or enabled status.

        Args:
            symbol: Asset symbol
            config: New config dict (optional)
            enabled: New enabled status (optional)

        Returns:
            True if update successful
        """
        updates = []
        params = []

        if config is not None:
            updates.append("config = %s")
            params.append(json.dumps(config))

        if enabled is not None:
            updates.append("enabled = %s")
            params.append(enabled)

        if not updates:
            return False

        updates.append("updated_at = NOW()")
        params.append(symbol)

        query = f"""
            UPDATE {table_name('asset_registry')}
            SET {', '.join(updates)}
            WHERE symbol = %s
        """

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                conn.commit()
                return cur.rowcount > 0

    @staticmethod
    def disable_asset(symbol: str) -> bool:
        """Disable monitoring for an asset."""
        return AssetRegistry.update_asset(symbol, enabled=False)

    @staticmethod
    def enable_asset(symbol: str) -> bool:
        """Enable monitoring for an asset."""
        return AssetRegistry.update_asset(symbol, enabled=True)

    @staticmethod
    def delete_asset(symbol: str) -> bool:
        """
        Delete an asset from the registry.

        Args:
            symbol: Asset symbol

        Returns:
            True if deletion successful
        """
        query = f"DELETE FROM {table_name('asset_registry')} WHERE symbol = %s"

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (symbol,))
                conn.commit()
                return cur.rowcount > 0

    @staticmethod
    def get_assets_with_config_key(config_key: str) -> List[Dict]:
        """
        Get all assets that have a specific config key defined.

        Useful for dispatcher to find assets that need specific metrics fetched.

        Args:
            config_key: Config key to check for (e.g., 'proof_of_reserve', 'dex_pools')

        Returns:
            List of assets with that config key
        """
        query = f"""
            SELECT id, symbol, name, config, enabled
            FROM {table_name('asset_registry')}
            WHERE enabled = true
              AND config ? %s
        """
        results = execute_query(query, (config_key,))
        for result in results:
            if isinstance(result['config'], str):
                result['config'] = json.loads(result['config'])
        return results


def load_all_configs_from_directory(directory: str) -> int:
    """
    Load all JSON config files from a directory into the registry.

    Args:
        directory: Path to directory containing JSON configs

    Returns:
        Number of assets loaded
    """
    loaded = 0
    dir_path = Path(directory)

    for json_file in dir_path.glob("*.json"):
        try:
            AssetRegistry.add_asset_from_file(str(json_file))
            print(f"  Loaded: {json_file.name}")
            loaded += 1
        except Exception as e:
            print(f"  Failed to load {json_file.name}: {e}")

    return loaded


if __name__ == "__main__":
    # Test registry operations
    print("Testing Asset Registry...")

    # Test get all assets
    assets = AssetRegistry.get_all_assets()
    print(f"Found {len(assets)} registered assets")
    for asset in assets:
        print(f"  - {asset['symbol']}: {asset['name']}")
