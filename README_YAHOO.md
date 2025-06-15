# NIFTY Options Greeks Calculator - Yahoo Finance Edition

A comprehensive FastAPI-based application for analyzing NIFTY 50 options with real-time market data from Yahoo Finance. This application provides advanced Greeks calculations, portfolio analysis, and theoretical options pricing using the Black-Scholes model.

## 🚀 Features

### Core Capabilities
- **Real-time NIFTY 50 Data**: Live spot prices from Yahoo Finance
- **Advanced Greeks Calculation**: Delta, Gamma, Theta, Vega, and Rho
- **Complete Options Chain**: Theoretical pricing for all strike prices
- **Historical Volatility**: Calculated from real market data
- **Portfolio Analysis**: Aggregate Greeks for multiple positions
- **Implied Volatility**: Calculate IV from market prices
- **Web Dashboard**: Interactive HTML interface
- **REST API**: Complete JSON API with comprehensive documentation

### Technical Features
- **FastAPI Framework**: High-performance async web framework
- **Yahoo Finance Integration**: Free, reliable market data
- **Black-Scholes Model**: Industry-standard options pricing
- **Comprehensive Logging**: Detailed logging with Loguru
- **Type Safety**: Full Pydantic validation
- **Error Handling**: Robust error handling and recovery

## 📦 Installation

### Prerequisites
- Python 3.8 or higher
- Internet connection for live data

### Quick Start
```bash
# Clone or download the project
cd "Nifty Analysis"

# Install dependencies
pip install -r requirements.txt

# Start the application
./start_yahoo_api.sh
```

### Manual Installation
```bash
# Install dependencies
pip install fastapi uvicorn pandas numpy scipy requests loguru pydantic

# Start the server
python -m uvicorn fastapi_yahoo:app --host 0.0.0.0 --port 8000 --reload
```

## 🌐 Usage

### Web Dashboard
Open your browser and navigate to:
- **Dashboard**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

### API Endpoints

#### 1. Health Check
```bash
GET /api/status
```
Returns API health status and data source connectivity.

#### 2. Current NIFTY Price
```bash
GET /api/nifty-price
```
Get real-time NIFTY 50 spot price from Yahoo Finance.

#### 3. Historical Volatility
```bash
GET /api/historical-volatility?days=30
```
Calculate historical volatility from recent price movements.

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
Generate complete options chain with theoretical pricing and Greeks.

#### 5. Implied Volatility Calculation
```bash
POST /api/calculate-implied-volatility
Content-Type: application/json

{
    "option_price": 100.0,
    "spot_price": 24700.0,
    "strike_price": 24700.0,
    "days_to_expiry": 30,
    "option_type": "call"
}
```

#### 6. Single Option Greeks
```bash
GET /api/option-greeks?spot_price=24700&strike_price=24700&days_to_expiry=30&option_type=call&volatility=0.15
```

#### 7. Portfolio Greeks
```bash
POST /api/portfolio-greeks
Content-Type: application/json

{
    "positions": [
        {
            "strike": 24700.0,
            "quantity": 1,
            "option_type": "call",
            "days_to_expiry": 30,
            "volatility": 0.15
        }
    ]
}
```

## 🧮 Mathematical Models

### Black-Scholes Formula
The application uses the Black-Scholes model for options pricing:

**Call Option Price:**
```
C = S₀ × N(d₁) - K × e^(-r×T) × N(d₂)
```

**Put Option Price:**
```
P = K × e^(-r×T) × N(-d₂) - S₀ × N(-d₁)
```

Where:
- `d₁ = (ln(S₀/K) + (r + σ²/2)×T) / (σ×√T)`
- `d₂ = d₁ - σ×√T`

### Greeks Calculations

#### Delta (Δ)
Price sensitivity to underlying asset price changes:
- **Call Delta**: `N(d₁)`
- **Put Delta**: `N(d₁) - 1`

#### Gamma (Γ)
Rate of change of Delta:
- **Gamma**: `φ(d₁) / (S₀ × σ × √T)`

#### Theta (Θ)
Time decay (per day):
- **Call Theta**: `[-S₀×φ(d₁)×σ/(2×√T) - r×K×e^(-r×T)×N(d₂)] / 365`
- **Put Theta**: `[-S₀×φ(d₁)×σ/(2×√T) + r×K×e^(-r×T)×N(-d₂)] / 365`

#### Vega (ν)
Sensitivity to volatility changes:
- **Vega**: `S₀ × φ(d₁) × √T / 100`

#### Rho (ρ)
Sensitivity to interest rate changes:
- **Call Rho**: `K × T × e^(-r×T) × N(d₂) / 100`
- **Put Rho**: `-K × T × e^(-r×T) × N(-d₂) / 100`

## 📊 Data Sources

### Yahoo Finance API
- **Symbol**: ^NSEI (NIFTY 50 Index)
- **Data**: Real-time spot prices, historical data
- **Reliability**: Free, no API key required
- **Update Frequency**: Real-time during market hours

### Default Parameters
- **Risk-free Rate**: 6.5% (configurable)
- **Volatility**: Calculated from 30-day historical data
- **Expiry**: Next Thursday (typical NIFTY expiry)
- **Strike Range**: ±15 strikes from ATM (50-point intervals)

## 🔧 Configuration

### Environment Variables
```bash
# Optional: Set custom risk-free rate
export RISK_FREE_RATE=0.065

# Optional: Set custom volatility
export DEFAULT_VOLATILITY=0.15

# Optional: Set custom port
export PORT=8000
```

### Logging Configuration
Logs are automatically created in the `logs/` directory:
- `logs/fastapi_yahoo.log` - Main application logs
- `logs/yahoo_nifty_greeks.log` - Greeks calculation logs
- `logs/error.log` - Error logs only

## 🧪 Testing

### Run Test Suite
```bash
# Start the server first
./start_yahoo_api.sh

# In another terminal, run tests
python test_yahoo_api.py
```

### Manual Testing
```bash
# Test Yahoo Finance connection
python -c "from yahoo_nifty_greeks import YahooFinanceAPI; print(YahooFinanceAPI().get_nifty_price())"

# Test options chain generation
python -c "from yahoo_nifty_greeks import NiftyOptionsChain; print(len(NiftyOptionsChain().generate_options_chain(num_strikes=5)))"
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
            "theoretical_price": 145.23,
            "delta": 0.5234,
            "gamma": 0.000156,
            "theta": -12.45,
            "vega": 89.34,
            "rho": 23.45,
            "moneyness": "ATM",
            "days_to_expiry": 7
        }
    ],
    "analytics": {
        "spot_price": 24718.6,
        "atm_strike": 24700.0,
        "total_options": 62,
        "implied_volatility": 0.1017
    },
    "metadata": {
        "total_options": 62,
        "expiry_date": "2025-06-19",
        "days_to_expiry": 7,
        "implied_volatility": 0.1017
    },
    "timestamp": "2025-06-15T15:30:49.123456"
}
```

### Portfolio Greeks Response
```json
{
    "success": true,
    "data": {
        "portfolio_greeks": {
            "delta": 0.2345,
            "gamma": 0.000234,
            "theta": -45.67,
            "vega": 123.45,
            "rho": 12.34,
            "net_premium": 2500.0,
            "total_positions": 2
        },
        "position_details": [
            {
                "strike": 24700.0,
                "option_type": "CALL",
                "quantity": 1,
                "delta": 0.5234,
                "gamma": 0.000156
            }
        ]
    },
    "timestamp": "2025-06-15T15:30:49.123456"
}
```

## 🛠️ Technical Architecture

### Core Components
1. **YahooFinanceAPI**: Handles market data fetching
2. **GreeksCalculator**: Black-Scholes calculations
3. **NiftyOptionsChain**: Options chain generation
4. **PortfolioGreeksCalculator**: Portfolio-level analysis
5. **FastAPI Application**: Web API and dashboard

### Data Flow
1. Yahoo Finance → Market Data
2. Historical Data → Volatility Calculation
3. Black-Scholes Model → Theoretical Pricing
4. Greeks Formulas → Risk Metrics
5. FastAPI → JSON Response

## 🤝 Migration from Angel One

This application completely replaces the Angel One SmartAPI integration:

### What Changed
- **Data Source**: Yahoo Finance instead of Angel One
- **Authentication**: No credentials required
- **Reliability**: Free, stable data source
- **Features**: Enhanced Greeks calculations

### What Stayed
- **FastAPI Framework**: Same high-performance API
- **Web Dashboard**: Similar user interface
- **Portfolio Analysis**: Enhanced portfolio Greeks
- **Logging**: Comprehensive logging system

## 📚 API Documentation

### Interactive Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

### Postman Collection
Import the API endpoints into Postman for easy testing:
1. Visit http://localhost:8000/docs
2. Download OpenAPI schema
3. Import into Postman

## 🚨 Error Handling

### Common Errors
1. **Network Issues**: Automatic retry with exponential backoff
2. **Data Validation**: Comprehensive Pydantic validation
3. **Market Closed**: Graceful handling of stale data
4. **Invalid Parameters**: Clear error messages

### Logging
All errors are logged with full stack traces:
```bash
tail -f logs/error.log
```

## 🔮 Future Enhancements

### Planned Features
- **Multiple Indices**: Support for BANKNIFTY, FINNIFTY
- **Real-time Streaming**: WebSocket data feeds
- **Advanced Analytics**: Volatility surface, Greeks heatmaps
- **Backtesting**: Historical strategy analysis
- **Mobile App**: React Native companion app

### Performance Optimizations
- **Caching**: Redis-based response caching
- **Database**: PostgreSQL for historical data
- **Async Processing**: Celery task queue
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
3. Test with `test_yahoo_api.py`
4. Create an issue with detailed error information

---

**Happy Trading! 📈**
