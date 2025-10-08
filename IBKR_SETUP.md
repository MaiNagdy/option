# IBKR Integration Setup Guide

This app can connect to Interactive Brokers (IBKR) for **more accurate implied volatility data and real-time news**.

## Prerequisites

1. **IBKR Account** (Paper or Live trading account)
2. **TWS (Trader Workstation)** or **IB Gateway** installed

## Setup Steps

### 1. Download and Install

Download TWS or IB Gateway from: https://www.interactivebrokers.com/en/trading/tws.php

**Recommended:** Use IB Gateway (lighter weight, no GUI)

### 2. Enable API Access

1. Open TWS or IB Gateway
2. Go to **File → Global Configuration → API → Settings**
3. **Enable ActiveX and Socket Clients** ✅
4. **Uncheck "Read-Only API"** (so you can read market data)
5. Add `127.0.0.1` to **Trusted IP Addresses**
6. **Port Settings:**
   - TWS Live: `7496`
   - TWS Paper: `7497` (default)
   - IB Gateway Live: `4001`
   - IB Gateway Paper: `4002`

### 3. Configure the App

Create a `.env` file in the project root:

```env
# IBKR Connection Settings
IBKR_HOST=127.0.0.1
IBKR_PORT=7497          # Use 7497 for TWS Paper, 4002 for IB Gateway Paper
IBKR_CLIENT_ID=1        # Any number 1-32
```

### 4. Market Data Subscriptions

To get real-time IV data, ensure you have:
- **US Securities Snapshot and Futures Value Bundle** (usually free for paper trading)
- **US Equity and Options Add-On Streaming Bundle** (for live data)

Check subscriptions: Account Management → Settings → Market Data Subscriptions

### 5. Run the App

```bash
# Start IB Gateway or TWS first (must be logged in)
python app.py
```

The app will:
- ✅ Try to connect to IBKR automatically
- ⚠️ Fall back to Yahoo Finance if IBKR is unavailable

## Connection Status

Check the console output when the app starts:

```
✅ Connected to IBKR at 127.0.0.1:7497
```

Or if not connected:

```
⚠️  IBKR connection failed: [Errno 10061] No connection could be made...
📊 Falling back to Yahoo Finance data
```

## Benefits of IBKR Integration

| Feature | Yahoo Finance | IBKR |
|---------|--------------|------|
| Option Prices | ✅ Free | ✅ Real-time |
| Implied Volatility | ⚠️ Often delayed/inaccurate | ✅ Accurate, real-time |
| News | ✅ Basic headlines | ✅ Briefing.com + Dow Jones |
| Historical Volatility | ❌ | ✅ 30-day HV |
| IV Percentile | ❌ | ✅ IV vs HV comparison |

## Troubleshooting

### "Connection refused"
- Ensure TWS/IB Gateway is running and logged in
- Check the port number matches your configuration
- Verify API is enabled in TWS settings

### "Not connected"
- Paper trading accounts: Use port 7497 (TWS) or 4002 (Gateway)
- Live accounts: Use port 7496 (TWS) or 4001 (Gateway)

### "Market data farm connection is inactive"
- You may not have market data subscriptions
- App will still work using Yahoo Finance data

### "Already connected"
- Only one client can connect with the same client ID
- Change `IBKR_CLIENT_ID` to a different number (1-32)

## No IBKR Account?

No problem! The app works perfectly fine with **Yahoo Finance data only**. IBKR is optional for enhanced accuracy.

---

**Note:** This app uses IBKR's API for **market data only** (read-only). No trading is performed.

