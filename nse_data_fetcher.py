"""
Advanced NSE India Data Fetcher
Robust scraper for fetching real-time NIFTY 50 data from NSE India website
Using enterprise-grade scraping techniques with session management and error handling
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time
from typing import Dict, List, Optional, Tuple
from loguru import logger
import warnings

warnings.filterwarnings('ignore')

# Configure logging
logger.add(
    "logs/nse_data_fetcher.log",
    rotation="1 day",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)


class NSEDataFetcher:
    """Advanced NSE India data fetcher with robust session management"""
    
    # NSE API endpoints
    BASE_URL = "https://www.nseindia.com"
    OPTION_CHAIN_URL = f"{BASE_URL}/api/option-chain-indices"
    MARKET_STATUS_URL = f"{BASE_URL}/api/marketStatus"
    INDICES_DATA_URL = f"{BASE_URL}/api/allIndices"
    
    def __init__(self):
        """Initialize NSE data fetcher with proper headers and session"""
        self.session = requests.Session()
        
        # Critical headers for NSE scraping
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://www.nseindia.com/option-chain',
            'X-Requested-With': 'XMLHttpRequest',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }
        
        self.session.headers.update(self.headers)
        self.cookies = None
        self.last_cookie_refresh = None
        
        logger.info("NSE Data Fetcher initialized")
        
    def _refresh_cookies(self) -> bool:
        """
        Refresh NSE session cookies
        NSE requires visiting the main page first to get session cookies
        """
        try:
            # Check if we need to refresh (cache for 5 minutes)
            if self.last_cookie_refresh:
                elapsed = (datetime.now() - self.last_cookie_refresh).seconds
                if elapsed < 300:  # 5 minutes
                    logger.debug("Using cached cookies")
                    return True
            
            logger.info("Refreshing NSE session cookies")
            
            # Visit the main page to establish session
            response = self.session.get(
                f"{self.BASE_URL}/option-chain",
                headers=self.headers,
                timeout=10,
                allow_redirects=True
            )
            
            if response.status_code == 200:
                self.cookies = dict(response.cookies)
                self.last_cookie_refresh = datetime.now()
                logger.success("NSE session cookies refreshed successfully")
                return True
            else:
                logger.warning(f"Failed to refresh cookies, status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error refreshing cookies: {str(e)}")
            return False
    
    def _make_request(self, url: str, max_retries: int = 3) -> Optional[Dict]:
        """
        Make a request to NSE with retry logic
        
        Args:
            url: URL to fetch
            max_retries: Maximum number of retry attempts
            
        Returns:
            JSON response data or None on failure
        """
        for attempt in range(max_retries):
            try:
                # Refresh cookies before request
                if not self._refresh_cookies():
                    logger.warning("Failed to refresh cookies, attempting request anyway")
                
                # Add a small delay to avoid rate limiting
                if attempt > 0:
                    time.sleep(2 ** attempt)  # Exponential backoff
                
                logger.debug(f"Making request to: {url} (attempt {attempt + 1}/{max_retries})")
                
                response = self.session.get(
                    url,
                    headers=self.headers,
                    timeout=15,
                    allow_redirects=True
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.success(f"Successfully fetched data from {url}")
                    return data
                elif response.status_code == 401:
                    logger.warning("Unauthorized - refreshing session")
                    self.last_cookie_refresh = None  # Force cookie refresh
                    continue
                else:
                    logger.warning(f"Request failed with status {response.status_code}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{max_retries})")
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
        
        logger.error(f"Failed to fetch data after {max_retries} attempts")
        return None
    
    def get_nifty_spot_price(self) -> Optional[float]:
        """
        Get current NIFTY 50 spot price from NSE
        
        Returns:
            Current NIFTY 50 price or None on failure
        """
        try:
            logger.info("Fetching NIFTY 50 spot price from NSE")
            
            data = self._make_request(self.INDICES_DATA_URL)
            
            if data and 'data' in data:
                # Find NIFTY 50 in the indices data
                for index in data['data']:
                    if index.get('index') == 'NIFTY 50':
                        price = float(index.get('last', 0))
                        logger.success(f"NIFTY 50 spot price: ₹{price}")
                        return price
                
                logger.warning("NIFTY 50 not found in indices data")
            else:
                logger.error("Invalid response format from NSE")
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching NIFTY spot price: {str(e)}")
            return None
    
    def get_options_chain(self, symbol: str = "NIFTY") -> Optional[Dict]:
        """
        Get complete options chain data from NSE
        
        Args:
            symbol: Index symbol (NIFTY, BANKNIFTY, FINNIFTY)
            
        Returns:
            Complete options chain data or None on failure
        """
        try:
            logger.info(f"Fetching options chain for {symbol}")
            
            url = f"{self.OPTION_CHAIN_URL}?symbol={symbol}"
            data = self._make_request(url)
            
            if data and 'records' in data:
                records = data['records']
                logger.success(f"Fetched options chain with {len(records.get('data', []))} strikes")
                return data
            else:
                logger.error("Invalid options chain response format")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching options chain: {str(e)}")
            return None
    
    def get_options_data_df(self, symbol: str = "NIFTY") -> Optional[pd.DataFrame]:
        """
        Get options chain data as a formatted DataFrame
        
        Args:
            symbol: Index symbol
            
        Returns:
            DataFrame with options data or None on failure
        """
        try:
            chain_data = self.get_options_chain(symbol)
            
            if not chain_data:
                return None
            
            records = chain_data.get('records', {})
            options_data = records.get('data', [])
            
            if not options_data:
                logger.warning("No options data found")
                return None
            
            # Parse options data
            parsed_data = []
            
            for item in options_data:
                strike = item.get('strikePrice')
                expiry = item.get('expiryDate')
                
                # Call data
                if 'CE' in item:
                    ce = item['CE']
                    parsed_data.append({
                        'symbol': symbol,
                        'expiry_date': expiry,
                        'strike': strike,
                        'option_type': 'CALL',
                        'last_price': ce.get('lastPrice', 0),
                        'open_interest': ce.get('openInterest', 0),
                        'change_in_oi': ce.get('changeinOpenInterest', 0),
                        'volume': ce.get('totalTradedVolume', 0),
                        'iv': ce.get('impliedVolatility', 0),
                        'ltp': ce.get('lastPrice', 0),
                        'bid_price': ce.get('bidprice', 0),
                        'ask_price': ce.get('askPrice', 0),
                        'bid_qty': ce.get('bidQty', 0),
                        'ask_qty': ce.get('askQty', 0),
                    })
                
                # Put data
                if 'PE' in item:
                    pe = item['PE']
                    parsed_data.append({
                        'symbol': symbol,
                        'expiry_date': expiry,
                        'strike': strike,
                        'option_type': 'PUT',
                        'last_price': pe.get('lastPrice', 0),
                        'open_interest': pe.get('openInterest', 0),
                        'change_in_oi': pe.get('changeinOpenInterest', 0),
                        'volume': pe.get('totalTradedVolume', 0),
                        'iv': pe.get('impliedVolatility', 0),
                        'ltp': pe.get('lastPrice', 0),
                        'bid_price': pe.get('bidprice', 0),
                        'ask_price': pe.get('askPrice', 0),
                        'bid_qty': pe.get('bidQty', 0),
                        'ask_qty': pe.get('askQty', 0),
                    })
            
            df = pd.DataFrame(parsed_data)
            logger.success(f"Created DataFrame with {len(df)} options")
            
            return df
            
        except Exception as e:
            logger.error(f"Error creating options DataFrame: {str(e)}")
            return None
    
    def get_historical_data(self, days: int = 30) -> Optional[pd.DataFrame]:
        """
        Get historical NIFTY data for volatility calculation
        
        Note: NSE doesn't provide easy historical data API
        We'll use spot price and calculate synthetic historical volatility
        
        Args:
            days: Number of days of historical data
            
        Returns:
            DataFrame with historical data (synthesized) or None
        """
        try:
            logger.info(f"Getting historical volatility data for {days} days")
            
            # Get current spot price
            spot_price = self.get_nifty_spot_price()
            
            if not spot_price:
                return None
            
            # For now, use market standard volatility
            # In production, you'd fetch actual historical data from another source
            # or use the options chain implied volatility
            logger.info("Using options chain IV for volatility estimation")
            
            return None  # Return None to trigger fallback to default volatility
            
        except Exception as e:
            logger.error(f"Error getting historical data: {str(e)}")
            return None
    
    def calculate_historical_volatility(self, days: int = 30) -> float:
        """
        Calculate historical volatility from options chain IV
        
        Args:
            days: Period for volatility calculation
            
        Returns:
            Annualized volatility (default to market standard if unavailable)
        """
        try:
            logger.info(f"Calculating historical volatility for {days} days")
            
            # Get options chain to extract implied volatility
            chain_data = self.get_options_chain()
            
            if not chain_data:
                logger.warning("Using default volatility: 15%")
                return 0.15
            
            # Extract ATM options IV
            records = chain_data.get('records', {})
            spot_price = records.get('underlyingValue', 0)
            options_data = records.get('data', [])
            
            # Find ATM options and get their IV
            ivs = []
            for item in options_data:
                strike = item.get('strikePrice')
                if abs(strike - spot_price) < 100:  # Near ATM
                    if 'CE' in item and item['CE'].get('impliedVolatility'):
                        ivs.append(item['CE']['impliedVolatility'])
                    if 'PE' in item and item['PE'].get('impliedVolatility'):
                        ivs.append(item['PE']['impliedVolatility'])
            
            if ivs:
                # Average IV of ATM options
                avg_iv = np.mean(ivs) / 100  # Convert from percentage
                logger.success(f"Calculated volatility from IV: {avg_iv:.2%}")
                return avg_iv
            else:
                logger.warning("No IV data found, using default: 15%")
                return 0.15
                
        except Exception as e:
            logger.error(f"Error calculating volatility: {str(e)}")
            return 0.15  # Default volatility
    
    def get_market_status(self) -> Dict[str, str]:
        """
        Get current market status
        
        Returns:
            Dictionary with market status information
        """
        try:
            logger.info("Fetching market status")
            
            data = self._make_request(self.MARKET_STATUS_URL)
            
            if data:
                logger.success("Market status fetched successfully")
                return data
            else:
                return {"status": "unknown"}
                
        except Exception as e:
            logger.error(f"Error fetching market status: {str(e)}")
            return {"status": "error", "message": str(e)}


# Singleton instance
_nse_fetcher = None


def get_nse_fetcher() -> NSEDataFetcher:
    """Get singleton NSE data fetcher instance"""
    global _nse_fetcher
    if _nse_fetcher is None:
        _nse_fetcher = NSEDataFetcher()
    return _nse_fetcher


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
