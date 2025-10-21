# -*- coding: utf-8 -*-
import os
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from urllib.parse import quote
from ib_insync import IB, Stock, util
import asyncio
import nest_asyncio
import time

# Enable nested event loops for ib_insync to work with FastAPI
nest_asyncio.apply()

# IBKR Connection settings
IBKR_HOST = os.getenv('IBKR_HOST', '127.0.0.1')
IBKR_PORT = int(os.getenv('IBKR_PORT', '7497'))  # 7497 for TWS, 4001 for IB Gateway
IBKR_CLIENT_ID = int(os.getenv('IBKR_CLIENT_ID', '1'))

# Global IBKR connection
ib_connection = None
use_ibkr = False

# Stock symbols to fetch option data for
SYMBOLS = [
    'NVDA', 'MSFT', 'GOOG', 'MU', 'LLY', 'RDDT', 'SMCI', 'MSTR',
    'TSLA', 'AVGO', 'NVO', 'XOM', 'MARA', 'COIN', 'AMZN', 'AMD',
    'NNE', 'AAPL', 'ASTS', 'ORCL'
]

TARGET_DAYS = 30  # Target expiration ~30 days from now


def clean_value(value):
    """Convert NaN, inf, or None to None (JSON null)"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if np.isnan(value) or np.isinf(value):
            return None
    return value


def connect_to_ibkr():
    """
    Attempt to connect to Interactive Brokers TWS or IB Gateway.
    Returns True if successful, False otherwise.
    """
    global ib_connection, use_ibkr
    
    if ib_connection and ib_connection.isConnected():
        return True
    
    try:
        ib_connection = IB()
        ib_connection.connect(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID, timeout=5)
        use_ibkr = True
        print(f"✅ Connected to IBKR at {IBKR_HOST}:{IBKR_PORT}")
        return True
    except Exception as e:
        print(f"⚠️  IBKR connection failed: {str(e)}")
        print(f"📊 Falling back to Yahoo Finance data")
        ib_connection = None
        use_ibkr = False
        return False


def get_ibkr_iv_and_news(symbol):
    """
    Get implied volatility rank and news from IBKR for a given symbol.
    Returns tuple: (iv_percentile, news_headline)
    """
    global ib_connection, use_ibkr
    
    if not use_ibkr or not ib_connection or not ib_connection.isConnected():
        return None, None
    
    try:
        # Create contract
        contract = Stock(symbol, 'SMART', 'USD')
        ib_connection.qualifyContracts(contract)
        
        # Get market data including IV
        ib_connection.reqMktData(contract, '', False, False)
        util.sleep(1)  # Wait for data
        
        ticker_data = ib_connection.ticker(contract)
        
        # Get historical volatility (30-day)
        hist_vol = ticker_data.histVolatility if hasattr(ticker_data, 'histVolatility') else None
        implied_vol = ticker_data.impliedVolatility if hasattr(ticker_data, 'impliedVolatility') else None
        
        # Get news headlines
        news_headline = None
        try:
            news_providers = ib_connection.reqNewsProviders()
            if news_providers:
                # Get latest news
                news = ib_connection.reqHistoricalNews(
                    contract.conId, 
                    providerCode='BRFG+DJNL',  # Briefing.com + Dow Jones
                    startDateTime='',
                    endDateTime='',
                    totalResults=3
                )
                util.sleep(1)
                
                if news:
                    # Get the first headline
                    news_headline = news[0].headline if len(news) > 0 else None
        except:
            pass
        
        # Calculate IV percentile if we have both historical and implied
        iv_percentile = None
        if implied_vol and hist_vol and hist_vol > 0:
            iv_percentile = (implied_vol / hist_vol) * 100
        
        return iv_percentile, news_headline
        
    except Exception as e:
        # Silently fail and use Yahoo Finance data
        return None, None


def get_iv_reason_from_news(symbol):
    """
    Fetch recent news for a stock and determine IV reason based on headlines.
    Uses Yahoo Finance news as a free source.
    """
    try:
        # Get stock object
        stock = yf.Ticker(symbol)
        
        # Fetch news (yfinance includes news in the object)
        news = stock.news
        
        if not news or len(news) == 0:
            return "No recent news available"
        
        # Get top 3 most recent headlines
        headlines = []
        for item in news[:3]:
            title = item.get('title', '')
            if title:
                headlines.append(title)
        
        if not headlines:
            return "No recent news available"
        
        # Analyze headlines for volatility catalysts
        combined_text = ' '.join(headlines).lower()
        
        # Keywords that indicate high volatility events
        high_vol_keywords = {
            'earnings': '📊 Earnings event',
            'beats': '📈 Earnings beat',
            'misses': '📉 Earnings miss',
            'guidance': '🎯 Guidance update',
            'bitcoin': '₿ Bitcoin volatility',
            'crypto': '₿ Crypto exposure',
            'satellite': '🛰️ Satellite launch/deployment',
            'launch': '🚀 Launch event',
            'deployment': '🚀 Deployment news',
            'bluebird': '🛰️ BlueBird satellite news',
            'spacex': '🚀 SpaceX partnership',
            'orbit': '🛰️ Orbital operations',
            'coverage': '🌐 Network coverage expansion',
            'acquisition': '🤝 M&A activity',
            'merger': '🤝 Merger announcement',
            'lawsuit': '⚖️ Legal action',
            'investigation': '🔍 Regulatory probe',
            'fda': '💊 FDA decision',
            'approval': '✅ Regulatory approval',
            'cut': '📉 Analyst downgrade',
            'downgrade': '👎 Downgrade',
            'upgrade': '👍 Upgrade',
            'surge': '⚡ Price surge',
            'plunge': '⚡ Sharp decline',
            'rally': '📈 Strong rally',
            'sell-off': '📉 Selling pressure',
            'short': '🎯 Short interest spike',
            'breakthrough': '💡 Major breakthrough',
            'recall': '⚠️ Product recall',
            'layoff': '👥 Restructuring',
            'partnership': '🤝 Partnership announced',
            'contract': '📄 Major contract win',
            'revenue': '💰 Revenue announcement',
            'bankruptcy': '🚨 Bankruptcy concerns',
            'delisting': '🚨 Delisting risk',
            'halt': '⏸️ Trading halt',
        }
        
        # Check for keywords (prioritize most specific matches first)
        matched_reasons = []
        for keyword, reason in high_vol_keywords.items():
            if keyword in combined_text:
                matched_reasons.append((keyword, reason))
        
        if matched_reasons:
            # Use the first matched reason
            reason = matched_reasons[0][1]
            # Truncate headline to fit
            headline_snippet = headlines[0][:50] + "..." if len(headlines[0]) > 50 else headlines[0]
            return f"{reason}: {headline_snippet}"
        
        # If no specific catalyst found, return first headline
        headline_snippet = headlines[0][:70] + "..." if len(headlines[0]) > 70 else headlines[0]
        return f"📰 {headline_snippet}"
        
    except Exception as e:
        # Fallback to generic message
        return f"⚠️ Check news (YF data may be delayed)"


def find_expiration_near_target_days(expirations, target_days=30):
    """
    Find the expiration date closest to target_days from now.
    """
    today = datetime.now().date()
    target_date = today + timedelta(days=target_days)
    
    closest_expiration = None
    min_diff = float('inf')
    
    for exp_str in expirations:
        exp_date = datetime.strptime(exp_str, '%Y-%m-%d').date()
        diff = abs((exp_date - target_date).days)
        
        if diff < min_diff:
            min_diff = diff
            closest_expiration = exp_str
    
    return closest_expiration


def find_atm_strike(strikes, current_price):
    """
    Find the strike price closest to the current stock price (ATM).
    """
    try:
        if len(strikes) == 0:
            return None
        closest_strike = min(strikes, key=lambda x: abs(x - current_price))
        return closest_strike
    except:
        return None


def get_option_data():
    """
    Fetch ATM option data with ~30 day expiration for covered calls and cash-secured puts.
    """
    print("=" * 100)
    print("ANALYZING COVERED CALL & CASH-SECURED PUT OPPORTUNITIES")
    print("=" * 100)
    print(f"Timestamp: {datetime.now()}")
    print(f"Target Expiration: ~{TARGET_DAYS} days from now")
    print(f"Strategy: ATM (At-The-Money) options - strike closest to current price")
    print(f"Number of symbols: {len(SYMBOLS)}")
    print("=" * 100)
    print()
    
    # Try to connect to IBKR for more accurate data
    print("🔗 Attempting to connect to Interactive Brokers...")
    connect_to_ibkr()
    print()
    
    results = []
    
    for symbol in SYMBOLS:
        try:
            print(f"Analyzing {symbol}...", end=' ')
            
            # Get ticker object
            ticker = yf.Ticker(symbol)
            
            # Get current stock price and valuation metrics
            info = ticker.info
            current_price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
            
            if not current_price:
                print(f"[X] Could not get current price")
                continue
            
            # Get valuation metrics
            pe_ratio = info.get('trailingPE') or info.get('forwardPE')
            pb_ratio = info.get('priceToBook')
            peg_ratio = info.get('pegRatio')
            ps_ratio = info.get('priceToSalesTrailing12Months')
            market_cap = info.get('marketCap')
            dividend_yield = info.get('dividendYield')
            ev_ebitda = info.get('enterpriseToEbitda')
            
            # Get Wall Street analyst targets
            analyst_target = info.get('targetMeanPrice')  # Average analyst price target
            analyst_low = info.get('targetLowPrice')
            analyst_high = info.get('targetHighPrice')
            num_analysts = info.get('numberOfAnalystOpinions')
            
            # Get data for intrinsic value calculations
            eps = info.get('trailingEps')
            book_value = info.get('bookValue')
            free_cash_flow = info.get('freeCashflow')
            shares_outstanding = info.get('sharesOutstanding')
            earnings_growth = info.get('earningsGrowth') or info.get('earningsQuarterlyGrowth')
            revenue_growth = info.get('revenueGrowth') or 0
            total_revenue = info.get('totalRevenue') or 0
            
            # Calculate INTRINSIC VALUE #2: DCF Value (Alpha Spread Methodology)
            # Conservative DCF using Free Cash Flow
            dcf_value = None
            if free_cash_flow and shares_outstanding and free_cash_flow > 0 and shares_outstanding > 0:
                fcf_per_share = free_cash_flow / shares_outstanding
                
                # Conservative growth rate (Alpha Spread uses conservative estimates)
                if earnings_growth and earnings_growth > 0:
                    # Use 70% of actual growth rate for conservatism
                    growth_rate = earnings_growth * 0.7
                    # Cap at 15% (Alpha Spread is conservative)
                    growth_rate = min(growth_rate, 0.15)
                else:
                    growth_rate = 0.04  # Conservative default
                
                # WACC (Weighted Average Cost of Capital) - Higher = More Conservative
                if market_cap:
                    if market_cap > 200e9:  # Large cap (MSFT, AAPL, GOOGL)
                        discount_rate = 0.10  # 10% for mega caps
                    elif market_cap > 50e9:  # Large cap
                        discount_rate = 0.11
                    elif market_cap > 10e9:  # Mid cap
                        discount_rate = 0.12
                    else:  # Small cap
                        discount_rate = 0.14
                else:
                    discount_rate = 0.12
                
                # Terminal growth - conservative perpetual growth
                terminal_growth = 0.025  # 2.5% perpetual growth
                
                if discount_rate > terminal_growth:
                    # Stage 1: High growth period (5 years)
                    stage1_pv = 0
                    current_fcf = fcf_per_share
                    
                    for year in range(1, 6):
                        # Declining growth in stage 1
                        year_growth = growth_rate * (0.85 ** (year - 1))
                        current_fcf = current_fcf * (1 + year_growth)
                        pv = current_fcf / ((1 + discount_rate) ** year)
                        stage1_pv += pv
                    
                    # Stage 2: Transition to terminal growth (years 6-10)
                    stage2_pv = 0
                    transition_years = 5
                    for year in range(6, 11):
                        # Gradually decline to terminal growth
                        year_in_stage2 = year - 5
                        year_growth = terminal_growth + (year_growth - terminal_growth) * ((transition_years - year_in_stage2) / transition_years)
                        current_fcf = current_fcf * (1 + year_growth)
                        pv = current_fcf / ((1 + discount_rate) ** year)
                        stage2_pv += pv
                    
                    # Terminal value (perpetuity from year 10)
                    terminal_fcf = current_fcf * (1 + terminal_growth)
                    terminal_value = terminal_fcf / (discount_rate - terminal_growth)
                    terminal_pv = terminal_value / ((1 + discount_rate) ** 10)
                
                    dcf_value = stage1_pv + stage2_pv + terminal_pv
            
            # Calculate INTRINSIC VALUE #3: Blended Intrinsic Value (Like Alpha Spread)
            # Alpha Spread uses a weighted blend of multiple methods, with fallbacks for speculative stocks
            lynch_value = None
            pe_value = None
            forward_eps = info.get('forwardEps')
            forward_pe = info.get('forwardPE')
            
            # Try earnings-based valuation first
            if forward_eps and forward_eps > 0:
                # Method 1: Use Forward EPS with conservative P/E (like Alpha Spread)
                if forward_pe and forward_pe > 0:
                    # Use 60% of forward P/E as fair value target
                    fair_pe = forward_pe * 0.60
                    pe_value = forward_eps * fair_pe
                else:
                    # Default to P/E of 20 for forward EPS
                    pe_value = forward_eps * 20
            elif eps and eps > 0:
                # Fallback to trailing EPS
                if forward_pe and forward_pe > 0:
                    fair_pe = forward_pe * 1.05
                    pe_value = eps * fair_pe
                elif pe_ratio and pe_ratio > 0:
                    fair_pe = min(pe_ratio * 1.05, 45)
                    pe_value = eps * fair_pe
                else:
                    pe_value = eps * 20
            
            # FALLBACK for speculative/pre-profit stocks (like BITF, NNE, ASTS)
            # Use Price-to-Sales ratio when earnings are negative/unavailable
            elif ps_ratio and revenue_growth:
                if total_revenue and shares_outstanding and total_revenue > 0 and shares_outstanding > 0:
                    revenue_per_share = total_revenue / shares_outstanding
                    
                    # For high-growth pre-profit companies, use conservative P/S multiple
                    # Based on revenue growth rate
                    if revenue_growth > 1.0:  # >100% growth
                        target_ps = 8  # High growth tech/space companies
                    elif revenue_growth > 0.5:  # >50% growth
                        target_ps = 5
                    elif revenue_growth > 0.25:  # >25% growth
                        target_ps = 3
                    else:
                        target_ps = 2  # Lower growth
                    
                    pe_value = revenue_per_share * target_ps
            
            # Another FALLBACK: Use book value multiple for asset-heavy companies
            elif book_value and book_value > 0:
                # For companies with tangible assets, use conservative P/B
                if pb_ratio and pb_ratio > 0:
                    # Use current P/B but cap it for conservatism
                    target_pb = min(pb_ratio, 3.0)  # Cap at 3x book
                    pe_value = book_value * target_pb
                else:
                    # Default to 1.5x book value
                    pe_value = book_value * 1.5
            
            # Now blend all available valuation methods
            values_to_blend = []
            weights = []
            
            if dcf_value and dcf_value > 0:
                values_to_blend.append(dcf_value)
                weights.append(0.50)  # DCF gets 50% weight
            
            if pe_value and pe_value > 0:
                values_to_blend.append(pe_value)
                weights.append(0.25)  # P/E (or P/S or P/B) gets 25% weight
            
            # Calculate weighted average (Blended Intrinsic Value)
            if values_to_blend:
                total_weight = sum(weights)
                lynch_value = sum(v * w for v, w in zip(values_to_blend, weights)) / total_weight
            
            # Final FALLBACK: If still no intrinsic value, use analyst target as proxy
            if not lynch_value and analyst_target and analyst_target > 0:
                lynch_value = analyst_target * 0.85  # Use 85% of analyst target for conservatism
            
            # Calculate Relative Value (vs Intrinsic Value)
            relative_value_pct = None
            if lynch_value and lynch_value > 0:
                relative_value_pct = ((current_price - lynch_value) / lynch_value) * 100
            
            # Get available expiration dates
            expirations = ticker.options
            
            if expirations is None or len(expirations) == 0:
                print(f"[X] No options available")
                continue
            
            # Find expiration closest to 30 days
            target_expiration = find_expiration_near_target_days(expirations, TARGET_DAYS)
            
            if not target_expiration:
                print(f"[X] No suitable expiration found")
                continue
            
            # Calculate days to expiration
            exp_date = datetime.strptime(target_expiration, '%Y-%m-%d').date()
            days_to_exp = (exp_date - datetime.now().date()).days
            
            # Get option chain for this expiration
            option_chain = ticker.option_chain(target_expiration)
            
            calls = option_chain.calls
            puts = option_chain.puts
            
            if len(calls) == 0 or len(puts) == 0:
                print(f"[X] No option data for expiration {target_expiration}")
                continue
            
            # Find ATM strike (closest to current price)
            available_strikes = calls['strike'].unique()
            atm_strike = find_atm_strike(available_strikes, current_price)
            
            if atm_strike is None:
                print(f"[X] Could not find ATM strike")
                continue
            
            # Get the ATM call (for covered call)
            atm_calls = calls[calls['strike'] == atm_strike]
            atm_call = atm_calls.iloc[0] if len(atm_calls) > 0 else None
            
            # Get the ATM put (for cash-secured put)
            atm_puts = puts[puts['strike'] == atm_strike]
            atm_put = atm_puts.iloc[0] if len(atm_puts) > 0 else None
            
            # Skip if neither call nor put is available
            if atm_call is None and atm_put is None:
                print(f"[X] No call or put found at strike {atm_strike}")
                continue
            
            # Inform user if only partial strategies available
            if atm_call is None:
                print(f"[!] {symbol}: No call at strike ${atm_strike:.2f} - Only Cash-Secured Put available")
            elif atm_put is None:
                print(f"[!] {symbol}: No put at strike ${atm_strike:.2f} - Only Covered Call available")
            
            # Get IV data from IBKR if connected, otherwise Yahoo Finance
            ibkr_iv_percentile, ibkr_news = get_ibkr_iv_and_news(symbol)
            yf_iv_reason = get_iv_reason_from_news(symbol)
            
            # Combine IBKR news with Yahoo Finance analysis
            if ibkr_news:
                iv_reason = f"📡 IBKR: {ibkr_news[:70]}..."
            else:
                iv_reason = yf_iv_reason
            
            # Add IV percentile if available from IBKR
            if ibkr_iv_percentile:
                iv_reason = f"{iv_reason} (IV: {ibkr_iv_percentile:.0f}% of HV)"
            
            # Add COVERED CALL result (if call option exists)
            if atm_call is not None:
                # Calculate metrics for COVERED CALL (selling call)
                call_bid = atm_call['bid']
                call_ask = atm_call['ask']
                call_last = atm_call.get('lastPrice', 0)
                
                if call_bid > 0:
                    call_premium_per_share = call_bid
                elif call_ask > 0 and call_bid >= 0:
                    call_premium_per_share = (call_bid + call_ask) / 2  # mid price
                else:
                    call_premium_per_share = call_last
                
                call_premium_total = call_premium_per_share * 100  # per contract
                call_capital = current_price * 100  # capital tied up in 100 shares
                call_return_pct = (call_premium_total / call_capital * 100) if call_capital > 0 else 0
                
                # Add covered call result
                results.append({
                    'symbol': symbol,
                    'strategy': 'Covered Call',
                    'current_price': current_price,
                    'strike_price': atm_strike,
                    'expiration_date': target_expiration,
                    'days_to_expiration': days_to_exp,
                    'premium_per_share': call_premium_per_share,
                    'premium_total': call_premium_total,
                    'capital_required': call_capital,
                    'return_percentage': call_return_pct,
                    'volume': atm_call.get('volume', 0),
                    'open_interest': atm_call.get('openInterest', 0),
                    'implied_volatility': atm_call.get('impliedVolatility', 0),
                    'iv_reason': iv_reason,
                    'pe_ratio': pe_ratio,
                    'pb_ratio': pb_ratio,
                    'peg_ratio': peg_ratio,
                    'ps_ratio': ps_ratio,
                    'market_cap': market_cap,
                    'dividend_yield': dividend_yield,
                    'ev_ebitda': ev_ebitda,
                    'dcf_intrinsic_value': dcf_value,
                    'lynch_fair_value': lynch_value,
                    'analyst_target': analyst_target,
                    'analyst_low': analyst_low,
                    'analyst_high': analyst_high,
                    'num_analysts': num_analysts,
                    'relative_value_pct': relative_value_pct
                })
            
            # Add CASH-SECURED PUT result (if put option exists)
            if atm_put is not None:
                # Calculate metrics for CASH-SECURED PUT (selling put)
                put_bid = atm_put['bid']
                put_ask = atm_put['ask']
                put_last = atm_put.get('lastPrice', 0)
                
                if put_bid > 0:
                    put_premium_per_share = put_bid
                elif put_ask > 0 and put_bid >= 0:
                    put_premium_per_share = (put_bid + put_ask) / 2  # mid price
                else:
                    put_premium_per_share = put_last
                
                put_premium_total = put_premium_per_share * 100  # per contract
                put_capital = atm_strike * 100  # cash secured (strike * 100)
                put_return_pct = (put_premium_total / put_capital * 100) if put_capital > 0 else 0
            
                # Add cash-secured put result
                results.append({
                    'symbol': symbol,
                    'strategy': 'Cash-Secured Put',
                    'current_price': current_price,
                    'strike_price': atm_strike,
                    'expiration_date': target_expiration,
                    'days_to_expiration': days_to_exp,
                    'premium_per_share': put_premium_per_share,
                    'premium_total': put_premium_total,
                    'capital_required': put_capital,
                    'return_percentage': put_return_pct,
                    'volume': atm_put.get('volume', 0),
                    'open_interest': atm_put.get('openInterest', 0),
                    'implied_volatility': atm_put.get('impliedVolatility', 0),
                    'iv_reason': iv_reason,
                    'pe_ratio': pe_ratio,
                    'pb_ratio': pb_ratio,
                    'peg_ratio': peg_ratio,
                    'ps_ratio': ps_ratio,
                    'market_cap': market_cap,
                    'dividend_yield': dividend_yield,
                    'ev_ebitda': ev_ebitda,
                    'dcf_intrinsic_value': dcf_value,
                    'lynch_fair_value': lynch_value,
                    'analyst_target': analyst_target,
                    'analyst_low': analyst_low,
                    'analyst_high': analyst_high,
                    'num_analysts': num_analysts,
                    'relative_value_pct': relative_value_pct
                })
            
            # Print summary
            call_msg = f"Call: {call_return_pct:.2f}%" if atm_call is not None else "Call: N/A"
            put_msg = f"Put: {put_return_pct:.2f}%" if atm_put is not None else "Put: N/A"
            print(f"[OK] {call_msg} | {put_msg}")
            
        except Exception as e:
            print(f"[X] Error: {str(e)}")
            continue
    
    print()
    print("=" * 100)
    print("RESULTS - RANKED BY RETURN PERCENTAGE (Premium/Capital)")
    print("=" * 100)
    print()
    
    if results:
        # Convert to DataFrame
        df = pd.DataFrame(results)
        
        # Sort by return percentage (descending)
        df = df.sort_values('return_percentage', ascending=False)
        
        # Format the display
        df['current_price'] = df['current_price'].apply(lambda x: f"${x:,.2f}")
        df['strike_price'] = df['strike_price'].apply(lambda x: f"${x:,.2f}")
        df['premium_per_share'] = df['premium_per_share'].apply(lambda x: f"${x:.2f}")
        df['premium_total'] = df['premium_total'].apply(lambda x: f"${x:.2f}")
        df['capital_required'] = df['capital_required'].apply(lambda x: f"${x:,.2f}")
        df['return_percentage'] = df['return_percentage'].apply(lambda x: f"{x:.3f}%")
        df['implied_volatility'] = df['implied_volatility'].apply(lambda x: f"{x:.2%}")
        df['dcf_intrinsic_value'] = df['dcf_intrinsic_value'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "N/A")
        df['lynch_fair_value'] = df['lynch_fair_value'].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "N/A")
        
        # Select and rename columns for display
        display_df = df[[
            'symbol', 'strategy', 'current_price', 'strike_price', 
            'expiration_date', 'days_to_expiration', 'premium_per_share',
            'premium_total', 'capital_required', 'return_percentage',
            'volume', 'open_interest', 'implied_volatility',
            'dcf_intrinsic_value', 'lynch_fair_value'
        ]].copy()
        
        display_df.columns = [
            'Symbol', 'Strategy', 'Current Price', 'Strike', 
            'Expiration', 'DTE', 'Premium/Share',
            'Premium Total', 'Capital Required', 'Return %',
            'Volume', 'Open Interest', 'IV',
            'DCF IV', 'Intrinsic Value'
        ]
        
        # Print the results
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_colwidth', None)
        
        print(display_df.to_string(index=False))
        print()
        
        # Save to CSV (with unformatted numbers for analysis)
        df_raw = pd.DataFrame(results).sort_values('return_percentage', ascending=False)
        output_file = f'option_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        df_raw.to_csv(output_file, index=False)
        print(f"[OK] Data saved to: {output_file}")
        print()
        
        # Print summary statistics
        print("=" * 100)
        print("SUMMARY STATISTICS")
        print("=" * 100)
        
        # Separate covered calls and puts
        calls_df = df_raw[df_raw['strategy'] == 'Covered Call']
        puts_df = df_raw[df_raw['strategy'] == 'Cash-Secured Put']
        
        print(f"\nCOVERED CALLS:")
        print(f"  Average Return: {calls_df['return_percentage'].mean():.3f}%")
        print(f"  Best Return: {calls_df['return_percentage'].max():.3f}% ({calls_df.iloc[calls_df['return_percentage'].argmax()]['symbol']})")
        print(f"  Worst Return: {calls_df['return_percentage'].min():.3f}% ({calls_df.iloc[calls_df['return_percentage'].argmin()]['symbol']})")
        
        print(f"\nCASH-SECURED PUTS:")
        print(f"  Average Return: {puts_df['return_percentage'].mean():.3f}%")
        print(f"  Best Return: {puts_df['return_percentage'].max():.3f}% ({puts_df.iloc[puts_df['return_percentage'].argmax()]['symbol']})")
        print(f"  Worst Return: {puts_df['return_percentage'].min():.3f}% ({puts_df.iloc[puts_df['return_percentage'].argmin()]['symbol']})")
        print()
        
        return df_raw
    else:
        print("No option data was retrieved.")
        return None


def get_option_data_for_symbols(symbols):
    """
    Get option data for specified symbols (for web API)
    Returns tuple: (results, errors)
    - results: list of dictionaries with analysis results
    - errors: dict mapping symbol to error message
    """
    TARGET_DAYS = 30
    results = []
    errors = {}
    
    # Try to connect to IBKR for more accurate IV data
    print("🔗 Attempting to connect to Interactive Brokers...")
    ibkr_connected = connect_to_ibkr()
    if ibkr_connected:
        print("✅ Connected to IBKR - Using enhanced IV data")
    else:
        print("📊 Using Yahoo Finance data")
    
    print(f"\n📊 Analyzing {len(symbols)} symbols: {', '.join(symbols)}")
    print("=" * 80)
    
    for idx, symbol in enumerate(symbols):
        try:
            print(f"🔍 Analyzing {symbol}...", end=' ', flush=True)
            ticker = yf.Ticker(symbol)
            
            # Get current stock price and valuation metrics
            info = ticker.info
            current_price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
            
            if not current_price:
                error_msg = "No price data available"
                print(f"❌ {error_msg}")
                errors[symbol] = error_msg
                continue
            
            # Get valuation metrics
            pe_ratio = info.get('trailingPE') or info.get('forwardPE')
            pb_ratio = info.get('priceToBook')
            peg_ratio = info.get('pegRatio')
            ps_ratio = info.get('priceToSalesTrailing12Months')
            market_cap = info.get('marketCap')
            dividend_yield = info.get('dividendYield')
            ev_ebitda = info.get('enterpriseToEbitda')

            # Get Wall Street analyst targets
            analyst_target = info.get('targetMeanPrice')
            analyst_low = info.get('targetLowPrice')
            analyst_high = info.get('targetHighPrice')
            num_analysts = info.get('numberOfAnalystOpinions')
            
            # Get data for intrinsic value calculations
            eps = info.get('trailingEps')
            book_value = info.get('bookValue')
            free_cash_flow = info.get('freeCashflow')
            shares_outstanding = info.get('sharesOutstanding')
            earnings_growth = info.get('earningsGrowth') or info.get('earningsQuarterlyGrowth')
            revenue_growth = info.get('revenueGrowth') or 0
            total_revenue = info.get('totalRevenue') or 0

            # === INTRINSIC VALUE CALCULATIONS (Alpha Spread methodology) ===
            
            # 1. DCF Value - Alpha Spread Style (More Optimistic for Growth)
            dcf_value = None
            if free_cash_flow and shares_outstanding and free_cash_flow > 0 and shares_outstanding > 0:
                fcf_per_share = free_cash_flow / shares_outstanding
                
                # Use full historical growth or estimate based on company profile
                if earnings_growth and earnings_growth > 0:
                    # Use 90% of historical growth (less conservative)
                    growth_rate = min(earnings_growth * 0.9, 0.35)  # Cap at 35% for high-growth
                elif revenue_growth and revenue_growth > 0:
                    # Use revenue growth as proxy
                    growth_rate = min(revenue_growth * 0.8, 0.30)
                else:
                    growth_rate = 0.08  # Default 8% for stable growth
                
                # More optimistic discount rates (Alpha Spread style)
                if market_cap:
                    if market_cap > 200e9:  # Mega-cap
                        discount_rate = 0.08
                    elif market_cap > 50e9:  # Large-cap
                        discount_rate = 0.09
                    elif market_cap > 10e9:  # Mid-cap
                        discount_rate = 0.10
                    else:  # Small-cap
                        discount_rate = 0.12
                else:
                    discount_rate = 0.10
                
                terminal_growth = 0.03  # Slightly higher terminal growth
                
                if discount_rate > terminal_growth:
                    # Project 10 years of FCF with declining growth
                    total_pv = 0
                    current_fcf = fcf_per_share
                    
                    for year in range(1, 11):
                        # Gradually decline growth rate to terminal
                        year_growth = terminal_growth + (growth_rate - terminal_growth) * ((10 - year) / 10)
                        current_fcf = current_fcf * (1 + year_growth)
                        pv = current_fcf / ((1 + discount_rate) ** year)
                        total_pv += pv
                    
                    # Terminal value (perpetuity growth model)
                    terminal_fcf = current_fcf * (1 + terminal_growth)
                    terminal_value = terminal_fcf / (discount_rate - terminal_growth)
                    terminal_pv = terminal_value / ((1 + discount_rate) ** 10)
                
                    dcf_value = total_pv + terminal_pv
            
                    # More lenient sanity check (Alpha Spread allows higher)
                    if dcf_value > current_price * 10:  # Allow up to 10x current price
                        dcf_value = current_price * 3  # Cap at 3x if extreme
            
            # 2. Intrinsic Value - Growth-Adjusted P/E (Alpha Spread Style)
            lynch_value = None
            forward_eps = info.get('forwardEps')
            forward_pe = info.get('forwardPE')
            
            # For profitable companies: Use P/E based valuation
            if forward_eps and forward_eps > 0:
                # Alpha Spread uses Forward EPS with a conservative P/E multiple
                # Target P/E ranges from 15-30 depending on growth and stability
                if forward_pe and forward_pe > 0:
                    # Use 60% of forward P/E as fair value target
                    fair_pe = forward_pe * 0.60
                    lynch_value = forward_eps * fair_pe
                else:
                    # Default to P/E of 20 for forward EPS
                    lynch_value = forward_eps * 20
            elif eps and eps > 0:
                # Fallback to trailing EPS if forward not available
                if forward_pe and forward_pe > 0:
                    fair_pe = forward_pe * 1.05
                    lynch_value = eps * fair_pe
                elif pe_ratio and pe_ratio > 0:
                    fair_pe = min(pe_ratio * 1.05, 45)
                    lynch_value = eps * fair_pe
                else:
                    lynch_value = eps * 20
                
                # NO Graham blending - Alpha Spread doesn't do this
            
            # For pre-profit/speculative companies: Use alternative methods
            elif ps_ratio and revenue_growth:
                if total_revenue and shares_outstanding and total_revenue > 0 and shares_outstanding > 0:
                    revenue_per_share = total_revenue / shares_outstanding
                    
                    # More generous P/S multiples (Alpha Spread style)
                    if revenue_growth > 1.0:  # Hyper-growth >100%
                        target_ps = 15  # Much higher for hyper-growth
                    elif revenue_growth > 0.5:  # High-growth >50%
                        target_ps = 10
                    elif revenue_growth > 0.25:  # Good growth >25%
                        target_ps = 6
                    else:
                        target_ps = 3
                    
                    lynch_value = revenue_per_share * target_ps
            
            # Final fallback: Use book value or analyst target
            if not lynch_value:
                if book_value and book_value > 0:
                    # Asset-based valuation (more generous)
                    if pb_ratio and pb_ratio > 0:
                        target_pb = min(pb_ratio * 0.95, 4.0)  # Less conservative P/B
                        lynch_value = book_value * target_pb
                    else:
                        lynch_value = book_value * 2.0
                elif analyst_target and analyst_target > 0:
                    # Use 90% of analyst target as proxy
                    lynch_value = analyst_target * 0.90
            
            # 3. Relative Value - Use intrinsic value (not conservative blend)
            relative_value_pct = None
            if lynch_value and lynch_value > 0:
                # Alpha Spread uses intrinsic value directly
                relative_value_pct = ((current_price - lynch_value) / lynch_value) * 100
            
            # Get options
            expirations = ticker.options
            if expirations is None or len(expirations) == 0:
                error_msg = "No options available"
                print(f"❌ {error_msg}")
                errors[symbol] = error_msg
                continue
            
            target_expiration = find_expiration_near_target_days(expirations, TARGET_DAYS)
            if not target_expiration:
                error_msg = f"No suitable expiration (~{TARGET_DAYS} days)"
                print(f"❌ {error_msg}")
                errors[symbol] = error_msg
                continue
            
            exp_date = datetime.strptime(target_expiration, '%Y-%m-%d').date()
            days_to_exp = (exp_date - datetime.now().date()).days
            
            retry_attempts = 0
            while True:
                try:
                    option_chain = ticker.option_chain(target_expiration)
                    break
                except Exception as chain_error:
                    if ("429" in str(chain_error) or "Too Many Requests" in str(chain_error)) and retry_attempts < 3:
                        wait_time = 2 + retry_attempts
                        print(f"⏳ Rate limited. Retrying in {wait_time}s...", end=' ', flush=True)
                        time.sleep(wait_time)
                        retry_attempts += 1
                        continue
                    raise
            calls = option_chain.calls
            puts = option_chain.puts
            
            if len(calls) == 0 and len(puts) == 0:
                error_msg = f"No option data for expiration {target_expiration}"
                print(f"❌ {error_msg}")
                errors[symbol] = error_msg
                continue
            
            # Determine nearest available strikes separately for calls and puts
            atm_call = None
            atm_put = None
            call_strike_price = None
            put_strike_price = None
            call_return_pct = None
            put_return_pct = None
            
            if len(calls) > 0:
                call_diff = (calls['strike'] - current_price).abs()
                call_idx = call_diff.idxmin()
                atm_call = calls.loc[call_idx]
                call_strike_price = float(atm_call['strike'])
            
            if len(puts) > 0:
                put_diff = (puts['strike'] - current_price).abs()
                put_idx = put_diff.idxmin()
                atm_put = puts.loc[put_idx]
                put_strike_price = float(atm_put['strike'])
            
            # Skip if no suitable strikes found at all
            if atm_call is None and atm_put is None:
                error_msg = f"No call or put strikes available near ${current_price:.2f}"
                print(f"❌ {error_msg}")
                errors[symbol] = error_msg
                continue
            
            # Add informative message if only partial strategies available
            if atm_call is None and atm_put is not None:
                warning_msg = (
                    f"No call option near ${current_price:.2f}; using put strike ${put_strike_price:.2f}"
                )
                print(f"⚠️  {symbol}: {warning_msg}")
                errors.setdefault(symbol, warning_msg)
            elif atm_put is None and atm_call is not None:
                warning_msg = (
                    f"No put option near ${current_price:.2f}; using call strike ${call_strike_price:.2f}"
                )
                print(f"⚠️  {symbol}: {warning_msg}")
                errors.setdefault(symbol, warning_msg)
            
            # Get IV data from IBKR if connected, otherwise Yahoo Finance
            ibkr_iv_percentile, ibkr_news = get_ibkr_iv_and_news(symbol)
            yf_iv_reason = get_iv_reason_from_news(symbol)
            
            # Combine IBKR news with Yahoo Finance analysis
            if ibkr_news:
                iv_reason = f"📡 IBKR: {ibkr_news[:70]}..."
            else:
                iv_reason = yf_iv_reason
            
            # Add IV percentile if available from IBKR
            if ibkr_iv_percentile:
                iv_reason = f"{iv_reason} (IV: {ibkr_iv_percentile:.0f}% of HV)"
            
            # Add COVERED CALL result (if call option exists)
            if atm_call is not None:
                # Calculate call metrics
                call_bid = atm_call['bid']
                call_ask = atm_call['ask']
                call_last = atm_call.get('lastPrice', 0)
                
                if call_bid > 0:
                    call_premium_per_share = call_bid
                elif call_ask > 0 and call_bid >= 0:
                    call_premium_per_share = (call_bid + call_ask) / 2
                else:
                    call_premium_per_share = call_last
                
                call_premium_total = call_premium_per_share * 100
                call_capital = current_price * 100
                call_return_pct = (call_premium_total / call_capital * 100) if call_capital > 0 else 0
                
                # Add covered call result
                results.append({
                    'symbol': symbol,
                    'strategy': 'Covered Call',
                    'current_price': clean_value(current_price),
                    'strike_price': clean_value(call_strike_price),
                    'expiration_date': target_expiration,
                    'days_to_expiration': days_to_exp,
                    'premium_per_share': clean_value(call_premium_per_share),
                    'premium_total': clean_value(call_premium_total),
                    'capital_required': clean_value(call_capital),
                    'return_percentage': clean_value(call_return_pct),
                    'volume': clean_value(float(atm_call.get('volume', 0))),
                    'open_interest': clean_value(float(atm_call.get('openInterest', 0))),
                    'implied_volatility': clean_value(float(atm_call.get('impliedVolatility', 0))),
                    'iv_reason': iv_reason,
                    'pe_ratio': clean_value(pe_ratio),
                    'pb_ratio': clean_value(pb_ratio),
                    'peg_ratio': clean_value(peg_ratio),
                    'ps_ratio': clean_value(ps_ratio),
                    'market_cap': clean_value(market_cap),
                    'dividend_yield': clean_value(dividend_yield),
                    'ev_ebitda': clean_value(ev_ebitda),
                    'dcf_intrinsic_value': clean_value(dcf_value),
                    'lynch_fair_value': clean_value(lynch_value),
                    'analyst_target': clean_value(analyst_target),
                    'analyst_low': clean_value(analyst_low),
                    'analyst_high': clean_value(analyst_high),
                    'num_analysts': clean_value(num_analysts),
                    'relative_value_pct': clean_value(relative_value_pct)
                })
            
            # Add CASH-SECURED PUT result (if put option exists)
            if atm_put is not None:
                # Calculate put metrics
                put_bid = atm_put['bid']
                put_ask = atm_put['ask']
                put_last = atm_put.get('lastPrice', 0)
                
                if put_bid > 0:
                    put_premium_per_share = put_bid
                elif put_ask > 0 and put_bid >= 0:
                    put_premium_per_share = (put_bid + put_ask) / 2
                else:
                    put_premium_per_share = put_last
                
                put_premium_total = put_premium_per_share * 100
                put_capital = put_strike_price * 100
                put_return_pct = (put_premium_total / put_capital * 100) if put_capital > 0 else 0
                
                # Add cash-secured put result
                results.append({
                    'symbol': symbol,
                    'strategy': 'Cash-Secured Put',
                    'current_price': clean_value(current_price),
                    'strike_price': clean_value(put_strike_price),
                    'expiration_date': target_expiration,
                    'days_to_expiration': days_to_exp,
                    'premium_per_share': clean_value(put_premium_per_share),
                    'premium_total': clean_value(put_premium_total),
                    'capital_required': clean_value(put_capital),
                    'return_percentage': clean_value(put_return_pct),
                    'volume': clean_value(float(atm_put.get('volume', 0))),
                    'open_interest': clean_value(float(atm_put.get('openInterest', 0))),
                    'implied_volatility': clean_value(float(atm_put.get('impliedVolatility', 0))),
                    'iv_reason': iv_reason,
                    'pe_ratio': clean_value(pe_ratio),
                    'pb_ratio': clean_value(pb_ratio),
                    'peg_ratio': clean_value(peg_ratio),
                    'ps_ratio': clean_value(ps_ratio),
                    'market_cap': clean_value(market_cap),
                    'dividend_yield': clean_value(dividend_yield),
                    'ev_ebitda': clean_value(ev_ebitda),
                    'dcf_intrinsic_value': clean_value(dcf_value),
                    'lynch_fair_value': clean_value(lynch_value),
                    'analyst_target': clean_value(analyst_target),
                    'analyst_low': clean_value(analyst_low),
                    'analyst_high': clean_value(analyst_high),
                    'num_analysts': clean_value(num_analysts),
                    'relative_value_pct': clean_value(relative_value_pct)
                })
            
            # Print summary
            call_msg = f"Call: {call_return_pct:.2f}%" if call_return_pct is not None else "Call: N/A"
            put_msg = f"Put: {put_return_pct:.2f}%" if put_return_pct is not None else "Put: N/A"
            print(f"✅ Success ({call_msg} | {put_msg})")

            # Gentle throttle between symbols to avoid rate limiting
            if idx < len(symbols) - 1:
                sleep_time = 0.5 + min(len(symbols), 10) * 0.1
                time.sleep(sleep_time)
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error: {error_msg}")
            errors[symbol] = f"Analysis error: {error_msg}"
            import traceback
            traceback.print_exc()
            continue
    
    # Print summary
    print("=" * 80)
    unique_symbols = set([r['symbol'] for r in results]) if results else set()
    print(f"✅ Analysis complete: {len(unique_symbols)} stocks, {len(results)} opportunities found")
    
    if errors:
        print(f"⚠️  Failed to analyze {len(errors)} symbols:")
        for sym, err in errors.items():
            print(f"   - {sym}: {err}")
    print("=" * 80)
    
    # Sort by return percentage
    results.sort(key=lambda x: x['return_percentage'], reverse=True)
    return results, errors


if __name__ == "__main__":
    try:
        option_data = get_option_data()
        
        if option_data is not None:
            print("=" * 100)
            print("[OK] ANALYSIS COMPLETE!")
            print("=" * 100)
            print("\nOPTION STRATEGY NOTES:")
            print("- Covered Call: Sell call while owning 100 shares (capital = current price x 100)")
            print("- Cash-Secured Put: Sell put with cash reserved (capital = strike x 100)")
            print("- Premium Total: Amount you receive for selling the option contract")
            print("- Return %: (Premium Total / Capital Required) x 100")
            print("- DTE: Days To Expiration")
            print("- IV: Implied Volatility")
            print("\nINTRINSIC VALUE CALCULATIONS (in CSV):")
            print("- DCF Intrinsic Value: Discounted Cash Flow (5-yr projection, 10% discount rate)")
            print("  If current price < DCF value = Undervalued")
            print("- Lynch Fair Value: Peter Lynch's P/E = Growth Rate formula")
            print("  If current price < Lynch value = Undervalued")
            print("\nVALUATION RATIOS (in CSV):")
            print("- P/E, P/B, PEG Ratios, Market Cap, Dividend Yield, EV/EBITDA, P/S Ratio")
        
    except Exception as e:
        print(f"\n[X] Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()