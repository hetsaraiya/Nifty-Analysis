"""
Enhanced NIFTY Options Greeks Calculator and Live Data Fetcher
Integrates with the existing Angel One SmartAPI for real-time options analysis
"""

import requests
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import math
from scipy.stats import norm
import warnings
from loguru import logger
from typing import Dict, List, Tuple, Optional, Union
from config import config
import os

warnings.filterwarnings('ignore')

# Configure Loguru for the Greeks calculator
logger.add(
    "logs/greeks_calculator.log",
    rotation="1 day",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)
logger.add(
    "logs/angel_one_api.log",  # Separate log for Angel One API calls
    rotation="1 day",
    retention="30 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
    filter=lambda record: "angel" in record["name"].lower() or "api" in record.get("extra", {}).get("context", "").lower()
)

class EnhancedAngelSmartAPI:
    """Enhanced Angel One SmartAPI client with comprehensive options data fetching and Loguru logging"""
    
    def __init__(self, api_key=None, secret_key=None):
        # Use provided keys or fall back to config
        env = os.environ.get('FLASK_ENV', 'development')
        app_config = config[env]
        
        self.api_key = api_key or app_config.ANGEL_ONE_API_KEY
        self.secret_key = secret_key or app_config.ANGEL_ONE_SECRET_KEY
        self.base_url = app_config.ANGEL_ONE_BASE_URL
        
        self.access_token = None
        self.refresh_token = None
        self.client_code = None
        self.session = requests.Session()
        
        logger.info("Enhanced Angel SmartAPI client initialized")
        logger.debug(f"Base URL: {self.base_url}")
        logger.debug(f"API Key configured: {bool(self.api_key)}")
        
    def login(self, client_code, password, totp):
        """Login to Angel Smart API with provided credentials and comprehensive logging"""
        logger.info("Initiating Angel One login process")
        logger.debug(f"Client code: {client_code[:4]}****")
        logger.debug(f"TOTP length: {len(totp)} characters")
        
        url = f"{self.base_url}/rest/auth/angelbroking/user/v1/loginByPassword"
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-UserType': 'USER',
            'X-SourceID': 'WEB',
            'X-ClientLocalIP': '192.168.1.1',
            'X-ClientPublicIP': '106.193.147.98',
            'X-MACAddress': '00:00:00:00:00:00',
            'X-PrivateKey': self.api_key
        }
        
        payload = {
            "clientcode": client_code,
            "password": password,
            "totp": totp
        }
        
        try:
            logger.debug("Sending login request to Angel One API")
            start_time = time.time()
            
            response = self.session.post(url, headers=headers, json=payload, timeout=15)
            
            request_duration = time.time() - start_time
            logger.debug(f"Login request completed in {request_duration:.2f}s")
            logger.debug(f"Response status: {response.status_code}")
            
            data = response.json()
            
            if data.get('status'):
                self.access_token = data['data']['jwtToken']
                self.refresh_token = data['data']['refreshToken']
                self.client_code = client_code
                
                # Update session headers
                self.session.headers.update({
                    'Authorization': f'Bearer {self.access_token}'
                })
                
                logger.success("Angel One login successful!")
                logger.info(f"JWT token obtained (length: {len(self.access_token)})")
                logger.debug(f"Refresh token available: {bool(self.refresh_token)}")
                return True
            else:
                error_msg = data.get('message', 'Unknown error')
                logger.error(f"Angel One login failed: {error_msg}")
                logger.debug(f"Full response data: {data}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("Angel One login request timed out")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("Angel One login connection error - check network")
            return False
        except Exception as e:
            logger.error(f"Angel One login error: {str(e)}")
            logger.exception("Full traceback for login error")
            return False
    
    def get_headers(self):
        """Get common headers for API requests"""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-UserType': 'USER',
            'X-SourceID': 'WEB',
            'X-ClientLocalIP': '192.168.1.1',
            'X-ClientPublicIP': '106.193.147.98',
            'X-MACAddress': '00:00:00:00:00:00',
            'X-PrivateKey': self.api_key
        }
    
    def get_ltp(self, exchange, symbol, token):
        """Get Last Traded Price with detailed logging"""
        logger.debug(f"Fetching LTP for {exchange}:{symbol} (token: {token})")
        
        url = f"{self.base_url}/rest/secure/angelbroking/order/v1/getLTP"
        
        payload = {
            "exchange": exchange,
            "tradingsymbol": symbol,
            "symboltoken": token
        }
        
        try:
            start_time = time.time()
            response = self.session.post(url, headers=self.get_headers(), json=payload, timeout=10)
            request_duration = time.time() - start_time
            
            logger.debug(f"LTP request completed in {request_duration:.2f}s")
            
            data = response.json()
            
            if data.get('status'):
                ltp = float(data['data']['ltp'])
                logger.success(f"LTP fetched successfully: {ltp}")
                return ltp
            else:
                logger.warning(f"LTP fetch failed: {data.get('message')}")
                return None
                
        except Exception as e:
            logger.error(f"LTP fetch error for {symbol}: {str(e)}")
            return None
    
    def search_scrip(self, exchange, symbol):
        """Search for scrip details with logging"""
        logger.debug(f"Searching scrip: {exchange}:{symbol}")
        
        url = f"{self.base_url}/rest/secure/angelbroking/order/v1/searchscrip"
        
        payload = {
            "exchange": exchange,
            "searchscrip": symbol
        }
        
        try:
            response = self.session.post(url, headers=self.get_headers(), json=payload, timeout=10)
            data = response.json()
            
            if data.get('status'):
                results = data['data']
                logger.success(f"Scrip search successful: found {len(results)} results")
                return results
            else:
                logger.warning(f"Scrip search failed: {data.get('message')}")
                return None
                
        except Exception as e:
            logger.error(f"Scrip search error for {symbol}: {str(e)}")
            return None
    
    def get_candle_data(self, exchange, symbol, token, interval, from_date, to_date):
        """Get historical candle data with comprehensive logging"""
        logger.info(f"Fetching candle data for {exchange}:{symbol}")
        logger.debug(f"Parameters - Token: {token}, Interval: {interval}, From: {from_date}, To: {to_date}")
        
        url = f"{self.base_url}/rest/secure/angelbroking/historical/v1/getCandleData"
        
        payload = {
            "exchange": exchange,
            "symboltoken": token,
            "interval": interval,
            "fromdate": from_date,
            "todate": to_date
        }
        
        try:
            start_time = time.time()
            response = self.session.post(url, headers=self.get_headers(), json=payload, timeout=15)
            request_duration = time.time() - start_time
            
            logger.debug(f"Candle data request completed in {request_duration:.2f}s")
            
            data = response.json()
            
            if data.get('status'):
                candle_data = data['data']
                logger.success(f"Candle data fetched successfully: {len(candle_data)} candles")
                return candle_data
            else:
                logger.warning(f"Candle data fetch failed: {data.get('message')}")
                return None
                
        except Exception as e:
            logger.error(f"Candle data fetch error for {symbol}: {str(e)}")
            return None

class AdvancedGreeksCalculator:
    """Advanced Greeks calculator with multiple models and risk metrics"""
    
    @staticmethod
    def black_scholes_call(S, K, T, r, sigma, q=0):
        """Calculate Black-Scholes call option price with dividend yield"""
        if T <= 0:
            return max(S - K, 0)
        
        try:
            d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            
            call_price = S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
            return max(call_price, 0)
        except Exception as e:
            logger.error(f"Error in Black-Scholes call calculation: {str(e)}")
            return max(S - K, 0)
    
    @staticmethod
    def black_scholes_put(S, K, T, r, sigma, q=0):
        """Calculate Black-Scholes put option price with dividend yield"""
        if T <= 0:
            return max(K - S, 0)
        
        try:
            d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            
            put_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)
            return max(put_price, 0)
        except Exception as e:
            logger.error(f"Error in Black-Scholes put calculation: {str(e)}")
            return max(K - S, 0)
    
    @staticmethod
    def calculate_greeks(S, K, T, r, sigma, option_type='call', q=0):
        """Calculate all Greeks for an option with enhanced accuracy"""
        if T <= 0:
            if option_type.lower() == 'call':
                return {
                    'delta': 1.0 if S > K else 0.0,
                    'gamma': 0.0,
                    'theta': 0.0,
                    'vega': 0.0,
                    'rho': 0.0,
                    'vomma': 0.0,
                    'vanna': 0.0
                }
            else:
                return {
                    'delta': -1.0 if S < K else 0.0,
                    'gamma': 0.0,
                    'theta': 0.0,
                    'vega': 0.0,
                    'rho': 0.0,
                    'vomma': 0.0,
                    'vanna': 0.0
                }
        
        try:
            d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            
            # First-order Greeks
            if option_type.lower() == 'call':
                delta = np.exp(-q * T) * norm.cdf(d1)
                theta = (-S * np.exp(-q * T) * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) 
                        - r * K * np.exp(-r * T) * norm.cdf(d2) 
                        + q * S * np.exp(-q * T) * norm.cdf(d1)) / 365
                rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100
            else:  # put
                delta = -np.exp(-q * T) * norm.cdf(-d1)
                theta = (-S * np.exp(-q * T) * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) 
                        + r * K * np.exp(-r * T) * norm.cdf(-d2) 
                        - q * S * np.exp(-q * T) * norm.cdf(-d1)) / 365
                rho = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100
            
            # Second-order Greeks
            gamma = np.exp(-q * T) * norm.pdf(d1) / (S * sigma * np.sqrt(T))
            vega = S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T) / 100
            
            # Third-order Greeks (Volga/Vomma and Vanna)
            vomma = vega * (d1 * d2) / sigma  # Volga/Vomma
            vanna = -np.exp(-q * T) * norm.pdf(d1) * d2 / sigma  # Vanna
            
            return {
                'delta': float(delta),
                'gamma': float(gamma),
                'theta': float(theta),
                'vega': float(vega),
                'rho': float(rho),
                'vomma': float(vomma),
                'vanna': float(vanna)
            }
            
        except Exception as e:
            logger.error(f"Error calculating Greeks: {str(e)}")
            return {
                'delta': 0.0,
                'gamma': 0.0,
                'theta': 0.0,
                'vega': 0.0,
                'rho': 0.0,
                'vomma': 0.0,
                'vanna': 0.0
            }
    
    @staticmethod
    def implied_volatility(option_price, S, K, T, r, option_type='call', q=0, max_iterations=100):
        """Calculate implied volatility using Newton-Raphson method"""
        if T <= 0 or option_price <= 0:
            return 0.0
        
        # Initial guess
        sigma = 0.2
        
        for i in range(max_iterations):
            try:
                if option_type.lower() == 'call':
                    price = AdvancedGreeksCalculator.black_scholes_call(S, K, T, r, sigma, q)
                else:
                    price = AdvancedGreeksCalculator.black_scholes_put(S, K, T, r, sigma, q)
                
                # Calculate vega for Newton-Raphson
                d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
                vega = S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T)
                
                # Newton-Raphson iteration
                price_diff = price - option_price
                
                if abs(price_diff) < 0.001 or vega == 0:
                    break
                
                sigma = sigma - price_diff / vega
                
                # Keep sigma within reasonable bounds
                sigma = max(0.01, min(sigma, 5.0))
                
            except Exception as e:
                logger.error(f"Error in IV calculation iteration {i}: {str(e)}")
                break
        
        return max(sigma, 0.01)

class EnhancedNiftyDataFetcher:
    """Enhanced Nifty data fetcher with comprehensive Greeks and risk analysis"""
    
    def __init__(self, angel_api=None):
        self.api = angel_api or EnhancedAngelSmartAPI()
        self.greeks_calc = AdvancedGreeksCalculator()
        
        # Nifty 50 index details
        self.nifty_token = "99926000"
        self.nifty_symbol = "NIFTY 50"
        
        # Risk-free rate and other parameters
        env = os.environ.get('FLASK_ENV', 'development')
        app_config = config[env]
        self.risk_free_rate = app_config.RISK_FREE_RATE
        self.dividend_yield = app_config.DIVIDEND_YIELD
        
    def get_nifty_spot_price(self):
        """Get current Nifty spot price with logging"""
        try:
            logger.debug("Fetching Nifty 50 spot price")
            spot_price = self.api.get_ltp("NSE", self.nifty_symbol, self.nifty_token)
            if spot_price:
                logger.success(f"Nifty spot price fetched successfully: ₹{spot_price}")
            else:
                logger.warning("Failed to fetch Nifty spot price")
            return spot_price
        except Exception as e:
            logger.error(f"Error fetching Nifty spot price: {str(e)}")
            return None
    
    def get_next_expiry_date(self, base_date=None):
        """Get next Thursday expiry date"""
        if base_date is None:
            base_date = datetime.now()
        
        # Find next Thursday
        days_ahead = 3 - base_date.weekday()  # Thursday is 3
        if days_ahead <= 0:
            days_ahead += 7
        
        next_expiry = base_date + timedelta(days=days_ahead)
        
        # If it's after 3:30 PM on Thursday, move to next week
        if (base_date.weekday() == 3 and base_date.hour >= 15 and base_date.minute >= 30):
            next_expiry += timedelta(days=7)
        
        return next_expiry
    
    def get_nifty_options_chain(self, expiry_date=None):
        """Get comprehensive Nifty options chain data"""
        spot_price = self.get_nifty_spot_price()
        
        if not spot_price:
            logger.error("Cannot fetch options chain without spot price")
            return None
        
        # Generate strike prices around current spot
        strikes = []
        base_strike = round(spot_price / 50) * 50
        
        # Generate strikes from -15 to +15 (31 strikes total)
        for i in range(-15, 16):
            strikes.append(base_strike + (i * 50))
        
        return {
            'spot_price': spot_price,
            'strikes': strikes,
            'base_strike': base_strike
        }
    
    def calculate_options_greeks(self, spot_price, strike_price, expiry_date, 
                               option_type='call', volatility=0.20, market_price=None):
        """Calculate comprehensive Greeks for a specific option"""
        
        # Calculate time to expiry
        if isinstance(expiry_date, str):
            expiry = datetime.strptime(expiry_date, '%Y-%m-%d')
        else:
            expiry = expiry_date
        
        today = datetime.now()
        time_to_expiry = (expiry - today).days / 365.0
        
        if time_to_expiry <= 0:
            time_to_expiry = 1/365.0  # Minimum 1 day
        
        # Calculate theoretical price
        if option_type.lower() == 'call':
            theo_price = self.greeks_calc.black_scholes_call(
                spot_price, strike_price, time_to_expiry, 
                self.risk_free_rate, volatility, self.dividend_yield
            )
        else:
            theo_price = self.greeks_calc.black_scholes_put(
                spot_price, strike_price, time_to_expiry, 
                self.risk_free_rate, volatility, self.dividend_yield
            )
        
        # Calculate Greeks
        greeks = self.greeks_calc.calculate_greeks(
            spot_price, strike_price, time_to_expiry, 
            self.risk_free_rate, volatility, option_type, self.dividend_yield
        )
        
        # Calculate implied volatility if market price is provided
        implied_vol = None
        if market_price and market_price > 0:
            implied_vol = self.greeks_calc.implied_volatility(
                market_price, spot_price, strike_price, time_to_expiry,
                self.risk_free_rate, option_type, self.dividend_yield
            )
        
        # Calculate additional metrics
        moneyness = spot_price / strike_price if option_type.lower() == 'call' else strike_price / spot_price
        intrinsic_value = max(0, spot_price - strike_price) if option_type.lower() == 'call' else max(0, strike_price - spot_price)
        time_value = theo_price - intrinsic_value
        
        return {
            'theoretical_price': theo_price,
            'intrinsic_value': intrinsic_value,
            'time_value': time_value,
            'moneyness': moneyness,
            'implied_volatility': implied_vol,
            'input_volatility': volatility,
            'time_to_expiry': time_to_expiry,
            'greeks': greeks
        }
    
    def get_live_nifty_data_with_greeks(self, expiry_date=None, volatility=0.20, include_analytics=True):
        """Get comprehensive live Nifty data with Greeks calculations and analytics"""
        
        logger.info("Starting comprehensive live Nifty data fetch with Greeks calculations")
        logger.debug(f"Parameters - Volatility: {volatility}, Include analytics: {include_analytics}")
        
        # Get spot price and options chain
        chain_data = self.get_nifty_options_chain()
        if not chain_data:
            logger.error("Failed to fetch options chain data - aborting")
            return None
        
        spot_price = chain_data['spot_price']
        strikes = chain_data['strikes']
        
        logger.info(f"Nifty Spot Price: ₹{spot_price}")
        logger.debug(f"Generated {len(strikes)} strike prices from {min(strikes)} to {max(strikes)}")
        
        # Set default expiry if not provided
        if not expiry_date:
            expiry_date = self.get_next_expiry_date()
        
        logger.info(f"Using expiry date: {expiry_date.strftime('%Y-%m-%d')}")
        logger.debug(f"Days to expiry: {(expiry_date - datetime.now()).days}")
        
        results = []
        calculation_start = time.time()
        
        logger.info("Starting Greeks calculations for all strikes and option types")
        
        for i, strike in enumerate(strikes):
            if i % 10 == 0:  # Log progress every 10 strikes
                logger.debug(f"Processing strike {i+1}/{len(strikes)}: {strike}")
            
            # Calculate for both Call and Put
            for option_type in ['call', 'put']:
                try:
                    option_data = self.calculate_options_greeks(
                        spot_price, strike, expiry_date, option_type, volatility=volatility
                    )
                    
                    result_row = {
                        'strike': strike,
                        'option_type': option_type.upper(),
                        'spot_price': spot_price,
                        'expiry_date': expiry_date.strftime('%Y-%m-%d'),
                        'time_to_expiry_days': round(option_data['time_to_expiry'] * 365, 1),
                        'theoretical_price': round(option_data['theoretical_price'], 2),
                        'intrinsic_value': round(option_data['intrinsic_value'], 2),
                        'time_value': round(option_data['time_value'], 2),
                        'moneyness': round(option_data['moneyness'], 4),
                        'input_volatility': volatility,
                        'delta': round(option_data['greeks']['delta'], 4),
                        'gamma': round(option_data['greeks']['gamma'], 6),
                        'theta': round(option_data['greeks']['theta'], 4),
                        'vega': round(option_data['greeks']['vega'], 4),
                        'rho': round(option_data['greeks']['rho'], 4),
                        'vomma': round(option_data['greeks']['vomma'], 6),
                        'vanna': round(option_data['greeks']['vanna'], 6)
                    }
                    
                    results.append(result_row)
                    
                except Exception as e:
                    logger.warning(f"Failed to calculate Greeks for {option_type} {strike}: {str(e)}")
                    continue
        
        calculation_duration = time.time() - calculation_start
        logger.success(f"Greeks calculations completed in {calculation_duration:.2f}s")
        logger.info(f"Successfully calculated {len(results)} option Greeks")
        
        df = pd.DataFrame(results)
        
        if include_analytics:
            logger.info("Calculating portfolio analytics")
            analytics_start = time.time()
            
            try:
                analytics = self.calculate_portfolio_analytics(df, spot_price)
                analytics_duration = time.time() - analytics_start
                logger.success(f"Portfolio analytics completed in {analytics_duration:.2f}s")
            except Exception as e:
                logger.error(f"Failed to calculate portfolio analytics: {str(e)}")
                analytics = {}
            
            total_duration = time.time() - calculation_start
            logger.success(f"Complete analysis finished in {total_duration:.2f}s")
            
            return {
                'data': df,
                'analytics': analytics,
                'metadata': {
                    'spot_price': spot_price,
                    'expiry_date': expiry_date.strftime('%Y-%m-%d'),
                    'volatility_used': volatility,
                    'risk_free_rate': self.risk_free_rate,
                    'dividend_yield': self.dividend_yield,
                    'timestamp': datetime.now().isoformat(),
                    'calculation_duration': round(total_duration, 2),
                    'total_options': len(results)
                }
            }
        
        logger.success("Data fetch completed without analytics")
        return df
    
    def calculate_portfolio_analytics(self, df, spot_price):
        """Calculate portfolio-level analytics with comprehensive logging"""
        try:
            logger.debug("Starting portfolio analytics calculation")
            
            calls = df[df['option_type'] == 'CALL'].copy()
            puts = df[df['option_type'] == 'PUT'].copy()
            
            logger.debug(f"Separated data - Calls: {len(calls)}, Puts: {len(puts)}")
            
            # Find ATM strike
            atm_strike = calls.iloc[(calls['strike'] - spot_price).abs().argsort()[:1]]['strike'].iloc[0]
            logger.debug(f"ATM strike identified: {atm_strike}")
            
            # Portfolio Greeks (assuming equal weighting)
            portfolio_delta = df['delta'].mean()
            portfolio_gamma = df['gamma'].mean()
            portfolio_theta = df['theta'].sum()  # Theta is additive
            portfolio_vega = df['vega'].sum()   # Vega is additive
            
            logger.debug("Portfolio Greeks calculated")
            
            # Volatility smile analysis
            otm_calls = calls[calls['strike'] > spot_price]
            otm_puts = puts[puts['strike'] < spot_price]
            atm_call = calls[calls['strike'] == atm_strike]
            atm_put = puts[puts['strike'] == atm_strike]
            
            logger.debug(f"Volatility smile data - OTM Calls: {len(otm_calls)}, OTM Puts: {len(otm_puts)}")
            
            # Risk metrics
            max_gamma_call_strike = calls.loc[calls['gamma'].idxmax(), 'strike'] if not calls.empty else atm_strike
            max_gamma_put_strike = puts.loc[puts['gamma'].idxmax(), 'strike'] if not puts.empty else atm_strike
            
            logger.debug(f"Risk metrics - Max gamma call strike: {max_gamma_call_strike}, Max gamma put strike: {max_gamma_put_strike}")
            
            analytics = {
                'atm_strike': float(atm_strike),
                'portfolio_greeks': {
                    'delta': round(portfolio_delta, 4),
                    'gamma': round(portfolio_gamma, 6),
                    'theta': round(portfolio_theta, 2),
                    'vega': round(portfolio_vega, 2)
                },
                'risk_metrics': {
                    'max_gamma_call_strike': float(max_gamma_call_strike),
                    'max_gamma_put_strike': float(max_gamma_put_strike),
                    'gamma_exposure': round(df['gamma'].sum(), 4)
                },
                'volatility_analysis': {
                    'avg_call_vega': round(calls['vega'].mean(), 2) if not calls.empty else 0,
                    'avg_put_vega': round(puts['vega'].mean(), 2) if not puts.empty else 0,
                    'total_vega_exposure': round(df['vega'].sum(), 2)
                }
            }
            
            logger.success("Portfolio analytics calculation completed successfully")
            return analytics
            
        except Exception as e:
            logger.error(f"Error calculating portfolio analytics: {str(e)}")
            logger.exception("Full traceback for portfolio analytics error")
            return {}
    
    def display_enhanced_greeks_data(self, data):
        """Display enhanced Greeks data in a formatted way"""
        if data is None:
            print("No data to display")
            return
        
        if isinstance(data, dict) and 'data' in data:
            df = data['data']
            analytics = data.get('analytics', {})
            metadata = data.get('metadata', {})
        else:
            df = data
            analytics = {}
            metadata = {}
        
        if df is None or df.empty:
            print("No data to display")
            return
        
        print("\n" + "="*120)
        print(f"ENHANCED NIFTY OPTIONS GREEKS ANALYSIS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*120)
        
        if metadata:
            print(f"Spot Price: {metadata.get('spot_price', 'N/A')}")
            print(f"Expiry Date: {metadata.get('expiry_date', 'N/A')}")
            print(f"Volatility: {metadata.get('volatility_used', 'N/A')}%")
            print(f"Risk-free Rate: {metadata.get('risk_free_rate', 'N/A')}%")
            print()
        
        # Separate calls and puts
        calls = df[df['option_type'] == 'CALL'].copy()
        puts = df[df['option_type'] == 'PUT'].copy()
        
        print("CALL OPTIONS:")
        print("-" * 120)
        print(f"{'Strike':<8} {'Price':<8} {'IV':<6} {'Delta':<8} {'Gamma':<10} {'Theta':<8} {'Vega':<8} {'Vomma':<10} {'Vanna':<10}")
        print("-" * 120)
        
        for _, row in calls.iterrows():
            print(f"{row['strike']:<8} {row['theoretical_price']:<8} {row['moneyness']:<6.3f} "
                  f"{row['delta']:<8} {row['gamma']:<10} {row['theta']:<8} "
                  f"{row['vega']:<8} {row['vomma']:<10} {row['vanna']:<10}")
        
        print("\nPUT OPTIONS:")
        print("-" * 120)
        print(f"{'Strike':<8} {'Price':<8} {'IV':<6} {'Delta':<8} {'Gamma':<10} {'Theta':<8} {'Vega':<8} {'Vomma':<10} {'Vanna':<10}")
        print("-" * 120)
        
        for _, row in puts.iterrows():
            print(f"{row['strike']:<8} {row['theoretical_price']:<8} {row['moneyness']:<6.3f} "
                  f"{row['delta']:<8} {row['gamma']:<10} {row['theta']:<8} "
                  f"{row['vega']:<8} {row['vomma']:<10} {row['vanna']:<10}")
        
        # Display analytics if available
        if analytics:
            print("\n" + "="*60)
            print("PORTFOLIO ANALYTICS")
            print("="*60)
            
            if 'atm_strike' in analytics:
                print(f"ATM Strike: {analytics['atm_strike']}")
            
            if 'portfolio_greeks' in analytics:
                pg = analytics['portfolio_greeks']
                print(f"Portfolio Delta: {pg.get('delta', 'N/A')}")
                print(f"Portfolio Gamma: {pg.get('gamma', 'N/A')}")
                print(f"Portfolio Theta: {pg.get('theta', 'N/A')}")
                print(f"Portfolio Vega: {pg.get('vega', 'N/A')}")
            
            if 'risk_metrics' in analytics:
                rm = analytics['risk_metrics']
                print(f"Max Gamma Call Strike: {rm.get('max_gamma_call_strike', 'N/A')}")
                print(f"Max Gamma Put Strike: {rm.get('max_gamma_put_strike', 'N/A')}")
                print(f"Total Gamma Exposure: {rm.get('gamma_exposure', 'N/A')}")

def main():
    """Main function to demonstrate the enhanced Greeks calculator"""
    print("Enhanced NIFTY Options Greeks Calculator")
    print("=======================================")
    
    # Get user credentials
    client_code = input("Enter your Angel One client code: ").strip()
    password = input("Enter your Angel One password: ").strip()
    totp = input("Enter current TOTP (6-digit code): ").strip()
    
    if not all([client_code, password, totp]):
        print("All credentials are required!")
        return
    
    # Initialize API
    angel_api = EnhancedAngelSmartAPI()
    
    # Login
    print("\nLogging into Angel One SmartAPI...")
    if not angel_api.login(client_code, password, totp):
        print("Login failed. Please check your credentials.")
        return
    
    print("Login successful!")
    
    # Initialize enhanced data fetcher
    nifty_fetcher = EnhancedNiftyDataFetcher(angel_api)
    
    # Get user preferences
    try:
        volatility = float(input("Enter implied volatility (e.g., 0.15 for 15%): ") or "0.15")
    except ValueError:
        volatility = 0.15
        print("Using default volatility: 15%")
    
    # Fetch comprehensive data
    print("\nFetching comprehensive Nifty options data with advanced Greeks...")
    
    try:
        result = nifty_fetcher.get_live_nifty_data_with_greeks(
            volatility=volatility, 
            include_analytics=True
        )
        
        if result:
            # Display the enhanced data
            nifty_fetcher.display_enhanced_greeks_data(result)
            
            # Save to CSV with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"enhanced_nifty_greeks_{timestamp}.csv"
            result['data'].to_csv(filename, index=False)
            print(f"\nData saved to {filename}")
            
            # Save analytics to JSON
            analytics_filename = f"nifty_analytics_{timestamp}.json"
            with open(analytics_filename, 'w') as f:
                json.dump({
                    'analytics': result.get('analytics', {}),
                    'metadata': result.get('metadata', {})
                }, f, indent=2)
            print(f"Analytics saved to {analytics_filename}")
            
        else:
            print("Failed to fetch data")
            
    except KeyboardInterrupt:
        print("\nOperation interrupted by user.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        logger.error(f"Main execution error: {str(e)}")

if __name__ == "__main__":
    main()
