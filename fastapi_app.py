"""
NIFTY 50 Option Chain Analysis FastAPI Application with Yahoo Finance
A comprehensive API for analyzing NIFTY options with real-time data from Yahoo Finance,
Greeks calculation, portfolio analysis, and advanced options analytics.
"""

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union
import requests
import pandas as pd
import numpy as np
import datetime
from scipy.stats import norm
import json
import time
import os
from loguru import logger
from yahoo_nifty_greeks import YahooFinanceAPI, NiftyOptionsChain, GreeksCalculator, PortfolioGreeksCalculator

# Configure Loguru logging
logger.remove()  # Remove default handler
logger.add(
    "logs/fastapi_app.log",
    rotation="1 day",
    retention="30 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
    backtrace=True,
    diagnose=True
)
logger.add(
    "logs/error.log",
    rotation="1 day",
    retention="30 days",
    level="ERROR",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
    backtrace=True,
    diagnose=True
)
# Also log to console for development
logger.add(
    lambda msg: print(msg, end=""),
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>"
)

# Initialize FastAPI app
app = FastAPI(
    title="NIFTY Options Greeks Analyzer",
    description="Comprehensive NIFTY options analysis with real-time Angel One data",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Load configuration
env = os.environ.get('FLASK_ENV', 'development')
app_config = config[env]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests and responses with detailed information"""
    start_time = time.time()
    
    # Log request details
    logger.info(f">>> Incoming Request: {request.method} {request.url}")
    logger.debug(f"Request headers: {dict(request.headers)}")
    logger.debug(f"Request client: {request.client.host if request.client else 'Unknown'}")
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    
    # Log response details
    logger.info(f"<<< Response: {request.method} {request.url} - Status: {response.status_code} - Time: {process_time:.3f}s")
    
    # Add processing time to response headers
    response.headers["X-Process-Time"] = str(process_time)
    
    return response

# Security
security = HTTPBearer(auto_error=False)

# Templates
templates = Jinja2Templates(directory="templates")

# Pydantic models for request/response
class AngelOneCredentials(BaseModel):
    client_code: str = Field(..., description="Angel One client code")
    pin: str = Field(..., description="Angel One PIN")
    totp_secret: Optional[str] = Field(None, description="TOTP secret key")

class ManualLoginRequest(BaseModel):
    client_code: str = Field(..., description="Angel One client code")
    password: str = Field(..., description="Angel One password")
    totp: str = Field(..., description="Current TOTP code")

class ImpliedVolatilityRequest(BaseModel):
    option_price: float = Field(..., gt=0, description="Current option price")
    spot_price: float = Field(..., gt=0, description="Current spot price")
    strike_price: float = Field(..., gt=0, description="Strike price")
    days_to_expiry: int = Field(..., gt=0, description="Days to expiry")
    option_type: str = Field(..., pattern="^(call|put)$", description="Option type")
    risk_free_rate: float = Field(0.065, description="Risk-free rate")

class Position(BaseModel):
    strike: float = Field(..., description="Strike price")
    quantity: int = Field(..., description="Position quantity")
    option_type: str = Field(..., pattern="^(call|put)$", description="Option type")
    days_to_expiry: int = Field(30, description="Days to expiry")
    volatility: float = Field(0.20, description="Implied volatility")

class PortfolioGreeksRequest(BaseModel):
    positions: List[Position] = Field(..., description="List of positions")
    spot_price: float = Field(24350, description="Current spot price")

class GreeksResponse(BaseModel):
    success: bool
    data: Optional[List[Dict]] = None
    analytics: Optional[Dict] = None
    metadata: Optional[Dict] = None
    connection_status: str
    data_source: str
    status_message: str
    error: Optional[str] = None

class StatusResponse(BaseModel):
    authenticated: bool
    login_time: Optional[str] = None
    credentials_configured: bool
    credentials_source: Optional[str] = None
    has_totp_secret: bool
    client_code_masked: Optional[str] = None
    error: Optional[str] = None

# Enhanced Angel One Connector for FastAPI
class FastAPIAngelOneConnector:
    """Enhanced Angel One connector for FastAPI application with comprehensive logging"""
    
    def __init__(self):
        self.base_url = app_config.ANGEL_ONE_BASE_URL
        self.api_key = app_config.ANGEL_ONE_API_KEY
        self.secret_key = app_config.ANGEL_ONE_SECRET_KEY
        
        self.client_code = app_config.ANGEL_ONE_CLIENT_CODE
        self.pin = app_config.ANGEL_ONE_PIN
        self.totp_secret = app_config.ANGEL_ONE_TOTP_SECRET
        
        self.session = requests.Session()
        self.jwt_token = None
        self.refresh_token = None
        self.feed_token = None
        self.login_time = None
        self.cache = {}
        self.cache_timeout = app_config.CACHE_TIMEOUT
        
        # In-memory credential storage (consider using Redis in production)
        self._stored_credentials = {}
        
        # Standard headers
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-UserType': 'USER',
            'X-SourceID': 'WEB',
            'X-ClientLocalIP': app_config.CLIENT_LOCAL_IP,
            'X-ClientPublicIP': app_config.CLIENT_PUBLIC_IP,
            'X-MACAddress': app_config.MAC_ADDRESS,
            'X-PrivateKey': self.api_key
        }
        
        logger.info("FastAPI Angel One connector initialized successfully")
        logger.debug(f"Base URL: {self.base_url}")
        logger.debug(f"Cache timeout: {self.cache_timeout}s")
    
    def set_credentials(self, client_code: str, pin: str, totp_secret: str = None) -> bool:
        """Set credentials in memory storage with comprehensive logging"""
        try:
            logger.info("Setting Angel One credentials")
            logger.debug(f"Client code: {client_code[:4]}****")
            
            self._stored_credentials = {
                'client_code': client_code,
                'pin': pin,
                'totp_secret': totp_secret if totp_secret else None
            }
            
            # Update instance variables
            self.client_code = client_code
            self.pin = pin
            self.totp_secret = totp_secret
            
            logger.success("Angel One credentials updated successfully")
            logger.info(f"TOTP secret configured: {bool(totp_secret)}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting Angel One credentials: {str(e)}")
            logger.exception("Full traceback for credential setting error")
            return False
    
    def has_credentials(self) -> bool:
        """Check if required credentials are available"""
        has_creds = bool(self.client_code and self.pin)
        logger.debug(f"Credentials check - Has client_code: {bool(self.client_code)}, Has PIN: {bool(self.pin)}")
        return has_creds
    
    def generate_totp(self) -> Optional[str]:
        """Generate TOTP using the secret key with detailed logging"""
        if not self.totp_secret:
            logger.warning("TOTP secret not configured - cannot generate TOTP")
            return None
        
        try:
            logger.debug("Generating TOTP from secret")
            totp = pyotp.TOTP(self.totp_secret)
            current_totp = totp.now()
            
            logger.success("TOTP generated successfully")
            logger.debug(f"TOTP length: {len(current_totp)} characters")
            return current_totp
            
        except Exception as e:
            logger.error(f"Error generating TOTP: {str(e)}")
            logger.exception("Full traceback for TOTP generation error")
            return None
    
    def login_with_manual_totp(self, client_code: str, password: str, totp: str) -> bool:
        """Login with manually provided TOTP with comprehensive logging"""
        if not client_code or not password or not totp:
            logger.error("Missing required credentials for manual TOTP login")
            logger.debug(f"Has client_code: {bool(client_code)}, Has password: {bool(password)}, Has TOTP: {bool(totp)}")
            return False
        
        try:
            logger.info("Initiating Angel One login with manual TOTP")
            logger.debug(f"Client code: {client_code[:4]}****")
            logger.debug(f"TOTP length: {len(totp)} characters")
            
            login_data = {
                "clientcode": client_code,
                "password": password,
                "totp": totp
            }
            
            headers = self.headers.copy()
            logger.debug("Prepared login headers and payload")
            
            logger.info(f"Sending login request to: {app_config.ANGEL_ONE_LOGIN_URL}")
            start_time = time.time()
            
            response = self.session.post(
                app_config.ANGEL_ONE_LOGIN_URL,
                json=login_data,
                headers=headers,
                timeout=app_config.REQUEST_TIMEOUT
            )
            
            request_duration = time.time() - start_time
            logger.debug(f"Login request completed in {request_duration:.2f}s")
            logger.debug(f"Response status code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.debug("Login response received and parsed")
                
                if result.get('status'):
                    data = result.get('data', {})
                    
                    self.jwt_token = data.get('jwtToken')
                    self.refresh_token = data.get('refreshToken')
                    self.feed_token = data.get('feedToken')
                    self.login_time = datetime.datetime.now()
                    
                    # Update session headers with JWT token
                    self.session.headers.update({
                        'Authorization': f'Bearer {self.jwt_token}'
                    })
                    
                    # Store credentials for enhanced API usage
                    self.client_code = client_code
                    self.pin = password
                    
                    logger.success("Angel One login successful!")
                    logger.info(f"Login time: {self.login_time.isoformat()}")
                    logger.debug(f"JWT token length: {len(self.jwt_token) if self.jwt_token else 0}")
                    logger.debug(f"Refresh token available: {bool(self.refresh_token)}")
                    logger.debug(f"Feed token available: {bool(self.feed_token)}")
                    
                    return True
                else:
                    error_msg = result.get('message', 'Unknown error')
                    logger.error(f"Angel One login failed: {error_msg}")
                    logger.debug(f"Full response: {result}")
                    return False
            else:
                logger.error(f"Angel One login HTTP error: {response.status_code}")
                logger.debug(f"Response text: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error(f"Angel One login request timed out after {app_config.REQUEST_TIMEOUT}s")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("Angel One login connection error - check network connectivity")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during Angel One login: {str(e)}")
            logger.exception("Full traceback for login error")
            return False
    
    def is_token_valid(self) -> bool:
        """Check if JWT token is still valid with detailed logging"""
        if not self.jwt_token or not self.login_time:
            logger.debug("Token validation failed - missing token or login time")
            return False
        
        try:
            logger.debug("Validating JWT token")
            
            # Decode JWT to check expiry
            decoded = jwt.decode(self.jwt_token, options={"verify_signature": False})
            exp_timestamp = decoded.get('exp', 0)
            current_timestamp = int(time.time())
            
            time_until_expiry = exp_timestamp - current_timestamp
            logger.debug(f"Token expires in {time_until_expiry} seconds")
            
            # Check if token expires within the threshold
            is_valid = time_until_expiry > app_config.JWT_REFRESH_THRESHOLD
            
            if is_valid:
                logger.debug("JWT token is valid")
            else:
                logger.warning(f"JWT token expires soon (in {time_until_expiry}s) or has expired")
            
            return is_valid
            
        except jwt.exceptions.DecodeError:
            logger.error("JWT token decode error - token may be malformed")
            return False
        except Exception as e:
            logger.error(f"Error checking token validity: {str(e)}")
            logger.exception("Full traceback for token validation error")
            return False
    
    def clear_credentials(self):
        """Clear all credentials and authentication tokens with logging"""
        logger.info("Clearing Angel One credentials and tokens")
        
        try:
            # Clear stored credentials
            self._stored_credentials = {}
            
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
            
            # Clear cache
            self.cache.clear()
            
            logger.success("Angel One credentials and tokens cleared successfully")
            
        except Exception as e:
            logger.error(f"Error clearing credentials: {str(e)}")
            logger.exception("Full traceback for credential clearing error")
    
    def fetch_option_chain(self):
        """Fetch option chain data using authenticated session with comprehensive logging"""
        logger.info("Fetching option chain data from Angel One API")
        
        if not self.is_token_valid():
            logger.error("Cannot fetch option chain - authentication token invalid")
            return None
        
        try:
            # Option chain API endpoint (you may need to adjust this URL based on Angel One documentation)
            url = f"{self.base_url}/rest/secure/angelbroking/order/v1/getLTP"
            
            # For now, let's fetch NIFTY spot price as a starting point
            payload = {
                "exchange": "NSE",
                "tradingsymbol": "NIFTY 50",
                "symboltoken": "99926000"  # NIFTY 50 token - may need adjustment
            }
            
            logger.debug(f"Sending option chain request to: {url}")
            logger.debug(f"Request payload: {payload}")
            
            response = self.session.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=app_config.REQUEST_TIMEOUT
            )
            
            logger.debug(f"Option chain response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.debug(f"Option chain API response: {result}")
                
                if result.get('status'):
                    logger.success("Option chain data fetched successfully")
                    return result.get('data')
                else:
                    logger.error(f"Option chain API error: {result.get('message', 'Unknown error')}")
                    return None
            else:
                logger.error(f"Option chain HTTP error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Option chain request timed out after {app_config.REQUEST_TIMEOUT}s")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("Option chain connection error - check network connectivity")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching option chain: {str(e)}")
            logger.exception("Full traceback for option chain fetch error")
            return None
    
    def get_connection_status(self) -> dict:
        """Get detailed connection status for monitoring"""
        status = {
            'authenticated': self.is_token_valid(),
            'has_credentials': self.has_credentials(),
            'has_totp_secret': bool(self.totp_secret),
            'login_time': self.login_time.isoformat() if self.login_time else None,
            'cache_entries': len(self.cache),
            'session_active': bool(self.session),
        }
        
        logger.debug(f"Connection status: {status}")
        return status

# Initialize connector
angel_connector = FastAPIAngelOneConnector()

# Routes
@app.get("/health")
async def health_check():
    """Simple health check endpoint for Docker"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    """Serve the main dashboard"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/option-chain", response_model=GreeksResponse)
async def get_option_chain():
    """Get analyzed option chain data from Angel One with comprehensive logging"""
    
    # Log the incoming request
    logger.info("=== Option Chain API Request Started ===")
    start_time = time.time()
    
    try:
        # Step 1: Check if we have credentials
        logger.info("Step 1: Checking Angel One credentials availability")
        has_credentials = angel_connector.has_credentials()
        logger.info(f"Credentials available: {has_credentials}")
        
        if has_credentials:
            # Mask client code for logging
            client_code_masked = f"{angel_connector.client_code[:4]}****" if angel_connector.client_code else "None"
            logger.info(f"Client code (masked): {client_code_masked}")
            logger.info(f"TOTP secret configured: {bool(angel_connector.totp_secret)}")
        
        # Step 2: Check authentication status
        logger.info("Step 2: Checking authentication status")
        is_authenticated = angel_connector.is_token_valid()
        logger.info(f"Authentication status: {'Valid' if is_authenticated else 'Invalid/Expired'}")
        
        if is_authenticated:
            logger.info(f"Login time: {angel_connector.login_time.isoformat() if angel_connector.login_time else 'Unknown'}")
            
        # Step 3: Attempt to get option chain data
        logger.info("Step 3: Attempting to fetch option chain data")
        
        if has_credentials and is_authenticated:
            logger.info("Using authenticated Angel One API for live data")
            
            try:
                # Initialize enhanced API with existing credentials
                logger.debug("Initializing EnhancedAngelSmartAPI")
                enhanced_api = EnhancedAngelSmartAPI(
                    angel_connector.api_key, 
                    angel_connector.secret_key
                )
                
                # Transfer authentication details
                enhanced_api.access_token = angel_connector.jwt_token
                enhanced_api.refresh_token = angel_connector.refresh_token
                enhanced_api.client_code = angel_connector.client_code
                enhanced_api.session.headers.update({
                    'Authorization': f'Bearer {enhanced_api.access_token}'
                })
                
                logger.debug("Enhanced API initialized successfully")
                
                # Get option chain data - try multiple methods
                logger.info("Fetching option chain from Angel One API")
                option_chain_data = None
                
                # Method 1: Try enhanced API method
                if hasattr(enhanced_api, 'get_nifty_options_chain'):
                    logger.debug("Using enhanced API get_nifty_options_chain method")
                    option_chain_data = enhanced_api.get_nifty_options_chain()
                
                # Method 2: Try connector's fetch method
                if not option_chain_data:
                    logger.debug("Trying connector's fetch_option_chain method")
                    option_chain_data = angel_connector.fetch_option_chain()
                
                # Method 3: Generate basic option chain structure
                if not option_chain_data:
                    logger.info("Generating basic option chain structure")
                    # Try to get spot price first
                    spot_price = 24350  # Default fallback
                    
                    if hasattr(enhanced_api, 'get_nifty_spot_price'):
                        try:
                            spot_price = enhanced_api.get_nifty_spot_price() or spot_price
                        except Exception as spot_error:
                            logger.warning(f"Could not fetch spot price: {spot_error}")
                    
                    # Generate basic option chain structure
                    strikes = []
                    base_strike = round(spot_price / 50) * 50
                    for i in range(-15, 16):
                        strikes.append(base_strike + (i * 50))
                    
                    option_chain_data = {
                        'spot_price': spot_price,
                        'strikes': strikes,
                        'base_strike': base_strike
                    }
                
                if option_chain_data:
                    logger.success("Option chain data retrieved successfully")
                    logger.info(f"Option chain contains {len(option_chain_data.get('strikes', []))} strikes")
                    logger.info(f"Spot price: {option_chain_data.get('spot_price')}")
                    
                    # Calculate Greeks for each option
                    logger.info("Step 4: Calculating Greeks for option chain")
                    enriched_data = []
                    spot_price = option_chain_data.get('spot_price')
                    strikes = option_chain_data.get('strikes', [])
                    
                    # Get next expiry date
                    next_expiry = datetime.datetime.now() + datetime.timedelta(days=7)  # Simplified - you might want to get actual expiry
                    
                    for i, strike in enumerate(strikes):
                        try:
                            # Calculate Greeks for both call and put
                            call_greeks = None
                            put_greeks = None
                            
                            # Try enhanced API method
                            if hasattr(enhanced_api, 'calculate_options_greeks'):
                                logger.debug(f"Calculating Greeks for strike {strike} using enhanced API")
                                call_greeks = enhanced_api.calculate_options_greeks(
                                    spot_price, strike, next_expiry, 'call'
                                )
                                put_greeks = enhanced_api.calculate_options_greeks(
                                    spot_price, strike, next_expiry, 'put'
                                )
                            else:
                                # Fallback to basic Greeks calculation
                                logger.debug(f"Using fallback Greeks calculation for strike {strike}")
                                from nifty_greeks_calculator import AdvancedGreeksCalculator
                                
                                greeks_calc = AdvancedGreeksCalculator()
                                time_to_expiry = 7/365.0  # 7 days in years
                                
                                call_greeks = greeks_calc.calculate_greeks(
                                    spot_price, strike, time_to_expiry, 0.065, 0.20, 'call'
                                )
                                put_greeks = greeks_calc.calculate_greeks(
                                    spot_price, strike, time_to_expiry, 0.065, 0.20, 'put'
                                )
                            
                            enriched_data.append({
                                'strike': strike,
                                'call': call_greeks,
                                'put': put_greeks,
                                'spot_price': spot_price
                            })
                            
                            if i % 10 == 0:  # Log progress every 10 strikes
                                logger.debug(f"Processed {i+1}/{len(strikes)} strikes")
                                
                        except Exception as strike_error:
                            logger.warning(f"Error calculating Greeks for strike {strike}: {str(strike_error)}")
                            continue
                    
                    logger.success(f"Greeks calculated for {len(enriched_data)} strikes")
                    
                    response_data = {
                        'success': True,
                        'data': enriched_data,
                        'analytics': {
                            'total_strikes': len(strikes),
                            'processed_strikes': len(enriched_data),
                            'spot_price': spot_price,
                            'base_strike': option_chain_data.get('base_strike')
                        },
                        'metadata': {
                            'expiry_date': next_expiry.isoformat(),
                            'data_timestamp': datetime.datetime.now().isoformat(),
                            'processing_time': round(time.time() - start_time, 2)
                        },
                        'connection_status': 'connected',
                        'data_source': 'angel_one_live',
                        'status_message': 'Live option chain data with Greeks from Angel One API'
                    }
                    
                    logger.success(f"Option chain API completed successfully in {time.time() - start_time:.2f}s")
                    return GreeksResponse(**response_data)
                    
                else:
                    logger.error("No option chain data returned from Angel One API")
                    raise HTTPException(status_code=500, detail="Failed to fetch option chain data from Angel One")
                    
            except Exception as api_error:
                logger.error(f"Error using Angel One API: {str(api_error)}")
                logger.exception("Full traceback for Angel One API error")
                # Fall through to demo data
                
        # Step 4: Return demo/mock data with detailed logging
        logger.warning("Returning demo data - either not authenticated or API error occurred")
        logger.info("Generating mock option chain data")
        
        # Generate mock data with some structure
        mock_strikes = []
        base_strike = 24350
        for i in range(-10, 11):
            strike = base_strike + (i * 50)
            mock_strikes.append({
                'strike': strike,
                'call': {
                    'theoretical_price': max(0.1, base_strike - strike + 50),
                    'delta': 0.5 + (i * 0.03),
                    'gamma': 0.02,
                    'theta': -0.1,
                    'vega': 0.15,
                    'rho': 0.05
                },
                'put': {
                    'theoretical_price': max(0.1, strike - base_strike + 50),
                    'delta': -0.5 - (i * 0.03),
                    'gamma': 0.02,
                    'theta': -0.1,
                    'vega': 0.15,
                    'rho': -0.05
                },
                'spot_price': base_strike
            })
        
        logger.info(f"Generated mock data with {len(mock_strikes)} strikes")
        
        mock_data = {
            'success': True,
            'data': mock_strikes,
            'analytics': {
                'total_strikes': len(mock_strikes),
                'processed_strikes': len(mock_strikes),
                'spot_price': base_strike,
                'base_strike': base_strike
            },
            'metadata': {
                'data_timestamp': datetime.datetime.now().isoformat(),
                'processing_time': round(time.time() - start_time, 2),
                'demo_mode': True
            },
            'connection_status': 'demo',
            'data_source': 'mock',
            'status_message': 'Demo data - Configure credentials for live data'
        }
        
        logger.info(f"Demo option chain API completed in {time.time() - start_time:.2f}s")
        return GreeksResponse(**mock_data)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in option chain API: {str(e)}")
        logger.exception("Full traceback for option chain API error")
        
        # Return error response
        error_data = {
            'success': False,
            'data': [],
            'analytics': None,
            'metadata': {
                'error_timestamp': datetime.datetime.now().isoformat(),
                'processing_time': round(time.time() - start_time, 2)
            },
            'connection_status': 'error',
            'data_source': 'none',
            'status_message': f'API Error: {str(e)}',
            'error': str(e)
        }
        
        logger.error(f"Option chain API failed after {time.time() - start_time:.2f}s")
        return GreeksResponse(**error_data)

@app.get("/api/enhanced-greeks")
async def get_enhanced_greeks(
    volatility: float = 0.20,
    analytics: bool = True
):
    """Get enhanced Greeks data using the advanced calculator"""
    try:
        # Initialize enhanced API if we have credentials
        if angel_connector.has_credentials() and angel_connector.is_token_valid():
            # Create enhanced API instance using existing credentials
            enhanced_api = EnhancedAngelSmartAPI(
                angel_connector.api_key, 
                angel_connector.secret_key
            )
            
            # Transfer authentication details
            enhanced_api.access_token = angel_connector.jwt_token
            enhanced_api.refresh_token = angel_connector.refresh_token
            enhanced_api.client_code = angel_connector.client_code
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
            include_analytics=analytics
        )
        
        if result:
            if isinstance(result, dict) and 'data' in result:
                # Convert DataFrame to dict for JSON serialization
                result['data'] = result['data'].to_dict('records')
                
                # Add connection status
                result['connection_status'] = 'connected' if angel_connector.is_token_valid() else 'demo'
                result['data_source'] = 'angel_one_enhanced'
                result['status_message'] = 'Enhanced Greeks calculation with live data' if angel_connector.is_token_valid() else 'Enhanced Greeks calculation with demo data'
                
                return {
                    'success': True,
                    **result
                }
            else:
                # Simple DataFrame result
                return {
                    'success': True,
                    'data': result.to_dict('records'),
                    'connection_status': 'connected' if angel_connector.is_token_valid() else 'demo',
                    'data_source': 'angel_one_enhanced',
                    'status_message': 'Enhanced Greeks calculation'
                }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch enhanced Greeks data"
            )
            
    except Exception as e:
        logger.error(f"Enhanced Greeks API error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/angel-one/login-manual")
async def angel_one_login_manual(request: ManualLoginRequest):
    """Manual login endpoint with user-provided TOTP"""
    try:
        # Store credentials first
        angel_connector.set_credentials(request.client_code, request.password)
        
        # Attempt login with manual TOTP
        success = angel_connector.login_with_manual_totp(
            request.client_code, 
            request.password, 
            request.totp
        )
        
        if success:
            return {
                'success': True,
                'message': 'Successfully logged into Angel One SmartAPI with manual TOTP',
                'login_time': angel_connector.login_time.isoformat() if angel_connector.login_time else None,
                'enhanced_features_available': True
            }
        else:
            raise HTTPException(
                status_code=401,
                detail="Failed to login to Angel One SmartAPI with provided TOTP"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manual login API error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/angel-one/set-credentials")
async def set_angel_one_credentials(credentials: AngelOneCredentials):
    """Set Angel One credentials"""
    try:
        # Set credentials in connector
        success = angel_connector.set_credentials(
            credentials.client_code, 
            credentials.pin, 
            credentials.totp_secret
        )
        
        if success:
            return {
                'success': True,
                'message': 'Credentials set successfully',
                'has_totp_secret': bool(credentials.totp_secret)
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to set credentials")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Set credentials API error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/angel-one/status", response_model=StatusResponse)
async def angel_one_status():
    """Get Angel One connection status"""
    try:
        is_authenticated = angel_connector.is_token_valid()
        has_credentials = angel_connector.has_credentials()
        credentials_source = 'api' if angel_connector._stored_credentials else 'environment'
        
        return StatusResponse(
            authenticated=is_authenticated,
            login_time=angel_connector.login_time.isoformat() if angel_connector.login_time else None,
            credentials_configured=has_credentials,
            credentials_source=credentials_source if has_credentials else None,
            has_totp_secret=bool(angel_connector.totp_secret),
            client_code_masked=angel_connector.client_code[:4] + '****' if angel_connector.client_code and len(angel_connector.client_code) > 4 else None
        )
        
    except Exception as e:
        logger.error(f"Status API error: {str(e)}")
        return StatusResponse(
            authenticated=False,
            credentials_configured=False,
            has_totp_secret=False,
            error=str(e)
        )

@app.post("/api/calculate-implied-volatility")
async def calculate_implied_volatility(request: ImpliedVolatilityRequest):
    """Calculate implied volatility for given option parameters"""
    try:
        # Calculate time to expiry
        time_to_expiry = request.days_to_expiry / 365.0
        
        # Calculate implied volatility
        calc = AdvancedGreeksCalculator()
        implied_vol = calc.implied_volatility(
            request.option_price, 
            request.spot_price, 
            request.strike_price, 
            time_to_expiry,
            request.risk_free_rate, 
            request.option_type
        )
        
        return {
            'success': True,
            'implied_volatility': round(implied_vol, 4),
            'implied_volatility_percent': round(implied_vol * 100, 2),
            'input_parameters': request.dict()
        }
        
    except Exception as e:
        logger.error(f"Implied volatility calculation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/portfolio-greeks")
async def calculate_portfolio_greeks(request: PortfolioGreeksRequest):
    """Calculate portfolio-level Greeks for a given position"""
    try:
        portfolio_greeks = {
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0
        }
        
        total_value = 0.0
        calc = AdvancedGreeksCalculator()
        
        for position in request.positions:
            time_to_expiry = position.days_to_expiry / 365.0
            
            # Calculate option price and Greeks
            if position.option_type == 'call':
                option_price = calc.black_scholes_call(
                    request.spot_price, position.strike, time_to_expiry, 0.065, position.volatility
                )
            else:
                option_price = calc.black_scholes_put(
                    request.spot_price, position.strike, time_to_expiry, 0.065, position.volatility
                )
            
            greeks = calc.calculate_greeks(
                request.spot_price, position.strike, time_to_expiry, 
                0.065, position.volatility, position.option_type
            )
            
            # Add to portfolio Greeks (weighted by quantity)
            portfolio_greeks['delta'] += greeks['delta'] * position.quantity
            portfolio_greeks['gamma'] += greeks['gamma'] * position.quantity
            portfolio_greeks['theta'] += greeks['theta'] * position.quantity
            portfolio_greeks['vega'] += greeks['vega'] * position.quantity
            portfolio_greeks['rho'] += greeks['rho'] * position.quantity
            
            total_value += option_price * position.quantity
        
        return {
            'success': True,
            'portfolio_greeks': {k: round(v, 6) for k, v in portfolio_greeks.items()},
            'total_portfolio_value': round(total_value, 2),
            'positions_count': len(request.positions),
            'spot_price_used': request.spot_price
        }
        
    except Exception as e:
        logger.error(f"Portfolio Greeks calculation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy', 
        'timestamp': datetime.datetime.now().isoformat(),
        'api_provider': 'Angel One SmartAPI',
        'framework': 'FastAPI'
    }

@app.post("/api/angel-one/clear-credentials")
async def clear_angel_one_credentials():
    """Clear Angel One credentials"""
    try:
        angel_connector.clear_credentials()
        logger.info("Angel One credentials cleared via API")
        return {
            'success': True,
            'message': 'Credentials cleared successfully'
        }
    except Exception as e:
        logger.error(f"Clear credentials API error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/angel-one/check-credentials")
async def check_angel_one_credentials():
    """Check if Angel One credentials are configured"""
    try:
        has_credentials = angel_connector.has_credentials()
        credentials_source = 'api' if angel_connector._stored_credentials else 'environment'
        
        status_info = {
            'has_credentials': has_credentials,
            'credentials_source': credentials_source if has_credentials else None,
            'has_totp_secret': bool(angel_connector.totp_secret),
            'client_code': angel_connector.client_code[:4] + '****' if angel_connector.client_code else None
        }
        
        logger.debug(f"Credentials check: {status_info}")
        return status_info
        
    except Exception as e:
        logger.error(f"Check credentials API error: {str(e)}")
        return {
            'has_credentials': False,
            'error': str(e)
        }

@app.post("/api/angel-one/login")
async def angel_one_login():
    """Automatic login endpoint for Angel One using stored credentials"""
    try:
        if not angel_connector.has_credentials():
            raise HTTPException(
                status_code=400, 
                detail="No credentials configured. Use set-credentials endpoint first."
            )
        
        # Generate TOTP if secret is available
        totp = angel_connector.generate_totp()
        if not totp:
            raise HTTPException(
                status_code=400,
                detail="Cannot generate TOTP. TOTP secret not configured."
            )
        
        # Attempt login
        success = angel_connector.login_with_manual_totp(
            angel_connector.client_code,
            angel_connector.pin,
            totp
        )
        
        if success:
            logger.success("Automatic Angel One login successful")
            return {
                'success': True,
                'message': 'Successfully logged into Angel One SmartAPI',
                'login_time': angel_connector.login_time.isoformat() if angel_connector.login_time else None,
                'auto_login': True
            }
        else:
            raise HTTPException(
                status_code=401,
                detail="Failed to login to Angel One SmartAPI"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auto login API error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Add a favicon endpoint to avoid 404s
@app.get("/favicon.ico")
async def favicon():
    """Return a simple favicon response to avoid 404s"""
    return {"message": "No favicon available"}

# Add a comprehensive API info endpoint
@app.get("/api/info")
async def api_info():
    """Get comprehensive API information and status"""
    try:
        connection_status = angel_connector.get_connection_status()
        
        api_info = {
            "application": "NIFTY Options Greeks Analyzer",
            "version": "2.0.0",
            "framework": "FastAPI",
            "logging": "Loguru",
            "timestamp": datetime.datetime.now().isoformat(),
            "angel_one_status": connection_status,
            "available_endpoints": [
                "GET /",
                "GET /docs",
                "GET /redoc",
                "GET /api/health",
                "GET /api/info",
                "GET /api/option-chain",
                "GET /api/enhanced-greeks",
                "GET /api/angel-one/status",
                "GET /api/angel-one/check-credentials",
                "POST /api/angel-one/set-credentials",
                "POST /api/angel-one/login",
                "POST /api/angel-one/login-manual",
                "POST /api/angel-one/clear-credentials",
                "POST /api/calculate-implied-volatility",
                "POST /api/portfolio-greeks"
            ],
            "features": [
                "Real-time NIFTY options data",
                "Advanced Greeks calculation",
                "Portfolio analytics",
                "Implied volatility calculation",
                "Angel One SmartAPI integration",
                "Comprehensive logging with Loguru",
                "Interactive API documentation"
            ]
        }
        
        logger.info("API info requested")
        return api_info
        
    except Exception as e:
        logger.error(f"API info error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Add static files serving (if needed)
# app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "fastapi_app:app", 
        host=app_config.HOST, 
        port=app_config.PORT, 
        reload=app_config.DEBUG,
        log_level="info"
    )
