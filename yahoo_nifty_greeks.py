"""
NIFTY Options Greeks Calculator with Yahoo Finance Data
Complete implementation using free Yahoo Finance API for real-time data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import json
from scipy.stats import norm
import warnings
from typing import Dict, List, Optional, Tuple, Union
from loguru import logger
import time

warnings.filterwarnings('ignore')

# Configure logging
logger.add(
    "logs/yahoo_nifty_greeks.log",
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
    def calculate_implied_volatility(option_price: float, S: float, K: float, T: float, r: float, option_type: str = 'call') -> float:
        """Calculate implied volatility using Newton-Raphson method"""
        if T <= 0:
            return 0.0
            
        # Initial guess
        sigma = 0.2
        tolerance = 1e-6
        max_iterations = 100
        
        for i in range(max_iterations):
            if option_type.lower() == 'call':
                price = GreeksCalculator.black_scholes_call(S, K, T, r, sigma)
            else:
                price = GreeksCalculator.black_scholes_put(S, K, T, r, sigma)
            
            # Calculate vega for Newton-Raphson
            d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            vega = S * norm.pdf(d1) * np.sqrt(T)
            
            if abs(vega) < 1e-10:
                break
                
            price_diff = price - option_price
            if abs(price_diff) < tolerance:
                return round(sigma, 6)
                
            sigma = sigma - price_diff / vega
            sigma = max(0.001, min(sigma, 5.0))  # Keep sigma within reasonable bounds
            
        return round(sigma, 6)

class YahooFinanceAPI:
    """Yahoo Finance API client for NIFTY data"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        logger.info("Yahoo Finance API client initialized")
    
    def get_nifty_price(self) -> Optional[float]:
        """Get current NIFTY 50 price from Yahoo Finance"""
        try:
            logger.info("Fetching NIFTY price from Yahoo Finance")
            url = "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'chart' in data and data['chart']['result']:
                result = data['chart']['result'][0]
                price = result['meta']['regularMarketPrice']
                
                logger.success(f"Successfully fetched NIFTY price: {price}")
                return float(price)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching NIFTY price: {e}")
        except Exception as e:
            logger.error(f"Error fetching NIFTY price: {e}")
        
        return None
    
    def get_nifty_historical_data(self, days: int = 30) -> Optional[pd.DataFrame]:
        """Get historical NIFTY data for volatility calculation"""
        try:
            logger.info(f"Fetching {days} days of NIFTY historical data")
            
            end_time = int(time.time())
            start_time = end_time - (days * 24 * 60 * 60)
            
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI?period1={start_time}&period2={end_time}&interval=1d"
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if 'chart' in data and data['chart']['result']:
                result = data['chart']['result'][0]
                timestamps = result['timestamp']
                quotes = result['indicators']['quote'][0]
                
                df = pd.DataFrame({
                    'timestamp': timestamps,
                    'open': quotes['open'],
                    'high': quotes['high'],
                    'low': quotes['low'],
                    'close': quotes['close'],
                    'volume': quotes['volume']
                })
                
                df['date'] = pd.to_datetime(df['timestamp'], unit='s')
                df = df.dropna()
                
                logger.success(f"Fetched {len(df)} days of historical data")
                return df
                
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
        
        return None
    
    def calculate_historical_volatility(self, days: int = 30) -> float:
        """Calculate historical volatility from price data"""
        try:
            df = self.get_nifty_historical_data(days)
            if df is None or len(df) < 2:
                logger.warning("Insufficient data for volatility calculation, using default")
                return 0.15
            
            # Calculate daily returns
            df['returns'] = np.log(df['close'] / df['close'].shift(1))
            daily_vol = df['returns'].std()
            
            # Annualize volatility (252 trading days)
            annual_vol = daily_vol * np.sqrt(252)
            
            logger.info(f"Calculated historical volatility: {annual_vol:.4f}")
            return round(annual_vol, 6)
            
        except Exception as e:
            logger.error(f"Error calculating volatility: {e}")
            return 0.15

class NiftyOptionsChain:
    """Generate complete NIFTY options chain with Greeks"""
    
    def __init__(self):
        self.yahoo_api = YahooFinanceAPI()
        self.greeks_calc = GreeksCalculator()
        logger.info("NIFTY Options Chain generator initialized")
    
    def get_next_expiry(self) -> datetime:
        """Get next Thursday (typical NIFTY expiry)"""
        today = datetime.now()
        days_ahead = 3 - today.weekday()  # Thursday is 3
        if days_ahead <= 0:
            days_ahead += 7
        return today + timedelta(days=days_ahead)
    
    def get_weekly_expiry_dates(self, num_weeks: int = 4) -> List[datetime]:
        """Get next few weekly expiry dates"""
        expiries = []
        current_expiry = self.get_next_expiry()
        
        for i in range(num_weeks):
            expiries.append(current_expiry + timedelta(weeks=i))
        
        return expiries
    
    def generate_strike_prices(self, spot_price: float, num_strikes: int = 31, atm_only: bool = False) -> List[float]:
        """Generate strike prices around spot price"""
        # Round to nearest 50
        base_strike = round(spot_price / 50) * 50
        
        if atm_only:
            # Generate only 5 strikes above and 5 below ATM (11 total including ATM)
            strikes = []
            for i in range(-5, 6):  # -5 to +5 inclusive = 11 strikes
                strikes.append(base_strike + (i * 50))
        else:
            # Generate strikes ±15 from ATM (default behavior)
            half_strikes = num_strikes // 2
            strikes = []
            for i in range(-half_strikes, half_strikes + 1):
                strikes.append(base_strike + (i * 50))
        
        return sorted(strikes)
    
    def generate_options_chain(self, 
                             spot_price: Optional[float] = None,
                             expiry_date: Optional[datetime] = None,
                             volatility: Optional[float] = None,
                             risk_free_rate: float = 0.065,
                             num_strikes: int = 31,
                             atm_only: bool = False) -> pd.DataFrame:
        """Generate complete options chain with Greeks"""
        
        logger.info("Generating NIFTY options chain")
        
        # Get spot price
        if spot_price is None:
            spot_price = self.yahoo_api.get_nifty_price()
            if spot_price is None:
                logger.error("Could not fetch spot price")
                raise ValueError("Could not fetch current NIFTY price")
        
        # Get expiry date
        if expiry_date is None:
            expiry_date = self.get_next_expiry()
        
        # Calculate or use provided volatility
        if volatility is None:
            volatility = self.yahoo_api.calculate_historical_volatility()
        
        # Calculate time to expiry
        time_to_expiry = max((expiry_date - datetime.now()).days, 1) / 365.0
        
        # Generate strikes
        strikes = self.generate_strike_prices(spot_price, num_strikes, atm_only)
        
        results = []
        
        logger.info(f"Calculating Greeks for {len(strikes)} strikes")
        
        for strike in strikes:
            # Calculate for Call
            call_price = self.greeks_calc.black_scholes_call(
                spot_price, strike, time_to_expiry, risk_free_rate, volatility
            )
            call_greeks = self.greeks_calc.calculate_greeks(
                spot_price, strike, time_to_expiry, risk_free_rate, volatility, 'call'
            )
            
            # Calculate for Put  
            put_price = self.greeks_calc.black_scholes_put(
                spot_price, strike, time_to_expiry, risk_free_rate, volatility
            )
            put_greeks = self.greeks_calc.calculate_greeks(
                spot_price, strike, time_to_expiry, risk_free_rate, volatility, 'put'
            )
            
            # Determine moneyness
            if abs(strike - spot_price) <= 25:  # Within ±25 points
                moneyness = 'ATM'
            elif strike < spot_price:
                moneyness = 'ITM' if 'call' else 'OTM'
            else:
                moneyness = 'OTM' if 'call' else 'ITM'
            
            # Add Call data
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
                'days_to_expiry': int(max(1, (expiry_date - datetime.now()).days)),
                'moneyness': 'ITM' if strike < spot_price else ('ATM' if abs(strike - spot_price) <= 25 else 'OTM'),
                'intrinsic_value': float(max(spot_price - strike, 0)),
                'time_value': float(max(call_price - max(spot_price - strike, 0), 0))
            })
            
            # Add Put data
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
                'days_to_expiry': int(max(1, (expiry_date - datetime.now()).days)),
                'moneyness': 'ITM' if strike > spot_price else ('ATM' if abs(strike - spot_price) <= 25 else 'OTM'),
                'intrinsic_value': float(max(strike - spot_price, 0)),
                'time_value': float(max(put_price - max(strike - spot_price, 0), 0))
            })
        
        df = pd.DataFrame(results)
        logger.success(f"Generated options chain with {len(df)} options")
        
        return df
    
    def analyze_options_chain(self, df: pd.DataFrame) -> Dict:
        """Analyze options chain and return key metrics"""
        try:
            if df.empty:
                return {}
                
            analysis = {
                'spot_price': float(df.iloc[0]['spot_price']),
                'expiry_date': str(df.iloc[0]['expiry_date']),
                'days_to_expiry': int(df.iloc[0]['days_to_expiry']),
                'implied_volatility': float(df.iloc[0]['implied_volatility']),
                'total_options': int(len(df)),
                'total_calls': int(len(df[df['option_type'] == 'CALL'])),
                'total_puts': int(len(df[df['option_type'] == 'PUT']))
            }
            
            # ATM analysis
            atm_options = df[df['moneyness'] == 'ATM']
            if not atm_options.empty:
                atm_calls = atm_options[atm_options['option_type'] == 'CALL']
                atm_puts = atm_options[atm_options['option_type'] == 'PUT']
                
                if not atm_calls.empty and not atm_puts.empty:
                    atm_call = atm_calls.iloc[0]
                    atm_put = atm_puts.iloc[0]
                    
                    analysis['atm_strike'] = float(atm_call['strike'])
                    analysis['atm_call_price'] = float(atm_call['theoretical_price'])
                    analysis['atm_put_price'] = float(atm_put['theoretical_price'])
                    analysis['atm_call_delta'] = float(atm_call['delta'])
                    analysis['atm_put_delta'] = float(atm_put['delta'])
                    analysis['atm_gamma'] = float(atm_call['gamma'])
                    analysis['atm_vega'] = float(atm_call['vega'])
            
            # Greeks extremes
            if not df.empty:
                max_gamma_idx = df['gamma'].idxmax()
                analysis['max_gamma'] = {
                    'value': float(df.loc[max_gamma_idx, 'gamma']),
                    'strike': float(df.loc[max_gamma_idx, 'strike']),
                    'option_type': str(df.loc[max_gamma_idx, 'option_type'])
                }
                
                min_theta_idx = df['theta'].idxmin()
                analysis['min_theta'] = {
                    'value': float(df.loc[min_theta_idx, 'theta']),
                    'strike': float(df.loc[min_theta_idx, 'strike']),
                    'option_type': str(df.loc[min_theta_idx, 'option_type'])
                }
                
                max_vega_idx = df['vega'].idxmax()
                analysis['max_vega'] = {
                    'value': float(df.loc[max_vega_idx, 'vega']),
                    'strike': float(df.loc[max_vega_idx, 'strike']),
                    'option_type': str(df.loc[max_vega_idx, 'option_type'])
                }
                
                # Price ranges
                calls = df[df['option_type'] == 'CALL']
                puts = df[df['option_type'] == 'PUT']
                
                if not calls.empty:
                    analysis['call_price_range'] = {
                        'min': float(calls['theoretical_price'].min()),
                        'max': float(calls['theoretical_price'].max()),
                        'avg': float(calls['theoretical_price'].mean())
                    }
                
                if not puts.empty:
                    analysis['put_price_range'] = {
                        'min': float(puts['theoretical_price'].min()),
                        'max': float(puts['theoretical_price'].max()),
                        'avg': float(puts['theoretical_price'].mean())
                    }
            
            logger.info("Options chain analysis completed")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing options chain: {e}")
            return {}

class PortfolioGreeksCalculator:
    """Calculate portfolio-level Greeks"""
    
    def __init__(self):
        self.greeks_calc = GreeksCalculator()
        logger.info("Portfolio Greeks calculator initialized")
    
    def calculate_portfolio_greeks(self, positions: List[Dict], spot_price: float) -> Dict:
        """Calculate aggregate Greeks for a portfolio of options"""
        portfolio_greeks = {
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0,
            'total_positions': len(positions),
            'net_premium': 0.0
        }
        
        position_details = []
        
        for pos in positions:
            try:
                # Extract position details
                strike = pos['strike']
                quantity = pos['quantity']
                option_type = pos['option_type'].lower()
                days_to_expiry = pos.get('days_to_expiry', 30)
                volatility = pos.get('volatility', 0.20)
                risk_free_rate = pos.get('risk_free_rate', 0.065)
                
                time_to_expiry = days_to_expiry / 365.0
                
                # Calculate option price and Greeks
                if option_type == 'call':
                    option_price = self.greeks_calc.black_scholes_call(
                        spot_price, strike, time_to_expiry, risk_free_rate, volatility
                    )
                else:
                    option_price = self.greeks_calc.black_scholes_put(
                        spot_price, strike, time_to_expiry, risk_free_rate, volatility
                    )
                
                greeks = self.greeks_calc.calculate_greeks(
                    spot_price, strike, time_to_expiry, risk_free_rate, volatility, option_type
                )
                
                # Calculate position-level Greeks (quantity-weighted)
                position_delta = greeks['delta'] * quantity
                position_gamma = greeks['gamma'] * quantity
                position_theta = greeks['theta'] * quantity
                position_vega = greeks['vega'] * quantity
                position_rho = greeks['rho'] * quantity
                position_premium = option_price * quantity
                
                # Add to portfolio totals
                portfolio_greeks['delta'] += position_delta
                portfolio_greeks['gamma'] += position_gamma
                portfolio_greeks['theta'] += position_theta
                portfolio_greeks['vega'] += position_vega
                portfolio_greeks['rho'] += position_rho
                portfolio_greeks['net_premium'] += position_premium
                
                # Store position details
                position_details.append({
                    'strike': float(strike),
                    'option_type': option_type.upper(),
                    'quantity': int(quantity),
                    'option_price': float(round(option_price, 2)),
                    'position_value': float(round(position_premium, 2)),
                    'delta': float(round(position_delta, 6)),
                    'gamma': float(round(position_gamma, 8)),
                    'theta': float(round(position_theta, 6)),
                    'vega': float(round(position_vega, 6)),
                    'rho': float(round(position_rho, 6))
                })
                
            except Exception as e:
                logger.error(f"Error calculating Greeks for position {pos}: {e}")
                continue
        
        # Round portfolio Greeks
        for greek in ['delta', 'gamma', 'theta', 'vega', 'rho', 'net_premium']:
            portfolio_greeks[greek] = float(round(portfolio_greeks[greek], 6))
        
        # Ensure all other values are also Python native types
        portfolio_greeks['total_positions'] = int(portfolio_greeks['total_positions'])
        
        result = {
            'portfolio_greeks': portfolio_greeks,
            'position_details': position_details,
            'spot_price': float(spot_price),
            'calculation_time': datetime.now().isoformat()
        }
        
        logger.info(f"Calculated portfolio Greeks for {len(positions)} positions")
        return result

# Demo and testing functions
def run_demo():
    """Run a demonstration of the NIFTY Greeks calculator"""
    print("🚀 NIFTY OPTIONS GREEKS CALCULATOR - YAHOO FINANCE EDITION")
    print("=" * 70)
    
    try:
        # Initialize
        options_chain = NiftyOptionsChain()
        
        # Generate options chain
        print("📊 Generating options chain...")
        df = options_chain.generate_options_chain()
        
        # Display sample data
        print(f"\n✅ Generated {len(df)} options")
        print(f"Spot Price: ₹{df.iloc[0]['spot_price']}")
        print(f"Expiry: {df.iloc[0]['expiry_date']}")
        print(f"Days to Expiry: {df.iloc[0]['days_to_expiry']}")
        print(f"Implied Volatility: {df.iloc[0]['implied_volatility']:.2%}")
        
        # Show ATM options
        atm_options = df[df['moneyness'] == 'ATM']
        if not atm_options.empty:
            print("\n🎯 ATM Options:")
            print(atm_options[['strike', 'option_type', 'theoretical_price', 'delta', 'gamma', 'theta', 'vega']].to_string(index=False))
        
        # Analyze chain
        print("\n📈 Analyzing options chain...")
        analysis = options_chain.analyze_options_chain(df)
        
        print(f"\nATM Strike: {analysis.get('atm_strike', 'N/A')}")
        print(f"Max Gamma: {analysis.get('max_gamma', {}).get('value', 'N/A')} at {analysis.get('max_gamma', {}).get('strike', 'N/A')} {analysis.get('max_gamma', {}).get('option_type', 'N/A')}")
        print(f"Min Theta: {analysis.get('min_theta', {}).get('value', 'N/A')} at {analysis.get('min_theta', {}).get('strike', 'N/A')} {analysis.get('min_theta', {}).get('option_type', 'N/A')}")
        
        # Save to CSV
        filename = f"nifty_options_yahoo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(filename, index=False)
        print(f"\n💾 Data saved to: {filename}")
        
        return df
        
    except Exception as e:
        logger.error(f"Demo error: {e}")
        print(f"❌ Error running demo: {e}")
        return None

if __name__ == "__main__":
    run_demo()
