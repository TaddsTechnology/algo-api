# 🚀 Enhanced Algo Trading API - Deployment Guide

## 📋 Complete System Overview

This system provides a high-performance algorithmic trading API with specialized futures data endpoints and real-time calculation engine.

### 🎯 Key Components Created

1. **Specialized Futures Fetchers**:
   - `kite_current_futures.py` - Current month futures (0-35 days)
   - `kite_near_futures.py` - Near month futures (36-70 days)  
   - `kite_far_futures.py` - Far month futures (71-105 days)
   - `kite_fast_futures.py` - Enhanced all futures combined

2. **Formula Calculation Engine**:
   - `formula_calculator.py` - Advanced formula processor
   - Supports technical indicators, spreads, and mathematical functions

3. **Enhanced FastAPI Application**:
   - `fast_api_enhanced.py` - Complete API with all endpoints
   - `app.py` - Main entry point for Hugging Face Spaces

4. **Deployment Configuration**:
   - `Dockerfile` - Enhanced container configuration
   - `requirements.txt` - Updated dependencies
   - Health checks and monitoring

## 🛠️ Hugging Face Spaces Deployment

### Step 1: Create New Space
1. Go to [Hugging Face Spaces](https://huggingface.co/spaces)
2. Click "Create new Space"
3. Choose:
   - **Space name**: `algo-trading-api` (or your preferred name)
   - **SDK**: Docker
   - **Visibility**: Public or Private (your choice)

### Step 2: Upload Files
Upload all these files to your Space:

**Core API Files**:
- `app.py` (main entry point)
- `fast_api_enhanced.py` (enhanced API)
- `kite_current_futures.py`
- `kite_near_futures.py` 
- `kite_far_futures.py`
- `kite_fast_futures.py`
- `formula_calculator.py`

**Configuration Files**:
- `Dockerfile`
- `requirements.txt`
- `KiteApi/` directory (entire folder)

**Optional Files**:
- `README_HF.md` (documentation)
- `DEPLOYMENT_GUIDE.md` (this file)

### Step 3: Set Environment Variables
In your Hugging Face Space settings, add these secrets:

```
KITE_API_KEY=your_kite_api_key_here
KITE_ACCESS_TOKEN=your_access_token_here
```

### Step 4: Deploy
1. Commit your files to the Space repository
2. The Docker container will automatically build
3. Your API will be available at: `https://your-username-space-name.hf.space`

## 🔧 Local Development Setup

### Prerequisites
```bash
pip install -r requirements.txt
```

### Run Locally
```bash
python app.py
```
Access at: `http://localhost:7860`

### Test Endpoints
```bash
# Health check
curl http://localhost:7860/api/health

# Current futures
curl http://localhost:7860/api/current-futures

# Calculate formula
curl -X POST http://localhost:7860/api/calculate \
  -H "Content-Type: application/json" \
  -d '{"formula": "NIFTY.ltp + BANKNIFTY.ltp"}'
```

## 📊 API Endpoints Reference

### 🎯 Futures Data Endpoints

| Endpoint | Method | Description | Refresh Rate |
|----------|--------|-------------|--------------|
| `/api/current-futures` | GET | Current month futures (0-35 days) | 0.5s |
| `/api/near-futures` | GET | Near month futures (36-70 days) | 1.0s |
| `/api/far-futures` | GET | Far month futures (71-105 days) | 1.5s |
| `/api/all-futures` | GET | All futures combined | 2.0s |
| `/api/futures/{symbol}` | GET | Specific futures contract | Real-time |
| `/api/popular-contracts/{category}` | GET | Popular contracts by category | Real-time |

### 🧮 Calculation Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/calculate` | POST | Calculate formulas with live data |
| `/api/functions` | GET | List available functions |
| `/api/validate-formula` | POST | Validate formula syntax |

### 🔍 System Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | System health and metrics |
| `/` | GET | API information and endpoints |
| `/docs` | GET | Interactive API documentation |

## 🧮 Formula System Guide

### Basic Syntax
```javascript
// Price references
SYMBOL.ltp          // Last traded price
SYMBOL.open         // Opening price
SYMBOL.high         // Day high
SYMBOL.low          // Day low
SYMBOL.close        // Previous close
SYMBOL.volume       // Trading volume
```

### Supported Functions

**Mathematical Functions**:
- `abs(x)` - Absolute value
- `sqrt(x)` - Square root  
- `log(x)` - Natural logarithm
- `max(a, b)` - Maximum value
- `min(a, b)` - Minimum value
- `round(x)` - Round to nearest integer

**Technical Indicators**:
- `rsi(symbol, period)` - Relative Strength Index
- `sma(symbols, period)` - Simple Moving Average
- `ema(symbols, period)` - Exponential Moving Average
- `macd(symbol)` - MACD indicator
- `bb_upper(symbol, period, std_dev)` - Bollinger Band upper
- `bb_lower(symbol, period, std_dev)` - Bollinger Band lower
- `stoch(symbol, period)` - Stochastic oscillator
- `atr(symbol, period)` - Average True Range

**Special Functions**:
- `spread(symbol1, symbol2, operation)` - Calculate spreads
- `pct_change(symbol)` - Percentage change from close

### Formula Examples

**Simple Calculations**:
```javascript
NIFTY.ltp * 1.02                    // 2% above NIFTY LTP
(NIFTY.high + NIFTY.low) / 2        // Midpoint
BANKNIFTY.volume / 1000000          // Volume in millions
```

**Spreads**:
```javascript
spread(NIFTY, BANKNIFTY, "subtract")    // NIFTY - BANKNIFTY
spread(NIFTY, BANKNIFTY, "ratio")       // NIFTY / BANKNIFTY
spread(NIFTY, BANKNIFTY, "add")         // NIFTY + BANKNIFTY
```

**Technical Analysis**:
```javascript
rsi(NIFTY, 14)                      // 14-period RSI
bb_upper(NIFTY, 20, 2)              // Bollinger Band upper (20, 2)
macd(BANKNIFTY)                     // MACD for BANKNIFTY
```

**Complex Formulas**:
```javascript
// Volatility-adjusted spread
spread(NIFTY, BANKNIFTY, "subtract") / atr(NIFTY, 14)

// Momentum comparison
(rsi(NIFTY, 14) + rsi(BANKNIFTY, 14)) / 2

// Price deviation from SMA
(NIFTY.ltp - sma([NIFTY], 20)) / sma([NIFTY], 20) * 100
```

## ⚡ Performance Optimization

### Data Refresh Strategy
- **Current futures**: 0.5s refresh (most active)
- **Near futures**: 1.0s refresh (moderate activity)
- **Far futures**: 1.5s refresh (less active)
- **Combined data**: 2.0s refresh (comprehensive view)

### Rate Limiting
- Built-in request throttling (100ms minimum between requests)
- Intelligent batching (15-20 symbols per batch)
- Automatic retry mechanisms
- Error recovery and fallback

### Memory Management
- Thread-safe data stores
- Efficient data structures
- Garbage collection optimization
- Resource cleanup

## 🔒 Security Best Practices

### API Key Management
- Use environment variables (never hardcode)
- Rotate tokens regularly
- Monitor API usage
- Set up alerts for unusual activity

### Error Handling
- Comprehensive error catching
- Detailed error logging
- Graceful degradation
- Automatic recovery mechanisms

## 📈 Monitoring & Maintenance

### Health Monitoring
```javascript
// Check system health
GET /api/health

Response:
{
  "status": "healthy",
  "data_count": {
    "current_futures": 45,
    "near_futures": 38,
    "far_futures": 22,
    "all_futures": 105
  },
  "last_updates": {
    "current_futures": 1698765432.123,
    "near_futures": 1698765431.456,
    "far_futures": 1698765430.789,
    "all_futures": 1698765429.012
  },
  "server_time": 1698765432.555
}
```

### Performance Metrics
- Data freshness tracking
- API response times
- Error rates and patterns
- Resource utilization

### Troubleshooting Common Issues

**1. "API Key not found" Error**
```bash
# Check environment variables in HF Spaces settings
# Or create kite_config_hf.py with credentials
```

**2. "Token expired" Error**
```bash
# Generate fresh access token using generate_access_token.py
# Update KITE_ACCESS_TOKEN in environment
```

**3. Slow API Response**
```bash
# Check /api/health for data freshness
# Reduce limit_contracts parameter
# Use LTP-only mode for faster updates
```

**4. Formula Calculation Errors**
```bash
# Use /api/validate-formula to check syntax
# Ensure symbols exist in current data
# Check /api/functions for available functions
```

## 🎯 Frontend Integration

### JavaScript Example
```javascript
// Fetch current futures data
const currentFutures = await fetch('https://your-space.hf.space/api/current-futures')
  .then(response => response.json());

// Calculate custom formula
const calculation = await fetch('https://your-space.hf.space/api/calculate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    formula: 'spread(NIFTY, BANKNIFTY, "ratio")',
    variables: { threshold: 0.5 }
  })
}).then(response => response.json());
```

### WebSocket Integration (Future Enhancement)
```javascript
// Real-time data streaming (when implemented)
const ws = new WebSocket('wss://your-space.hf.space/ws/current-futures');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  updateFuturesDisplay(data);
};
```

## 🔄 Continuous Improvement

### Monitoring Checklist
- [ ] Check API health daily
- [ ] Monitor error rates
- [ ] Review performance metrics
- [ ] Update access tokens as needed
- [ ] Monitor resource usage

### Enhancement Roadmap
- [ ] WebSocket real-time streaming
- [ ] Historical data integration
- [ ] Advanced technical indicators
- [ ] Custom alert system
- [ ] Portfolio tracking features

## ✅ Deployment Checklist

### Pre-deployment
- [ ] All files uploaded to HF Space
- [ ] Environment variables set correctly
- [ ] Docker configuration tested
- [ ] API credentials validated

### Post-deployment
- [ ] Health check endpoint responding
- [ ] All futures endpoints working
- [ ] Formula calculation functional
- [ ] Error handling working properly
- [ ] Performance within expected ranges

### Verification Tests
```bash
# Test all major endpoints
curl https://your-space.hf.space/api/health
curl https://your-space.hf.space/api/current-futures
curl https://your-space.hf.space/api/near-futures  
curl https://your-space.hf.space/api/far-futures
curl https://your-space.hf.space/api/functions

# Test formula calculation
curl -X POST https://your-space.hf.space/api/calculate \
  -H "Content-Type: application/json" \
  -d '{"formula": "abs(100 + 50)"}'
```

---

## 🎯 Ready for Production!

Your enhanced algorithmic trading API is now ready for deployment with:
- ⚡ Ultra-fast data fetching (0.5-2s refresh rates)
- 🎯 Specialized futures category endpoints  
- 🧮 Advanced formula calculation engine
- 📊 Comprehensive monitoring and health checks
- 🔒 Secure credential management
- 🚀 Production-ready Docker deployment

**Happy Trading! 📈🚀**