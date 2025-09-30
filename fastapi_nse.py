"""
NIFTY 50 Option Chain Analysis FastAPI Application with NSE India Data
A comprehensive API for analyzing NIFTY options with real-time data from NSE India,
Greeks calculation, portfolio analysis, and advanced options analytics.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time
import os
from loguru import logger
from nse_nifty_greeks import NSEFinanceAPI, NiftyOptionsChain, GreeksCalculator, PortfolioGreeksCalculator
from enhanced_oi_calculator import OpenInterestCalculator, MarketDataEnhancer

# Configure Loguru logging
logger.remove()  # Remove default handler
logger.add(
    "logs/fastapi_nse.log",
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
# Console logging for development
logger.add(
    lambda msg: print(msg, end=""),
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>"
)

# Initialize FastAPI app
app = FastAPI(
    title="NIFTY Options Greeks Analyzer - NSE India Edition",
    description="Comprehensive NIFTY options analysis with real-time NSE India data",
    version="4.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

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
    """Log all HTTP requests and responses"""
    start_time = time.time()
    
    # Log request
    logger.info(f">>> {request.method} {request.url}")
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    
    # Log response
    logger.info(f"<<< {request.method} {request.url} - {response.status_code} - {process_time:.3f}s")
    
    # Add processing time to response headers
    response.headers["X-Process-Time"] = str(process_time)
    
    return response

# Templates
templates = Jinja2Templates(directory="templates")

# Pydantic models for request/response
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
    spot_price: Optional[float] = Field(None, description="Current spot price (will fetch if not provided)")

class OptionsChainRequest(BaseModel):
    spot_price: Optional[float] = Field(None, description="Current spot price (will fetch if not provided)")
    expiry_date: Optional[str] = Field(None, description="Expiry date (YYYY-MM-DD format, defaults to next Thursday)")
    volatility: Optional[float] = Field(None, description="Implied volatility (will calculate if not provided)")
    risk_free_rate: float = Field(0.065, description="Risk-free rate")
    num_strikes: int = Field(31, ge=5, le=101, description="Number of strikes to generate")
    atm_only: bool = Field(False, description="Generate only 5 strikes above and 5 below ATM (11 total)")

class GreeksResponse(BaseModel):
    success: bool
    data: Optional[List[Dict]] = None
    analytics: Optional[Dict] = None
    metadata: Optional[Dict] = None
    data_source: str = "NSE India"
    timestamp: str
    error: Optional[str] = None

class StatusResponse(BaseModel):
    status: str
    data_source: str
    timestamp: str
    api_version: str
    endpoints_available: int

# Initialize components
nse_api = NSEFinanceAPI()
options_chain = NiftyOptionsChain()
greeks_calc = GreeksCalculator()
portfolio_calc = PortfolioGreeksCalculator()
oi_calculator = OpenInterestCalculator()
market_enhancer = MarketDataEnhancer()

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main dashboard"""
    try:
        # Get current market data for the dashboard
        spot_price = nse_api.get_nifty_price()
        
        context = {
            "request": request,
            "title": "NIFTY Options Greeks Analyzer",
            "version": "4.0.0",
            "data_source": "NSE India",
            "spot_price": spot_price,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        logger.info("Dashboard page requested")
        return templates.TemplateResponse("index.html", context)
        
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        context = {
            "request": request,
            "title": "NIFTY Options Greeks Analyzer",
            "error": "Could not load dashboard data"
        }
        return templates.TemplateResponse("index.html", context)

@app.get("/health")
async def health_check():
    """Simple health check endpoint for Docker"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Get API status and health check"""
    try:
        # Test NSE India connection
        spot_price = nse_api.get_nifty_price()
        status = "healthy" if spot_price else "degraded"
        
        return StatusResponse(
            status=status,
            data_source="NSE India",
            timestamp=datetime.now().isoformat(),
            api_version="4.0.0",
            endpoints_available=8
        )
        
    except Exception as e:
        logger.error(f"Status check error: {str(e)}")
        return StatusResponse(
            status="error",
            data_source="NSE India",
            timestamp=datetime.now().isoformat(),
            api_version="3.0.0",
            endpoints_available=8
        )

@app.get("/api/nifty-price")
async def get_nifty_price():
    """Get current NIFTY 50 price"""
    try:
        logger.info("NIFTY price requested")
        spot_price = nse_api.get_nifty_price()
        
        if spot_price is None:
            raise HTTPException(status_code=503, detail="Could not fetch NIFTY price")
        
        return {
            "success": True,
            "data": {
                "spot_price": spot_price,
                "symbol": "NIFTY 50",
                "source": "NSE India"
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching NIFTY price: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/historical-volatility")
async def get_historical_volatility(days: int = 30):
    """Get historical volatility for NIFTY"""
    try:
        logger.info(f"Historical volatility requested for {days} days")
        
        if days < 5 or days > 252:
            raise HTTPException(status_code=400, detail="Days must be between 5 and 252")
        
        volatility = nse_api.calculate_historical_volatility(days)
        
        return {
            "success": True,
            "data": {
                "volatility": volatility,
                "volatility_percent": round(volatility * 100, 2),
                "period_days": days,
                "annualized": True
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating volatility: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/options-chain", response_model=GreeksResponse)
async def generate_options_chain(request: OptionsChainRequest):
    """Generate complete NIFTY options chain with Greeks and Enhanced OI Analysis"""
    try:
        logger.info("Enhanced options chain generation requested")
        
        # Parse expiry date if provided
        expiry_date = None
        if request.expiry_date:
            try:
                expiry_date = datetime.strptime(request.expiry_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid expiry date format. Use YYYY-MM-DD")
        
        # Generate base options chain
        df = options_chain.generate_options_chain(
            spot_price=request.spot_price,
            expiry_date=expiry_date,
            volatility=request.volatility,
            risk_free_rate=request.risk_free_rate,
            num_strikes=request.num_strikes,
            atm_only=request.atm_only
        )
        
        # Convert DataFrame to list of dictionaries
        options_data = df.to_dict('records')
        
        # Get spot price and volatility for enhancements
        spot_price = float(df.iloc[0]['spot_price'])
        volatility = float(df.iloc[0]['implied_volatility'])
        
        # Enhance options data with realistic OI and market data
        logger.info("Enhancing options data with realistic Open Interest patterns")
        enhanced_options_data = market_enhancer.enhance_options_data(
            options_data, spot_price, volatility
        )
        
        # Calculate comprehensive analytics including OI analysis
        logger.info("Calculating comprehensive market analytics")
        comprehensive_analytics = market_enhancer.calculate_comprehensive_analytics(
            enhanced_options_data, spot_price
        )
        
        # Combine with original analysis
        analysis = options_chain.analyze_options_chain(df)
        analysis.update(comprehensive_analytics)
        
        metadata = {
            "total_options": int(len(enhanced_options_data)),
            "spot_price": spot_price,
            "expiry_date": str(df.iloc[0]['expiry_date']),
            "days_to_expiry": int(df.iloc[0]['days_to_expiry']),
            "implied_volatility": volatility,
            "risk_free_rate": float(request.risk_free_rate),
            "strikes_range": {
                "min": float(df['strike'].min()),
                "max": float(df['strike'].max()),
                "count": int(len(df['strike'].unique()))
            },
            "oi_enhancement": "Theoretical OI patterns based on market behavior",
            "data_features": [
                "Theoretical Option Pricing (Black-Scholes)",
                "Complete Greeks Calculation",
                "Realistic Open Interest Patterns", 
                "Max Pain Analysis",
                "Support/Resistance Identification",
                "Put-Call Ratio Analysis"
            ]
        }
        
        logger.success(f"Generated enhanced options chain with {len(enhanced_options_data)} options and comprehensive OI analysis")
        
        return GreeksResponse(
            success=True,
            data=enhanced_options_data,
            analytics=analysis,
            metadata=metadata,
            data_source="NSE India + Enhanced OI Analysis",
            timestamp=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating options chain: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/calculate-implied-volatility")
async def calculate_implied_volatility(request: ImpliedVolatilityRequest):
    """Calculate implied volatility from option price"""
    try:
        logger.info("Implied volatility calculation requested")
        
        time_to_expiry = request.days_to_expiry / 365.0
        
        implied_vol = greeks_calc.calculate_implied_volatility(
            option_price=request.option_price,
            S=request.spot_price,
            K=request.strike_price,
            T=time_to_expiry,
            r=request.risk_free_rate,
            option_type=request.option_type.lower()
        )
        
        return {
            "success": True,
            "data": {
                "implied_volatility": implied_vol,
                "implied_volatility_percent": round(implied_vol * 100, 2),
                "option_price": request.option_price,
                "spot_price": request.spot_price,
                "strike_price": request.strike_price,
                "days_to_expiry": request.days_to_expiry,
                "option_type": request.option_type.upper()
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error calculating implied volatility: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/portfolio-greeks")
async def calculate_portfolio_greeks(request: PortfolioGreeksRequest):
    """Calculate portfolio-level Greeks"""
    try:
        logger.info(f"Portfolio Greeks calculation requested for {len(request.positions)} positions")
        
        # Get spot price if not provided
        spot_price = request.spot_price
        if spot_price is None:
            spot_price = nse_api.get_nifty_price()
            if spot_price is None:
                raise HTTPException(status_code=503, detail="Could not fetch current NIFTY price")
        
        # Convert positions to list of dictionaries
        positions = [pos.dict() for pos in request.positions]
        
        # Calculate portfolio Greeks
        result = portfolio_calc.calculate_portfolio_greeks(positions, spot_price)
        
        logger.success(f"Calculated portfolio Greeks for {len(positions)} positions")
        
        return {
            "success": True,
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating portfolio Greeks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/option-greeks")
async def calculate_single_option_greeks(
    spot_price: float,
    strike_price: float,
    days_to_expiry: int,
    option_type: str,
    volatility: float = 0.20,
    risk_free_rate: float = 0.065
):
    """Calculate Greeks for a single option"""
    try:
        logger.info(f"Single option Greeks calculation requested: {option_type.upper()} {strike_price}")
        
        if option_type.lower() not in ['call', 'put']:
            raise HTTPException(status_code=400, detail="Option type must be 'call' or 'put'")
        
        time_to_expiry = days_to_expiry / 365.0
        
        # Calculate option price
        if option_type.lower() == 'call':
            option_price = greeks_calc.black_scholes_call(
                spot_price, strike_price, time_to_expiry, risk_free_rate, volatility
            )
        else:
            option_price = greeks_calc.black_scholes_put(
                spot_price, strike_price, time_to_expiry, risk_free_rate, volatility
            )
        
        # Calculate Greeks
        greeks = greeks_calc.calculate_greeks(
            spot_price, strike_price, time_to_expiry, risk_free_rate, volatility, option_type.lower()
        )
        
        # Calculate additional metrics
        if option_type.lower() == 'call':
            intrinsic_value = max(spot_price - strike_price, 0)
        else:
            intrinsic_value = max(strike_price - spot_price, 0)
        
        time_value = max(option_price - intrinsic_value, 0)
        
        moneyness = 'ATM' if abs(strike_price - spot_price) <= 25 else ('ITM' if (
            (option_type.lower() == 'call' and strike_price < spot_price) or
            (option_type.lower() == 'put' and strike_price > spot_price)
        ) else 'OTM')
        
        result = {
            "option_details": {
                "spot_price": spot_price,
                "strike_price": strike_price,
                "option_type": option_type.upper(),
                "days_to_expiry": days_to_expiry,
                "time_to_expiry": round(time_to_expiry, 6),
                "volatility": volatility,
                "risk_free_rate": risk_free_rate
            },
            "pricing": {
                "theoretical_price": round(option_price, 2),
                "intrinsic_value": round(intrinsic_value, 2),
                "time_value": round(time_value, 2),
                "moneyness": moneyness
            },
            "greeks": greeks
        }
        
        return {
            "success": True,
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating option Greeks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/info")
async def get_api_info():
    """Get comprehensive API information"""
    try:
        # Test data source connectivity
        spot_price = nse_api.get_nifty_price()
        data_status = "connected" if spot_price else "disconnected"
        
        api_info = {
            "title": "NIFTY Options Greeks Analyzer",
            "version": "3.0.0",
            "description": "NSE India powered NIFTY options analysis API",
            "data_source": {
                "provider": "NSE India",
                "status": data_status,
                "last_price": spot_price,
                "features": [
                    "Real-time NIFTY pricing",
                    "Historical volatility calculation",
                    "Live market data access"
                ]
            },
            "capabilities": [
                "Black-Scholes options pricing",
                "Complete Greeks calculation (Delta, Gamma, Theta, Vega, Rho)",
                "Implied volatility calculation",
                "Portfolio Greeks aggregation",
                "Options chain generation",
                "Historical volatility analysis"
            ],
            "endpoints": [
                "GET / - Web dashboard",
                "GET /api/status - API health check",
                "GET /api/nifty-price - Current NIFTY price",
                "GET /api/historical-volatility - Historical volatility",
                "POST /api/options-chain - Generate options chain",
                "POST /api/calculate-implied-volatility - Calculate IV",
                "POST /api/portfolio-greeks - Portfolio analysis",
                "GET /api/option-greeks - Single option Greeks",
                "GET /api/info - This endpoint"
            ],
            "documentation": {
                "swagger_ui": "/docs",
                "redoc": "/redoc"
            },
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info("API info requested")
        return api_info
        
    except Exception as e:
        logger.error(f"API info error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "3.0.0"
    }

@app.get("/api/oi-chart-data")
async def get_oi_chart_data():
    """Generate sample OI chart data for testing the enhanced visualization"""
    try:
        logger.info("OI chart data requested")
        
        # Get current spot price
        spot_price = nse_api.get_nifty_price()
        if not spot_price:
            spot_price = 24350  # Fallback
            
        # Generate strikes around current price
        strikes = []
        base_strike = round(spot_price / 50) * 50
        for i in range(-10, 11):
            strikes.append(base_strike + (i * 50))
        
        # Calculate theoretical OI
        oi_data = oi_calculator.calculate_theoretical_oi(
            spot_price, strikes, volatility=0.20, days_to_expiry=7
        )
        
        # Generate chart data
        chart_data = oi_calculator.generate_oi_chart_data(oi_data)
        
        # Calculate analytics
        max_pain = oi_calculator.calculate_max_pain(oi_data)
        support_levels, resistance_levels = oi_calculator.identify_support_resistance(oi_data, spot_price)
        
        response_data = {
            "success": True,
            "chart_data": chart_data,
            "analytics": {
                "spot_price": spot_price,
                "max_pain_strike": max_pain,
                "total_call_oi": chart_data["total_call_oi"],
                "total_put_oi": chart_data["total_put_oi"],
                "total_pcr": chart_data["total_pcr"],
                "support_levels": support_levels,
                "resistance_levels": resistance_levels
            },
            "metadata": {
                "total_strikes": len(strikes),
                "strike_range": f"{min(strikes)} - {max(strikes)}",
                "generated_at": datetime.now().isoformat()
            }
        }
        
        logger.success("Generated OI chart data successfully")
        return response_data
        
    except Exception as e:
        logger.error(f"Error generating OI chart data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "fastapi_nse:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )
