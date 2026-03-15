#!/usr/bin/env python3
"""
fetch_market_data.py
Fetches global indices, Nifty Top 10, US Top 10.
Now includes:
- Options OI & PCR (where available)
- MACD (using ta library)
- Last 30 days OHLC for charting
"""
import json
import datetime
import sys
import pandas as pd
import ta

try:
    import yfinance as yf
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance"])
    import yfinance as yf

SYMBOLS = {
    # Global indices & commodities
    'sp':     '^GSPC',
    'ndq':    '^IXIC',
    'dji':    '^DJI',
    'inr':    'INR=X',
    'crude':  'CL=F',
    'gold':   'GC=F',
    'silver': 'SI=F',
    # Indian indices
    'n50':    '^NSEI',
    'bn':     '^NSEBANK',
    'sx':     '^BSESN',
    'fn':     'NIFTY_FIN_SERVICE.NS',
    'vix':    '^INDIAVIX',
    # Nifty Top 10 stocks
    't_RELIANCE':   'RELIANCE.NS',
    't_HDFCBANK':   'HDFCBANK.NS',
    't_ICICIBANK':  'ICICIBANK.NS',
    't_INFY':       'INFY.NS',
    't_TCS':        'TCS.NS',
    't_AIRTEL':     'BHARTIARTL.NS',
    't_ITC':        'ITC.NS',
    't_SBI':        'SBIN.NS',
    't_KOTAK':      'KOTAKBANK.NS',
    't_LT':         'LT.NS',
    # US Top 10 stocks (by market cap)
    'u_AAPL':   'AAPL',
    'u_MSFT':   'MSFT',
    'u_NVDA':   'NVDA',
    'u_AMZN':   'AMZN',
    'u_GOOGL':  'GOOGL',
    'u_META':   'META',
    'u_TSLA':   'TSLA',
    'u_BRK':    'BRK-B',
    'u_JPM':    'JPM',
    'u_UNH':    'UNH',
}

data = {}
errors = []

for key, sym in SYMBOLS.items():
    print(f"Processing {key} ({sym})...")
    try:
        ticker = yf.Ticker(sym)
        info = ticker.fast_info
        price = info.last_price
        prev  = info.previous_close

        if not price or not prev or prev <= 0:
            errors.append(f"{key}: invalid price/prev")
            continue

        chg_pct = ((price - prev) / prev) * 100
        entry = {
            'price': round(float(price), 2),
            'chgPct': round(float(chg_pct), 2),
            'src': 'GHA'
        }

        # ----- Options Data (OI, PCR) -----
        # Only for symbols that might have options (indices & stocks)
        if any(x in sym for x in ['^NSEI', '^NSEBANK', '.NS', '^BSESN']):
            try:
                expirations = ticker.options
                if expirations:
                    chain = ticker.option_chain(expirations[0])  # nearest expiry
                    total_call_oi = chain.calls['openInterest'].sum()
                    total_put_oi = chain.puts['openInterest'].sum()
                    pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 0
                    entry['callOI'] = int(total_call_oi)
                    entry['putOI'] = int(total_put_oi)
                    entry['pcr'] = round(pcr, 2)
                else:
                    entry['pcr'] = None
            except Exception as opt_err:
                print(f"  Options not available for {key}: {opt_err}")
                entry['pcr'] = None

        # ----- MACD (requires 1 month historical data) -----
        hist = ticker.history(period="1mo")
        if not hist.empty:
            # MACD calculation
            macd = ta.trend.MACD(hist['Close'])
            entry['macd'] = {
                'macd': round(macd.macd().iloc[-1], 2),
                'signal': round(macd.macd_signal().iloc[-1], 2),
                'histogram': round(macd.macd_diff().iloc[-1], 2)
            }
            # Store last 30 days OHLC for charting (compact format)
            hist_records = []
            for date, row in hist.iterrows():
                hist_records.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'o': round(row['Open'], 2),
                    'h': round(row['High'], 2),
                    'l': round(row['Low'], 2),
                    'c': round(row['Close'], 2)
                })
            entry['history'] = hist_records
        else:
            entry['macd'] = None
            entry['history'] = []

        data[key] = entry
        print(f"  [OK] {key}: {price:.2f} ({chg_pct:+.2f}%)")

    except Exception as e:
        errors.append(f"{key}: {e}")
        print(f"  [ERR] {key}: {e}")

output = {
    'updated': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
    'data': data,
    'errors': errors
}

with open('data.json', 'w') as f:
    json.dump(output, f, indent=2)

print(f"\n✅ Wrote data.json — {len(data)} symbols, {len(errors)} errors")
