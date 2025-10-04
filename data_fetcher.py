"""
Advanced NSE India Data Fetcher using curl_cffi
"""

from curl_cffi import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time
from typing import Dict, List, Optional
from loguru import logger
import warnings
import random

warnings.filterwarnings('ignore')

logger.add(
    "logs/data_fetcher.log",
    rotation="1 day",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)


class NSEDataFetcher:
    """Advanced NSE India data fetcher with curl_cffi browser impersonation"""
    
    BASE_URL = "https://www.nseindia.com"
    OPTION_CHAIN_URL = f"{BASE_URL}/api/option-chain-indices"
    MARKET_STATUS_URL = f"{BASE_URL}/api/marketStatus"
    INDICES_DATA_URL = f"{BASE_URL}/api/allIndices"
    
    BROWSERS = ["chrome", "safari", "edge"]
    
    def __init__(self):
        self.session = None
        self.current_browser = random.choice(self.BROWSERS)
        self._init_session()
        logger.info(f"NSE Data Fetcher initialized with {self.current_browser} impersonation")
    
    def _init_session(self):
        if self.session:
            try:
                self.session.close()
            except:
                pass
        
        self.session = requests.Session(impersonate=self.current_browser, timeout=20)
        logger.debug(f"Session initialized with {self.current_browser} impersonation")
    
    def _rotate_browser(self):
        old_browser = self.current_browser
        self.current_browser = random.choice([b for b in self.BROWSERS if b != self.current_browser])
        self._init_session()
        logger.info(f"Rotated: {old_browser} -> {self.current_browser}")
    
    def _refresh_cookies(self) -> bool:
        try:
            logger.info("Establishing NSE session")
            response = self.session.get(f"{self.BASE_URL}/", allow_redirects=True)
            
            if response.status_code == 200:
                logger.success("NSE session established")
                return True
            return False
        except Exception as e:
            logger.error(f"Error establishing session: {str(e)}")
            return False
    
    def _make_request(self, url: str, max_retries: int = 5) -> Optional[Dict]:
        for attempt in range(max_retries):
            try:
                if attempt == 0 or attempt == 2:
                    self._refresh_cookies()
                
                if attempt == 3:
                    self._rotate_browser()
                    self._refresh_cookies()
                
                if attempt > 0:
                    time.sleep(min(2 ** attempt, 10))
                
                logger.debug(f"Request to: {url} (attempt {attempt + 1})")
                response = self.session.get(url, allow_redirects=True)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data:
                            logger.success(f"Success: {url}")
                            return data
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON error: {str(e)}")
                        continue
                        
                elif response.status_code == 403:
                    logger.warning("403 Forbidden - rotating browser")
                    self._rotate_browser()
                    continue
                    
                elif response.status_code == 429:
                    logger.warning("429 Too Many Requests")
                    time.sleep(15)
                    continue
                    
            except Exception as e:
                logger.error(f"Error: {str(e)}")
        
        logger.error(f"Failed after {max_retries} attempts")
        return None
    
    def get_nifty_spot_price(self) -> Optional[float]:
        try:
            logger.info("Fetching NIFTY 50 spot price")
            data = self._make_request(self.INDICES_DATA_URL)
            
            if data and 'data' in data:
                for index in data['data']:
                    if index.get('index') == 'NIFTY 50':
                        price = float(index.get('last', 0))
                        logger.success(f"NIFTY 50: ₹{price}")
                        return price
            
            return None
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return None
    
    def get_options_chain(self, symbol: str = "NIFTY") -> Optional[pd.DataFrame]:
        try:
            logger.info(f"Fetching options chain for {symbol}")
            url = f"{self.OPTION_CHAIN_URL}?symbol={symbol}"
            data = self._make_request(url)
            
            if not data or 'records' not in data:
                return None
            
            records = data['records']['data']
            if not records:
                return None
            
            options_data = []
            for record in records:
                strike = record.get('strikePrice')
                expiry = record.get('expiryDate')
                
                if 'CE' in record:
                    ce = record['CE']
                    options_data.append({
                        'strike': strike,
                        'expiry': expiry,
                        'option_type': 'CE',
                        'last_price': ce.get('lastPrice'),
                        'open_interest': ce.get('openInterest'),
                        'change_in_oi': ce.get('changeinOpenInterest'),
                        'volume': ce.get('totalTradedVolume'),
                        'iv': ce.get('impliedVolatility'),
                    })
                
                if 'PE' in record:
                    pe = record['PE']
                    options_data.append({
                        'strike': strike,
                        'expiry': expiry,
                        'option_type': 'PE',
                        'last_price': pe.get('lastPrice'),
                        'open_interest': pe.get('openInterest'),
                        'change_in_oi': pe.get('changeinOpenInterest'),
                        'volume': pe.get('totalTradedVolume'),
                        'iv': pe.get('impliedVolatility'),
                    })
            
            df = pd.DataFrame(options_data)
            logger.success(f"Fetched {len(df)} options")
            return df
            
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return None
    
    def calculate_historical_volatility(self, days: int = 30) -> float:
        try:
            df = self.get_options_chain()
            
            if df is not None and not df.empty and 'iv' in df.columns:
                valid_ivs = df[df['iv'].notna()]['iv']
                if len(valid_ivs) > 0:
                    avg_iv = valid_ivs.mean()
                    logger.success(f"Volatility from IV: {avg_iv:.2f}%")
                    return avg_iv
            
            return 15.0
        except Exception as e:
            return 15.0
    
    def close(self):
        if self.session:
            try:
                self.session.close()
            except:
                pass


_nse_fetcher_instance = None

def get_nse_fetcher() -> NSEDataFetcher:
    """Get singleton NSE data fetcher instance"""
    global _nse_fetcher_instance
    if _nse_fetcher_instance is None:
        _nse_fetcher_instance = NSEDataFetcher()
    return _nse_fetcher_instance


# Test function
def test_nse_fetcher():
    """Test NSE data fetcher functionality"""
    print("🧪 Testing NSE Data Fetcher")
    print("=" * 60)
    
    fetcher = NSEDataFetcher()
    
    # Test 1: Get spot price
    print("\n1️⃣ Testing NIFTY spot price...")
    spot_price = fetcher.get_nifty_spot_price()
    if spot_price:
        print(f"✅ NIFTY 50: ₹{spot_price}")
    else:
        print("❌ Failed to fetch spot price")
    
    # Test 2: Get options chain
    print("\n2️⃣ Testing options chain...")
    chain = fetcher.get_options_chain()
    if chain:
        records = chain.get('records', {})
        print(f"✅ Fetched options chain")
        print(f"   Underlying: {records.get('underlyingValue')}")
        print(f"   Options: {len(records.get('data', []))} strikes")
    else:
        print("❌ Failed to fetch options chain")
    
    # Test 3: Get options DataFrame
    print("\n3️⃣ Testing options DataFrame...")
    df = fetcher.get_options_data_df()
    if df is not None and not df.empty:
        print(f"✅ Created DataFrame with {len(df)} options")
        print(f"\nSample data:")
        print(df.head(10))
    else:
        print("❌ Failed to create DataFrame")
    
    # Test 4: Calculate volatility
    print("\n4️⃣ Testing volatility calculation...")
    vol = fetcher.calculate_historical_volatility()
    print(f"✅ Calculated volatility: {vol:.2%}")
    
    print("\n" + "=" * 60)
    print("✅ Testing complete!")


if __name__ == "__main__":
    test_nse_fetcher()
