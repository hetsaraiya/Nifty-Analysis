# NIFTY Options Greeks Calculator - NSE India Edition

A comprehensive FastAPI-based application for analyzing NIFTY 50 options with **real-time market data from NSE India**. This application provides advanced Greeks calculations, portfolio analysis, and theoretical options pricing using the Black-Scholes model.

## 🚀 Features

### Core Capabilities
- **Real-time NIFTY 50 Data**: Live spot prices directly from NSE India
- **Live Options Chain**: Real options data from NSE including strikes, OI, volumes
- **Advanced Greeks Calculation**: Delta, Gamma, Theta, Vega, and Rho
- **Complete Options Chain**: Theoretical pricing for all strike prices
- **Historical Volatility**: Calculated from NSE options implied volatility
- **Portfolio Analysis**: Aggregate Greeks for multiple positions
- **Implied Volatility**: Calculate IV from market prices
- **Web Dashboard**: Interactive HTML interface
- **REST API**: Complete JSON API with comprehensive documentation

### Technical Features
- **FastAPI Framework**: High-performance async web framework
- **NSE India Integration**: Direct data from National Stock Exchange
- **Advanced Web Scraping**: Robust session management and error handling
- **Black-Scholes Model**: Industry-standard options pricing
- **Comprehensive Logging**: Detailed logging with Loguru
- **Type Safety**: Full Pydantic validation
- **Error Handling**: Robust error handling and graceful fallbacks

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- Internet connection for live NSE data

### Quick Start
```bash
# Clone or download the project
cd Nifty-Analysis

# Install dependencies
pip install -r requirements.txt

# Start the application
./start_nse_api.sh
```

### Manual Installation
```bash
# Install dependencies
pip install fastapi uvicorn pandas numpy scipy requests loguru pydantic jinja2

# Start the server
python -m uvicorn fastapi_nse:app --host 0.0.0.0 --port 8000 --reload
```

## 🌐 Usage

### Web Dashboard
Open your browser and navigate to:
```
http://localhost:8000
```

### API Documentation
Interactive API documentation available at:
```
http://localhost:8000/docs     # Swagger UI
http://localhost:8000/redoc    # ReDoc
```

### API Endpoints

#### 1. Health Check
```bash
GET /api/status
```
Returns API health status and NSE data source connectivity.

#### 2. Current NIFTY Price
```bash
GET /api/nifty-price
```
Get real-time NIFTY 50 spot price from NSE India.

#### 3. Historical Volatility
```bash
GET /api/historical-volatility?days=30
```
Calculate historical volatility from NSE options data.

#### 4. Options Chain Generation
```bash
POST /api/options-chain
Content-Type: application/json

{
    "num_strikes": 31,
    "risk_free_rate": 0.065,
    "volatility": 0.15
}
```
Generate complete options chain with live NSE data, theoretical pricing and Greeks.

#### 5. Implied Volatility Calculation
```bash
POST /api/calculate-implied-volatility
Content-Type: application/json

{
    "option_price": 250.5,
    "spot_price": 24500,
    "strike_price": 24500,
    "days_to_expiry": 7,
    "risk_free_rate": 0.065,
    "option_type": "call"
}
```

#### 6. Single Option Greeks
```bash
GET /api/option-greeks?spot_price=24500&strike=24500&days_to_expiry=7&volatility=0.15&option_type=call
```

#### 7. Portfolio Greeks
```bash
POST /api/portfolio-greeks
Content-Type: application/json

{
    "positions": [
        {
            "quantity": 100,
            "delta": 0.5,
            "gamma": 0.001,
            "theta": -10,
            "vega": 50,
            "rho": 5,
            "price": 250
        }
    ],
    "spot_price": 24500
}
```

## 📈 Example Responses

### Options Chain Response
```json
{
    "success": true,
    "data": [
        {
            "symbol": "NIFTY",
            "strike": 24700.0,
            "option_type": "CALL",
            "spot_price": 24718.6,
            "market_price": 145.50,
            "theoretical_price": 145.23,
            "open_interest": 2500000,
            "volume": 150000,
            "delta": 0.5234,
            "gamma": 0.000156,
            "theta": -12.45,
            "vega": 89.34,
            "rho": 23.45,
            "implied_volatility": 0.1017,
            "moneyness": "ATM",
            "days_to_expiry": 7,
            "data_source": "NSE_LIVE"
        }
    ],
    "analytics": {
        "spot_price": 24718.6,
        "atm_strike": 24700.0,
        "total_options": 62,
        "average_iv": 0.1017
    }
}
```

## 🧮 Mathematical Models

### Black-Scholes Formula
The application uses the classic Black-Scholes model for options pricing:

**Call Option:**
```
C = S₀N(d₁) - Ke⁻ʳᵀN(d₂)
```

**Put Option:**
```
P = Ke⁻ʳᵀN(-d₂) - S₀N(-d₁)
```

Where:
- `d₁ = [ln(S₀/K) + (r + σ²/2)T] / (σ√T)`
- `d₂ = d₁ - σ√T`
- S₀ = Current stock price
- K = Strike price
- r = Risk-free rate
- T = Time to expiration
- σ = Volatility
- N() = Cumulative normal distribution

### Greeks Calculations
- **Delta (Δ)**: Rate of change of option price with respect to underlying price
- **Gamma (Γ)**: Rate of change of delta with respect to underlying price
- **Theta (Θ)**: Rate of change of option price with respect to time
- **Vega (ν)**: Rate of change of option price with respect to volatility
- **Rho (ρ)**: Rate of change of option price with respect to interest rate

## 🧪 Testing

### Run Test Suite
```bash
# Start the server first
./start_nse_api.sh

# In another terminal, test endpoints
curl http://localhost:8000/api/status
curl http://localhost:8000/api/nifty-price
```

### Manual Testing
```bash
# Test NSE data fetcher
python -c "from nse_data_fetcher import NSEDataFetcher; print(NSEDataFetcher().get_nifty_spot_price())"

# Test options chain generation
python -c "from nse_nifty_greeks import NiftyOptionsChain; print(len(NiftyOptionsChain().generate_options_chain(num_strikes=5)))"

# Run full demo
python nse_nifty_greeks.py
```

## 🏗️ Architecture

### Project Structure
```
Nifty-Analysis/
├── fastapi_nse.py              # Main FastAPI application
├── nse_data_fetcher.py         # NSE India data scraper
├── nse_nifty_greeks.py         # Greeks calculator with NSE data
├── enhanced_oi_calculator.py   # Open Interest analytics
├── templates/
│   └── index.html              # Web dashboard
├── logs/                       # Application logs
├── requirements.txt            # Python dependencies
├── start_nse_api.sh           # Startup script
└── README.md                   # This file
```

### Data Flow
1. **NSE Data Fetcher** (`nse_data_fetcher.py`):
   - Establishes session with NSE India website
   - Manages cookies and headers for authentication
   - Fetches real-time spot prices, options chain data
   - Implements retry logic and error handling

2. **Greeks Calculator** (`nse_nifty_greeks.py`):
   - Uses NSE data for live market prices
   - Calculates theoretical prices using Black-Scholes
   - Computes all Greeks for each option
   - Generates complete options chain

3. **FastAPI Application** (`fastapi_nse.py`):
   - Provides REST API endpoints
   - Serves web dashboard
   - Handles request validation
   - Manages logging and error responses

## 🚨 Error Handling

### Common Scenarios
1. **NSE Website Unavailable**: Gracefully falls back to theoretical calculations
2. **Market Closed**: Uses last known data with appropriate warnings
3. **Network Issues**: Automatic retry with exponential backoff
4. **Invalid Parameters**: Clear error messages with validation details

### Logging
All operations are logged with full context:
```bash
tail -f logs/fastapi_nse.log
tail -f logs/nse_data_fetcher.log
```

## 🔮 Future Enhancements

### Planned Features
- **Multiple Indices**: Support for BANKNIFTY, FINNIFTY
- **Real-time Streaming**: WebSocket data feeds
- **Advanced Analytics**: Volatility surface, Greeks heatmaps
- **Backtesting**: Historical strategy analysis
- **Mobile App**: React Native companion app
- **Options Strategies**: Pre-built strategy analyzers

### Performance Optimizations
- **Caching**: Redis-based response caching
- **Database**: PostgreSQL for historical data
- **Async Processing**: Background task queue
- **Load Balancing**: Multi-instance deployment

## 📄 License

This project is open-source and available under the MIT License.

## 👥 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## 📞 Support

For issues and questions:
1. Check the logs in `logs/` directory
2. Review API documentation at `/docs`
3. Test with demo scripts
4. Create an issue with detailed error information

## ⚠️ Disclaimer

This application is for educational and research purposes only. Options trading involves substantial risk and is not suitable for every investor. The information provided by this application should not be considered as financial advice. Always consult with a qualified financial advisor before making investment decisions.

---

**Happy Trading! 📈**

*Powered by NSE India Data*
