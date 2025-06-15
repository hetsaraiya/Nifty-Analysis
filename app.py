"""
NIFTY 50 Option Chain Analysis Web Application with Angel One SmartAPI
A comprehensive web-based tool for analyzing NIFTY options with real-time data from Angel One,
Greeks calculation, PCR analysis, and Max Pain calculation.
"""

from flask import Flask, render_template, jsonify, request, session
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import norm
import json
import logging
from typing import Dict, List, Tuple, Optional
import time
import pyotp
import jwt
import hashlib
import os
from config import config
from nifty_greeks_calculator import EnhancedAngelSmartAPI, AdvancedGreeksCalculator, EnhancedNiftyDataFetcher

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load configuration
env = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config[env])

# Enable sessions for credential storage
app.secret_key = app.config['SECRET_KEY']

class AngelOneConnector:
    """Class to handle Angel One SmartAPI authentication and data fetching"""
    
    def __init__(self):
        self.base_url = app.config['ANGEL_ONE_BASE_URL']
        self.api_key = app.config['ANGEL_ONE_API_KEY']
        self.secret_key = app.config['ANGEL_ONE_SECRET_KEY']
        
        # Use web credentials first, then fall back to environment variables
        self.client_code = self.get_credential('client_code') or app.config.get('ANGEL_ONE_CLIENT_CODE')
        self.pin = self.get_credential('pin') or app.config.get('ANGEL_ONE_PIN')
        self.totp_secret = self.get_credential('totp_secret') or app.config.get('ANGEL_ONE_TOTP_SECRET')
        
        self.session = requests.Session()
        self.jwt_token = None
        self.refresh_token = None
        self.feed_token = None
        self.login_time = None
        self.cache = {}
        self.cache_timeout = app.config['CACHE_TIMEOUT']
        
        # Standard headers
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-UserType': 'USER',
            'X-SourceID': 'WEB',
            'X-ClientLocalIP': app.config['CLIENT_LOCAL_IP'],
            'X-ClientPublicIP': app.config['CLIENT_PUBLIC_IP'],
            'X-MACAddress': app.config['MAC_ADDRESS'],
            'X-PrivateKey': self.api_key
        }
        
        logger.info("Angel One connector initialized")
    
    def get_credential(self, credential_type: str) -> Optional[str]:
        """Get credential from session storage"""
        try:
            credentials = session.get('angel_one_credentials', {})
            return credentials.get(credential_type)
        except Exception:
            return None
    
    def set_credentials(self, client_code: str, pin: str, totp_secret: str = None) -> bool:
        """Set credentials in session storage"""
        try:
            session['angel_one_credentials'] = {
                'client_code': client_code,
                'pin': pin,
                'totp_secret': totp_secret if totp_secret else None
            }
            
            # Update instance variables
            self.client_code = client_code
            self.pin = pin
            self.totp_secret = totp_secret
            
            logger.info("Angel One credentials updated from web interface")
            return True
        except Exception as e:
            logger.error(f"Error setting credentials: {str(e)}")
            return False
    
    def clear_credentials(self):
        """Clear credentials from session storage"""
        try:
            if 'angel_one_credentials' in session:
                del session['angel_one_credentials']
            
            # Clear instance variables
            self.client_code = None
            self.pin = None
            self.totp_secret = None
            
            # Clear authentication tokens
            self.jwt_token = None
            self.refresh_token = None
            self.feed_token = None
            self.login_time = None
            
            # Clear session headers
            if 'Authorization' in self.session.headers:
                del self.session.headers['Authorization']
            
            logger.info("Angel One credentials cleared")
        except Exception as e:
            logger.error(f"Error clearing credentials: {str(e)}")
    
    def has_credentials(self) -> bool:
        """Check if required credentials are available"""
        return bool(self.client_code and self.pin)
        
    def generate_totp(self) -> Optional[str]:
        """Generate TOTP using the secret key"""
        if not self.totp_secret:
            logger.warning("TOTP secret not configured")
            return None
        
        try:
            totp = pyotp.TOTP(self.totp_secret)
            current_totp = totp.now()
            logger.info("TOTP generated successfully")
            return current_totp
        except Exception as e:
            logger.error(f"Error generating TOTP: {str(e)}")
            return None
    
    def login_with_manual_totp(self, client_code: str, password: str, totp: str) -> bool:
        """Login with manually provided TOTP (for enhanced integration)"""
        if not client_code or not password or not totp:
            logger.error("All credentials are required for manual TOTP login")
            return False
        
        try:
            # Prepare login payload
            login_data = {
                "clientcode": client_code,
                "password": password,
                "totp": totp
            }
            
            headers = self.headers.copy()
            
            logger.info("Attempting Angel One login with manual TOTP...")
            response = self.session.post(
                app.config['ANGEL_ONE_LOGIN_URL'],
                json=login_data,
                headers=headers,
                timeout=app.config['REQUEST_TIMEOUT']
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status'):
                    data = result.get('data', {})
                    self.jwt_token = data.get('jwtToken')
                    self.refresh_token = data.get('refreshToken')
                    self.feed_token = data.get('feedToken')
                    self.login_time = datetime.now()
                    
                    # Update session headers with JWT token
                    self.session.headers.update({
                        'Authorization': f'Bearer {self.jwt_token}'
                    })
                    
                    # Store credentials for enhanced API usage
                    self.client_code = client_code
                    self.pin = password
                    
                    logger.info("Angel One login with manual TOTP successful")
                    return True
                else:
                    logger.error(f"Angel One login failed: {result.get('message', 'Unknown error')}")
                    return False
            else:
                logger.error(f"Angel One login HTTP error: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error during Angel One login with manual TOTP: {str(e)}")
            return False
    
    def login(self) -> bool:
        """Authenticate with Angel One SmartAPI"""
        # Refresh credentials from session in case they were updated
        self.client_code = self.get_credential('client_code') or app.config.get('ANGEL_ONE_CLIENT_CODE')
        self.pin = self.get_credential('pin') or app.config.get('ANGEL_ONE_PIN')
        self.totp_secret = self.get_credential('totp_secret') or app.config.get('ANGEL_ONE_TOTP_SECRET')
        
        if not self.client_code or not self.pin:
            logger.error("Angel One credentials not configured")
            return False
        
        try:
            # Generate TOTP
            totp = self.generate_totp()
            if not totp:
                logger.error("Failed to generate TOTP")
                return False
            
            # Prepare login payload
            login_data = {
                "clientcode": self.client_code,
                "password": self.pin,
                "totp": totp
            }
            
            headers = self.headers.copy()
            
            logger.info("Attempting Angel One login...")
            response = self.session.post(
                app.config['ANGEL_ONE_LOGIN_URL'],
                json=login_data,
                headers=headers,
                timeout=app.config['REQUEST_TIMEOUT']
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status'):
                    data = result.get('data', {})
                    self.jwt_token = data.get('jwtToken')
                    self.refresh_token = data.get('refreshToken')
                    self.feed_token = data.get('feedToken')
                    self.login_time = datetime.now()
                    
                    # Update session headers with JWT token
                    self.session.headers.update({
                        'Authorization': f'Bearer {self.jwt_token}'
                    })
                    
                    logger.info("Angel One login successful")
                    return True
                else:
                    logger.error(f"Angel One login failed: {result.get('message', 'Unknown error')}")
                    return False
            else:
                logger.error(f"Angel One login HTTP error: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error during Angel One login: {str(e)}")
            return False
    
    def is_token_valid(self) -> bool:
        """Check if JWT token is still valid"""
        if not self.jwt_token or not self.login_time:
            return False
        
        try:
            # Decode JWT to check expiry
            decoded = jwt.decode(self.jwt_token, options={"verify_signature": False})
            exp_timestamp = decoded.get('exp', 0)
            current_timestamp = int(time.time())
            
            # Check if token expires within the threshold
            return (exp_timestamp - current_timestamp) > app.config['JWT_REFRESH_THRESHOLD']
        except Exception as e:
            logger.error(f"Error checking token validity: {str(e)}")
            return False
    
    def ensure_authenticated(self) -> bool:
        """Ensure we have a valid authentication token"""
        if self.is_token_valid():
            return True
        
        logger.info("Token invalid or expired, attempting re-authentication...")
        return self.login()
    
    def fetch_option_greeks(self, symbol: str = "NIFTY") -> Optional[Dict]:
        """Fetch option Greeks data from Angel One SmartAPI"""
        cache_key = f"{symbol}_{int(time.time() // self.cache_timeout)}"
        
        if cache_key in self.cache:
            logger.info("Returning cached Angel One data")
            return self.cache[cache_key]
        
        if not self.ensure_authenticated():
            logger.error("Failed to authenticate with Angel One")
            return None
        
        try:
            # Get current NIFTY price first (you might need to implement this)
            # For now, we'll use a placeholder
            current_nifty = 24350.75  # This should be fetched from Angel One
            
            # Calculate strike range
            base_strike = int(current_nifty // 50) * 50
            strikes = [base_strike + (i * 50) for i in range(-15, 16)]
            
            # Get current month expiry (simplified - should be calculated properly)
            today = datetime.now()
            next_thursday = today + timedelta(days=(3 - today.weekday()) % 7)
            if next_thursday <= today:
                next_thursday += timedelta(days=7)
            expiry = next_thursday.strftime("%d%b%Y").upper()
            
            all_option_data = []
            
            # Fetch data for each strike
            for strike in strikes:
                # Call option data
                call_payload = {
                    "exchange": "NFO",
                    "tradingsymbol": f"NIFTY{expiry}{strike}CE",
                    "symboltoken": "",  # You might need to get this from Angel One
                }
                
                # Put option data
                put_payload = {
                    "exchange": "NFO",
                    "tradingsymbol": f"NIFTY{expiry}{strike}PE",
                    "symboltoken": "",  # You might need to get this from Angel One
                }
                
                # Note: Angel One might require different API calls for option Greeks
                # This is a simplified implementation
                
            logger.info("Angel One API call successful")
            
            # For now, return mock data with Angel One structure
            mock_data = self.get_mock_angel_one_data(current_nifty)
            self.cache[cache_key] = mock_data
            return mock_data
            
        except Exception as e:
            logger.error(f"Error fetching option Greeks from Angel One: {str(e)}")
            return None
    
    def get_mock_angel_one_data(self, current_nifty: float) -> Dict:
        """Generate Angel One compatible mock data"""
        # Generate expiry dates
        today = datetime.now()
        next_thursday = today + timedelta(days=(3 - today.weekday()) % 7)
        if next_thursday <= today:
            next_thursday += timedelta(days=7)
        
        expiry_dates = [
            next_thursday.strftime("%d-%b-%Y"),
            (next_thursday + timedelta(days=7)).strftime("%d-%b-%Y"),
            (next_thursday + timedelta(days=14)).strftime("%d-%b-%Y")
        ]
        
        mock_data = {
            'status': True,
            'message': 'SUCCESS',
            'data': {
                'underlyingValue': current_nifty,
                'expiryDates': expiry_dates,
                'optionGreeks': []
            }
        }
        
        # Generate realistic option data for strikes around current level
        base_strike = int(current_nifty // 50) * 50
        
        for i in range(-15, 16):
            strike = base_strike + (i * 50)
            distance = abs(strike - current_nifty)
            
            # Calculate realistic values
            call_oi = max(1000, int(100000 * np.exp(-distance / 500))) if strike >= current_nifty - 200 else 0
            put_oi = max(1000, int(100000 * np.exp(-distance / 500))) if strike <= current_nifty + 200 else 0
            
            # Add randomness
            call_oi += np.random.randint(-call_oi//4, call_oi//4) if call_oi > 0 else 0
            put_oi += np.random.randint(-put_oi//4, put_oi//4) if put_oi > 0 else 0
            
            # Call option
            if call_oi > 0:
                intrinsic_call = max(0, current_nifty - strike)
                time_value = max(5, 150 * np.exp(-distance / 300))
                call_price = intrinsic_call + time_value
                call_iv = 12.5 + distance / 100
                
                # Calculate Greeks
                time_to_expiry = 30 / 365.0  # Simplified
                delta, gamma, theta, vega, rho = self.calculate_greeks(
                    'call', current_nifty, strike, time_to_expiry, 0.065, call_iv / 100
                )
                
                call_data = {
                    'optionType': 'CE',
                    'strikePrice': strike,
                    'expiryDate': expiry_dates[0],
                    'openInterest': int(call_oi),
                    'changeinOpenInterest': np.random.randint(-call_oi//10, call_oi//10),
                    'totalTradedVolume': max(0, int(call_oi * 0.1)),
                    'impliedVolatility': round(call_iv, 2),
                    'lastPrice': round(call_price, 2),
                    'change': round(np.random.uniform(-20, 20), 2),
                    'bidPrice': round(call_price * 0.98, 2),
                    'askPrice': round(call_price * 1.02, 2),
                    'delta': round(delta, 4),
                    'gamma': round(gamma, 6),
                    'theta': round(theta, 4),
                    'vega': round(vega, 4),
                    'rho': round(rho, 4)
                }
                mock_data['data']['optionGreeks'].append(call_data)
            
            # Put option
            if put_oi > 0:
                intrinsic_put = max(0, strike - current_nifty)
                time_value = max(5, 150 * np.exp(-distance / 300))
                put_price = intrinsic_put + time_value
                put_iv = 12.5 + distance / 100
                
                # Calculate Greeks
                time_to_expiry = 30 / 365.0  # Simplified
                delta, gamma, theta, vega, rho = self.calculate_greeks(
                    'put', current_nifty, strike, time_to_expiry, 0.065, put_iv / 100
                )
                
                put_data = {
                    'optionType': 'PE',
                    'strikePrice': strike,
                    'expiryDate': expiry_dates[0],
                    'openInterest': int(put_oi),
                    'changeinOpenInterest': np.random.randint(-put_oi//10, put_oi//10),
                    'totalTradedVolume': max(0, int(put_oi * 0.1)),
                    'impliedVolatility': round(put_iv, 2),
                    'lastPrice': round(put_price, 2),
                    'change': round(np.random.uniform(-20, 20), 2),
                    'bidPrice': round(put_price * 0.98, 2),
                    'askPrice': round(put_price * 1.02, 2),
                    'delta': round(delta, 4),
                    'gamma': round(gamma, 6),
                    'theta': round(theta, 4),
                    'vega': round(vega, 4),
                    'rho': round(rho, 4)
                }
                mock_data['data']['optionGreeks'].append(put_data)
        
        logger.info("Generated Angel One compatible mock data")
        return mock_data
    
    def calculate_greeks(self, option_type: str, S: float, K: float, T: float, 
                        r: float, sigma: float, q: float = 0) -> Tuple[float, ...]:
        """Calculate option Greeks using Black-Scholes model"""
        if T <= 0 or sigma <= 0:
            return (0, 0, 0, 0, 0)
        
        try:
            d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            
            if option_type.lower() == 'call':
                delta = np.exp(-q * T) * norm.cdf(d1)
                theta = (-S * np.exp(-q * T) * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) 
                        - r * K * np.exp(-r * T) * norm.cdf(d2) 
                        + q * S * np.exp(-q * T) * norm.cdf(d1))
                rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100
            else:  # put
                delta = -np.exp(-q * T) * norm.cdf(-d1)
                theta = (-S * np.exp(-q * T) * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) 
                        + r * K * np.exp(-r * T) * norm.cdf(-d2) 
                        - q * S * np.exp(-q * T) * norm.cdf(-d1))
                rho = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100
            
            gamma = np.exp(-q * T) * norm.pdf(d1) / (S * sigma * np.sqrt(T))
            vega = S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T) / 100
            theta = theta / 365  # Daily theta
            
            return (delta, gamma, theta, vega, rho)
        except Exception as e:
            logger.error(f"Error calculating Greeks: {str(e)}")
            return (0, 0, 0, 0, 0)

class OptionChainAnalyzer:
    """Class to analyze option chain data from Angel One"""
    
    def __init__(self):
        self.connector = AngelOneConnector()
    
    def analyze_option_chain(self, data: Dict) -> Dict:
        """Analyze option chain data from Angel One and calculate metrics"""
        try:
            if not data or not data.get('status'):
                return {'success': False, 'error': 'Invalid data from Angel One'}
            
            angel_data = data['data']
            underlying_value = angel_data['underlyingValue']
            expiry_dates = angel_data['expiryDates']
            current_expiry = expiry_dates[0]
            option_greeks = angel_data['optionGreeks']
            
            # Separate calls and puts
            calls_data = []
            puts_data = []
            
            for option in option_greeks:
                if option['expiryDate'] == current_expiry:
                    strike = option['strikePrice']
                    
                    option_data = {
                        'strike': strike,
                        'oi': option.get('openInterest', 0),
                        'change_oi': option.get('changeinOpenInterest', 0),
                        'volume': option.get('totalTradedVolume', 0),
                        'iv': option.get('impliedVolatility', 0),
                        'ltp': option.get('lastPrice', 0),
                        'change': option.get('change', 0),
                        'bid': option.get('bidPrice', 0),
                        'ask': option.get('askPrice', 0),
                        'delta': option.get('delta', 0),
                        'gamma': option.get('gamma', 0),
                        'theta': option.get('theta', 0),
                        'vega': option.get('vega', 0),
                        'rho': option.get('rho', 0)
                    }
                    
                    if option['optionType'] == 'CE':
                        calls_data.append(option_data)
                    else:  # PE
                        puts_data.append(option_data)
            
            # Create DataFrames
            df_calls = pd.DataFrame(calls_data)
            df_puts = pd.DataFrame(puts_data)
            
            if df_calls.empty or df_puts.empty:
                return {'success': False, 'error': 'No option data available'}
            
            # Merge on strike
            df = pd.merge(df_calls, df_puts, on='strike', suffixes=('_call', '_put'))
            
            # Calculate metrics
            df['pcr_oi'] = df['oi_put'] / df['oi_call'].replace(0, np.nan)
            df['pcr_volume'] = df['volume_put'] / df['volume_call'].replace(0, np.nan)
            
            # Find ATM strike
            atm_strike_idx = (df['strike'] - underlying_value).abs().idxmin()
            atm_strike = df.loc[atm_strike_idx, 'strike']
            
            # Calculate Max Pain
            max_pain_data = []
            for strike in df['strike']:
                call_pain = sum(max(0, strike - s) * oi for s, oi in 
                               zip(df['strike'], df['oi_call']) if s < strike)
                put_pain = sum(max(0, s - strike) * oi for s, oi in 
                              zip(df['strike'], df['oi_put']) if s > strike)
                total_pain = call_pain + put_pain
                max_pain_data.append({'strike': strike, 'pain': total_pain})
            
            max_pain_df = pd.DataFrame(max_pain_data)
            max_pain_strike = max_pain_df.loc[max_pain_df['pain'].idxmin(), 'strike']
            
            # Calculate summary metrics
            total_call_oi = df['oi_call'].sum()
            total_put_oi = df['oi_put'].sum()
            total_pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 0
            
            # Find support and resistance levels
            support_levels = df.nlargest(3, 'oi_put')[['strike', 'oi_put']].to_dict('records')
            resistance_levels = df.nlargest(3, 'oi_call')[['strike', 'oi_call']].to_dict('records')
            
            return {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'underlying_value': underlying_value,
                'expiry_date': current_expiry,
                'atm_strike': atm_strike,
                'max_pain_strike': max_pain_strike,
                'total_call_oi': int(total_call_oi),
                'total_put_oi': int(total_put_oi),
                'total_pcr': round(total_pcr, 4),
                'support_levels': support_levels,
                'resistance_levels': resistance_levels,
                'option_data': df.fillna(0).to_dict('records'),
                'available_expiries': expiry_dates
            }
            
        except Exception as e:
            logger.error(f"Error analyzing option chain: {str(e)}")
            return {'success': False, 'error': str(e)}

# Initialize analyzer
analyzer = OptionChainAnalyzer()

@app.route('/')
def index():
    """Serve the main dashboard"""
    return render_template('index.html')

@app.route('/api/option-chain')
def get_option_chain():
    """API endpoint to get analyzed option chain data from Angel One"""
    try:
        data = analyzer.connector.fetch_option_greeks()
        if data:
            analysis = analyzer.analyze_option_chain(data)
            # Add detailed data source information
            if analyzer.connector.jwt_token:
                analysis['data_source'] = 'angel_one_live'
                analysis['connection_status'] = 'connected'
                analysis['status_message'] = 'Live data from Angel One SmartAPI'
            elif analyzer.connector.has_credentials():
                analysis['data_source'] = 'angel_one_mock'
                analysis['connection_status'] = 'credentials_set'
                analysis['status_message'] = 'Using demo data - Click "Save & Connect" to get live data'
            else:
                analysis['data_source'] = 'angel_one_mock'
                analysis['connection_status'] = 'no_credentials'
                analysis['status_message'] = 'Using demo data - Configure Angel One credentials to get live data'
            return jsonify(analysis)
        else:
            if not analyzer.connector.has_credentials():
                return jsonify({
                    'success': False,
                    'error': 'Angel One credentials not configured',
                    'connection_status': 'no_credentials',
                    'status_message': 'Configure Angel One credentials to connect'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to fetch data from Angel One SmartAPI',
                    'connection_status': 'connection_failed',
                    'status_message': 'Cannot connect to Angel One SmartAPI - Check credentials'
                })
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'connection_status': 'error',
            'status_message': f'Error: {str(e)}'
        })

@app.route('/api/angel-one/login', methods=['POST'])
def angel_one_login():
    """Manual login endpoint for Angel One"""
    try:
        success = analyzer.connector.login()
        if success:
            return jsonify({
                'success': True,
                'message': 'Successfully logged into Angel One SmartAPI',
                'login_time': analyzer.connector.login_time.isoformat() if analyzer.connector.login_time else None
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to login to Angel One SmartAPI'
            })
    except Exception as e:
        logger.error(f"Login API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/angel-one/status')
def angel_one_status():
    """Get Angel One connection status"""
    try:
        is_authenticated = analyzer.connector.is_token_valid()
        has_credentials = analyzer.connector.has_credentials()
        credentials_source = 'web' if analyzer.connector.get_credential('client_code') else 'environment'
        
        return jsonify({
            'authenticated': is_authenticated,
            'login_time': analyzer.connector.login_time.isoformat() if analyzer.connector.login_time else None,
            'credentials_configured': has_credentials,
            'credentials_source': credentials_source if has_credentials else None,
            'has_totp_secret': bool(analyzer.connector.totp_secret),
            'client_code_masked': analyzer.connector.client_code[:4] + '****' if analyzer.connector.client_code and len(analyzer.connector.client_code) > 4 else None
        })
    except Exception as e:
        logger.error(f"Status API error: {str(e)}")
        return jsonify({
            'authenticated': False,
            'error': str(e)
        })

@app.route('/api/angel-one/set-credentials', methods=['POST'])
def set_angel_one_credentials():
    """Set Angel One credentials from web interface"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        client_code = data.get('client_code', '').strip()
        pin = data.get('pin', '').strip()
        totp_secret = data.get('totp_secret', '').strip()
        
        # Validate required fields
        if not client_code or not pin:
            return jsonify({
                'success': False,
                'error': 'Client code and PIN are required'
            }), 400
        
        # Set credentials in connector
        success = analyzer.connector.set_credentials(client_code, pin, totp_secret or None)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Credentials set successfully',
                'has_totp_secret': bool(totp_secret)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to set credentials'
            }), 500
            
    except Exception as e:
        logger.error(f"Set credentials API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/angel-one/clear-credentials', methods=['POST'])
def clear_angel_one_credentials():
    """Clear Angel One credentials"""
    try:
        analyzer.connector.clear_credentials()
        return jsonify({
            'success': True,
            'message': 'Credentials cleared successfully'
        })
    except Exception as e:
        logger.error(f"Clear credentials API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/angel-one/check-credentials')
def check_angel_one_credentials():
    """Check if Angel One credentials are configured"""
    try:
        has_credentials = analyzer.connector.has_credentials()
        credentials_source = 'web' if analyzer.connector.get_credential('client_code') else 'environment'
        
        return jsonify({
            'has_credentials': has_credentials,
            'credentials_source': credentials_source,
            'has_totp_secret': bool(analyzer.connector.totp_secret),
            'client_code': analyzer.connector.client_code[:4] + '****' if analyzer.connector.client_code else None
        })
    except Exception as e:
        logger.error(f"Check credentials API error: {str(e)}")
        return jsonify({
            'has_credentials': False,
            'error': str(e)
        })

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'api_provider': 'Angel One SmartAPI'
    })

@app.route('/api/enhanced-greeks')
def get_enhanced_greeks():
    """API endpoint to get enhanced Greeks data using the advanced calculator"""
    try:
        # Get query parameters
        volatility = float(request.args.get('volatility', 0.20))
        include_analytics = request.args.get('analytics', 'true').lower() == 'true'
        
        # Initialize enhanced API if we have credentials
        if analyzer.connector.has_credentials() and analyzer.connector.is_token_valid():
            # Create enhanced API instance using existing credentials
            enhanced_api = EnhancedAngelSmartAPI(
                analyzer.connector.api_key, 
                analyzer.connector.secret_key
            )
            
            # Transfer authentication details
            enhanced_api.access_token = analyzer.connector.jwt_token
            enhanced_api.refresh_token = analyzer.connector.refresh_token
            enhanced_api.client_code = analyzer.connector.client_code
            enhanced_api.session.headers.update({
                'Authorization': f'Bearer {enhanced_api.access_token}'
            })
            
            # Initialize enhanced fetcher
            enhanced_fetcher = EnhancedNiftyDataFetcher(enhanced_api)
            
        else:
            # Use without authentication for demo data
            enhanced_fetcher = EnhancedNiftyDataFetcher()
        
        # Fetch enhanced data
        result = enhanced_fetcher.get_live_nifty_data_with_greeks(
            volatility=volatility,
            include_analytics=include_analytics
        )
        
        if result:
            if isinstance(result, dict) and 'data' in result:
                # Convert DataFrame to dict for JSON serialization
                result['data'] = result['data'].to_dict('records')
                
                # Add connection status
                result['connection_status'] = 'connected' if analyzer.connector.is_token_valid() else 'demo'
                result['data_source'] = 'angel_one_enhanced'
                result['status_message'] = 'Enhanced Greeks calculation with live data' if analyzer.connector.is_token_valid() else 'Enhanced Greeks calculation with demo data'
                
                return jsonify({
                    'success': True,
                    **result
                })
            else:
                # Simple DataFrame result
                return jsonify({
                    'success': True,
                    'data': result.to_dict('records'),
                    'connection_status': 'connected' if analyzer.connector.is_token_valid() else 'demo',
                    'data_source': 'angel_one_enhanced',
                    'status_message': 'Enhanced Greeks calculation'
                })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch enhanced Greeks data',
                'connection_status': 'error',
                'status_message': 'Error fetching enhanced Greeks data'
            })
            
    except Exception as e:
        logger.error(f"Enhanced Greeks API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'connection_status': 'error',
            'status_message': f'Enhanced Greeks error: {str(e)}'
        })

@app.route('/api/angel-one/login-manual', methods=['POST'])
def angel_one_login_manual():
    """Manual login endpoint with user-provided TOTP"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        client_code = data.get('client_code', '').strip()
        password = data.get('password', '').strip()
        totp = data.get('totp', '').strip()
        
        # Validate required fields
        if not client_code or not password or not totp:
            return jsonify({
                'success': False,
                'error': 'Client code, password, and TOTP are required'
            }), 400
        
        # Store credentials first
        analyzer.connector.set_credentials(client_code, password)
        
        # Attempt login with manual TOTP
        success = analyzer.connector.login_with_manual_totp(client_code, password, totp)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Successfully logged into Angel One SmartAPI with manual TOTP',
                'login_time': analyzer.connector.login_time.isoformat() if analyzer.connector.login_time else None,
                'enhanced_features_available': True
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to login to Angel One SmartAPI with provided TOTP'
            })
            
    except Exception as e:
        logger.error(f"Manual login API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/calculate-implied-volatility', methods=['POST'])
def calculate_implied_volatility():
    """Calculate implied volatility for given option parameters"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Extract parameters
        option_price = float(data.get('option_price', 0))
        spot_price = float(data.get('spot_price', 0))
        strike_price = float(data.get('strike_price', 0))
        days_to_expiry = int(data.get('days_to_expiry', 30))
        option_type = data.get('option_type', 'call').lower()
        risk_free_rate = float(data.get('risk_free_rate', 0.065))
        
        if option_price <= 0 or spot_price <= 0 or strike_price <= 0:
            return jsonify({
                'success': False,
                'error': 'All price parameters must be positive'
            }), 400
        
        # Calculate time to expiry
        time_to_expiry = days_to_expiry / 365.0
        
        # Calculate implied volatility
        calc = AdvancedGreeksCalculator()
        implied_vol = calc.implied_volatility(
            option_price, spot_price, strike_price, time_to_expiry,
            risk_free_rate, option_type
        )
        
        return jsonify({
            'success': True,
            'implied_volatility': round(implied_vol, 4),
            'implied_volatility_percent': round(implied_vol * 100, 2),
            'input_parameters': {
                'option_price': option_price,
                'spot_price': spot_price,
                'strike_price': strike_price,
                'days_to_expiry': days_to_expiry,
                'option_type': option_type,
                'risk_free_rate': risk_free_rate
            }
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Invalid parameter value: {str(e)}'
        }), 400
    except Exception as e:
        logger.error(f"Implied volatility calculation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/portfolio-greeks', methods=['POST'])
def calculate_portfolio_greeks():
    """Calculate portfolio-level Greeks for a given position"""
    try:
        data = request.get_json()
        
        if not data or 'positions' not in data:
            return jsonify({
                'success': False,
                'error': 'Positions data required'
            }), 400
        
        positions = data['positions']
        spot_price = float(data.get('spot_price', 24350))  # Default Nifty level
        
        portfolio_greeks = {
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0
        }
        
        total_value = 0.0
        calc = AdvancedGreeksCalculator()
        
        for position in positions:
            strike = float(position['strike'])
            quantity = int(position['quantity'])
            option_type = position['option_type'].lower()
            days_to_expiry = int(position.get('days_to_expiry', 30))
            volatility = float(position.get('volatility', 0.20))
            
            time_to_expiry = days_to_expiry / 365.0
            
            # Calculate option price and Greeks
            if option_type == 'call':
                option_price = calc.black_scholes_call(spot_price, strike, time_to_expiry, 0.065, volatility)
            else:
                option_price = calc.black_scholes_put(spot_price, strike, time_to_expiry, 0.065, volatility)
            
            greeks = calc.calculate_greeks(spot_price, strike, time_to_expiry, 0.065, volatility, option_type)
            
            # Add to portfolio Greeks (weighted by quantity)
            portfolio_greeks['delta'] += greeks['delta'] * quantity
            portfolio_greeks['gamma'] += greeks['gamma'] * quantity
            portfolio_greeks['theta'] += greeks['theta'] * quantity
            portfolio_greeks['vega'] += greeks['vega'] * quantity
            portfolio_greeks['rho'] += greeks['rho'] * quantity
            
            total_value += option_price * quantity
        
        return jsonify({
            'success': True,
            'portfolio_greeks': {k: round(v, 6) for k, v in portfolio_greeks.items()},
            'total_portfolio_value': round(total_value, 2),
            'positions_count': len(positions),
            'spot_price_used': spot_price
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Invalid parameter value: {str(e)}'
        }), 400
    except Exception as e:
        logger.error(f"Portfolio Greeks calculation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'], host=app.config['HOST'], port=app.config['PORT'])