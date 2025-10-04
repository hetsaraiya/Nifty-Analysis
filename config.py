"""
Configuration settings for NIFTY Option Chain Analysis Application
"""

import os
from datetime import timedelta

class Config:
    """Base configuration class"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'nifty-option-chain-analysis-2024'
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Cache settings
    CACHE_TIMEOUT = int(os.environ.get('CACHE_TIMEOUT', 300))  # 5 minutes
    
    # Network configuration
    CLIENT_LOCAL_IP = os.environ.get('CLIENT_LOCAL_IP', '127.0.0.1')
    CLIENT_PUBLIC_IP = os.environ.get('CLIENT_PUBLIC_IP', '127.0.0.1')
    MAC_ADDRESS = os.environ.get('MAC_ADDRESS', '00:00:00:00:00:00')
    
    # Request settings
    REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', 15))
    
    # Option analysis settings
    DEFAULT_SYMBOL = 'NIFTY'
    RISK_FREE_RATE = float(os.environ.get('RISK_FREE_RATE', 0.065))  # 6.5%
    DIVIDEND_YIELD = float(os.environ.get('DIVIDEND_YIELD', 0.0))    # 0% for index
    
    # Auto-refresh settings
    AUTO_REFRESH_INTERVAL = int(os.environ.get('AUTO_REFRESH_INTERVAL', 30))  # seconds
    
    # Chart settings
    MAX_STRIKES_IN_CHART = int(os.environ.get('MAX_STRIKES_IN_CHART', 21))  # ATM ± 10
    GREEKS_CALCULATION_RANGE = int(os.environ.get('GREEKS_CALCULATION_RANGE', 2))  # ATM ± 2
    
    # Application settings
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5000))
    
    # Security settings
    SESSION_TIMEOUT = int(os.environ.get('SESSION_TIMEOUT', 3600))  # 1 hour
    REQUIRE_ALL_CREDENTIALS = os.environ.get('REQUIRE_ALL_CREDENTIALS', 'True').lower() == 'true'
    
    # Logging settings
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s: %(message)s'
    
    # Angel One specific settings
    JWT_REFRESH_THRESHOLD = 300  # Refresh JWT if expires within 5 minutes
    MAX_RETRY_ATTEMPTS = 3
    RETRY_DELAY = 2  # seconds

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    CACHE_TIMEOUT = 60  # Shorter cache for development
    REQUIRE_ALL_CREDENTIALS = False  # Allow mock data in development

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    
    # Enhanced security for production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    REQUIRE_ALL_CREDENTIALS = True

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    CACHE_TIMEOUT = 0  # No cache for testing
    REQUIRE_ALL_CREDENTIALS = False

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}