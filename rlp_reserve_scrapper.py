#!/usr/bin/env python3
"""
Resolv Reserves Data Scraper
Fetches proof of reserve data from Apostro's Resolv dashboard
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

class ResolvReservesScraper:
    def __init__(self):
        self.url = "https://info.apostro.xyz/resolv-reserves"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def fetch_page(self):
        """Fetch the HTML content"""
        response = requests.get(self.url, headers=self.headers)
        response.raise_for_status()
        return response.text
    
    def parse_metric(self, text):
        """Extract numeric value from text like '$557.56M' or '0.04%'"""
        # Remove commas and extract number
        text = text.strip()
        
        # Handle percentage
        if '%' in text:
            return float(text.replace('%', '').replace(',', ''))
        
        # Handle dollar amounts with M/K/B suffixes
        if '$' in text:
            text = text.replace('$', '').replace(',', '')
            multiplier = 1
            if 'M' in text:
                multiplier = 1_000_000
                text = text.replace('M', '')
            elif 'K' in text:
                multiplier = 1_000
                text = text.replace('K', '')
            elif 'B' in text:
                multiplier = 1_000_000_000
                text = text.replace('B', '')
            
            # Handle negative values
            if text.startswith('-'):
                return -float(text[1:]) * multiplier
            return float(text) * multiplier
        
        return text
    
    def scrape_data(self):
        """Main scraping function"""
        html = self.fetch_page()
        soup = BeautifulSoup(html, 'html.parser')
        
        data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'general_metrics': {},
            'exposure_by_asset': [],
            'collateral_pool': [],
            'backing_assets_location': [],
            'hedging_positions': []
        }
        
        # Extract timestamp from page
        timestamp_elem = soup.find(text=re.compile(r'\d{2} \w{3} \d{2}:\d{2} UTC'))
        if timestamp_elem:
            data['page_timestamp'] = timestamp_elem.strip()
        
        # Extract general metrics
        metrics_section = soup.find('h2', text='GENERAL METRICS')
        if metrics_section:
            metrics_list = metrics_section.find_next('ul')
            if metrics_list:
                for li in metrics_list.find_all('li'):
                    text = li.get_text()
                    if ':' in text:
                        key, value = text.split(':', 1)
                        key = key.strip().lower().replace(' ', '_')
                        data['general_metrics'][key] = self.parse_metric(value)
        
        # Extract tables
        tables = soup.find_all('table')
        
        # Table 1: Exposure by Asset
        if len(tables) > 0:
            for row in tables[0].find_all('tr')[1:]:  # Skip header
                cols = row.find_all('td')
                if len(cols) >= 4:
                    data['exposure_by_asset'].append({
                        'asset': cols[0].get_text().strip().replace('.', ''),
                        'long': self.parse_metric(cols[1].get_text()),
                        'short': self.parse_metric(cols[2].get_text()),
                        'net': self.parse_metric(cols[3].get_text())
                    })
        
        # Table 2: Collateral Pool by Asset
        if len(tables) > 1:
            for row in tables[1].find_all('tr')[1:]:  # Skip header
                cols = row.find_all('td')
                if len(cols) >= 3:
                    asset_name = cols[0].get_text().strip().replace('.', '')
                    if asset_name and asset_name != 'Total':
                        data['collateral_pool'].append({
                            'asset': asset_name,
                            'percentage': self.parse_metric(cols[1].get_text()),
                            'value': self.parse_metric(cols[2].get_text())
                        })
        
        # Table 3: Backing Assets by Location
        if len(tables) > 2:
            for row in tables[2].find_all('tr')[1:]:  # Skip header
                cols = row.find_all('td')
                if len(cols) >= 3:
                    location = cols[0].get_text().strip().replace('.', '')
                    if location and location != 'Total':
                        data['backing_assets_location'].append({
                            'location': location,
                            'percentage': self.parse_metric(cols[1].get_text()),
                            'value': self.parse_metric(cols[2].get_text())
                        })
        
        # Table 4: Hedging positions
        if len(tables) > 3:
            for row in tables[3].find_all('tr')[1:]:  # Skip header
                cols = row.find_all('td')
                if len(cols) >= 4:
                    position = cols[0].get_text().strip().replace('.', '')
                    if position and position != 'Total':
                        data['hedging_positions'].append({
                            'position': position,
                            'margin': self.parse_metric(cols[1].get_text()),
                            'share': self.parse_metric(cols[2].get_text()),
                            'size': self.parse_metric(cols[3].get_text())
                        })
        
        return data
    
    def get_summary(self):
        """Get a quick summary of key metrics"""
        data = self.scrape_data()
        
        summary = {
            'tvl': data['general_metrics'].get('tvl'),
            'usr_tvl': data['general_metrics'].get('usr_tvl'),
            'rlp_tvl': data['general_metrics'].get('rlp_tvl'),
            'market_delta': data['general_metrics'].get('market_delta'),
            'usr_over_collateralization': data['general_metrics'].get('usr_over_collateralization'),
            'top_3_collateral': data['collateral_pool'][:3] if data['collateral_pool'] else [],
            'top_3_locations': data['backing_assets_location'][:3] if data['backing_assets_location'] else []
        }
        
        return summary


def main():
    """Example usage"""
    scraper = ResolvReservesScraper()
    
    print("Fetching Resolv Reserves data...")
    print("=" * 60)
    
    try:
        # Get full data
        data = scraper.scrape_data()
        
        # Print summary
        print(f"\n📊 GENERAL METRICS")
        print(f"   TVL: ${data['general_metrics'].get('tvl', 0):,.0f}")
        print(f"   USR TVL: ${data['general_metrics'].get('usr_tvl', 0):,.0f}")
        print(f"   RLP TVL: ${data['general_metrics'].get('rlp_tvl', 0):,.0f}")
        print(f"   Market Delta: {data['general_metrics'].get('market_delta', 0):.2f}%")
        print(f"   USR Over-collateralization: {data['general_metrics'].get('usr_over_collateralization', 0):.2f}%")
        
        print(f"\n🏦 TOP COLLATERAL ASSETS")
        for asset in data['collateral_pool'][:5]:
            print(f"   {asset['asset']:12s}: {asset['percentage']:6.1f}% (${asset['value']:,.0f})")
        
        print(f"\n📍 BACKING ASSETS BY LOCATION")
        for loc in data['backing_assets_location'][:5]:
            print(f"   {loc['location']:20s}: {loc['percentage']:6.1f}% (${loc['value']:,.0f})")
        
        print(f"\n💱 EXPOSURE BY ASSET")
        for exp in data['exposure_by_asset']:
            net_str = f"${exp['net']:,.0f}" if exp['net'] >= 0 else f"-${abs(exp['net']):,.0f}"
            print(f"   {exp['asset']:8s}: Long ${exp['long']:,.0f} | Short ${exp['short']:,.0f} | Net {net_str}")

        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()