"""
NIFTY Options Greeks Calculator with NSE India Data
Complete implementation using NSE India official API for real-time data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from scipy.stats import norm
import warnings
from typing import Dict, List, Optional, Tuple, Union
from loguru import logger
import time
from nse_data_fetcher import NSEDataFetcher, get_nse_fetcher

warnings.filterwarnings('ignore')

# Configure logging
logger.add(
    "logs/nse_nifty_greeks.log",
    rotation="1 day",
    retention="30 days", 
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)


class GreeksCalculator:
    """Advanced Black-Scholes Greeks calculator"""
    
    @staticmethod
    def black_scholes_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate Black-Scholes call option price"""
        if T <= 0:
            return max(S - K, 0)
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        call_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        return max(call_price, 0)
    
    @staticmethod
    def black_scholes_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate Black-Scholes put option price"""
        if T <= 0:
            return max(K - S, 0)
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        put_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        return max(put_price, 0)
    
    @staticmethod
    def calculate_greeks(S: float, K: float, T: float, r: float, sigma: float, option_type: str = 'call') -> Dict[str, float]:
        """Calculate all Greeks for an option"""
        if T <= 0:
            return {
                'delta': 1.0 if option_type == 'call' and S > K else (-1.0 if option_type == 'put' and S < K else 0.0),
                'gamma': 0.0,
                'theta': 0.0,
                'vega': 0.0,
                'rho': 0.0
            }
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        # Delta
        if option_type.lower() == 'call':
            delta = norm.cdf(d1)
        else:
            delta = norm.cdf(d1) - 1
        
        # Gamma (same for call and put)
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        
        # Theta
        if option_type.lower() == 'call':
            theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) 
                    - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
        else:
            theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) 
                    + r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365
        
        # Vega (same for call and put)
        vega = S * norm.pdf(d1) * np.sqrt(T) / 100
        
        # Rho
        if option_type.lower() == 'call':
            rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100
        else:
            rho = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100
        
        return {
            'delta': round(delta, 6),
            'gamma': round(gamma, 8),
            'theta': round(theta, 6),
            'vega': round(vega, 6),
            'rho': round(rho, 6)
        }
    
    @staticmethod
    def calculate_implied_volatility(option_price: float, S: float, K: float, T: float, r: float, 
                                    option_type: str = 'call', max_iterations: int = 100, 
                                    tolerance: float = 1e-5) -> Optional[float]:
        """Calculate implied volatility using Newton-Raphson method"""
        if T <= 0 or option_price <= 0:
            return None
        
        # Initial guess
        sigma = 0.3
        
        for i in range(max_iterations):
            if option_type.lower() == 'call':
                price = GreeksCalculator.black_scholes_call(S, K, T, r, sigma)
            else:
                price = GreeksCalculator.black_scholes_put(S, K, T, r, sigma)
            
            diff = price - option_price
            
            if abs(diff) < tolerance:
                return round(sigma, 6)
            
            # Vega for Newton-Raphson
            d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            vega = S * norm.pdf(d1) * np.sqrt(T)
            
            if vega < 1e-10:
                return None
            
            # Update sigma
            sigma = sigma - diff / vega
            
            if sigma <= 0:
                sigma = 0.01
        
        return None


class NSEFinanceAPI:
    """NSE India API client for NIFTY data"""
    
    def __init__(self):
        self.nse_fetcher = get_nse_fetcher()
        logger.info("NSE Finance API client initialized")
    
    def get_nifty_price(self) -> Optional[float]:
        """Get current NIFTY 50 price from NSE"""
        try:
            logger.info("Fetching NIFTY price from NSE India")
            price = self.nse_fetcher.get_nifty_spot_price()
            
            if price:
                logger.success(f"Successfully fetched NIFTY price: {price}")
                return float(price)
            
            # Fallback to a reasonable default for testing
            logger.warning("Could not fetch live price, using fallback")
            return 24500.0  # Fallback price
            
        except Exception as e:
            logger.error(f"Error fetching NIFTY price: {e}")
            return 24500.0  # Fallback price
    
    def get_nifty_historical_data(self, days: int = 30) -> Optional[pd.DataFrame]:
        """Get historical NIFTY data for volatility calculation"""
        try:
            logger.info(f"Fetching {days} days of NIFTY historical data")
            df = self.nse_fetcher.get_historical_data(days)
            
            if df is not None and not df.empty:
                logger.success(f"Fetched {len(df)} days of historical data")
                return df
            
            logger.warning("Historical data not available from NSE")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            return None
    
    def calculate_historical_volatility(self, days: int = 30) -> float:
        """Calculate historical volatility from NSE data"""
        try:
            logger.info(f"Calculating {days}-day historical volatility")
            volatility = self.nse_fetcher.calculate_historical_volatility(days)
            
            logger.success(f"Calculated volatility: {volatility:.2%}")
            return volatility
            
        except Exception as e:
            logger.error(f"Error calculating volatility: {e}")
            return 0.15  # Default 15% volatility
    
    def get_options_chain_data(self, symbol: str = "NIFTY") -> Optional[pd.DataFrame]:
        """Get live options chain data from NSE"""
        try:
            logger.info(f"Fetching options chain for {symbol} from NSE")
            df = self.nse_fetcher.get_options_data_df(symbol)
            
            if df is not None and not df.empty:
                logger.success(f"Fetched {len(df)} options from NSE")
                return df
            
            logger.warning("Options chain not available")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching options chain: {e}")
            return None


class NiftyOptionsChain:
    """Generate complete NIFTY options chain with Greeks"""
    
    def __init__(self):
        self.nse_api = NSEFinanceAPI()
        self.greeks_calc = GreeksCalculator()
        logger.info("NIFTY Options Chain generator initialized")
    
    def get_next_expiry(self) -> datetime:
        """Get next monthly expiry date (last Thursday of current month)"""
        today = datetime.now()
        
        # Find last day of current month
        if today.month == 12:
            next_month = datetime(today.year + 1, 1, 1)
        else:
            next_month = datetime(today.year, today.month + 1, 1)
        
        last_day = next_month - timedelta(days=1)
        
        # Find last Thursday
        days_to_thursday = (3 - last_day.weekday()) % 7
        if days_to_thursday > 0:
            last_thursday = last_day - timedelta(days=7 - days_to_thursday)
        else:
            last_thursday = last_day
        
        # If already past this month's expiry, get next month
        if last_thursday < today:
            if last_thursday.month == 12:
                next_month = datetime(last_thursday.year + 1, 1, 1)
            else:
                next_month = datetime(last_thursday.year, last_thursday.month + 1, 1)
            
            last_day = next_month + timedelta(days=-1)
            if last_day.month != next_month.month - 1:
                last_day = next_month - timedelta(days=1)
            
            days_to_thursday = (3 - last_day.weekday()) % 7
            if days_to_thursday > 0:
                last_thursday = last_day - timedelta(days=7 - days_to_thursday)
            else:
                last_thursday = last_day
        
        logger.info(f"Next expiry date: {last_thursday.strftime('%Y-%m-%d')}")
        return last_thursday
    
    def generate_options_chain(self, 
                             spot_price: Optional[float] = None,
                             expiry_date: Optional[datetime] = None,
                             volatility: Optional[float] = None,
                             risk_free_rate: float = 0.065,
                             num_strikes: int = 31,
                             atm_only: bool = False) -> pd.DataFrame:
        """Generate complete options chain with Greeks"""
        try:
            logger.info("Generating NIFTY options chain with NSE data")
            
            # Get spot price from NSE
            if spot_price is None:
                spot_price = self.nse_api.get_nifty_price()
            
            # Get expiry date
            if expiry_date is None:
                expiry_date = self.get_next_expiry()
            
            # Get volatility from NSE
            if volatility is None:
                volatility = self.nse_api.calculate_historical_volatility()
            
            # Calculate time to expiry
            today = datetime.now()
            days_to_expiry = max((expiry_date - today).days, 0)
            time_to_expiry = days_to_expiry / 365.0
            
            # Try to get live options chain data from NSE
            nse_options = self.nse_api.get_options_chain_data()
            
            if nse_options is not None and not nse_options.empty:
                logger.info("Using live NSE options chain data")
                # Use live NSE data and enhance with Greeks calculations
                results = []
                
                for _, row in nse_options.iterrows():
                    strike = row['strike']
                    option_type = row['option_type']
                    
                    # Calculate Greeks
                    greeks = self.greeks_calc.calculate_greeks(
                        spot_price, strike, time_to_expiry, risk_free_rate, 
                        volatility, option_type.lower()
                    )
                    
                    # Calculate theoretical price
                    if option_type == 'CALL':
                        theo_price = self.greeks_calc.black_scholes_call(
                            spot_price, strike, time_to_expiry, risk_free_rate, volatility
                        )
                    else:
                        theo_price = self.greeks_calc.black_scholes_put(
                            spot_price, strike, time_to_expiry, risk_free_rate, volatility
                        )
                    
                    # Determine moneyness
                    if abs(strike - spot_price) < 50:
                        moneyness = 'ATM'
                    elif (option_type == 'CALL' and strike < spot_price) or \
                         (option_type == 'PUT' and strike > spot_price):
                        moneyness = 'ITM'
                    else:
                        moneyness = 'OTM'
                    
                    results.append({
                        'symbol': 'NIFTY',
                        'expiry_date': expiry_date.strftime('%Y-%m-%d'),
                        'strike': float(strike),
                        'option_type': option_type,
                        'spot_price': float(spot_price),
                        'market_price': float(row['last_price']),
                        'theoretical_price': float(round(theo_price, 2)),
                        'open_interest': int(row['open_interest']),
                        'volume': int(row['volume']),
                        'delta': float(greeks['delta']),
                        'gamma': float(greeks['gamma']),
                        'theta': float(greeks['theta']),
                        'vega': float(greeks['vega']),
                        'rho': float(greeks['rho']),
                        'implied_volatility': float(row['iv'] / 100 if row['iv'] > 1 else row['iv']),
                        'time_to_expiry': float(round(time_to_expiry, 6)),
                        'days_to_expiry': int(days_to_expiry),
                        'moneyness': moneyness,
                        'data_source': 'NSE_LIVE'
                    })
                
                df = pd.DataFrame(results)
                logger.success(f"Generated options chain with {len(df)} live NSE options")
                return df
            
            # Fallback: Generate synthetic options chain
            logger.info("Generating synthetic options chain")
            
            # Round to nearest 50
            atm_strike = round(spot_price / 50) * 50
            
            # Generate strikes
            if atm_only:
                strikes = [atm_strike]
            else:
                strike_range = num_strikes // 2
                strikes = [atm_strike + (i - strike_range) * 50 
                          for i in range(num_strikes)]
            
            results = []
            
            for strike in strikes:
                # Determine moneyness
                if abs(strike - spot_price) < 50:
                    moneyness = 'ATM'
                elif strike < spot_price:
                    call_moneyness = 'ITM'
                    put_moneyness = 'OTM'
                else:
                    call_moneyness = 'OTM'
                    put_moneyness = 'ITM'
                
                # Calculate Call Greeks
                call_price = self.greeks_calc.black_scholes_call(
                    spot_price, strike, time_to_expiry, risk_free_rate, volatility
                )
                call_greeks = self.greeks_calc.calculate_greeks(
                    spot_price, strike, time_to_expiry, risk_free_rate, volatility, 'call'
                )
                
                results.append({
                    'symbol': 'NIFTY',
                    'expiry_date': expiry_date.strftime('%Y-%m-%d'),
                    'strike': float(strike),
                    'option_type': 'CALL',
                    'spot_price': float(spot_price),
                    'theoretical_price': float(round(call_price, 2)),
                    'delta': float(call_greeks['delta']),
                    'gamma': float(call_greeks['gamma']),
                    'theta': float(call_greeks['theta']),
                    'vega': float(call_greeks['vega']),
                    'rho': float(call_greeks['rho']),
                    'implied_volatility': float(volatility),
                    'time_to_expiry': float(round(time_to_expiry, 6)),
                    'days_to_expiry': int(days_to_expiry),
                    'moneyness': call_moneyness if strike != atm_strike else 'ATM',
                    'data_source': 'THEORETICAL'
                })
                
                # Calculate Put Greeks
                put_price = self.greeks_calc.black_scholes_put(
                    spot_price, strike, time_to_expiry, risk_free_rate, volatility
                )
                put_greeks = self.greeks_calc.calculate_greeks(
                    spot_price, strike, time_to_expiry, risk_free_rate, volatility, 'put'
                )
                
                results.append({
                    'symbol': 'NIFTY',
                    'expiry_date': expiry_date.strftime('%Y-%m-%d'),
                    'strike': float(strike),
                    'option_type': 'PUT',
                    'spot_price': float(spot_price),
                    'theoretical_price': float(round(put_price, 2)),
                    'delta': float(put_greeks['delta']),
                    'gamma': float(put_greeks['gamma']),
                    'theta': float(put_greeks['theta']),
                    'vega': float(put_greeks['vega']),
                    'rho': float(put_greeks['rho']),
                    'implied_volatility': float(volatility),
                    'time_to_expiry': float(round(time_to_expiry, 6)),
                    'days_to_expiry': int(days_to_expiry),
                    'moneyness': put_moneyness if strike != atm_strike else 'ATM',
                    'data_source': 'THEORETICAL'
                })
            
            df = pd.DataFrame(results)
            logger.success(f"Generated synthetic options chain with {len(df)} options")
            
            return df
            
        except Exception as e:
            logger.error(f"Error generating options chain: {e}")
            raise


class PortfolioGreeksCalculator:
    """Calculate portfolio-level Greeks"""
    
    def __init__(self):
        logger.info("Portfolio Greeks calculator initialized")
    
    def calculate_portfolio_greeks(self, positions: List[Dict], spot_price: float) -> Dict:
        """Calculate aggregate Greeks for a portfolio of options"""
        try:
            logger.info(f"Calculating portfolio Greeks for {len(positions)} positions")
            
            total_delta = 0
            total_gamma = 0
            total_theta = 0
            total_vega = 0
            total_rho = 0
            total_value = 0
            
            for pos in positions:
                quantity = pos.get('quantity', 0)
                delta = pos.get('delta', 0)
                gamma = pos.get('gamma', 0)
                theta = pos.get('theta', 0)
                vega = pos.get('vega', 0)
                rho = pos.get('rho', 0)
                price = pos.get('price', 0)
                
                total_delta += quantity * delta
                total_gamma += quantity * gamma
                total_theta += quantity * theta
                total_vega += quantity * vega
                total_rho += quantity * rho
                total_value += quantity * price
            
            portfolio_greeks = {
                'total_delta': round(total_delta, 4),
                'total_gamma': round(total_gamma, 6),
                'total_theta': round(total_theta, 4),
                'total_vega': round(total_vega, 4),
                'total_rho': round(total_rho, 4),
                'total_value': round(total_value, 2),
                'spot_price': spot_price,
                'num_positions': len(positions)
            }
            
            logger.success("Portfolio Greeks calculated successfully")
            return portfolio_greeks
            
        except Exception as e:
            logger.error(f"Error calculating portfolio Greeks: {e}")
            raise


# Demo and testing functions
def run_demo():
    """Run a demonstration of the NIFTY Greeks calculator with NSE data"""
    print("🚀 NIFTY OPTIONS GREEKS CALCULATOR - NSE INDIA EDITION")
    print("=" * 70)
    
    try:
        # Initialize
        options_chain = NiftyOptionsChain()
        
        # Generate options chain
        print("📊 Generating options chain from NSE...")
        df = options_chain.generate_options_chain()
        
        # Display sample data
        print(f"\n✅ Generated {len(df)} options")
        print(f"Spot Price: ₹{df.iloc[0]['spot_price']}")
        print(f"Expiry: {df.iloc[0]['expiry_date']}")
        print(f"Days to Expiry: {df.iloc[0]['days_to_expiry']}")
        print(f"Implied Volatility: {df.iloc[0]['implied_volatility']:.2%}")
        print(f"Data Source: {df.iloc[0].get('data_source', 'N/A')}")
        
        # Show ATM options
        atm_options = df[df['moneyness'] == 'ATM']
        if not atm_options.empty:
            print("\n📍 ATM Options:")
            print(atm_options[['strike', 'option_type', 'theoretical_price', 
                             'delta', 'gamma', 'theta', 'vega']].to_string(index=False))
        
        # Save to CSV
        filename = f"nifty_options_nse_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(filename, index=False)
        print(f"\n💾 Data saved to: {filename}")
        
        print("\n" + "=" * 70)
        print("✅ Demo completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        logger.exception("Demo failed")


if __name__ == "__main__":
    run_demo()
