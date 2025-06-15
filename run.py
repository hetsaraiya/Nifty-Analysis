#!/usr/bin/env python3
"""
Startup script for NIFTY Option Chain Analysis Application
Usage: python run.py [environment]
Environment options: development, production, testing
"""

import os
import sys
import logging
from app import app
from config import config

def setup_logging(config_class):
    """Configure logging based on environment"""
    logging.basicConfig(
        level=getattr(logging, config_class.LOG_LEVEL),
        format=config_class.LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('nifty_analysis.log') if not config_class.DEBUG else logging.NullHandler()
        ]
    )

def main():
    """Main entry point"""
    # Determine environment
    env = sys.argv[1] if len(sys.argv) > 1 else 'development'
    if env not in config:
        print(f"Invalid environment: {env}")
        print("Available environments: development, production, testing")
        sys.exit(1)
    
    # Load configuration
    config_class = config[env]
    app.config.from_object(config_class)
    
    # Setup logging
    setup_logging(config_class)
    
    # Display startup information
    logger = logging.getLogger(__name__)
    logger.info(f"Starting NIFTY Option Chain Analysis in {env} mode")
    logger.info(f"Server will run on {config_class.HOST}:{config_class.PORT}")
    logger.info(f"Debug mode: {config_class.DEBUG}")
    logger.info(f"Cache timeout: {config_class.CACHE_TIMEOUT} seconds")
    logger.info(f"Auto-refresh interval: {config_class.AUTO_REFRESH_INTERVAL} seconds")
    
    # Run the application
    try:
        app.run(
            host=config_class.HOST,
            port=config_class.PORT,
            debug=config_class.DEBUG,
            threaded=True
        )
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application failed to start: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()