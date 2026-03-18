"""
NIFTY 50 COMPLETE ANALYSIS - DEEP OCEAN THEME
CARD STYLE: Glassmorphism Frosted — Stat Card + Progress Bar (Layout 4)
CHANGE IN OPEN INTEREST: Navy Command Theme (v3)
FII/DII SECTION: Theme 3 · Pulse Flow
MARKET DIRECTION: Holographic Glass Widget (Compact)
KEY LEVELS: 1H Candles · Last 120 bars · ±200 pts from price · Rounded to 25
AUTO REFRESH: JSON timestamp polling every 30s · Reloads ONLY when script re-runs · No flicker · No scroll jump
STRATEGY CHECKLIST TAB: Rules-based scoring · Auto-filled from live data · N/A safe
INTRADAY OI TREND TAB: Every-run snapshot → oi_log.json · 3/5/15 Min filter · IST timestamps
NIFTY 50 HEATMAP TAB: Live yfinance data · Color-coded by % change · Market Breadth · High Weightage Movers

FIX v5: Nifty 50 Heatmap tab added
FIX v4: Intraday OI Trend tab + oi_log.json persistence
FIX v3: Holiday-aware expiry logic
FIX v2: Expiry date now time-aware
FIX v1: Net OI = PE Δ - CE Δ
"""
from curl_cffi import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta, date
import yfinance as yf
import warnings
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import pytz
warnings.filterwarnings('ignore')

NSE_FO_HOLIDAYS = {
    "26-Jan-2025","19-Feb-2025","14-Mar-2025","31-Mar-2025","10-Apr-2025",
    "14-Apr-2025","18-Apr-2025","01-May-2025","15-Aug-2025","27-Aug-2025",
    "02-Oct-2025","20-Oct-2025","21-Oct-2025","05-Nov-2025","19-Nov-2025","25-Dec-2025",
    "15-Jan-2026","26-Jan-2026","03-Mar-2026","26-Mar-2026","31-Mar-2026",
    "03-Apr-2026","14-Apr-2026","01-May-2026","28-May-2026","26-Jun-2026",
    "14-Sep-2026","02-Oct-2026","20-Oct-2026","10-Nov-2026","24-Nov-2026","25-Dec-2026",
}

# ═══════════════════════════════════════════════════════════════════════════════
#  NIFTY 50 HEATMAP — DATA & HTML
# ═══════════════════════════════════════════════════════════════════════════════

NIFTY50_SYMBOLS = [
    ("ADANIPORTS", "ADANIPORTS.NS"), ("APOLLOHOSP", "APOLLOHOSP.NS"),
    ("ASIANPAINT", "ASIANPAINT.NS"), ("AXISBANK",   "AXISBANK.NS"),
    ("BAJAJ-AUTO","BAJAJ-AUTO.NS"),  ("BAJAJFINSV", "BAJAJFINSV.NS"),
    ("BAJFINANCE","BAJFINANCE.NS"),  ("BEL",        "BEL.NS"),
    ("BHARTIARTL","BHARTIARTL.NS"), ("CIPLA",       "CIPLA.NS"),
    ("COALINDIA", "COALINDIA.NS"),  ("DRREDDY",     "DRREDDY.NS"),
    ("EICHERMOT", "EICHERMOT.NS"),  ("ETERNAL",     "ETERNAL.NS"),
    ("GRASIM",    "GRASIM.NS"),     ("HCLTECH",     "HCLTECH.NS"),
    ("HDFCBANK",  "HDFCBANK.NS"),   ("HDFCLIFE",    "HDFCLIFE.NS"),
    ("HEROMOTOCO","HEROMOTOCO.NS"), ("HINDALCO",    "HINDALCO.NS"),
    ("HINDUNILVR","HINDUNILVR.NS"), ("ICICIBANK",   "ICICIBANK.NS"),
    ("INDIGO",    "INDIGO.NS"),     ("INFY",        "INFY.NS"),
    ("ITC",       "ITC.NS"),        ("JIOFIN",      "JIOFIN.NS"),
    ("JSWSTEEL",  "JSWSTEEL.NS"),   ("KOTAKBANK",   "KOTAKBANK.NS"),
    ("LT",        "LT.NS"),         ("M&M",         "M&M.NS"),
    ("MARUTI",    "MARUTI.NS"),     ("MAXHEALTH",   "MAXHEALTH.NS"),
    ("NESTLEIND", "NESTLEIND.NS"),  ("NTPC",        "NTPC.NS"),
    ("ONGC",      "ONGC.NS"),       ("POWERGRID",   "POWERGRID.NS"),
    ("RELIANCE",  "RELIANCE.NS"),   ("SBILIFE",     "SBILIFE.NS"),
    ("SBIN",      "SBIN.NS"),       ("SHRIRAMFIN",  "SHRIRAMFIN.NS"),
    ("SUNPHARMA", "SUNPHARMA.NS"),  ("TATAMOTORS",  "TMCV.NS"),
    ("TATAMOTORS",  "TMPV.NS"),
    ("TATACONSUM","TATACONSUM.NS"), ("TATASTEEL",   "TATASTEEL.NS"),
    ("TCS",       "TCS.NS"),        ("TECHM",       "TECHM.NS"),
    ("TITAN",     "TITAN.NS"),      ("TRENT",       "TRENT.NS"),
    ("ULTRACEMCO","ULTRACEMCO.NS"), ("WIPRO",       "WIPRO.NS"),
]

# High-weightage stocks (top 15 by approximate Nifty weight)
HIGH_WEIGHTAGE = {
    "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS",
    "BHARTIARTL", "LT", "AXISBANK", "KOTAKBANK", "SBIN"
}

# Fixed display order by Nifty index weight
HIGH_WEIGHTAGE_ORDER = [
    "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS",
    "BHARTIARTL", "LT", "AXISBANK", "KOTAKBANK", "SBIN"
]

def fetch_heatmap_data():
    """
    Fetches live % change data for all 50 Nifty stocks using yfinance.
    Returns a list of dicts: {symbol, name, price, prev_close, change_pct, change_abs, volume}
    """
    print("  📊 Fetching Nifty 50 heatmap data via yfinance...")
    results = []
    tickers_str = " ".join([sym for _, sym in NIFTY50_SYMBOLS])
    try:
        data = yf.download(tickers_str, period="5d", interval="1d",
                   group_by="ticker", auto_adjust=True, progress=False)
        ist_tz = pytz.timezone('Asia/Kolkata')
        timestamp = datetime.now(ist_tz).strftime('%d-%b-%Y %H:%M IST')

        for name, sym in NIFTY50_SYMBOLS:
            try:
                if len(NIFTY50_SYMBOLS) == 1:
                    df = data
                else:
                    df = data[sym] if sym in data.columns.get_level_values(0) else None
                if df is None or df.empty or len(df) < 2:
                    try:
                        df_fallback = yf.download(sym, period="5d", interval="1d",
                                                   auto_adjust=True, progress=False)
                        if not df_fallback.empty and len(df_fallback) >= 2:
                            df = df_fallback
                        else:
                            results.append({
                                'symbol': name, 'ticker': sym,
                                'price': 0, 'prev_close': 0,
                                'change_pct': 0, 'change_abs': 0,
                                'volume': 0, 'high_wt': name in HIGH_WEIGHTAGE
                            })
                            continue
                    except Exception:
                        results.append({
                            'symbol': name, 'ticker': sym,
                            'price': 0, 'prev_close': 0,
                            'change_pct': 0, 'change_abs': 0,
                            'volume': 0, 'high_wt': name in HIGH_WEIGHTAGE
                        })
                        continue
   
                # dropna: bulk yf.download() fills NaN for dates a ticker had no data.
                # Without this, df.iloc[-2]['Close'] is often NaN → renders as ₹nan.
                df_clean = df.dropna(subset=['Close'])
                if len(df_clean) < 2:
                    # Per-ticker fallback when bulk data is insufficient
                    try:
                        df_fb = yf.download(sym, period="5d", interval="1d",
                                            auto_adjust=True, progress=False)
                        df_clean = df_fb.dropna(subset=['Close']) if not df_fb.empty else df_clean
                    except Exception:
                        pass
                if len(df_clean) < 2:
                    results.append({
                        'symbol': name, 'ticker': sym,
                        'price': 0, 'prev_close': 0,
                        'change_pct': 0, 'change_abs': 0,
                        'volume': 0, 'high_wt': name in HIGH_WEIGHTAGE
                    })
                    continue
                today   = df_clean.iloc[-1]
                prev    = df_clean.iloc[-2]
                price   = float(today['Close'])
                p_close = float(prev['Close'])
                chg_abs = price - p_close
                chg_pct = (chg_abs / p_close * 100) if p_close > 0 else 0
                vol     = int(today['Volume']) if not pd.isna(today['Volume']) else 0
                results.append({
                    'symbol':     name,
                    'ticker':     sym,
                    'price':      round(price, 2),
                    'prev_close': round(p_close, 2),
                    'change_pct': round(chg_pct, 2),
                    'change_abs': round(chg_abs, 2),
                    'volume':     vol,
                    'high_wt':    name in HIGH_WEIGHTAGE,
                })
            except Exception as e:
                print(f"    ⚠️  {name}: {e}")
                results.append({
                    'symbol': name, 'ticker': sym,
                    'price': 0, 'prev_close': 0,
                    'change_pct': 0, 'change_abs': 0,
                    'volume': 0, 'high_wt': name in HIGH_WEIGHTAGE
                })
        advance = sum(1 for r in results if r['change_pct'] > 0)
        decline = sum(1 for r in results if r['change_pct'] < 0)
        neutral = sum(1 for r in results if r['change_pct'] == 0)
        print(f"  ✅ Heatmap: {len(results)} stocks | Adv: {advance} Dec: {decline} Neu: {neutral}")
        return results, timestamp, advance, decline, neutral
    except Exception as e:
        print(f"  ❌ Heatmap fetch failed: {e}")
        return [], "N/A", 0, 0, 0
def fetch_global_bias():
    """
    Fetches DJI, NASDAQ, S&P 500 previous session data via yfinance.
    Returns 'bullish', 'bearish', or 'neutral' based on majority direction.
    """
    print("  🌐 Fetching global indices bias (DJI / NASDAQ / S&P 500)...")
    tickers = {"DJI": "^DJI", "NASDAQ": "^IXIC", "SP500": "^GSPC"}
    score = 0
    results = []
    for name, sym in tickers.items():
        try:
            df = yf.Ticker(sym).history(period="2d", interval="1d")
            if df is None or len(df) < 2:
                print(f"    ⚠️  {name}: insufficient data")
                continue
            prev  = float(df['Close'].iloc[-2])
            last  = float(df['Close'].iloc[-1])
            chg   = round((last - prev) / prev * 100, 2)
            direction = "▲" if chg >= 0 else "▼"
            print(f"    {direction} {name}: {chg:+.2f}%")
            score += 1 if chg >= 0 else -1
            results.append(chg)
        except Exception as e:
            print(f"    ⚠️  {name} fetch failed: {e}")

    if not results:
        print("  ⚠️  Global bias: all fetches failed — defaulting to None")
        return None

    if score >= 2:
        bias = "bullish"
    elif score <= -2:
        bias = "bearish"
    else:
        bias = "neutral"

    print(f"  ✅ Global bias → {bias.upper()} (score: {score}/{len(results)})")
    return bias
def fetch_india_vix():
    """Fetches India VIX from yfinance."""
    try:
        print("  🌡️ Fetching India VIX...")
        df = yf.Ticker("^INDIAVIX").history(period="5d", interval="1d")
        if df is None or df.empty or len(df) < 2:
            print("  ⚠️  India VIX: insufficient data")
            return None, None
        vix_today = float(df['Close'].iloc[-1])
        vix_prev  = float(df['Close'].iloc[-2])
        vix_trend = "rising" if vix_today > vix_prev else "falling"
        print(f"  ✅ India VIX: {vix_today:.2f} ({vix_trend})")
        return round(vix_today, 2), vix_trend
    except Exception as e:
        print(f"  ⚠️  India VIX fetch failed: {e}")
        return None, None   
def fetch_volume_at_levels(technical):
    """
    Uses NIFTYBEES.NS (Nifty ETF) for both price and volume.
    ETF price ≈ Nifty/100, so levels are scaled down before comparison.
    """
    try:
        import yfinance as _yf
        print("  📦 Fetching volume at support/resistance levels...")

        if not technical.get('support') or not technical.get('resistance'):
            print("  ⚠️  Key levels are N/A — skipping volume at levels")
            return None, None

        df = _yf.Ticker("NIFTYBEES.NS").history(interval="1h", period="60d")

        if df is None or df.empty or len(df) < 25:
            print("  ⚠️  Insufficient NIFTYBEES 1H data")
            return None, None

        df = df.dropna(subset=['Close', 'Volume'])
        df = df[df['Volume'] > 0]

        if len(df) < 25:
            print("  ⚠️  Not enough non-zero volume rows in NIFTYBEES")
            return None, None

        # NIFTYBEES trades at ~Nifty/100, so scale levels down
        support    = technical['support']    / 100
        resistance = technical['resistance'] / 100
        proximity  = 200 / 100  # ±2.0 on ETF scale = ±200 on Nifty scale

        df['vol_avg_20'] = df['Volume'].rolling(20).mean()
        df = df.dropna(subset=['vol_avg_20'])

        near_support    = df[abs(df['Close'] - support)    <= proximity]
        near_resistance = df[abs(df['Close'] - resistance) <= proximity]

        vol_support = vol_resistance = None

        if not near_support.empty:
            avg_vol_sup  = near_support['vol_avg_20'].mean()
            zone_vol_sup = near_support['Volume'].mean()
            if avg_vol_sup > 0:
                vol_support = round((zone_vol_sup - avg_vol_sup) / avg_vol_sup * 100, 1)
                print(f"  ✅ Vol at Support ({technical['support']}): {vol_support:+.1f}% vs avg  [{len(near_support)} candles]")
            else:
                print(f"  ⚠️  Vol at Support: avg volume is zero")
        else:
            print(f"  ⚠️  No bars found near support ({technical['support']} ±75 pts) — will show N/A")

        if not near_resistance.empty:
            avg_vol_res  = near_resistance['vol_avg_20'].mean()
            zone_vol_res = near_resistance['Volume'].mean()
            if avg_vol_res > 0:
                vol_resistance = round((zone_vol_res - avg_vol_res) / avg_vol_res * 100, 1)
                print(f"  ✅ Vol at Resistance ({technical['resistance']}): {vol_resistance:+.1f}% vs avg  [{len(near_resistance)} candles]")
            else:
                print(f"  ⚠️  Vol at Resistance: avg volume is zero")
        else:
            print(f"  ⚠️  No bars found near resistance ({technical['resistance']} ±75 pts) — will show N/A")

        return vol_support, vol_resistance

    except Exception as e:
        print(f"  ❌ Volume at levels fetch failed: {e}")
        return None, None

def build_heatmap_tab_html(heatmap_data, timestamp, advance, decline, neutral):
    """
    Builds the complete HTML for the Nifty 50 Heatmap tab.
    Embedded as JSON in <script> — fully dynamic on client side.
    Also includes High Weightage Movers table and Intraday OI Change chart.
    """
    # Serialize heatmap data to JSON for embedding
    hm_json = json.dumps(heatmap_data, ensure_ascii=False)

    # High weightage movers in fixed Nifty weight order
    hw_lookup = {r['symbol']: r for r in heatmap_data if r['high_wt']}
    hw_sorted = [hw_lookup[sym] for sym in HIGH_WEIGHTAGE_ORDER if sym in hw_lookup]
    hw_rows_html = ""
    for s in hw_sorted:
        chg_col = "#00e676" if s['change_pct'] >= 0 else "#ff5252"
        sign    = "+" if s['change_pct'] >= 0 else ""
        hw_rows_html += f"""
                <tr>
                    <td class="hm-mover-sym">{s['symbol']}</td>
                    <td class="hm-mover-prev">₹{s['prev_close']:,.2f}</td>
                    <td class="hm-mover-price">₹{s['price']:,.2f}</td>
                    <td class="hm-mover-chg" style="color:{chg_col};">{sign}{s['change_pct']:.2f}%</td>
                </tr>"""

    total = advance + decline + neutral or 1
    adv_pct = round(advance / total * 100, 1)
    dec_pct = round(decline / total * 100, 1)

    return f"""
    <!-- TAB 4: NIFTY 50 HEATMAP -->
    <div class="tab-panel" id="tab-heatmap">
      <div class="section">
        <div class="section-title">
          <span>🟩</span> NIFTY 50 HEATMAP
          <span style="font-size:10px;color:rgba(128,222,234,0.35);font-weight:400;margin-left:auto;display:flex;flex-direction:column;align-items:flex-end;gap:3px;">
            <span>Stock data as of: {timestamp}</span>
            <span style="font-size:9px;color:rgba(239,68,68,0.45);letter-spacing:0.5px;">⟳ OI chart auto-refreshes · Stock tiles update on script re-run</span>
          </span>
        </div>

        <!-- Breadth Strip -->
        <div class="hm-breadth-strip">
          <div class="hm-bs-left">
            <div class="hm-bs-stat hm-bs-adv">
              <div class="hm-bs-num" id="hmAdvCount">{advance}</div>
              <div class="hm-bs-lbl">ADVANCE</div>
            </div>
            <div class="hm-bs-stat hm-bs-dec">
              <div class="hm-bs-num" id="hmDecCount">{decline}</div>
              <div class="hm-bs-lbl">DECLINE</div>
            </div>
            <div class="hm-bs-stat hm-bs-neu">
              <div class="hm-bs-num" id="hmNeuCount">{neutral}</div>
              <div class="hm-bs-lbl">NEUTRAL</div>
            </div>
          </div>
          <div class="hm-bs-donut-wrap">
            <canvas id="hmDonutCanvas" width="110" height="110"></canvas>
            <div class="hm-bs-donut-center">
              <div class="hm-bs-donut-num">50</div>
              <div class="hm-bs-donut-sub">STOCKS</div>
            </div>
          </div>
          <div class="hm-bs-right">
            <div class="hm-breadth-label" style="font-size:11px;color:rgba(128,222,234,0.5);margin-bottom:8px;letter-spacing:1px;">MARKET BREADTH</div>
            <div class="hm-breadth-row">
              <span class="hm-br-dot" style="background:#00e676;"></span>
              <span class="hm-br-label">Advancing</span>
              <div class="hm-br-bar-wrap"><div class="hm-br-bar" style="width:{adv_pct}%;background:linear-gradient(90deg,#00e676,#00bfa5);"></div></div>
              <span class="hm-br-val" style="color:#00e676;">{advance}</span>
            </div>
            <div class="hm-breadth-row">
              <span class="hm-br-dot" style="background:#ff5252;"></span>
              <span class="hm-br-label">Declining</span>
              <div class="hm-br-bar-wrap"><div class="hm-br-bar" style="width:{dec_pct}%;background:linear-gradient(90deg,#ff5252,#d50000);"></div></div>
              <span class="hm-br-val" style="color:#ff5252;">{decline}</span>
            </div>
            <div class="hm-breadth-row">
              <span class="hm-br-dot" style="background:#78909c;"></span>
              <span class="hm-br-label">Neutral</span>
              <div class="hm-br-bar-wrap"><div class="hm-br-bar" style="width:2%;background:#546e7a;"></div></div>
              <span class="hm-br-val" style="color:#9ab0bc;">{neutral}</span>
            </div>
          </div>
        </div>

        <!-- Heatmap Grid -->
        <div class="hm-grid" id="hmGrid">
          <!-- Populated by JS -->
        </div>

        <!-- Color Legend -->
        <div class="hm-legend">
          <div style="font-size:9px;letter-spacing:2px;color:rgba(128,222,234,0.4);text-transform:uppercase;font-weight:700;margin-bottom:8px;">COLOR SCALE</div>
          <div class="hm-legend-bar">
            <span class="hm-leg-txt" style="color:#d50000;">≤ -2%</span>
            <div class="hm-leg-gradient"></div>
            <span class="hm-leg-txt" style="color:#00e676;">≥ +2%</span>
          </div>
        </div>
      </div>

      <!-- High Weightage Movers + OI Chart (2-col) -->
      <div class="section">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:start;">

          <!-- High Weightage Movers Table -->
          <div>
            <div class="section-title" style="border-bottom:1px solid rgba(79,195,247,0.18);padding-bottom:10px;margin-bottom:14px;">
              <span>⚖️</span> HIGH WEIGHTAGE MOVERS
            </div>
            <div class="hm-mover-wrap">
              <table class="hm-mover-table">
                <thead>
                  <tr>
                    <th style="text-align:left;">SYMBOL</th>
                    <th>PREV CLOSE</th>
                    <th>PRICE</th>
                    <th>% CHG</th>
                  </tr>
                </thead>
                <tbody id="hmMoverBody">
                  {hw_rows_html}
                </tbody>
              </table>
            </div>
          </div>

          <!-- Intraday OI Change Chart (mini) -->
          <div>
            <div class="section-title" style="border-bottom:1px solid rgba(79,195,247,0.18);padding-bottom:10px;margin-bottom:14px;">
              <span>⚡</span> INTRADAY OI CHANGE
              <span id="hmOIPCR" style="margin-left:auto;font-family:'JetBrains Mono',monospace;font-size:11px;color:rgba(128,222,234,0.5);">PCR: —</span>
            </div>
            <div style="display:flex;gap:10px;margin-bottom:8px;">
              <button class="hm-idx-btn active" id="hmBtnNifty" onclick="setHMIndex('nifty',this)">NIFTY</button>
              <button class="hm-idx-btn" id="hmBtnBankNifty" onclick="setHMIndex('banknifty',this)">BANKNIFTY</button>
            </div>
            <div class="hm-oi-chart-wrap">
              <canvas id="hmOICanvas" width="420" height="200"></canvas>
            </div>
            <div style="display:flex;gap:16px;margin-top:8px;">
              <div style="display:flex;align-items:center;gap:6px;font-size:10px;color:rgba(176,190,197,0.5);">
                <span style="display:inline-block;width:24px;height:2px;background:#ef4444;border-radius:1px;"></span> Call OI Change
              </div>
              <div style="display:flex;align-items:center;gap:6px;font-size:10px;color:rgba(176,190,197,0.5);">
                <span style="display:inline-block;width:24px;height:2px;background:#10b981;border-radius:1px;"></span> Put OI Change
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Heatmap data embedded as JSON for JS rendering -->
      <script id="hmDataScript" type="application/json">{hm_json}</script>
    </div><!-- /tab-heatmap -->
"""


def get_heatmap_javascript():
    """Returns the JavaScript for the heatmap tab rendering."""
    return """
/* ════════════════════════════════════════════════════════════════
   NIFTY 50 HEATMAP — client-side rendering engine
   Data loaded from embedded JSON, refreshed on silent page reload
   ════════════════════════════════════════════════════════════════ */
(function() {
    var _hmIndex = 'nifty';

    function getColor(pct) {
        var capped = Math.max(-3, Math.min(3, pct));
        if (pct === 0) return { bg: 'rgba(55,65,81,0.8)', border: 'rgba(100,116,139,0.4)', text: '#94a3b8' };
        if (pct > 0) {
            var intensity = Math.min(1, pct / 2.5);
            var r = Math.round(0   + (0   - 0)   * intensity);
            var g = Math.round(180 + (230 - 180) * intensity);
            var b = Math.round(80  + (118 - 80)  * intensity);
            var a = 0.25 + intensity * 0.55;
            return {
                bg:     'rgba(' + r + ',' + g + ',' + b + ',' + a + ')',
                border: 'rgba(' + r + ',' + g + ',' + b + ',0.5)',
                text:   pct > 1.5 ? '#fff' : '#a7f3d0'
            };
        } else {
            var intensity = Math.min(1, Math.abs(pct) / 2.5);
            var r = Math.round(220 + (239 - 220) * intensity);
            var g = Math.round(50  + (68  - 50)  * intensity);
            var b = Math.round(50  + (68  - 50)  * intensity);
            var a = 0.25 + intensity * 0.55;
            return {
                bg:     'rgba(' + r + ',' + g + ',' + b + ',' + a + ')',
                border: 'rgba(' + r + ',' + g + ',' + b + ',0.5)',
                text:   Math.abs(pct) > 1.5 ? '#fff' : '#fca5a5'
            };
        }
    }

    // Full Nifty 50 weight order — descending by approximate index weight
    var NIFTY_WEIGHT_ORDER = [
        "HDFCBANK","RELIANCE","ICICIBANK","INFY","TCS",
        "BHARTIARTL","LT","AXISBANK","SBIN","KOTAKBANK",
        "BAJFINANCE","HINDUNILVR","MARUTI","SUNPHARMA","HCLTECH",
        "TITAN","WIPRO","NTPC","M&M","ONGC",
        "ULTRACEMCO","POWERGRID","TATAMOTORS","COALINDIA","ADANIPORTS",
        "BAJAJ-AUTO","BAJAJFINSV","ETERNAL","GRASIM","ITC",
        "JSWSTEEL","TATACONSUM","TATASTEEL","TECHM","DRREDDY",
        "CIPLA","HINDALCO","EICHERMOT","SBILIFE","HDFCLIFE",
        "JIOFIN","HEROMOTOCO","TRENT","MAXHEALTH","INDIGO",
        "NESTLEIND","ASIANPAINT","SHRIRAMFIN","BEL","APOLLOHOSP"
    ];

    function renderHeatmap() {
    var el = document.getElementById('hmDataScript');
    var grid = document.getElementById('hmGrid');
    if (!el || !grid) {
        console.warn('HM: elements missing after refresh');
        return;
    }
    var rawText = el.textContent || el.innerHTML || el.innerText || '';
    if (!rawText || rawText.trim() === '') {
        console.warn('HM: empty data script');
        return;
    }
    var data;
    try { data = JSON.parse(rawText); }
    catch(e) { console.warn('HM parse error:', e); return; }

        // Sort by Nifty index weight (descending) — unknowns go to end
        var weightIndex = {};
        NIFTY_WEIGHT_ORDER.forEach(function(sym, i){ weightIndex[sym] = i; });
        data = data.slice().sort(function(a, b) {
            var ai = weightIndex[a.symbol] !== undefined ? weightIndex[a.symbol] : 999;
            var bi = weightIndex[b.symbol] !== undefined ? weightIndex[b.symbol] : 999;
            return ai - bi;
        });

        var html = '';
        data.forEach(function(s) {
            var c    = getColor(s.change_pct);
            var sign = s.change_pct >= 0 ? '+' : '';
            var hwBorder = s.high_wt ? '2px solid rgba(79,195,247,0.6)' : ('1px solid ' + c.border);
            var priceStr = s.price > 0 ? '₹' + s.price.toLocaleString('en-IN') : '—';
            html += '<div class="hm-cell" style="background:' + c.bg + ';border:' + hwBorder + ';color:' + c.text + ';"'
                  + ' title="' + s.symbol + ' | Prev: ₹' + s.prev_close + ' | Price: ₹' + s.price + ' | Chg: ' + sign + s.change_pct + '%">'
                  + '<div class="hm-cell-sym">' + s.symbol + '</div>'
                  + '<div class="hm-cell-price">' + priceStr + '</div>'
                  + '<div class="hm-cell-chg">' + sign + s.change_pct.toFixed(2) + '%</div>'
                  + '</div>';
        });
        grid.innerHTML = html;

        // Update breadth counters
        var adv = data.filter(function(s){ return s.change_pct > 0; }).length;
        var dec = data.filter(function(s){ return s.change_pct < 0; }).length;
        var neu = data.filter(function(s){ return s.change_pct === 0; }).length;
        var e;
        e = document.getElementById('hmAdvCount'); if(e) e.textContent = adv;
        e = document.getElementById('hmDecCount'); if(e) e.textContent = dec;
        e = document.getElementById('hmNeuCount'); if(e) e.textContent = neu;

        // Update mover table
        // Update mover table — fixed Nifty weight order
        var WEIGHT_ORDER = [
            "RELIANCE","HDFCBANK","ICICIBANK","INFY","TCS",
            "BHARTIARTL","LT","AXISBANK","KOTAKBANK","SBIN"
        ];
        var hwLookup = {};
        data.forEach(function(s){ if(s.high_wt) hwLookup[s.symbol] = s; });
        var hwStocks = WEIGHT_ORDER.map(function(sym){ return hwLookup[sym]; }).filter(Boolean);
        var moverBody = document.getElementById('hmMoverBody');
        if (moverBody) {
            var mhtml = '';
            hwStocks.forEach(function(s) {
                var col  = s.change_pct >= 0 ? '#00e676' : '#ff5252';
                var sign = s.change_pct >= 0 ? '+' : '';
                mhtml += '<tr>'
                       + '<td class="hm-mover-sym">' + s.symbol + '</td>'
                       + '<td class="hm-mover-prev">₹' + s.prev_close.toLocaleString('en-IN') + '</td>'
                       + '<td class="hm-mover-price">₹' + s.price.toLocaleString('en-IN') + '</td>'
                       + '<td class="hm-mover-chg" style="color:' + col + ';">' + sign + s.change_pct.toFixed(2) + '%</td>'
                       + '</tr>';
            });
            moverBody.innerHTML = mhtml;
        }

        drawDonut(adv, dec, neu);
    }

    function drawDonut(adv, dec, neu) {
        var canvas = document.getElementById('hmDonutCanvas');
        if (!canvas || !canvas.getContext) return;
        var ctx = canvas.getContext('2d');
        var cx = 55, cy = 55, r = 40, lw = 10;
        ctx.clearRect(0, 0, 110, 110);
        var total = adv + dec + neu || 1;
        var slices = [
            { val: adv, color: '#00e676' },
            { val: dec, color: '#ef4444' },
            { val: neu, color: '#546e7a' },
        ];
        var start = -Math.PI / 2;
        slices.forEach(function(sl) {
            if (!sl.val) return;
            var sweep = (sl.val / total) * 2 * Math.PI;
            ctx.beginPath();
            ctx.arc(cx, cy, r, start, start + sweep);
            ctx.strokeStyle = sl.color;
            ctx.lineWidth = lw;
            ctx.stroke();
            start += sweep;
        });
        // center text handled by CSS overlay
    }

    /* ── OI Chart from oi_log.json ────────────────────────────── */
    function drawHMOIChart(data) {
        var canvas = document.getElementById('hmOICanvas');
        if (!canvas || !canvas.getContext) return;
        var ctx = canvas.getContext('2d');
        var W = canvas.parentElement ? canvas.parentElement.clientWidth - 32 : 420;
        var H = 200;
        canvas.width = W; canvas.height = H;
        ctx.clearRect(0, 0, W, H);
        if (!data || data.length < 2) {
            ctx.fillStyle = 'rgba(128,222,234,0.2)';
            ctx.font = '11px JetBrains Mono, monospace';
            ctx.textAlign = 'center';
            ctx.fillText('Loading OI data…', W/2, H/2);
            return;
        }
        var reversed = data.slice().reverse();
        var ceArr    = reversed.map(function(r){ return r.call_oi_chg || 0; });
        var peArr    = reversed.map(function(r){ return r.put_oi_chg  || 0; });
        var allVals  = ceArr.concat(peArr);
        var minV = Math.min.apply(null, allVals);
        var maxV = Math.max.apply(null, allVals);
        var range = (maxV - minV) || 1;
        var pad = 14;
        function toX(i) { return (i / (ceArr.length - 1)) * (W - 2*pad) + pad; }
        function toY(v) { return H - ((v - minV) / range) * (H - 2*pad) - pad; }

        // Zero line
        ctx.save();
        ctx.strokeStyle = 'rgba(79,195,247,0.12)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        var zy = toY(0);
        ctx.beginPath(); ctx.moveTo(pad, zy); ctx.lineTo(W-pad, zy); ctx.stroke();
        ctx.restore();

        // Draw CE (red)
        ctx.strokeStyle = '#ef4444'; ctx.lineWidth = 2; ctx.lineJoin = 'round';
        ctx.beginPath();
        ceArr.forEach(function(v, i){ i===0 ? ctx.moveTo(toX(i),toY(v)) : ctx.lineTo(toX(i),toY(v)); });
        ctx.stroke();

        // Draw PE (green)
        ctx.strokeStyle = '#10b981'; ctx.lineWidth = 2; ctx.lineJoin = 'round';
        ctx.beginPath();
        peArr.forEach(function(v, i){ i===0 ? ctx.moveTo(toX(i),toY(v)) : ctx.lineTo(toX(i),toY(v)); });
        ctx.stroke();

        // Time labels on x-axis (every ~5th point)
        ctx.fillStyle = 'rgba(128,222,234,0.3)';
        ctx.font = '8px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        var step = Math.max(1, Math.floor(reversed.length / 6));
        for (var i = 0; i < reversed.length; i += step) {
            ctx.fillText(reversed[i].time || '', toX(i), H - 2);
        }
    }

    window.setHMIndex = function(idx, btn) {
        _hmIndex = idx;
        document.querySelectorAll('.hm-idx-btn').forEach(function(b){ b.classList.remove('active'); });
        btn.classList.add('active');
        // Re-draw with same data (different index would need separate fetch)
        if (window._oiData && window._oiData.length) drawHMOIChart(window._oiData);
    };

    /* Called on tab switch or page load */
    window.renderHeatmap = renderHeatmap;

    window.addEventListener('load', function() {
    setTimeout(renderHeatmap, 100);
    setTimeout(renderHeatmap, 500);
    setTimeout(renderHeatmap, 1500);
    setTimeout(function() {
        if (window._oiData && window._oiData.length) drawHMOIChart(window._oiData);
    }, 800);
});

    // Hook into loadOILog to also refresh OI chart
    var _origRenderOI = window.renderOITable;

    /* After oi_log loads, also draw heatmap OI chart */
    var _origLoad = window.loadOILog;
    function patchedLoadOILog() {
        fetch('oi_log.json?_t=' + Date.now(), {cache:'no-store'})
            .then(function(r){ return r.json(); })
            .then(function(data) {
                if (Array.isArray(data) && data.length) {
                    window._oiData = data;
                    drawHMOIChart(data);
                    var pcr = data[0] && data[0].pcr ? data[0].pcr : null;
                    var el = document.getElementById('hmOIPCR');
                    if (el && pcr) el.textContent = 'PCR: ' + pcr;
                }
            })
            .catch(function(){});
    }

    // Run OI chart draw periodically
    setInterval(function() {
    patchedLoadOILog();
    renderHeatmap();
}, 30000);

// Initial draw
setTimeout(patchedLoadOILog, 1200);
setTimeout(renderHeatmap, 800);
setTimeout(renderHeatmap, 2000);
})();
"""


def get_heatmap_css():
    """Returns the CSS for the heatmap tab."""
    return """
        /* ══ NIFTY 50 HEATMAP ═══════════════════════════════════════ */
        .hm-breadth-strip{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:20px;background:rgba(6,13,20,0.7);border:1px solid rgba(79,195,247,0.14);border-radius:14px;padding:20px 24px;margin-bottom:20px;}
        .hm-bs-left{display:flex;gap:24px;align-items:center;}
        .hm-bs-stat{text-align:center;}
        .hm-bs-num{font-family:'Orbitron',monospace;font-size:clamp(26px,4vw,36px);font-weight:900;line-height:1;}
        .hm-bs-adv .hm-bs-num{color:#00e676;text-shadow:0 0 20px rgba(0,230,118,0.5);}
        .hm-bs-dec .hm-bs-num{color:#ff5252;text-shadow:0 0 20px rgba(255,82,82,0.5);}
        .hm-bs-neu .hm-bs-num{color:#9ab0bc;}
        .hm-bs-lbl{font-size:9px;letter-spacing:2.5px;color:rgba(176,190,197,0.4);text-transform:uppercase;font-weight:700;margin-top:4px;}
        .hm-bs-donut-wrap{position:relative;width:110px;height:110px;flex-shrink:0;}
        .hm-bs-donut-center{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center;}
        .hm-bs-donut-num{font-family:'Orbitron',monospace;font-size:20px;font-weight:900;color:#e0f7fa;}
        .hm-bs-donut-sub{font-size:8px;letter-spacing:2px;color:rgba(128,222,234,0.4);text-transform:uppercase;}
        .hm-bs-right{flex:1;min-width:200px;}
        .hm-breadth-label{font-size:11px;color:rgba(128,222,234,0.5);margin-bottom:8px;letter-spacing:1px;}
        .hm-breadth-row{display:flex;align-items:center;gap:8px;margin-bottom:10px;}
        .hm-br-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;}
        .hm-br-label{font-size:10px;color:rgba(176,190,197,0.5);width:70px;flex-shrink:0;}
        .hm-br-bar-wrap{flex:1;height:4px;background:rgba(0,0,0,0.35);border-radius:2px;overflow:hidden;}
        .hm-br-bar{height:100%;border-radius:2px;transition:width 1s ease;}
        .hm-br-val{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;width:20px;text-align:right;flex-shrink:0;}
        .hm-grid{display:grid;grid-template-columns:repeat(10,minmax(0,1fr));gap:6px;margin-bottom:16px;}
        .hm-cell{border-radius:10px;padding:10px 8px;cursor:default;transition:all 0.2s ease;position:relative;overflow:hidden;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:72px;text-align:center;}
        .hm-cell:hover{transform:scale(1.06);z-index:10;box-shadow:0 8px 24px rgba(0,0,0,0.5);filter:brightness(1.15);}
        .hm-cell-sym{font-family:'Oxanium',sans-serif;font-size:clamp(8px,1.2vw,11px);font-weight:700;letter-spacing:0.3px;line-height:1.2;word-break:break-word;}
        .hm-cell-price{font-family:'JetBrains Mono',monospace;font-size:clamp(7px,0.9vw,9px);opacity:0.75;margin-top:3px;font-weight:600;}
        .hm-cell-chg{font-family:'Oxanium',sans-serif;font-size:clamp(9px,1.2vw,12px);font-weight:800;margin-top:2px;letter-spacing:0.3px;}
        .hm-legend{display:flex;flex-direction:column;align-items:center;margin-bottom:4px;}
        .hm-legend-bar{display:flex;align-items:center;gap:12px;width:100%;max-width:400px;}
        .hm-leg-gradient{flex:1;height:10px;border-radius:5px;background:linear-gradient(90deg,#b91c1c,#ef4444,#374151,#10b981,#065f46);}
        .hm-leg-txt{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;}
        .hm-mover-wrap{background:rgba(6,13,20,0.7);border:1px solid rgba(79,195,247,0.14);border-radius:12px;overflow:hidden;}
        .hm-mover-table{width:100%;border-collapse:collapse;font-family:'JetBrains Mono',monospace;}
        .hm-mover-table thead th{padding:10px 14px;font-size:9px;letter-spacing:2px;color:rgba(128,222,234,0.45);text-transform:uppercase;font-weight:700;text-align:right;border-bottom:1px solid rgba(79,195,247,0.15);background:rgba(79,195,247,0.05);}
        .hm-mover-table thead th:first-child{text-align:left;}
        .hm-mover-table tbody tr{border-bottom:1px solid rgba(79,195,247,0.06);transition:background 0.15s;}
        .hm-mover-table tbody tr:hover{background:rgba(79,195,247,0.05);}
        .hm-mover-table tbody td{padding:9px 14px;font-size:12px;text-align:right;color:#c8d8e0;}
        .hm-mover-sym{text-align:left!important;color:#e0f7fa!important;font-weight:700;}
        .hm-mover-prev{color:#8faabe!important;}
        .hm-mover-price{color:#4fc3f7!important;font-weight:600;}
        .hm-mover-chg{font-weight:700;}
        .hm-oi-chart-wrap{background:rgba(6,13,20,0.7);border:1px solid rgba(79,195,247,0.14);border-radius:12px;padding:14px;overflow:hidden;}
        .hm-idx-btn{padding:7px 18px;font-family:'Oxanium',sans-serif;font-size:11px;font-weight:700;letter-spacing:2px;color:rgba(176,190,197,0.5);background:transparent;border:1px solid rgba(79,195,247,0.2);border-radius:8px;cursor:pointer;transition:all 0.2s ease;}
        .hm-idx-btn:hover{color:#4fc3f7;border-color:rgba(79,195,247,0.5);background:rgba(79,195,247,0.08);}
        .hm-idx-btn.active{color:#00e5ff;border-color:rgba(79,195,247,0.6);background:rgba(79,195,247,0.15);box-shadow:0 0 10px rgba(79,195,247,0.1);}
        @media(max-width:900px){.hm-grid{grid-template-columns:repeat(7,minmax(0,1fr));}}
        @media(max-width:600px){
          .hm-grid{grid-template-columns:repeat(5,minmax(0,1fr));gap:4px;}
          .hm-cell{min-height:58px;padding:8px 4px;}
          .hm-breadth-strip{flex-direction:column;align-items:flex-start;}
          div[style*="grid-template-columns:1fr 1fr"]{grid-template-columns:1fr!important;}
          .hm-bs-donut-wrap{align-self:center;}
        }
        @media(max-width:400px){.hm-grid{grid-template-columns:repeat(4,minmax(0,1fr));}}
"""


def _last_5_trading_days():
    ist_off = timedelta(hours=5, minutes=30)
    today   = (datetime.utcnow() + ist_off).date()
    days, d = [], today - timedelta(days=1)
    while len(days) < 10:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    days.reverse()
    return days

def _parse_nse_fiidii(raw):
    if not isinstance(raw, list) or not raw:
        return []
    days = []
    for row in raw[:15]:
        try:
            dt_obj  = datetime.strptime(row.get("date", ""), "%d-%b-%Y")
            fii_net = float(row.get("fiiBuyValue",0) or 0) - float(row.get("fiiSellValue",0) or 0)
            dii_net = float(row.get("diiBuyValue",0) or 0) - float(row.get("diiSellValue",0) or 0)
            days.append({'date': dt_obj.strftime("%b %d"), 'day': dt_obj.strftime("%a"),
                         'fii': round(fii_net,2), 'dii': round(dii_net,2)})
        except Exception:
            continue
    if len(days) < 3:
        return []
    days = days[:10]
    days.reverse()
    return days

def _fetch_from_groww():
    try:
        from bs4 import BeautifulSoup
        import requests as _req
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://groww.in/",
        }
        resp = _req.get("https://groww.in/fii-dii-data", headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"  ⚠️  Groww HTTP {resp.status_code}"); return []
        soup  = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")
        if not table:
            print("  ⚠️  Groww: table not found"); return []
        rows  = table.find_all("tr")
        days  = []
        for row in rows[1:]:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) < 7: continue
            try:
                dt_obj  = datetime.strptime(cols[0], "%d %b %Y")
                fii_net = float(cols[3].replace(",","").replace("+",""))
                dii_net = float(cols[6].replace(",","").replace("+",""))
                days.append({'date': dt_obj.strftime("%b %d"), 'day': dt_obj.strftime("%a"),
                             'fii': round(fii_net,2), 'dii': round(dii_net,2)})
            except Exception:
                continue
            if len(days) == 10: break
        if len(days) >= 3:
            days.reverse()
            print(f"  ✅ FII/DII from Groww: {days[0]['date']} → {days[-1]['date']}")
            return days
        return []
    except Exception as e:
        print(f"  ⚠️  Groww scrape failed: {e}"); return []

def _fetch_from_nse_curl():
    try:
        from curl_cffi import requests as curl_req
        headers = {
            "authority": "www.nseindia.com",
            "accept": "application/json, text/plain, */*",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "referer": "https://www.nseindia.com/reports/fii-dii",
            "accept-language": "en-US,en;q=0.9",
        }
        s = curl_req.Session()
        s.get("https://www.nseindia.com/", headers=headers, impersonate="chrome", timeout=12)
        time.sleep(1.2)
        s.get("https://www.nseindia.com/reports/fii-dii", headers=headers, impersonate="chrome", timeout=12)
        time.sleep(0.8)
        resp = s.get("https://www.nseindia.com/api/fiidiiTradeReact", headers=headers, impersonate="chrome", timeout=20)
        if resp.status_code == 200:
            days = _parse_nse_fiidii(resp.json())
            if days:
                print(f"  ✅ FII/DII from NSE (curl_cffi): {days[0]['date']} → {days[-1]['date']}")
                return days
    except Exception as e:
        print(f"  ⚠️  NSE curl_cffi failed: {e}")
    return []

def fetch_fii_dii_data():
    days = _fetch_from_groww()
    if days: return days
    days = _fetch_from_nse_curl()
    if days: return days
    print("  📌 FII/DII: using date-corrected fallback")
    tdays = _last_5_trading_days()
    placeholder = [
        (-1540.20,2103.50),(823.60,891.40),(-411.80,1478.30),(69.45,1174.21),(-972.13,1666.98),
        (-2103.40,1845.60),(1245.30,2340.10),(-876.50,1923.40),(432.80,1654.20),(-1120.60,2010.80)
    ]
    return [{'date': d.strftime('%b %d'), 'day': d.strftime('%a'),
             'fii': placeholder[i][0], 'dii': placeholder[i][1], 'fallback': True}
            for i, d in enumerate(tdays)]

def compute_fii_dii_summary(data):
    fii_vals = [d['fii'] for d in data]
    dii_vals = [d['dii'] for d in data]
    fii_avg  = sum(fii_vals) / len(fii_vals)
    dii_avg  = sum(dii_vals) / len(dii_vals)
    net_avg  = fii_avg + dii_avg
    fii_span = f'<span style="color:#ff5252;font-weight:700;">₹{fii_avg:.0f} Cr/day</span>'
    dii_span = f'<span style="color:#40c4ff;font-weight:700;">₹{dii_avg:+.0f} Cr/day</span>'
    net_span = f'<span style="color:#b388ff;font-weight:700;">₹{net_avg:+.0f} Cr/day</span>'
    if fii_avg > 0 and dii_avg > 0:
        label='STRONGLY BULLISH'; emoji='🚀'; color='#00e676'; badge_cls='fii-bull'
        fii_span = f'<span style="color:#00e676;font-weight:700;">₹{fii_avg:+.0f} Cr/day</span>'
        insight=(f"Both FIIs (avg {fii_span}) and DIIs (avg {dii_span}) are net buyers — "
                 f"strong dual institutional confirmation. Net combined flow: {net_span}.")
    elif fii_avg < 0 and dii_avg > 0 and dii_avg > abs(fii_avg):
        label='CAUTIOUSLY BULLISH'; emoji='📈'; color='#69f0ae'; badge_cls='fii-cbull'
        insight=(f"FIIs are net sellers (avg {fii_span}) but DIIs are absorbing strongly (avg {dii_span}). "
                 f"DII support is cushioning downside — FII return is key for breakout. Net combined flow: {net_span}.")
    elif fii_avg < 0 and dii_avg > 0:
        label='MIXED / NEUTRAL'; emoji='⚖️'; color='#ffd740'; badge_cls='fii-neu'
        insight=(f"FII selling (avg {fii_span}) is partly offset by DII buying (avg {dii_span}). "
                 f"Watch for 3+ consecutive days of FII buying for trend confirmation. Net combined flow: {net_span}.")
    elif fii_avg < 0 and dii_avg < 0:
        label='BEARISH'; emoji='📉'; color='#ff5252'; badge_cls='fii-bear'
        dii_span=f'<span style="color:#ff5252;font-weight:700;">₹{dii_avg:.0f} Cr/day</span>'
        insight=(f"Both FIIs (avg {fii_span}) and DIIs (avg {dii_span}) are net sellers — "
                 f"clear bearish institutional pressure. Exercise caution. Net combined flow: {net_span}.")
    else:
        label='NEUTRAL'; emoji='🔄'; color='#b0bec5'; badge_cls='fii-neu'
        insight="Mixed signals from institutional participants. Wait for a clearer trend."
    max_abs = max(abs(v) for row in data for v in (row['fii'], row['dii'])) or 1
    return {'fii_avg': fii_avg, 'dii_avg': dii_avg, 'net_avg': net_avg,
            'label': label, 'emoji': emoji, 'color': color,
            'badge_cls': badge_cls, 'insight': insight, 'max_abs': max_abs}


# ═══════════════════════════════════════════════════════════════════════════════
#  STRATEGY CHECKLIST ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def score_pcr(pcr):
    if pcr is None:
        return 0, "N/A", "PCR not available"
    if pcr < 0.8:
        return -1, f"{pcr:.3f}", f"PCR {pcr:.3f} → below 0.8 — excess call writing, bearish sentiment"
    elif pcr > 1.2:
        return +1, f"{pcr:.3f}", f"PCR {pcr:.3f} → above 1.2 — excess put writing, bullish sentiment"
    else:
        return 0, f"{pcr:.3f}", f"PCR {pcr:.3f} → in 0.8–1.2 range — neutral/mixed sentiment"

def score_rsi(rsi):
    if rsi is None:
        return 0, "N/A", "RSI not available"
    if rsi >= 60:
        return +1, f"{rsi:.1f}", f"RSI {rsi:.1f} → above 60 — bullish momentum building"
    elif rsi <= 40:
        return -1, f"{rsi:.1f}", f"RSI {rsi:.1f} → below 40 — bearish momentum, oversold"
    else:
        return 0, f"{rsi:.1f}", f"RSI {rsi:.1f} → 40–60 zone — neutral, no overbought/oversold signal"

def score_macd(macd_bullish):
    if macd_bullish is None:
        return 0, "N/A", "MACD data not available"
    if macd_bullish:
        return +1, "Bullish Crossover", "MACD crossed above signal line — bullish momentum"
    else:
        return -1, "Bearish Crossover", "MACD crossed below signal line — bearish momentum"

def score_trend(sma_20_above, sma_50_above, sma_200_above):
    if sma_200_above is None:
        return 0, "N/A", "Trend data not available"
    above_count = sum([sma_20_above, sma_50_above, sma_200_above])
    if above_count == 3:
        return +1, "Strong Uptrend", "Price above all SMAs (20/50/200) — strong structural uptrend"
    elif above_count >= 2:
        return +1, "Uptrend", "Price above majority of SMAs — uptrend intact"
    elif above_count == 0:
        return -1, "Downtrend", "Price below all SMAs (20/50/200) — structural downtrend"
    else:
        return -1, "Weak / Mixed", "Price below majority of SMAs — trend weakening"

def score_global(global_bias):
    if global_bias is None:
        return 0, "N/A", "Global bias not provided"
    if global_bias == "bullish":
        return +1, "Bullish", "Global indices (Dow/S&P/SGX Gift Nifty) showing bullish bias"
    elif global_bias == "bearish":
        return -1, "Bearish", "Global indices showing bearish pressure"
    else:
        return 0, "Neutral", "Global indices mixed — no directional edge"
        
def score_vix(vix, trend):
    if vix is None:
        return 0, "N/A", "India VIX not available"
    if vix > 20:
        return -1, f"{vix:.1f} ({trend})", f"VIX {vix:.1f} above 20 — high fear, bearish/volatile market"
    elif vix < 13:
        return +1, f"{vix:.1f} ({trend})", f"VIX {vix:.1f} below 13 — low fear, complacency, bullish bias"
    elif 13 <= vix <= 16:
        score = +1 if trend == "falling" else 0
        return score, f"{vix:.1f} ({trend})", f"VIX {vix:.1f} in normal range — {trend}"
    else:  # 16–20
        score = -1 if trend == "rising" else 0
        return score, f"{vix:.1f} ({trend})", f"VIX {vix:.1f} elevated — {'rising, caution' if trend == 'rising' else 'stable watch zone'}"
        
def score_oi_direction(oi_class):
    if oi_class is None:
        return 0, "N/A", "OI direction data not available"
    if oi_class == "bullish":
        return +1, "Bullish OI", "Net OI change is bullish — put build-up / call unwinding dominant"
    elif oi_class == "bearish":
        return -1, "Bearish OI", "Net OI change is bearish — call build-up / put unwinding dominant"
    else:
        return 0, "Neutral OI", "OI changes balanced — no clear directional signal"

BULLISH_MILD   = ["Bull Call Spread","Bull Put Spread","Jade Lizard","The Wheel Strategy (CSP + Covered Call)"]
BULLISH_STRONG = ["Long Call","Bull Call Spread","Bull Call Ladder","Bull Put Spread","Bull Put Ladder",
                  "Synthetic Long","Call Ratio Backspread","Strap (Bullish Bias)"]
BEARISH_MILD   = ["Bear Call Spread","Bear Put Spread","Reverse Jade Lizard"]
BEARISH_STRONG = ["Long Put","Bear Put Spread","Bear Call Spread","Bear Put Ladder","Bear Call Ladder",
                  "Synthetic Short","Put Ratio Backspread","Strip (Bearish Bias)"]
NEUTRAL_LOW_VOL    = ["Short Straddle","Short Strangle","Iron Condor","Iron Butterfly","Condor Spread (Short)"]
NEUTRAL_NORMAL_VOL = ["Iron Condor","Iron Butterfly","Calendar Spread","Diagonal Spread","Butterfly Spread (Short)"]
VOLATILITY_LONG    = ["Long Straddle","Long Strangle","Long Guts","Strap (Bullish Bias)","Strip (Bearish Bias)","Butterfly Spread (Long)"]
ADVANCED_MISC      = ["Call Ratio Spread","Put Ratio Spread","Christmas Tree Spread"]

STRAT_TYPE_MAP = {
    "Long Call":"bullish","Bull Call Spread":"bullish","Bull Call Ladder":"bullish",
    "Bull Put Spread":"bullish","Bull Put Ladder":"bullish","Synthetic Long":"bullish",
    "Call Ratio Backspread":"bullish","Strap (Bullish Bias)":"volatility",
    "Jade Lizard":"bullish","The Wheel Strategy (CSP + Covered Call)":"bullish",
    "Long Put":"bearish","Bear Put Spread":"bearish","Bear Call Spread":"bearish",
    "Bear Put Ladder":"bearish","Bear Call Ladder":"bearish","Synthetic Short":"bearish",
    "Put Ratio Backspread":"bearish","Strip (Bearish Bias)":"volatility",
    "Reverse Jade Lizard":"bearish",
    "Short Straddle":"neutral","Short Strangle":"neutral","Iron Condor":"neutral",
    "Iron Butterfly":"neutral","Condor Spread (Short)":"neutral",
    "Calendar Spread":"neutral","Diagonal Spread":"neutral","Butterfly Spread (Short)":"neutral",
    "Long Straddle":"volatility","Long Strangle":"volatility","Long Guts":"volatility",
    "Butterfly Spread (Long)":"volatility",
    "Call Ratio Spread":"advanced","Put Ratio Spread":"advanced","Christmas Tree Spread":"advanced",
}

def get_strike_suggestion(strategy_name, atm, ce_wall, pe_wall):
    """
    Returns a concise strike recommendation string for each strategy.
    atm      = ATM strike (nearest to spot)
    ce_wall  = Strike with max CE OI (acts as resistance)
    pe_wall  = Strike with max PE OI (acts as support)
    All strikes rounded to nearest 50.
    """
    atm_p50  = atm + 50    # 1 strike OTM call
    atm_m50  = atm - 50    # 1 strike OTM put
    atm_p100 = atm + 100
    atm_m100 = atm - 100
    atm_m150 = atm - 150

    recs = {
        # ── BULLISH ───────────────────────────────────────────────────────────
        "Long Call":
            f"BUY {atm}CE (ATM) or {atm_p50}CE (slight OTM)",
        "Bull Call Spread":
            f"BUY {atm}CE  +  SELL {ce_wall}CE (call wall)",
        "Bull Call Ladder":
            f"BUY {atm}CE  +  SELL {atm_p50}CE  +  SELL {atm_p100}CE",
        "Bull Put Spread":
            f"SELL {atm_m50}PE  +  BUY {pe_wall}PE (put wall hedge)",
        "Bull Put Ladder":
            f"SELL {atm}PE  +  BUY {atm_m50}PE  +  BUY {atm_m100}PE",
        "Synthetic Long":
            f"BUY {atm}CE  +  SELL {atm}PE  (same expiry)",
        "Call Ratio Backspread":
            f"SELL 1× {atm}CE  +  BUY 2× {atm_p50}CE",
        "Strap (Bullish Bias)":
            f"BUY 2× {atm}CE  +  BUY 1× {atm}PE  (same strike & expiry)",
        "Jade Lizard":
            f"SELL {atm_p50}CE  +  SELL {atm_m50}/{atm_m100}PE spread",
        "The Wheel Strategy (CSP + Covered Call)":
            f"SELL {pe_wall}PE (cash-secured); on assignment SELL {ce_wall}CE",

        # ── BEARISH ───────────────────────────────────────────────────────────
        "Long Put":
            f"BUY {atm}PE (ATM) or {atm_m50}PE (slight OTM)",
        "Bear Put Spread":
            f"BUY {atm}PE  +  SELL {pe_wall}PE (put wall)",
        "Bear Call Spread":
            f"SELL {atm_p50}CE  +  BUY {ce_wall}CE (call wall hedge)",
        "Bear Put Ladder":
            f"BUY {atm}PE  +  SELL {atm_m50}PE  +  SELL {atm_m100}PE",
        "Bear Call Ladder":
            f"SELL {atm}CE  +  BUY {atm_p50}CE  +  BUY {atm_p100}CE",
        "Synthetic Short":
            f"SELL {atm}CE  +  BUY {atm}PE  (same expiry)",
        "Put Ratio Backspread":
            f"SELL 1× {atm}PE  +  BUY 2× {atm_m50}PE",
        "Strip (Bearish Bias)":
            f"BUY 1× {atm}CE  +  BUY 2× {atm}PE  (same strike & expiry)",
        "Reverse Jade Lizard":
            f"SELL {atm_m50}PE  +  SELL {atm_p50}/{atm_p100}CE spread",

        # ── NEUTRAL ───────────────────────────────────────────────────────────
        "Short Straddle":
            f"SELL {atm}CE  +  SELL {atm}PE  (same ATM strike)",
        "Short Strangle":
            f"SELL {atm_p50}CE  +  SELL {atm_m50}PE  (OTM both sides)",
        "Iron Condor":
            f"SELL {atm_p50}CE / BUY {ce_wall}CE  +  SELL {atm_m50}PE / BUY {pe_wall}PE",
        "Iron Butterfly":
            f"SELL {atm}CE + SELL {atm}PE  |  BUY {atm_p100}CE + BUY {atm_m100}PE",
        "Condor Spread (Short)":
            f"SELL {atm_p50}CE + SELL {atm_m50}PE  +  BUY {atm_p100}CE + BUY {atm_m100}PE",
        "Calendar Spread":
            f"SELL near-expiry {atm}CE/PE  +  BUY next-expiry {atm}CE/PE",
        "Diagonal Spread":
            f"SELL near-expiry {atm_p50}CE  +  BUY next-expiry {atm}CE",
        "Butterfly Spread (Short)":
            f"SELL {atm_m50}CE + SELL {atm_p50}CE  +  BUY 2× {atm}CE",

        # ── VOLATILITY ────────────────────────────────────────────────────────
        "Long Straddle":
            f"BUY {atm}CE  +  BUY {atm}PE  (same ATM strike & expiry)",
        "Long Strangle":
            f"BUY {atm_p50}CE  +  BUY {atm_m50}PE  (OTM both sides)",
        "Long Guts":
            f"BUY {atm}CE  +  BUY {atm}PE  (ITM both sides, 1 strike apart)",
        "Butterfly Spread (Long)":
            f"BUY {atm_m50}CE  +  SELL 2× {atm}CE  +  BUY {atm_p50}CE",

        # ── ADVANCED ─────────────────────────────────────────────────────────
        "Call Ratio Spread":
            f"BUY 1× {atm}CE  +  SELL 2× {atm_p50}CE",
        "Put Ratio Spread":
            f"BUY 1× {atm}PE  +  SELL 2× {atm_m50}PE",
        "Christmas Tree Spread":
            f"BUY {atm}PE  +  SELL {atm_m50}PE  +  SELL {atm_m150}PE  (step-down strikes)",
    }
    return recs.get(strategy_name, f"ATM: ₹{atm:,} | CE Wall: ₹{ce_wall:,} | PE Wall: ₹{pe_wall:,}")


def suggest_strategies(total_score, vol_view):
    if   total_score >= 3:  bias = "strong_bullish";  bias_label = "STRONGLY BULLISH"
    elif total_score >= 1:  bias = "mild_bullish";    bias_label = "MILDLY BULLISH"
    elif total_score <= -3: bias = "strong_bearish";  bias_label = "STRONGLY BEARISH"
    elif total_score <= -1: bias = "mild_bearish";    bias_label = "MILDLY BEARISH"
    else:                   bias = "neutral";          bias_label = "NEUTRAL / RANGE-BOUND"
    strats = []
    if   bias == "strong_bullish": strats.extend(BULLISH_STRONG)
    elif bias == "mild_bullish":   strats.extend(BULLISH_MILD)
    elif bias == "strong_bearish": strats.extend(BEARISH_STRONG)
    elif bias == "mild_bearish":   strats.extend(BEARISH_MILD)
    else:
        if   vol_view == "low":  strats.extend(NEUTRAL_LOW_VOL)
        elif vol_view == "high": strats.extend(VOLATILITY_LONG)
        else:                    strats.extend(NEUTRAL_NORMAL_VOL)
    if vol_view == "high" and bias != "neutral":
        strats.extend(VOLATILITY_LONG)
    strats.extend(ADVANCED_MISC)
    seen = set(); unique = []
    for s in strats:
        if s not in seen:
            seen.add(s); unique.append(s)
    return bias_label, unique

def build_strategy_checklist_html(html_data, vol_support=None, vol_resistance=None, global_bias=None, vol_view="normal", vix_val=None, vix_trend=None):
    d = html_data
    pcr_val = d.get('pcr') if d.get('has_option_data') else None
    rsi_val = d.get('rsi')
    macd_bull = d.get('macd_bullish')
    sma20 = d.get('sma_20_above'); sma50 = d.get('sma_50_above'); sma200 = d.get('sma_200_above')
    oi_cls = d.get('oi_class') if d.get('has_option_data') else None
    signals = [
        ("📊", "PCR (OI Ratio)",         *score_pcr(pcr_val),          True),
        ("📈", "RSI (14-Day)",            *score_rsi(rsi_val),           True),
        ("⚡", "MACD Signal",             *score_macd(macd_bull),        True),
        ("📉", "Market Trend (SMAs)",     *score_trend(sma20, sma50, sma200), True),
        ("🔄", "OI Direction",            *score_oi_direction(oi_cls),   True),
        ("🌐", "Global Market Bias",      *score_global(global_bias),    True),
        ("🌡️", "India VIX",              *score_vix(vix_val, vix_trend), True),

    ]
    auto_scores  = [s[2] for s in signals if s[5]]
    manual_scores = [s[2] for s in signals if not s[5]]
    total_score  = sum(auto_scores) + sum(manual_scores)
    bull_count = sum(1 for s in signals if s[2] > 0)
    bear_count = sum(1 for s in signals if s[2] < 0)
    neu_count  = sum(1 for s in signals if s[2] == 0 and s[3] != "N/A")
    na_count   = sum(1 for s in signals if s[3] == "N/A")
    bias_label, strategy_list = suggest_strategies(total_score, vol_view)
    max_possible = len(signals)
    circumference = 289.0
    if total_score >= 0:
        arc_pct = min(1.0, total_score / max(1, max_possible))
    else:
        arc_pct = min(1.0, abs(total_score) / max(1, max_possible))
    dashoffset = circumference * (1 - arc_pct)
    if   total_score >= 3:  ring_color = "#00e676"; bias_gradient = "linear-gradient(135deg,#00e676,#00bfa5)"
    elif total_score >= 1:  ring_color = "#69f0ae"; bias_gradient = "linear-gradient(135deg,#69f0ae,#00c853)"
    elif total_score <= -3: ring_color = "#ff5252"; bias_gradient = "linear-gradient(135deg,#ff5252,#b71c1c)"
    elif total_score <= -1: ring_color = "#ff8a65"; bias_gradient = "linear-gradient(135deg,#ff8a65,#e64a19)"
    else:                   ring_color = "#ffb74d"; bias_gradient = "linear-gradient(135deg,#ffcd3c,#f7931e)"
    score_sign = "+" if total_score > 0 else ""

    def sig_card(icon, name, score, display_val, msg, is_auto):
        if display_val == "N/A":
            tile_cls = "o5-tile o5-na"; chip_cls = "o5-chip o5-chip-na"; s_txt = "N/A"
            val_color = "color:rgba(176,190,197,0.3);"
            bar_style = "background:linear-gradient(90deg,transparent,rgba(176,190,197,0.15),transparent);"
        elif score > 0:
            tile_cls = "o5-tile o5-bull"; chip_cls = "o5-chip o5-chip-bull"; s_txt = f"+{score}"
            val_color = "color:#34d399;"
            bar_style = "background:linear-gradient(90deg,transparent,#10b981,transparent);"
        elif score < 0:
            tile_cls = "o5-tile o5-bear"; chip_cls = "o5-chip o5-chip-bear"; s_txt = str(score)
            val_color = "color:#f87171;"
            bar_style = "background:linear-gradient(90deg,transparent,#ef4444,transparent);"
        else:
            tile_cls = "o5-tile o5-neu"; chip_cls = "o5-chip o5-chip-neu"; s_txt = "0"
            val_color = "color:#fbbf24;"
            bar_style = "background:linear-gradient(90deg,transparent,#f59e0b,transparent);"
        auto_badge = '<span class="auto-badge">AUTO</span>' if is_auto else '<span class="manual-badge">MANUAL</span>'
        return f"""
        <div class="{tile_cls}">
            <div class="o5-tile-top">
                <span class="o5-tile-label">{name} {auto_badge}</span>
                <div class="{chip_cls}">{s_txt}</div>
            </div>
            <div class="o5-val" style="{val_color}">{display_val}</div>
            <div class="o5-msg">{msg}</div>
            <div class="o5-tile-bar" style="{bar_style}"></div>
        </div>"""

    sig_cards_html = "".join(sig_card(*s) for s in signals)

    tag_map = {
        "bullish":   ("strat-bull", "strat-tag-bull", "🟢 Bullish"),
        "bearish":   ("strat-bear", "strat-tag-bear", "🔴 Bearish"),
        "neutral":   ("strat-neu",  "strat-tag-neu",  "🟡 Neutral"),
        "volatility":("strat-vol",  "strat-tag-vol",  "🟣 Volatility"),
        "advanced":  ("strat-misc", "strat-tag-misc", "🔵 Advanced"),
    }
    # ── Strike data for recommendations ──────────────────────────────────
    atm_strike  = d.get('atm_strike', 0)
    ce_wall     = d.get('max_ce_oi', atm_strike + 200 if atm_strike else 0)
    pe_wall     = d.get('max_pe_oi', atm_strike - 200 if atm_strike else 0)
    has_strikes = atm_strike > 0

    # Base R:R from market analysis — needed before card loop
    rr_ratio = d.get('risk_reward_ratio', 0) or 0

    # Per-strategy INDEPENDENT R:R — based on each strategy's structural profit/loss profile
    # Uses: atm_strike, ce_wall (resistance), pe_wall (support), current_price
    # These are real structural R:Rs, NOT derived from market direction R:R
    def calc_strat_rr(strat_name, spot, atm, ce, pe, sl_pts, reward_pts_base):
        """
        Returns (rr_ratio, rr_note) for each strategy independently.
        sl_pts      = hard stop loss distance in points (from market analysis)
        reward_pts  = distance to target 1 (support/resistance)
        For spreads: max_profit = spread_width - net_debit (approx)
                     max_loss   = net_debit (approx half spread for even split)
        """
        spread = 200   # standard Nifty spread width (4 strikes × 50)
        half   = spread / 2   # approx net debit for ATM spread
        sl     = max(sl_pts, 50)        # never divide by zero
        rw     = max(reward_pts_base, 50)

        rr_map = {
            # Naked directional — full premium at risk, uncapped reward
            "Long Call":            round(rw / sl, 2),
            "Long Put":             round(rw / sl, 2),
            "Synthetic Long":       round(rw / sl, 2),
            "Synthetic Short":      round(rw / sl, 2),
            # Debit spreads — max loss = net debit (~half spread), max profit = spread - debit
            "Bull Call Spread":     round((spread - half) / half, 2),   # ~1.0 for equal width
            "Bear Put Spread":      round((spread - half) / half, 2),
            "Bull Put Spread":      round((spread - half) / half, 2),
            "Bear Call Spread":     round((spread - half) / half, 2),
            # Ladders — extra short strike adds premium but adds tail risk
            "Bull Call Ladder":     round((spread * 0.6) / (spread * 0.4), 2),
            "Bear Put Ladder":      round((spread * 0.6) / (spread * 0.4), 2),
            "Bull Put Ladder":      round((spread * 0.5) / (spread * 0.5), 2),
            "Bear Call Ladder":     round((spread * 0.5) / (spread * 0.5), 2),
            # Ratio backspreads — small loss in middle, big win at extremes
            "Call Ratio Backspread":  round((spread * 1.5) / (spread * 0.5), 2),
            "Put Ratio Backspread":   round((spread * 1.5) / (spread * 0.5), 2),
            # Strap/Strip — 2:1 long positions, pays on big move
            "Strap (Bullish Bias)": round((rw * 1.5) / (sl * 0.8), 2),
            "Strip (Bearish Bias)": round((rw * 1.5) / (sl * 0.8), 2),
            # Income strategies — limited credit, unlimited risk
            "Jade Lizard":          round((spread * 0.3) / (spread * 0.7), 2),
            "Reverse Jade Lizard":  round((spread * 0.3) / (spread * 0.7), 2),
            "The Wheel Strategy (CSP + Covered Call)": round((spread * 0.25) / (spread * 0.75), 2),
            # Neutral short premium — limited credit, large risk
            "Short Straddle":       round((half * 0.4) / (spread * 1.0), 2),
            "Short Strangle":       round((half * 0.35) / (spread * 1.2), 2),
            # Iron structures — defined on both sides
            "Iron Condor":          round((half * 0.5) / (half * 0.5), 2),
            "Iron Butterfly":       round((half * 0.6) / (half * 0.4), 2),
            "Condor Spread (Short)":round((half * 0.45) / (half * 0.55), 2),
            # Calendar/Diagonal — time value play
            "Calendar Spread":      round((half * 0.8) / (half * 0.6), 2),
            "Diagonal Spread":      round((half * 0.9) / (half * 0.6), 2),
            "Butterfly Spread (Short)": round((half * 0.4) / (half * 0.6), 2),
            # Long vol
            "Long Straddle":        round((rw * 1.2) / (half * 0.8), 2),
            "Long Strangle":        round((rw * 1.0) / (half * 0.7), 2),
            "Long Guts":            round((rw * 0.9) / (half * 0.9), 2),
            "Butterfly Spread (Long)": round((half * 1.2) / (half * 0.5), 2),
            # Advanced ratio
            "Call Ratio Spread":    round((spread * 0.8) / (spread * 0.5), 2),
            "Put Ratio Spread":     round((spread * 0.8) / (spread * 0.5), 2),
            "Christmas Tree Spread":round((spread * 0.7) / (spread * 0.45), 2),
        }
        return rr_map.get(strat_name, round(rw / sl, 2))

    # ── All variables needed by card loop must be defined HERE ───────────────
    current_price = d.get('current_price', 0)
    support       = d.get('support', 0)
    resistance    = d.get('resistance', 0)
    stop_loss_val = d.get('stop_loss', None)
    target_1_val  = d.get('target_1', resistance)
    target_2_val  = d.get('target_2', 0)
    expiry_date   = d.get('expiry', 'N/A')

    sl_pts_for_rr     = abs(int(current_price - stop_loss_val)) if stop_loss_val and current_price else int(current_price * 0.005) if current_price else 150
    reward_pts_for_rr = abs(int(target_1_val  - current_price)) if target_1_val  and current_price else 200
    sl_pts_for_rr     = max(sl_pts_for_rr,     100)
    reward_pts_for_rr = max(reward_pts_for_rr, 150)

    strat_cards_html = ""
    strat_data_js = {}  # for JS lookup

    _border_grad = {
        "bullish":    "linear-gradient(180deg,#00e676,#00796b)",
        "bearish":    "linear-gradient(180deg,#ff5252,#b71c1c)",
        "neutral":    "linear-gradient(180deg,#ffb74d,#e65100)",
        "volatility": "linear-gradient(180deg,#b388ff,#6200ea)",
        "advanced":   "linear-gradient(180deg,#4fc3f7,#0277bd)",
    }
    _rb_cls = {"PRIMARY":"sc-rb-primary","SECONDARY":"sc-rb-secondary","ADVANCED":"sc-rb-advanced"}
    _type_info = {
        "bullish":    ("Debit / Credit", "Directional"),
        "bearish":    ("Debit / Credit", "Directional"),
        "neutral":    ("Premium Sell",   "Range-bound"),
        "volatility": ("Debit",          "Vol Breakout"),
        "advanced":   ("Multi-leg",      "Experienced"),
    }

    for i, s in enumerate(strategy_list, 1):
        stype      = STRAT_TYPE_MAP.get(s, "advanced")
        _, tag_cls, tag_txt = tag_map.get(stype, tag_map["advanced"])
        rank       = "PRIMARY" if i <= 4 else ("SECONDARY" if i <= 8 else "ADVANCED")
        strike_rec = get_strike_suggestion(s, atm_strike, ce_wall, pe_wall) if has_strikes else "Strike data unavailable"
        safe_name  = s.replace('"', '&quot;').replace("'", "\\'")
        strat_rr   = calc_strat_rr(s, current_price, atm_strike, ce_wall, pe_wall, sl_pts_for_rr, reward_pts_for_rr)
        strat_data_js[s] = {"strike": strike_rec, "type": stype, "rank": rank, "rr": strat_rr}

        bar_grad = _border_grad.get(stype, _border_grad["advanced"])
        if   strat_rr >= 2: rr_col, rr_lbl = "#00e676", "&#10003; Good"
        elif strat_rr >= 1: rr_col, rr_lbl = "#ffb74d", "&#9888; Acceptable"
        else:               rr_col, rr_lbl = "#ff5252", "&#10005; Poor"
        rb_cls   = _rb_cls.get(rank, "sc-rb-advanced")
        rr_bar_w = min(95, int(strat_rr / 3.0 * 100))
        tl, ts   = _type_info.get(stype, ("Multi-leg", "Complex"))
        panel_id = f"sc-dp-{i}"

        strat_cards_html += f"""
        <div class="sc-row" data-type="{stype}" data-strat="{safe_name}" onclick="scToggle(this,'{panel_id}')">
            <div class="sc-row-bar" style="background:{bar_grad};"></div>
            <div class="sc-row-num">{i:02d}</div>
            <div class="sc-row-body">
                <div class="sc-row-name">{s}</div>
                <div class="sc-row-strike">&#127919; <span>{strike_rec}</span></div>
            </div>
            <div class="sc-row-meta">
                <span class="sc-row-tag {tag_cls}">{tag_txt}</span>
                <span class="sc-rb {rb_cls}">{rank}</span>
                <span class="sc-row-rr" style="color:{rr_col};">R:R {strat_rr:.2f}</span>
            </div>
            <div class="sc-row-chevron" id="chev-{panel_id}">&#8250;</div>
        </div>
        <div class="sc-dp" id="{panel_id}">
            <div class="sc-dp-grid">
                <div class="sc-dp-box">
                    <div class="sc-dp-lbl">STRATEGY TYPE</div>
                    <div class="sc-dp-val" style="color:{rr_col};">{tl}</div>
                    <div class="sc-dp-sub">{ts}</div>
                </div>
                <div class="sc-dp-box">
                    <div class="sc-dp-lbl">RISK : REWARD</div>
                    <div class="sc-dp-val" style="color:{rr_col};">1 : {strat_rr:.2f}</div>
                    <div class="sc-dp-sub">{rr_lbl}</div>
                    <div class="sc-dp-rr-track"><div class="sc-dp-rr-fill" style="width:{rr_bar_w}%;background:{bar_grad};"></div></div>
                </div>
                <div class="sc-dp-box">
                    <div class="sc-dp-lbl">RANK</div>
                    <div class="sc-dp-val" style="color:#80deea;">{rank}</div>
                    <div class="sc-dp-sub">#{i:02d} of {len(strategy_list)}</div>
                </div>
            </div>
            <div class="sc-dp-strike-box">
                <span class="sc-dp-strike-lbl">&#127919; Strike Rec:</span> {strike_rec}
            </div>
            <div class="sc-dp-actions">
                <button class="sc-dp-btn sc-dp-btn-close" onclick="scClose('{panel_id}',event)">&#10005; Close</button>
                <button class="sc-dp-btn sc-dp-btn-load" onclick="scLoadPlan('{safe_name}',event)">&#128203; Load Trade Plan &#8599;</button>
            </div>
        </div>"""

    # Build JS strategy data map
    import json as _json
    strat_js_map = _json.dumps(strat_data_js, ensure_ascii=False)

    timestamp = d.get('timestamp', 'N/A')
    na_span     = '<span class="na-inline">N/A</span>'
    na_pill     = f'<span class="sc-pill sc-pill-na">— N/A: {na_count}</span>' if na_count > 0 else ''
    score_note  = ("Strong directional conviction — proceed with caution and stop losses."
                   if abs(total_score) >= 3 else
                   "Moderate signal — size positions conservatively."
                   if abs(total_score) >= 1 else
                   "Mixed signals — range-bound or sideways strategies preferred.")
    strat_count = len(strategy_list)

    # ── Trade Plan auto-values (already defined above for card loop) ─────────

    if stop_loss_val:
        sl_display = f"&#8377;{int(stop_loss_val):,}"
        sl_pts     = abs(int(current_price - stop_loss_val))
    else:
        sl_pts     = int(current_price * 0.005) if current_price else 50
        sl_display = f"~&#8377;{int(current_price - sl_pts):,} (0.5% below spot)"

    if target_1_val:
        tgt1_display = f"&#8377;{int(target_1_val):,}"
        reward_pts   = abs(int(target_1_val - current_price))
    else:
        tgt1_display = "N/A"
        reward_pts   = 0

    tgt2_display = f"&#8377;{int(target_2_val):,}" if target_2_val else "N/A (CE/PE wall)"
    primary_strat        = strategy_list[0] if strategy_list else "N/A"
    primary_strike_rec   = get_strike_suggestion(primary_strat, atm_strike, ce_wall, pe_wall) if has_strikes and strategy_list else "N/A"

    html_parts = []
    html_parts.append(f"""
    <div class="tab-panel" id="tab-checklist">
        <div class="section">
            <div class="o5-wrap">
                <div class="o5-top-banner">
                    <div class="o5-banner-left">
                        <div class="o5-score-circle" style="border-color:{ring_color};box-shadow:0 0 20px {ring_color}44,inset 0 0 16px {ring_color}11;">
                            <div class="o5-score-num" style="color:{ring_color};">{score_sign}{total_score}</div>
                            <div class="o5-score-lbl">SCORE</div>
                        </div>
                        <div>
                            <div class="o5-verdict" style="color:{ring_color};text-shadow:0 0 20px {ring_color}66;">{bias_label}</div>
                            <div class="o5-sub">Score {score_sign}{total_score} from {len(signals)} signals ({na_count} skipped as N/A). {score_note}</div>
                        </div>
                    </div>
                    <div class="o5-pills">
                        <span class="sc-pill sc-pill-bull">&#10003; BULL: {bull_count}</span>
                        <span class="sc-pill sc-pill-bear">&#10007; BEAR: {bear_count}</span>
                        <span class="sc-pill sc-pill-neu">&#9633; NEUTRAL: {neu_count}</span>
                        {na_pill}
                    </div>
                </div>
                <div class="o5-grid">{sig_cards_html}</div>
            </div>
        </div>
        <div class="section">
            <div class="section-title">
                <span>&#127919;</span> SUGGESTED STRATEGY TYPES
                <span style="font-size:10px;color:rgba(176,190,197,0.4);font-weight:400;letter-spacing:1px;">
                    For study &amp; backtesting only &mdash; NOT financial advice
                </span>
            </div>
            <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:16px;">
                <div style="font-size:13px;color:rgba(176,190,197,0.7);">
                    IV View: <strong style="color:{ring_color};">{vol_view.upper()}</strong>
                    &nbsp;&middot;&nbsp; Bias: <strong style="color:{ring_color};">{bias_label}</strong>
                    &nbsp;&middot;&nbsp; <span style="color:rgba(128,222,234,0.7);">{strat_count} strategies found</span>
                </div>
                <div style="display:flex;gap:8px;flex-wrap:wrap;">
                    <button class="filter-btn active" onclick="filterStrats('all',this)">All</button>
                    <button class="filter-btn" onclick="filterStrats('bullish',this)">&#128994; Bullish</button>
                    <button class="filter-btn" onclick="filterStrats('bearish',this)">&#128308; Bearish</button>
                    <button class="filter-btn" onclick="filterStrats('neutral',this)">&#128993; Neutral</button>
                    <button class="filter-btn" onclick="filterStrats('volatility',this)">&#128995; Volatility</button>
                    <button class="filter-btn" onclick="filterStrats('advanced',this)">&#128309; Advanced</button>
                </div>
            </div>
            <!-- compact strategy summary strip -->
            <div class="sc-summary-strip">
                <div class="sc-ss-item">
                    <span class="sc-ss-dot" style="background:#00e5ff;box-shadow:0 0 5px #00e5ff;"></span>
                    <span class="sc-ss-lbl">PRIMARY</span>
                    <span class="sc-ss-val" style="color:#00e5ff;">{min(4, strat_count)}</span>
                </div>
                <div class="sc-ss-sep"></div>
                <div class="sc-ss-item">
                    <span class="sc-ss-dot" style="background:#ffb74d;"></span>
                    <span class="sc-ss-lbl">SECONDARY</span>
                    <span class="sc-ss-val" style="color:#ffb74d;">{max(0, min(4, strat_count - 4))}</span>
                </div>
                <div class="sc-ss-sep"></div>
                <div class="sc-ss-item">
                    <span class="sc-ss-dot" style="background:#b388ff;"></span>
                    <span class="sc-ss-lbl">ADVANCED</span>
                    <span class="sc-ss-val" style="color:#b388ff;">{max(0, strat_count - 8)}</span>
                </div>
                <div class="sc-ss-sep"></div>
                <div style="margin-left:auto;font-family:'JetBrains Mono',monospace;font-size:11px;color:rgba(128,222,234,0.65);">
                    ATM: &#8377;{atm_strike:,} &nbsp;&middot;&nbsp; CE Wall: &#8377;{ce_wall:,} &nbsp;&middot;&nbsp; PE Wall: &#8377;{pe_wall:,}
                </div>
            </div>
            <div class="sc-compact-grid" id="stratGrid">{strat_cards_html}</div>
        </div>
        <!-- ══════════════ TRADE PLAN SECTION ══════════════ -->
        <script id="stratDataMap" type="application/json">{strat_js_map}</script>
        <div class="section">
            <div class="section-title"><span>&#128203;</span> TRADE PLAN — AUTO FILLED
                <span style="font-size:10px;color:rgba(176,190,197,0.4);font-weight:400;letter-spacing:1px;margin-left:auto;">
                    Click any strategy card above to update this plan
                </span>
            </div>
            <div class="tp-wrap">

                <!-- Row 1: Primary strategy banner -->
                <div class="tp-banner" id="tp-banner">
                    <div class="tp-banner-left">
                        <div class="tp-banner-label">SELECTED STRATEGY <span id="tp-rank-badge" class="tp-rank-badge">PRIMARY</span></div>
                        <div class="tp-banner-strat" id="tp-strat-name">{primary_strat}</div>
                        <div class="tp-banner-strike" id="tp-strike-rec">&#127919; {primary_strike_rec}</div>
                    </div>
                    <div class="tp-banner-right">
                        <div class="tp-banner-label">EXPIRY</div>
                        <div class="tp-banner-exp">{expiry_date}</div>
                    </div>
                </div>

                <!-- Row 2: The 3 exit conditions -->
                <div class="tp-exits">
                    <div class="tp-exit tp-exit-profit">
                        <div class="tp-exit-icon">&#9989;</div>
                        <div class="tp-exit-title">PROFIT EXIT</div>
                        <div class="tp-exit-val">{tgt1_display}</div>
                        <div class="tp-exit-sub">Target 1 · {reward_pts} pts from spot</div>
                        <div class="tp-exit-val2">{tgt2_display}</div>
                        <div class="tp-exit-sub">Target 2 (CE/PE wall)</div>
                        <div class="tp-exit-rule">&#128161; Take 50–60% profits at Target 1. Let the rest run to Target 2.</div>
                    </div>
                    <div class="tp-exit tp-exit-loss">
                        <div class="tp-exit-icon">&#10060;</div>
                        <div class="tp-exit-title">STOP LOSS EXIT</div>
                        <div class="tp-exit-val">{sl_display}</div>
                        <div class="tp-exit-sub">Hard stop · {sl_pts} pts from spot</div>
                        <div class="tp-exit-rule">&#128161; Exit immediately when hit — no averaging down. Max 2% of capital at risk per trade.</div>
                    </div>
                    <div class="tp-exit tp-exit-time">
                        <div class="tp-exit-icon">&#9200;</div>
                        <div class="tp-exit-title">TIME EXIT</div>
                        <div class="tp-exit-val">40% DTE Rule</div>
                        <div class="tp-exit-sub">Exit if target not reached by 40% of expiry elapsed</div>
                        <div class="tp-exit-rule">&#128161; Theta decay accelerates after 40% DTE. A stalled trade is a losing trade — exit and preserve capital.</div>
                    </div>
                </div>

            </div>
        </div>
        <!-- ══════════════ END TRADE PLAN ══════════════ -->

        <div class="section">
            <div class="section-title"><span>&#128218;</span> SCORING LEGEND</div>
            <div class="logic-box" style="margin-top:0;">
                <div class="logic-box-head">HOW THE SCORE WORKS</div>
                <div class="logic-grid">
                    <div class="logic-item"><span class="lc-bull">+1</span> Signal is bullish &mdash; adds to bull case</div>
                    <div class="logic-item"><span class="lc-bear">&minus;1</span> Signal is bearish &mdash; adds to bear case</div>
                    <div class="logic-item"><span class="lc-side">0</span> Neutral signal &mdash; no directional contribution</div>
                    <div class="logic-item"><span class="lc-info">N/A</span> Data not available &mdash; excluded from score</div>
                    <div class="logic-item"><span class="lc-bull">&ge; +3</span> Strongly Bullish &middot; <span class="lc-bull">+1/+2</span> Mildly Bullish</div>
                    <div class="logic-item"><span class="lc-bear">&le; &minus;3</span> Strongly Bearish &middot; <span class="lc-bear">&minus;1/&minus;2</span> Mildly Bearish</div>
                    <div class="logic-item"><span class="lc-info">AUTO</span> Filled from live NSE + yfinance data</div>
                    <div class="logic-item"><span class="lc-side">MANUAL</span> Requires your input &mdash; shown as N/A if not set</div>
                </div>
            </div>
        </div>
        <div class="section">
            <div class="disclaimer">
                <span class="disc-icon">⚠️</span>
                <span class="disc-label">Disclaimer</span>
                <span class="disc-sep">|</span>
                <span class="disc-text">This checklist is for <strong>EDUCATIONAL purposes only</strong> &mdash; NOT financial advice.</span>
                <span class="disc-sep">|</span>
                <span class="disc-text">Strategy suggestions are rules-based &amp; have not been backtested.</span>
                <span class="disc-sep">|</span>
                <span class="disc-text">Always validate with your own analysis &amp; consult a SEBI-registered advisor.</span>
            </div>
        </div>
    </div>
""")
    return "".join(html_parts)


# ═══════════════════════════════════════════════════════════════════════════════
#  INTRADAY OI TREND — OI LOG HELPER
# ═══════════════════════════════════════════════════════════════════════════════

def log_oi_snapshot(option_analysis, technical, key_levels=None):
    if not option_analysis or not technical:
        print("  ⚠️  OI snapshot skipped — missing option_analysis or technical data")
        return

    ist_tz  = pytz.timezone('Asia/Kolkata')
    ist_now = datetime.now(ist_tz)

    # ── Market hours gate: only log between 09:00 and 15:30 IST ──
    market_open  = ist_now.replace(hour=9,  minute=0,  second=0, microsecond=0)
    market_close = ist_now.replace(hour=15, minute=30, second=0, microsecond=0)
    if not (market_open <= ist_now <= market_close):
        print(f"  ⏸️  OI snapshot skipped — outside market hours ({ist_now.strftime('%H:%M IST')})")
        return

    ce_chg  = option_analysis.get('total_ce_oi_change', 0)
    pe_chg  = option_analysis.get('total_pe_oi_change', 0)
    diff    = pe_chg - ce_chg
    pcr     = round(option_analysis.get('pcr_oi', 0), 2)
    spot    = round(float(technical.get('current_price', 0)), 2)

    # ── VWAP calculation (moved up — needed for signal logic below) ──
    # ^NSEI is an index with zero volume → VWAP always equals spot (wrong).
    # NIFTYBEES.NS is the Nifty ETF trading at ~Nifty/100 with real volume.
    # Multiply its VWAP by 100 to get Nifty-equivalent VWAP.
    vwap = spot
    try:
        import yfinance as _yf
        df_1m = _yf.Ticker("NIFTYBEES.NS").history(interval="1m", period="1d")
        if not df_1m.empty:
            df_1m = df_1m.dropna(subset=['Close','Volume'])
            df_1m = df_1m[df_1m['Volume'] > 0]
            if len(df_1m) >= 5:
                tp  = (df_1m['High'] + df_1m['Low'] + df_1m['Close']) / 3
                cum_tpv = (tp * df_1m['Volume']).cumsum()
                cum_vol = df_1m['Volume'].cumsum()
                vwap_series = cum_tpv / cum_vol
                last_vwap = vwap_series.iloc[-1]
                if not pd.isna(last_vwap) and last_vwap > 0:
                    vwap = round(float(last_vwap) * 100, 2)   # scale ETF → Nifty
                    print(f"  ✅ VWAP (NIFTYBEES×100): {vwap}")
                else:
                    print(f"  ⚠️  VWAP: series NaN — fallback to spot")
            else:
                print(f"  ⚠️  VWAP: insufficient 1m bars ({len(df_1m)}) — fallback to spot")
        else:
            print(f"  ⚠️  VWAP: empty dataframe — fallback to spot")
    except Exception as e:
        print(f"  ⚠️  VWAP calc failed: {e} — using spot as VWAP")

    spot_above_vwap = spot >= vwap

    # ── OI Signal Logic: Step 1 — direction, Step 2 — ratio, Step 3 — PCR+VWAP tiebreaker ──
    # Step 1: CE and PE moving in OPPOSITE directions → clear signal
    if   ce_chg > 0 and pe_chg < 0:
        # Calls building + Puts unwinding = true bearish
        opt_signal = "STRONG SELL"
    elif ce_chg < 0 and pe_chg > 0:
        # Calls unwinding + Puts building = true bullish
        opt_signal = "STRONG BUY"

    # Step 2: Both building → check if one side clearly dominates (1.5× ratio)
    elif ce_chg > 0 and pe_chg > 0:
        if   pe_chg > ce_chg * 1.5:
            opt_signal = "BUY"           # Put build clearly dominant
        elif ce_chg > pe_chg * 1.5:
            opt_signal = "SELL"          # Call build clearly dominant
        else:
            # Step 3: Neither dominates → use PCR + VWAP as tiebreaker
            # PCR > 1.8 (panic zone): VWAP decides — if spot below VWAP,
            #   floor has broken and retail fear is valid → SELL
            # PCR 1.2–1.8 (normal institutional put writing): bullish only
            #   if price is respecting that floor (spot above VWAP)
            # PCR 0.8–1.2: neutral regardless
            # PCR < 0.8: bearish only if price confirms (spot below VWAP)
            if pcr > 1.8:
                opt_signal = "SELL"      if not spot_above_vwap else "BUY"
            elif pcr > 1.2:
                opt_signal = "BUY"       if spot_above_vwap     else "NEUTRAL"
            elif pcr < 0.8:
                opt_signal = "SELL"      if not spot_above_vwap else "NEUTRAL"
            else:
                opt_signal = "NEUTRAL"   # PCR 0.8–1.2: truly ambiguous

    # Step 4: Both unwinding → no conviction either way
    elif ce_chg < 0 and pe_chg < 0:
        opt_signal = "NEUTRAL"

    else:
        opt_signal = "NEUTRAL"

    fut_price = round(spot - 25, 2)
    try:
        import yfinance as _yf
        gift = _yf.Ticker("^NSEMDCP50")
        gift_hist = gift.history(period="1d", interval="1m")
        if not gift_hist.empty:
            fut_price = round(float(gift_hist['Close'].iloc[-1]), 2)
    except Exception as e:
        print(f"  ⚠️  Futures price fetch failed: {e} — using spot - 25 as proxy")

    vwap_signal = "BUY" if spot_above_vwap else "SELL"

    # ── Nifty 50 % move from previous day close ──
    nifty_move_pct = None
    try:
        import yfinance as _yf
        df_nsei = _yf.Ticker("^NSEI").history(period="5d", interval="1d")
        if df_nsei is not None and len(df_nsei) >= 2:
            prev_close_day = float(df_nsei['Close'].iloc[-2])
            if prev_close_day > 0:
                nifty_move_pct = round((spot - prev_close_day) / prev_close_day * 100, 2)
                print(f"  ✅ Nifty Move %: {nifty_move_pct:+.2f}% (Spot={spot}, Prev Close={prev_close_day})")
    except Exception as e:
        print(f"  ⚠️  Nifty move % calc failed: {e}")

    # ── Nearest level & distance based on signal direction ──
    # SELL: target is S1 if spot > S1 (not yet reached), else switch to S2 (already broke S1)
    # BUY:  target is R1 if spot < R1 (not yet reached), else switch to R2 (already broke R1)
    # Distance is always stored as a POSITIVE number (how far to next target)
    nearest_level = None
    distance_pts  = None
    nearest_label = None
    if key_levels:
        if opt_signal in ("SELL", "STRONG SELL"):
            s1 = key_levels.get("support")
            s2 = key_levels.get("strong_support")
            if s1 is not None and spot > s1:
                # Spot still above S1 — S1 is the next downside target
                nearest_level = s1
                nearest_label = "S1"
                distance_pts  = round(spot - s1, 1)          # positive: how far to fall
            elif s2 is not None:
                # Spot has crossed/touched S1 — next target is S2
                nearest_level = s2
                nearest_label = "S2"
                distance_pts  = round(max(spot - s2, 0), 1)  # positive: how far to S2
            elif s1 is not None:
                # No S2 available, fallback to S1
                nearest_level = s1
                nearest_label = "S1"
                distance_pts  = round(abs(spot - s1), 1)

        elif opt_signal in ("BUY", "STRONG BUY"):
            r1 = key_levels.get("resistance")
            r2 = key_levels.get("strong_resistance")
            if r1 is not None and spot < r1:
                # Spot still below R1 — R1 is the next upside target
                nearest_level = r1
                nearest_label = "R1"
                distance_pts  = round(r1 - spot, 1)          # positive: how far to rise
            elif r2 is not None:
                # Spot has crossed/touched R1 — next target is R2
                nearest_level = r2
                nearest_label = "R2"
                distance_pts  = round(max(r2 - spot, 0), 1)  # positive: how far to R2
            elif r1 is not None:
                # No R2 available, fallback to R1
                nearest_level = r1
                nearest_label = "R1"
                distance_pts  = round(abs(r1 - spot), 1)

    # ── RSI 14-period + EMA 5/13 on 15-min candles ────────────────────────
    # Single yfinance fetch shared by both indicators — no double API call.
    rsi_15m    = None
    ema_signal = None   # "BUY" | "SELL"
    ema5_val   = None
    ema13_val  = None
    try:
        import yfinance as _yf
        df_15 = _yf.Ticker("^NSEI").history(period="5d", interval="15m")
        if df_15 is not None and len(df_15) >= 20:
            close = df_15['Close'].dropna()
            # ── RSI 14 ──────────────────────────────────────────────────
            delta  = close.diff()
            gain   = delta.where(delta > 0, 0.0).rolling(14).mean()
            loss   = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
            rs     = gain / loss.replace(0, float('inf'))
            rsi_s  = 100 - (100 / (1 + rs))
            rsi_15m = round(float(rsi_s.iloc[-1]), 1) if not pd.isna(rsi_s.iloc[-1]) else None
            # ── EMA 5 / 13 ──────────────────────────────────────────────
            ema5  = close.ewm(span=5,  adjust=False).mean()
            ema13 = close.ewm(span=13, adjust=False).mean()
            ema5_val  = round(float(ema5.iloc[-1]),  2) if not pd.isna(ema5.iloc[-1])  else None
            ema13_val = round(float(ema13.iloc[-1]), 2) if not pd.isna(ema13.iloc[-1]) else None
            if ema5_val and ema13_val:
                ema_signal = "BUY" if ema5_val > ema13_val else "SELL"
            print(f"  ✅ RSI 15m: {rsi_15m} | EMA5: {ema5_val} EMA13: {ema13_val} → {ema_signal}")
        else:
            print(f"  ⚠️  RSI/EMA: insufficient 15m bars ({len(df_15) if df_15 is not None else 0})")
    except Exception as e:
        print(f"  ⚠️  RSI/EMA 15m calc failed: {e}")

    snapshot = {
        "time":          ist_now.strftime("%H:%M"),
        "timestamp":     ist_now.strftime("%d-%b-%Y %H:%M IST"),
        "call_oi_chg":   ce_chg,
        "put_oi_chg":    pe_chg,
        "diff":          diff,
        "pcr":           pcr,
        "opt_signal":    opt_signal,
        "vwap":          vwap,
        "fut_price":     fut_price,
        "spot_price":    spot,
        "vwap_signal":   vwap_signal,
        "nifty_move_pct": nifty_move_pct,
        "nearest_level": nearest_level,
        "nearest_label": nearest_label,
        "distance_pts":  distance_pts,
        "rsi_15m":       rsi_15m,
        "ema_signal":    ema_signal,
        "ema5":          ema5_val,
        "ema13":         ema13_val,
    }

    log_file = "oi_log.json"
    entries  = []

    if os.path.exists(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                entries = json.load(f)
            if not isinstance(entries, list):
                entries = []
        except Exception as e:
            print(f"  ⚠️  Could not read existing oi_log.json: {e} — starting fresh")
            entries = []
    else:
        print("  📭 oi_log.json not found — starting fresh log for today")

    # ── Daily reset: clear previous day entries on every trading day run ──
    today_str  = ist_now.strftime('%d-%b-%Y')
    is_weekday = ist_now.weekday() < 5  # Mon=0 to Fri=4
    is_holiday = today_str in NSE_FO_HOLIDAYS
    is_trading_day = is_weekday and not is_holiday

    if not is_trading_day:
        # Weekend or holiday — preserve last session data, skip new snapshot
        print(f"  ⏸️  Not a trading day ({today_str}) — preserving last session data, skipping snapshot")
        return

    # It IS a trading day — always purge any non-today entries before appending
    if entries:
        before_count = len(entries)
        entries = [
            e for e in entries
            if e.get('timestamp', '').startswith(today_str)
        ]
        removed = before_count - len(entries)
        if removed > 0:
            print(f"  🔄 Purged {removed} old entries — keeping only today: {today_str}")
        else:
            print(f"  ✅ Log already clean — all entries are from today: {today_str}")

    entries.insert(0, snapshot)
    entries = entries[:200]

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    print(f"  📊 OI snapshot logged → {ist_now.strftime('%H:%M IST')} | "
          f"CE Δ={ce_chg:+,} | PE Δ={pe_chg:+,} | Diff={diff:+,} | "
          f"PCR={pcr:.2f} | Signal={opt_signal} | Spot={spot} | "
          f"Move%={nifty_move_pct:+.2f}% | Total entries={len(entries)}"
          if nifty_move_pct is not None else
          f"  📊 OI snapshot logged → {ist_now.strftime('%H:%M IST')} | "
          f"CE Δ={ce_chg:+,} | PE Δ={pe_chg:+,} | Diff={diff:+,} | "
          f"PCR={pcr:.2f} | Signal={opt_signal} | Spot={spot} | "
          f"Move%=N/A | Total entries={len(entries)}")


def build_intraday_oi_tab_html():
    return """
    <!-- TAB: INTRADAY OI TREND -->
    <div class="tab-panel" id="tab-oi-trend">
      <div class="section">
        <div class="section-title">
          <span>&#128202;</span> INTRADAY OI TREND
          <span class="annot-badge">AUTO-LOGGED EVERY RUN &middot; IST</span>
          <span style="font-size:10px;color:rgba(128,222,234,0.35);font-weight:400;margin-left:auto;">
            Source: <code style="color:#4fc3f7;font-family:'JetBrains Mono',monospace;">oi_log.json</code>
          </span>
        </div>
        <div class="oi-controls">
          <div class="oi-interval-btns">
            <button class="oi-int-btn active" id="btn3" onclick="setOIInterval(3,this)">3 Min</button>
            <button class="oi-int-btn" id="btn5" onclick="setOIInterval(5,this)">5 Min</button>
            <button class="oi-int-btn" id="btn15" onclick="setOIInterval(15,this)">15 Min</button>
          </div>
          <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
            <div class="oi-live-badge"><span class="oi-live-dot"></span> LIVE &middot; IST &middot; Auto-refresh 30s</div>
            <div id="oiLastFetch" style="font-family:'JetBrains Mono',monospace;font-size:9px;color:rgba(128,222,234,0.8);letter-spacing:1px;">Last fetch: —</div>
          </div>
        </div>
        <div class="oi-summary-strip">
          <div class="oi-sum-card">
            <div class="oi-sum-label">Latest PCR</div>
            <div class="oi-sum-val oi-pcr-val" id="oiLatestPCR">—</div>
          </div>
          <div class="oi-sum-card">
            <div class="oi-sum-label">Net OI Diff</div>
            <div class="oi-sum-val" id="oiLatestDiff">—</div>
          </div>
          <div class="oi-sum-card">
            <div class="oi-sum-label">Spot Price</div>
            <div class="oi-sum-val oi-spot-cell" id="oiLatestSpot">—</div>
          </div>
          <div class="oi-sum-card">
            <div class="oi-sum-label">OI Signal</div>
            <div class="oi-sum-val" id="oiLatestSignal">—</div>
          </div>
        </div>
        <!-- OI Stat Boxes -->
        <div class="oi-stat-strip">
          <div class="oi-stat-box">
            <div class="oi-stat-label">LATEST DIFF</div>
            <div class="oi-stat-val" id="oiStatLatest">—</div>
            <div class="oi-stat-sub">PE &#916; &#8722; CE &#916;</div>
          </div>
          <div class="oi-stat-box">
            <div class="oi-stat-label">SESSION HIGH</div>
            <div class="oi-stat-val oi-stat-pos" id="oiStatHigh">—</div>
            <div class="oi-stat-sub">Most bullish</div>
          </div>
          <div class="oi-stat-box">
            <div class="oi-stat-label">SESSION LOW</div>
            <div class="oi-stat-val oi-stat-neg" id="oiStatLow">—</div>
            <div class="oi-stat-sub">Most bearish</div>
          </div>
          <div class="oi-stat-box">
            <div class="oi-stat-label">TREND SIGNAL</div>
            <div class="oi-stat-val" id="oiStatSignal">—</div>
            <div class="oi-stat-sub" id="oiStatSignalSub">Calculating...</div>
          </div>
        </div>

        <!-- Signal History Bar -->
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
          <span style="font-size:8px;letter-spacing:2px;color:rgba(128,222,234,0.9);text-transform:uppercase;white-space:nowrap;font-family:'JetBrains Mono',monospace;">SIGNAL HISTORY</span>
          <div id="oiSignalBar" style="flex:1;display:flex;gap:3px;height:6px;border-radius:4px;overflow:hidden;"></div>
        </div>

        <div class="oi-chart-wrap">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
            <div class="oi-chart-label">NET OI DIFF (PE &#916; &#8722; CE &#916;) &mdash; INTRADAY SPARKLINE</div>
            <div id="oiChartEntries" style="font-family:'JetBrains Mono',monospace;font-size:9px;color:rgba(128,222,234,0.8);letter-spacing:1px;"></div>
          </div>
          <!-- Chart: Y-labels + Canvas + Crosshair + Tooltip -->
          <div style="display:flex;gap:0;position:relative;">
            <div id="oiYLabels" style="width:58px;display:flex;flex-direction:column;justify-content:space-between;padding:4px 0;pointer-events:none;flex-shrink:0;"></div>
            <div style="flex:1;position:relative;min-width:0;">
              <canvas id="oiSparklineCanvas" style="width:100%;height:200px;display:block;"></canvas>
              <div id="oiCrosshair" style="position:absolute;top:0;bottom:0;width:1px;background:rgba(79,195,247,0.3);pointer-events:none;display:none;z-index:10;"></div>
              <div id="oiChartTooltip" style="position:absolute;pointer-events:none;background:rgba(6,13,20,0.97);border:1px solid rgba(79,195,247,0.35);border-radius:8px;padding:9px 13px;font-family:'JetBrains Mono',monospace;font-size:11px;color:#e0f7fa;display:none;z-index:20;white-space:nowrap;box-shadow:0 8px 24px rgba(0,0,0,0.6);min-width:160px;">
                <div id="oiTTTime" style="font-size:9px;color:rgba(128,222,234,0.45);letter-spacing:1px;margin-bottom:5px;"></div>
                <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:2px;"><span style="color:rgba(176,190,197,0.5);">NET DIFF</span><span id="oiTTDiff" style="font-weight:700;"></span></div>
                <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:2px;"><span style="color:rgba(176,190,197,0.5);">CE &#916;</span><span id="oiTTCE" style="font-weight:700;color:#f87171;"></span></div>
                <div style="display:flex;justify-content:space-between;gap:16px;margin-bottom:2px;"><span style="color:rgba(176,190,197,0.5);">PE &#916;</span><span id="oiTTPE" style="font-weight:700;color:#34d399;"></span></div>
                <div style="display:flex;justify-content:space-between;gap:16px;"><span style="color:rgba(176,190,197,0.5);">SIGNAL</span><span id="oiTTSignal" style="font-weight:700;"></span></div>
              </div>
            </div>
          </div>
          <!-- X-axis time labels -->
          <div id="oiXLabels" style="display:flex;justify-content:space-between;padding:4px 0 0 60px;"></div>
          <!-- Legend -->
          <div style="display:flex;gap:20px;justify-content:center;flex-wrap:wrap;margin-top:10px;padding-top:10px;border-top:1px solid rgba(79,195,247,0.08);">
            <div style="display:flex;align-items:center;gap:7px;font-size:10px;color:rgba(176,190,197,0.45);">
              <span style="display:inline-block;width:24px;height:2px;background:linear-gradient(90deg,#10b981,#34d399);border-radius:1px;"></span> Bullish Zone
            </div>
            <div style="display:flex;align-items:center;gap:7px;font-size:10px;color:rgba(176,190,197,0.45);">
              <span style="display:inline-block;width:24px;height:2px;background:linear-gradient(90deg,#ef4444,#f97316);border-radius:1px;"></span> Bearish Zone
            </div>
            <div style="display:flex;align-items:center;gap:7px;font-size:10px;color:rgba(176,190,197,0.45);">
              <span style="display:inline-block;width:24px;height:2px;border-top:1px dashed rgba(79,195,247,0.5);"></span> Zero Line
            </div>
          </div>
        </div>
        <div class="oi-table-wrap">
          <!-- FOCUS / DETAIL toggle -->
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:2px;color:rgba(128,222,234,0.4);text-transform:uppercase;">VIEW</span>
            <button id="btnFocus" onclick="setOIView('focus')" class="oi-view-btn oi-view-active">⚡ FOCUS</button>
            <button id="btnDetail" onclick="setOIView('detail')" class="oi-view-btn">📊 DETAIL</button>
          </div>
          <div class="oi-table-scroll-hint">&#8596; Scroll to see all columns</div>
          <table class="oi-table">
            <thead>
              <tr>
                <th style="text-align:left;">TIME (IST)</th>
                <th class="col-detail">CALL OI &#916;</th>
                <th class="col-detail">PUT OI &#916;</th>
                <th class="col-detail">DIFF</th>
                <th>PCR</th>
                <th>OPTION SIGNAL</th>
                <th>SPOT PRICE</th>
                <th>SPOT &#916;</th>
                <th>NIFTY MOVE %</th>
                <th>STREAK</th>
                <th>NEAREST LEVEL</th>
                <th>DISTANCE</th>
                <th>RSI 15M</th>
                <th>EMA 5/13</th>
                <th class="col-detail">VWAP</th>
              </tr>
            </thead>
            <tbody id="oiTableBody">
              <tr><td colspan="15" class="oi-empty-state">&#8987; Loading oi_log.json&hellip;</td></tr>
            </tbody>
          </table>
        </div>
          <div class="logic-box" style="margin-top:16px;">
          <div class="logic-box-head">&#128214; HOW TO READ THIS TABLE</div>
          <div class="logic-grid">
            <div class="logic-item"><span class="lc-bear">Call OI +</span> Writers adding calls &#8594; Bearish pressure</div>
            <div class="logic-item"><span class="lc-bull">Put OI +</span> Writers adding puts &#8594; Bullish support</div>
            <div class="logic-item"><span class="lc-info">DIFF</span> = PE &#916; &#8722; CE &#916; &nbsp;&middot;&nbsp; <span class="lc-bull">+ve = Bullish</span> &nbsp;<span class="lc-bear">&#8722;ve = Bearish</span></div>
            <div class="logic-item"><span class="lc-info">3/5/15 Min</span> filters raw rows or aggregates into time slots</div>
            <div class="logic-item"><span class="lc-bull">SPOT &#916;</span> Price change since previous snapshot &nbsp;&middot;&nbsp; &#9650; up &nbsp; &#9660; down &nbsp; &#8594; flat</div>
            <div class="logic-item"><span class="lc-bull">NIFTY MOVE %</span> % change from previous day close &nbsp;&middot;&nbsp; &#9650; green = up &nbsp; &#9660; red = down &nbsp; &#8594; flat = ±0.1%</div>
            <div class="logic-item"><span class="lc-bull">STREAK</span> Consecutive snapshots with same signal &nbsp;&middot;&nbsp; &#215;1 = just flipped &nbsp;&middot;&nbsp; &#215;5+ = strong trend</div>
            <div class="logic-item"><span class="lc-info">RSI 15M</span> 14-period RSI on 15-min candles &nbsp;&middot;&nbsp; <span class="lc-bull">&lt;30 = Oversold (OS) &nbsp;BUY zone</span> &nbsp;<span class="lc-bear">&gt;70 = Overbought (OB) &nbsp;SELL zone</span> &nbsp;&middot;&nbsp; 55+ = mild bull &nbsp;45&minus; = mild bear</div>
            <div class="logic-item"><span class="lc-info">EMA 5/13</span> 15-min EMA crossover &nbsp;&middot;&nbsp; <span class="lc-bull">▲ BUY = EMA5 &gt; EMA13 (uptrend)</span> &nbsp;<span class="lc-bear">▼ SELL = EMA5 &lt; EMA13 (downtrend)</span> &nbsp;&middot;&nbsp; Gap = distance between EMAs (bigger = stronger trend)</div>
            <div class="logic-item"><span class="lc-info">VWAP</span> Volume Weighted Avg Price &nbsp;&middot;&nbsp; <span class="lc-bull">▲ Above = Bullish bias</span> &nbsp;<span class="lc-bear">▼ Below = Bearish bias</span></div>
            <div class="logic-item"><span class="lc-info">Timestamps</span> All times shown in IST (Asia/Kolkata)</div>
          </div>
        </div>
      </div>
    </div><!-- /tab-oi-trend -->
"""




# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PRE-TRADE CHECKLIST — v6 addition
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_pretrade_checklist_css():
    """CSS for the Pre-Trade Checklist tab — deep ocean theme."""
    return """
        /* PRE-TRADE CHECKLIST */
        .ptc-progress-wrap{background:rgba(6,13,20,0.85);border:1px solid rgba(79,195,247,0.18);border-radius:14px;padding:18px 22px;margin-bottom:22px;}
        .ptc-progress-header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:12px;}
        .ptc-progress-label{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:2.5px;text-transform:uppercase;color:rgba(128,222,234,0.8);font-weight:700;}
        .ptc-progress-count{font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:#80deea;}
        .ptc-reset-btn{font-family:'Oxanium',sans-serif;font-size:10px;font-weight:700;letter-spacing:1px;padding:5px 14px;border-radius:20px;border:1px solid rgba(79,195,247,0.3);background:rgba(79,195,247,0.06);color:rgba(79,195,247,0.7);cursor:pointer;transition:all 0.2s ease;}
        .ptc-reset-btn:hover{border-color:rgba(79,195,247,0.6);color:#4fc3f7;background:rgba(79,195,247,0.12);}
        .ptc-bar-track{height:6px;background:rgba(0,0,0,0.4);border-radius:3px;overflow:hidden;margin-bottom:12px;}
        .ptc-bar-fill{height:100%;border-radius:3px;background:linear-gradient(90deg,#00e5ff,#0288d1);transition:width 0.5s cubic-bezier(0.4,0,0.2,1),background 0.4s ease;}
        .ptc-verdict{display:flex;align-items:center;gap:10px;font-size:13px;color:#80deea;font-family:'Rajdhani',sans-serif;font-weight:600;transition:color 0.3s ease;}
        .ptc-verdict-icon{font-size:18px;flex-shrink:0;}
        .ptc-list{display:flex;flex-direction:column;gap:0;}
        .ptc-section-label{font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:3px;text-transform:uppercase;font-weight:700;padding:6px 14px;margin:16px 0 6px 0;display:inline-block;border-radius:4px;}
        .ptc-item{display:flex;align-items:center;gap:14px;padding:13px 18px;margin-bottom:5px;border-radius:6px;cursor:pointer;background:rgba(19,26,34,0.9);border:1px solid rgba(79,195,247,0.07);border-left-width:3px;user-select:none;transition:opacity 0.25s ease,filter 0.25s ease,background 0.2s ease;position:relative;overflow:hidden;}
        .ptc-item::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.04),transparent);}
        .ptc-item:hover{filter:brightness(1.12);background:rgba(26,36,48,0.95);}
        .ptc-item.ptc-checked{opacity:0.42;}
        .ptc-item.ptc-checked .ptc-text{text-decoration:line-through;text-decoration-color:rgba(176,190,197,0.4);}
        .ptc-checkbox{width:20px;height:20px;border:2px solid;border-radius:3px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;transition:all 0.2s ease;background:rgba(0,0,0,0.25);}
        .ptc-text{font-family:'Rajdhani',sans-serif;font-size:clamp(13px,1.6vw,15px);font-weight:500;color:#c9d1d9;line-height:1.45;transition:text-decoration 0.2s ease;}
        .ptc-text b{font-weight:700;}
        .ptc-warning{font-size:11px;color:#ff4d4d;font-family:'JetBrains Mono',monospace;letter-spacing:0.5px;font-weight:700;margin-left:4px;}
        .ptc-mindset-box{display:flex;align-items:flex-start;gap:16px;background:linear-gradient(135deg,rgba(79,195,247,0.05),rgba(124,77,255,0.05));border:1px solid rgba(79,195,247,0.14);border-radius:12px;padding:18px 22px;margin-top:22px;}
        .ptc-mindset-icon{font-size:22px;flex-shrink:0;margin-top:2px;}
        .ptc-mindset-title{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:2.5px;color:rgba(128,222,234,0.8);text-transform:uppercase;font-weight:700;margin-bottom:7px;}
        .ptc-mindset-text{font-size:clamp(13px,1.5vw,14px);color:rgba(200,221,232,0.9);line-height:1.7;font-family:'Rajdhani',sans-serif;font-weight:500;}
        .ptc-mindset-text strong{color:#4fc3f7;font-weight:700;}
        @media(max-width:600px){.ptc-item{padding:10px 12px;gap:10px;}.ptc-text{font-size:13px;}.ptc-mindset-box{flex-direction:column;gap:10px;}}
"""


def build_pretrade_checklist_tab_html():
    """
    Builds the complete Pre-Trade Checklist tab HTML.
    23 rules across 7 colour-coded sections.
    """

    # ── Section + item definitions ────────────────────────────────────────────
    sections = [
        {
            "id": "core", "label": "Core Rules", "icon": "&#9881;",
            "bg": "rgba(255,77,77,0.08)", "col": "#ff6060",
            "items": [
                {"id": "rr",      "c": "#ff4d4d",
                 "h": 'Is R:R ratio &ge; 1.5? <b style="color:#ff4d4d;">If not, skip this trade.</b>'},
                {"id": "levels",  "c": "#ffa500",
                 "h": 'Is current price too close to <b style="color:#ffa500;">resistance (bearish) or support (bullish)</b>? If yes, wait.'},
                {"id": "exits",   "c": "#e6c619",
                 "h": 'Have I <b style="color:#e6c619;">written down all 3 exit conditions</b> above?'},
                {"id": "capital", "c": "#00bcd4",
                 "h": 'Am I risking <b style="color:#00bcd4;">&le; 2% of total capital</b> on this trade?'},
                {"id": "event",   "c": "#9b59b6",
                 "h": 'Is there a <b style="color:#9b59b6;">major event</b> (RBI, earnings, expiry) before my time exit?'},
                {"id": "halfway", "c": "#2ecc71",
                 "h": 'If halfway to target and stalled &mdash; <b style="color:#2ecc71;">take 50% profits and reassess.</b>'},
            ]
        },
        {
            "id": "market", "label": "Market Context", "icon": "&#127760;",
            "bg": "rgba(0,229,255,0.08)", "col": "#00e5ff",
            "items": [
                {"id": "broader",  "c": "#00e5ff",
                 "h": 'Is the broader market <b style="color:#00e5ff;">(Nifty/Sensex)</b> trending in my trade direction?'},
                {"id": "trend",    "c": "#00e5ff",
                 "h": 'Am I trading <b style="color:#00e5ff;">with the primary trend</b> on the higher timeframe?'},
                {"id": "vol_sess", "c": "#00e5ff",
                 "h": 'Is this a <b style="color:#00e5ff;">low-volume / holiday session</b>? If yes, avoid or reduce size.'},
            ]
        },
        {
            "id": "setup", "label": "Setup Quality", "icon": "&#127919;",
            "bg": "rgba(255,171,64,0.08)", "col": "#ffab40",
            "items": [
                {"id": "confluence", "c": "#ffab40",
                 "h": 'Is there a clear <b style="color:#ffab40;">confluence</b> &mdash; volume, breakout, or pattern confirmation?'},
                {"id": "candle",     "c": "#ffab40",
                 "h": 'Have I waited for <b style="color:#ffab40;">candle close confirmation</b> &mdash; not just a wick touch?'},
                {"id": "agrade",     "c": "#ffab40",
                 "h": 'Is this an <b style="color:#ffab40;">A-grade setup</b>, or am I forcing a trade out of FOMO?'},
            ]
        },
        {
            "id": "timing", "label": "Timing", "icon": "&#9201;",
            "bg": "rgba(181,234,58,0.08)", "col": "#b5ea3a",
            "items": [
                {"id": "open15", "c": "#b5ea3a",
                 "h": 'Am I <b style="color:#b5ea3a;">avoiding the first 15 minutes</b> of market open?'},
                {"id": "eod1h",  "c": "#b5ea3a",
                 "h": 'Is there <b style="color:#b5ea3a;">less than 1 hour left</b> in the session? If yes, reduce size or avoid.'},
            ]
        },
        {
            "id": "psych", "label": "Psychology &amp; Discipline", "icon": "&#129504;",
            "bg": "rgba(240,98,146,0.08)", "col": "#f06292",
            "items": [
                {"id": "losses2", "c": "#f06292",
                 "h": 'Have I already taken <b style="color:#f06292;">2+ losses today</b>? <span class="ptc-warning">If yes &mdash; STOP trading.</span>'},
                {"id": "revenge", "c": "#f06292",
                 "h": 'Am I trading to <b style="color:#f06292;">recover a loss</b>? <span class="ptc-warning">Revenge trading check.</span>'},
                {"id": "mental",  "c": "#f06292",
                 "h": 'Am I in the <b style="color:#f06292;">right mental state</b> &mdash; calm, not anxious or overconfident?'},
            ]
        },
        {
            "id": "position", "label": "Position &amp; Execution", "icon": "&#128208;",
            "bg": "rgba(77,182,172,0.08)", "col": "#4db6ac",
            "items": [
                {"id": "possize", "c": "#4db6ac",
                 "h": 'Is my <b style="color:#4db6ac;">position size pre-calculated</b> before entry?'},
                {"id": "slplace", "c": "#4db6ac",
                 "h": 'Will I place my <b style="color:#4db6ac;">stop-loss order immediately</b> after entry?'},
                {"id": "target",  "c": "#4db6ac",
                 "h": 'Is my <b style="color:#4db6ac;">target based on structure</b> &mdash; not wishful thinking?'},
            ]
        },
        {
            "id": "options", "label": "Options-Specific", "icon": "&#128202;",
            "bg": "rgba(206,147,216,0.08)", "col": "#ce93d8",
            "items": [
                {"id": "iv",          "c": "#ce93d8",
                 "h": 'Is <b style="color:#ce93d8;">IV (Implied Volatility)</b> too high to buy options profitably?'},
                {"id": "theta",       "c": "#ce93d8",
                 "h": 'Is <b style="color:#ce93d8;">theta (time decay)</b> working for or against me?'},
                {"id": "expiry_time", "c": "#ce93d8",
                 "h": 'Am I close to <b style="color:#ce93d8;">expiry</b> with insufficient time for the move to play out?'},
            ]
        },
    ]

    all_ids  = [it["id"] for sec in sections for it in sec["items"]]
    TOTAL    = len(all_ids)
    ids_json = "[" + ",".join(f'"{i}"' for i in all_ids) + "]"

    # ── Build HTML for all items ──────────────────────────────────────────────
    body_html = ""
    for sec in sections:
        body_html += (
            f'<div class="ptc-section-label"'
            f' style="background:{sec["bg"]};color:{sec["col"]};">'
            f'{sec["icon"]} &nbsp;{sec["label"]}</div>'
        )
        for it in sec["items"]:
            body_html += (
                f'<div class="ptc-item" id="ptc-{it["id"]}"'
                f' style="border-left-color:{it["c"]};"'
                f' onclick="ptcToggle(\'{it["id"]}\')">'
                f'<div class="ptc-checkbox"'
                f' style="border-color:{it["c"]};color:{it["c"]};"'
                f' id="ptc-cb-{it["id"]}"></div>'
                f'<div class="ptc-text">{it["h"]}</div></div>'
            )

    return f"""
    <!-- TAB: PRE-TRADE CHECKLIST -->
    <div class="tab-panel" id="tab-pretrade">
      <div class="section">
        <div class="section-title">
          <span>&#9989;</span> PRE-TRADE CHECKLIST
          <span style="font-size:11px;color:rgba(128,222,234,0.75);font-weight:600;letter-spacing:1px;margin-left:auto;">
            {TOTAL} rules &middot; Click to check / uncheck
          </span>
        </div>

        <div class="ptc-progress-wrap">
          <div class="ptc-progress-header">
            <span class="ptc-progress-label">CHECKLIST PROGRESS</span>
            <div style="display:flex;align-items:center;gap:12px;">
              <span class="ptc-progress-count">
                <span id="ptcChecked">0</span> / {TOTAL} checked
              </span>
              <button class="ptc-reset-btn" onclick="ptcReset()">&#8635; Reset</button>
            </div>
          </div>
          <div class="ptc-bar-track">
            <div class="ptc-bar-fill" id="ptcBarFill" style="width:0%"></div>
          </div>
          <div class="ptc-verdict">
            <span class="ptc-verdict-icon" id="ptcVerdictIcon">&#9634;</span>
            <span id="ptcVerdictText">Complete the checklist before entering any trade.</span>
          </div>
        </div>

        <div class="ptc-list">
          {body_html}
        </div>

        <div class="ptc-mindset-box">
          <span class="ptc-mindset-icon">&#129497;</span>
          <div>
            <div class="ptc-mindset-title">TRADING MINDSET REMINDER</div>
            <div class="ptc-mindset-text">
              A loss that follows your rules is <strong>not a failure</strong>.
              A loss without rules <strong>is</strong>. &nbsp;&middot;&nbsp;
              Your job is not to be right &mdash; it is to <strong>manage risk</strong>.
              &nbsp;&middot;&nbsp; <strong>No setup = No trade.</strong>
            </div>
          </div>
        </div>

        <div class="disclaimer" style="margin-top:16px;">
          <span class="disc-icon">&#9888;&#65039;</span>
          <span class="disc-label">Disclaimer</span>
          <span class="disc-sep">|</span>
          <span class="disc-text">For <strong>EDUCATIONAL purposes only</strong> &mdash; NOT financial advice.</span>
          <span class="disc-sep">|</span>
          <span class="disc-text">Always consult a SEBI-registered advisor before trading.</span>
        </div>
      </div>
    </div><!-- /tab-pretrade -->

    <script>
    (function() {{
      var IDS   = {ids_json};
      var TOTAL = {TOTAL};
      var KEY   = 'ptc_v1';

      function save() {{
        var s = {{}};
        IDS.forEach(function(id) {{
          var r = document.getElementById('ptc-' + id);
          s[id] = r ? r.classList.contains('ptc-checked') : false;
        }});
        try {{ sessionStorage.setItem(KEY, JSON.stringify(s)); }} catch(e) {{}}
      }}

      function load() {{
        try {{ var r = sessionStorage.getItem(KEY); return r ? JSON.parse(r) : {{}}; }}
        catch(e) {{ return {{}}; }}
      }}

      function apply(s) {{
        IDS.forEach(function(id) {{
          var row = document.getElementById('ptc-' + id);
          var cb  = document.getElementById('ptc-cb-' + id);
          if (!row || !cb) return;
          if (s[id]) {{ row.classList.add('ptc-checked');    cb.innerHTML = '&#10003;'; }}
          else       {{ row.classList.remove('ptc-checked'); cb.innerHTML = ''; }}
        }});
        redraw();
      }}

      function redraw() {{
        var n   = document.querySelectorAll('.ptc-item.ptc-checked').length;
        var pct = Math.round(n / TOTAL * 100);
        var fill = document.getElementById('ptcBarFill');
        var cnt  = document.getElementById('ptcChecked');
        var icon = document.getElementById('ptcVerdictIcon');
        var txt  = document.getElementById('ptcVerdictText');
        if (fill) fill.style.width = pct + '%';
        if (cnt)  cnt.textContent  = n;
        if (pct === 100) {{
          if (fill) fill.style.background = 'linear-gradient(90deg,#00e676,#00bfa5)';
          if (icon) icon.innerHTML = '&#128640;';
          if (txt)  {{ txt.textContent = 'All checks passed \u2014 you may proceed!'; txt.style.color = '#00e676'; }}
        }} else if (pct >= 70) {{
          if (fill) fill.style.background = 'linear-gradient(90deg,#ffb74d,#ff8f00)';
          if (icon) icon.innerHTML = '&#9888;&#65039;';
          if (txt)  {{ txt.textContent = 'Almost there \u2014 complete remaining checks.'; txt.style.color = '#ffb74d'; }}
        }} else {{
          if (fill) fill.style.background = 'linear-gradient(90deg,#00e5ff,#0288d1)';
          if (icon) icon.innerHTML = '&#9634;';
          if (txt)  {{ txt.textContent = 'Complete the checklist before entering any trade.'; txt.style.color = 'rgba(128,222,234,0.6)'; }}
        }}
      }}

      window.ptcToggle = function(id) {{
        var row = document.getElementById('ptc-' + id);
        var cb  = document.getElementById('ptc-cb-' + id);
        if (!row || !cb) return;
        if (!row.classList.contains('ptc-checked')) {{
          row.classList.add('ptc-checked');    cb.innerHTML = '&#10003;';
        }} else {{
          row.classList.remove('ptc-checked'); cb.innerHTML = '';
        }}
        redraw(); save();
      }};

      window.ptcReset = function() {{
        IDS.forEach(function(id) {{
          var row = document.getElementById('ptc-' + id);
          var cb  = document.getElementById('ptc-cb-' + id);
          if (row) row.classList.remove('ptc-checked');
          if (cb)  cb.innerHTML = '';
        }});
        redraw();
        try {{ sessionStorage.removeItem(KEY); }} catch(e) {{}}
      }};

      window.addEventListener('load', function() {{ apply(load()); }});

      /* Hook into switchTab so state restores on tab activation */
      var _orig = window.switchTab;
      if (typeof _orig === 'function') {{
        window.switchTab = function(tab) {{
          _orig(tab);
          if (tab === 'pretrade') {{ setTimeout(function() {{ apply(load()); }}, 60); }}
        }};
      }}
    }})();
    </script>
"""



class NiftyHTMLAnalyzer:
    def __init__(self):
        self.yf_symbol  = "^NSEI"
        self.nse_symbol = "NIFTY"
        self.report_lines = []
        self.html_data    = {}
        self.heatmap_data = []
        self.heatmap_timestamp = "N/A"
        self.heatmap_advance = 0
        self.heatmap_decline = 0
        self.heatmap_neutral = 0

    def log(self, message):
        print(message)
        self.report_lines.append(message)

    def _make_nse_session(self):
        headers = {
            "authority": "www.nseindia.com",
            "accept": "application/json, text/plain, */*",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "referer": "https://www.nseindia.com/option-chain",
            "accept-language": "en-US,en;q=0.9",
        }
        session = requests.Session()
        try:
            session.get("https://www.nseindia.com/", headers=headers, impersonate="chrome", timeout=15)
            time.sleep(1.5)
            session.get("https://www.nseindia.com/option-chain", headers=headers, impersonate="chrome", timeout=15)
            time.sleep(1)
        except Exception as e:
            print(f"  ⚠️  Session warm-up warning: {e}")
        return session, headers

    def get_upcoming_expiry_tuesday(self):
        ist_tz      = pytz.timezone('Asia/Kolkata')
        now_ist     = datetime.now(ist_tz)
        today_ist   = now_ist.date()
        weekday     = today_ist.weekday()
        past_cutoff = (now_ist.hour, now_ist.minute) >= (16, 0)
        if weekday == 1 and not past_cutoff:
            days_ahead = 0
        elif weekday == 1 and past_cutoff:
            days_ahead = 7
        elif weekday < 1:
            days_ahead = 1 - weekday
        else:
            days_ahead = 8 - weekday
        raw_tuesday = today_ist + timedelta(days=days_ahead)
        candidate = raw_tuesday
        for _ in range(6):
            cstr       = candidate.strftime('%d-%b-%Y')
            is_weekend = candidate.weekday() >= 5
            if cstr not in NSE_FO_HOLIDAYS and not is_weekend:
                break
            candidate -= timedelta(days=1)
        expiry_str = candidate.strftime('%d-%b-%Y')
        holiday_shifted = (candidate != raw_tuesday)
        shift_note = f" ⚠️ HOLIDAY SHIFT from {raw_tuesday.strftime('%d-%b-%Y')}" if holiday_shifted else ""
        print(f"  📅 Now (IST): {now_ist.strftime('%A %d-%b-%Y %H:%M')} | "
              f"Raw Tue: {raw_tuesday.strftime('%d-%b-%Y')} | "
              f"Adjusted expiry: {expiry_str}{shift_note} | "
              f"Past 4PM: {past_cutoff}")
        return expiry_str

    def fetch_available_expiries(self, session, headers):
        try:
            url  = f"https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol={self.nse_symbol}"
            resp = session.get(url, headers=headers, impersonate="chrome", timeout=20)
            if resp.status_code == 200:
                data     = resp.json()
                expiries = data.get('records', {}).get('expiryDates', [])
                if expiries:
                    print(f"  📅 NSE available expiries: {expiries[:5]}")
                    return expiries[0]
        except Exception as e:
            print(f"  ⚠️  Could not fetch expiry list: {e}")
        return None

    def fetch_nse_option_chain_silent(self):
        session, headers = self._make_nse_session()
        real_expiry = self.fetch_available_expiries(session, headers)
        if real_expiry:
            print(f"  🗓️  Fetching option chain for NSE live expiry: {real_expiry}")
            result = self._fetch_chain_for_expiry(session, headers, real_expiry)
            if result:
                return result
            print(f"  ⚠️  Chain data empty for live expiry {real_expiry}. Trying fallback...")
        computed_expiry = self.get_upcoming_expiry_tuesday()
        if computed_expiry != real_expiry:
            print(f"  🔄 Fallback computed expiry: {computed_expiry}")
            result = self._fetch_chain_for_expiry(session, headers, computed_expiry)
            if result:
                return result
        if real_expiry and real_expiry != computed_expiry:
            print(f"  🔄 Last attempt with real_expiry: {real_expiry}")
            result = self._fetch_chain_for_expiry(session, headers, real_expiry)
            if result:
                return result
        print("  ❌ Option chain fetch failed after all attempts.")
        return None

    def _fetch_chain_for_expiry(self, session, headers, expiry):
        api_url = (f"https://www.nseindia.com/api/option-chain-v3"
                   f"?type=Indices&symbol={self.nse_symbol}&expiry={expiry}")
        for attempt in range(1, 3):
            try:
                print(f"    Attempt {attempt}: expiry={expiry}")
                resp = session.get(api_url, headers=headers, impersonate="chrome", timeout=30)
                print(f"    HTTP {resp.status_code}")
                if resp.status_code != 200:
                    time.sleep(2); continue
                json_data  = resp.json()
                data       = json_data.get('records', {}).get('data', [])
                if not data:
                    print(f"    ⚠️  Empty data for expiry={expiry}"); return None
                rows = []
                for item in data:
                    strike = item.get('strikePrice')
                    ce = item.get('CE', {}); pe = item.get('PE', {})
                    rows.append({
                        'Expiry': expiry, 'Strike': strike,
                        'CE_LTP': ce.get('lastPrice', 0), 'CE_OI': ce.get('openInterest', 0),
                        'CE_Vol': ce.get('totalTradedVolume', 0),
                        'PE_LTP': pe.get('lastPrice', 0), 'PE_OI': pe.get('openInterest', 0),
                        'PE_Vol': pe.get('totalTradedVolume', 0),
                        'CE_OI_Change': ce.get('changeinOpenInterest', 0),
                        'PE_OI_Change': pe.get('changeinOpenInterest', 0),
                    })
                df_full    = pd.DataFrame(rows).sort_values('Strike').reset_index(drop=True)
                underlying = json_data.get('records', {}).get('underlyingValue', 0)
                atm_strike = round(underlying / 50) * 50
                all_strikes = sorted(df_full['Strike'].unique())
                if atm_strike in all_strikes:
                    atm_idx = all_strikes.index(atm_strike)
                else:
                    atm_idx = min(range(len(all_strikes)), key=lambda i: abs(all_strikes[i] - underlying))
                    atm_strike = all_strikes[atm_idx]
                lower_idx = max(0, atm_idx - 10); upper_idx = min(len(all_strikes) - 1, atm_idx + 10)
                selected_strikes = all_strikes[lower_idx: upper_idx + 1]
                df = df_full[df_full['Strike'].isin(selected_strikes)].reset_index(drop=True)
                print(f"    ✅ Strikes: {len(df_full)} → ATM±10 filtered: {len(df)}")
                return {'expiry': expiry, 'df': df, 'raw_data': data,
                        'underlying': underlying, 'atm_strike': atm_strike}
            except Exception as e:
                print(f"    ❌ Attempt {attempt} error: {e}"); time.sleep(2)
        return None

    def analyze_option_chain_data(self, oc_data):
        if not oc_data: return None
        df = oc_data['df']
        total_ce_oi  = df['CE_OI'].sum(); total_pe_oi  = df['PE_OI'].sum()
        total_ce_vol = df['CE_Vol'].sum(); total_pe_vol = df['PE_Vol'].sum()
        pcr_oi  = total_pe_oi  / total_ce_oi  if total_ce_oi  > 0 else 0
        pcr_vol = total_pe_vol / total_ce_vol if total_ce_vol > 0 else 0
        total_ce_oi_change = int(df['CE_OI_Change'].sum())
        total_pe_oi_change = int(df['PE_OI_Change'].sum())
        net_oi_change = total_pe_oi_change - total_ce_oi_change
        if   total_ce_oi_change > 0 and total_pe_oi_change < 0:
            oi_direction,oi_signal,oi_icon,oi_class="Strong Bearish","Call Build-up + Put Unwinding","🔴","bearish"
        elif total_ce_oi_change < 0 and total_pe_oi_change > 0:
            oi_direction,oi_signal,oi_icon,oi_class="Strong Bullish","Put Build-up + Call Unwinding","🟢","bullish"
        elif total_ce_oi_change > 0 and total_pe_oi_change > 0:
            if   total_pe_oi_change > total_ce_oi_change * 1.5:
                oi_direction,oi_signal,oi_icon,oi_class="Bullish","Put Build-up Dominant","🟢","bullish"
            elif total_ce_oi_change > total_pe_oi_change * 1.5:
                oi_direction,oi_signal,oi_icon,oi_class="Bearish","Call Build-up Dominant","🔴","bearish"
            else:
                oi_direction,oi_signal,oi_icon,oi_class="Neutral (High Vol)","Both Calls & Puts Building","🟡","neutral"
        elif total_ce_oi_change < 0 and total_pe_oi_change < 0:
            oi_direction,oi_signal,oi_icon,oi_class="Neutral (Unwinding)","Both Calls & Puts Unwinding","🟡","neutral"
        else:
            if   net_oi_change > 0: oi_direction,oi_signal,oi_icon,oi_class="Moderately Bullish","Net Put Accumulation","🟢","bullish"
            elif net_oi_change < 0: oi_direction,oi_signal,oi_icon,oi_class="Moderately Bearish","Net Call Accumulation","🔴","bearish"
            else:                   oi_direction,oi_signal,oi_icon,oi_class="Neutral","Balanced OI Changes","🟡","neutral"
        max_ce_oi_row = df.loc[df['CE_OI'].idxmax()]; max_pe_oi_row = df.loc[df['PE_OI'].idxmax()]
        df['pain']    = abs(df['CE_OI'] - df['PE_OI']); max_pain_row = df.loc[df['pain'].idxmin()]
        df['Total_OI'] = df['CE_OI'] + df['PE_OI']
        return {
            'expiry': oc_data['expiry'], 'underlying_value': oc_data['underlying'],
            'atm_strike': oc_data['atm_strike'],
            'pcr_oi': round(pcr_oi,3), 'pcr_volume': round(pcr_vol,3),
            'total_ce_oi': int(total_ce_oi), 'total_pe_oi': int(total_pe_oi),
            'max_ce_oi_strike': int(max_ce_oi_row['Strike']), 'max_ce_oi_value': int(max_ce_oi_row['CE_OI']),
            'max_pe_oi_strike': int(max_pe_oi_row['Strike']), 'max_pe_oi_value': int(max_pe_oi_row['CE_OI']),
            'max_pain': int(max_pain_row['Strike']),
            'total_ce_oi_change': total_ce_oi_change, 'total_pe_oi_change': total_pe_oi_change,
            'net_oi_change': net_oi_change,
            'oi_direction': oi_direction, 'oi_signal': oi_signal,
            'oi_icon': oi_icon, 'oi_class': oi_class, 'df': df,
        }

    def get_technical_data(self):
        try:
            print("Calculating technical indicators...")
            nifty = yf.Ticker(self.yf_symbol)
            df = nifty.history(period="1y")
            if df.empty: print("Warning: Failed to fetch historical data"); return None
            df['SMA_20']  = df['Close'].rolling(20).mean()
            df['SMA_50']  = df['Close'].rolling(50).mean()
            df['SMA_200'] = df['Close'].rolling(200).mean()
            delta = df['Close'].diff()
            gain  = delta.where(delta > 0, 0).rolling(14).mean()
            loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
            df['RSI']    = 100 - (100 / (1 + gain / loss))
            df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
            df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD']   = df['EMA_12'] - df['EMA_26']
            df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

            # ── Use last non-NaN row for MACD/Signal (handles mid-session NaN) ──
            df_clean = df.dropna(subset=['MACD', 'Signal'])
            latest = df.iloc[-1]
            macd_val   = float(df_clean['MACD'].iloc[-1])   if not df_clean.empty else float('nan')
            signal_val = float(df_clean['Signal'].iloc[-1]) if not df_clean.empty else float('nan')
            # Previous row for histogram slope (early crossover detection)
            macd_prev_val   = float(df_clean['MACD'].iloc[-2])   if len(df_clean) >= 2 else macd_val
            signal_prev_val = float(df_clean['Signal'].iloc[-2]) if len(df_clean) >= 2 else signal_val
            current_price = latest['Close']
            print("  Fetching 1H candles for Key Levels (tiered lookback: 6M → 1Y → wide window)...")
            from datetime import datetime, timedelta

            end_date  = datetime.today()
            start_6m  = end_date - timedelta(days=180)
            start_1yr = end_date - timedelta(days=365)

            s1 = s2 = r1 = r2 = None

            def _find_levels(highs, lows, price, window):
                res_c = [h for h in highs if price < h <= price + window]
                sup_c = [l for l in lows  if price - window <= l < price]
                return res_c, sup_c

            # Step 1: 6 months of 1H data
            try:
                df_6m = nifty.history(interval="1h", start=start_6m, end=end_date)
                if not df_6m.empty:
                    highs_6m = sorted(df_6m['High'].values)
                    lows_6m  = sorted(df_6m['Low'].values)
                    res_c, sup_c = _find_levels(highs_6m, lows_6m, current_price, 300)
                    print(f"  6M 1H: {len(df_6m)} candles | res_c={len(res_c)} sup_c={len(sup_c)}")
                else:
                    res_c, sup_c = [], []
            except Exception as e:
                print(f"  ⚠️  6M 1H fetch failed: {e}")
                res_c, sup_c = [], []

            # Step 2: expand to 1 year if not enough
            if len(res_c) < 2 or len(sup_c) < 2:
                print("  🔄 6M insufficient — expanding to 1 year")
                try:
                    df_1yr = nifty.history(interval="1h", start=start_1yr, end=end_date)
                    if not df_1yr.empty:
                        highs_1yr = sorted(df_1yr['High'].values)
                        lows_1yr  = sorted(df_1yr['Low'].values)
                        res_c, sup_c = _find_levels(highs_1yr, lows_1yr, current_price, 300)
                        print(f"  1Y 1H: {len(df_1yr)} candles | res_c={len(res_c)} sup_c={len(sup_c)}")
                    else:
                        res_c, sup_c = [], []
                except Exception as e:
                    print(f"  ⚠️  1Y 1H fetch failed: {e}")
                    res_c, sup_c = [], []

            # Step 3: widen window to ±500 on same 1Y data
            if len(res_c) < 2 or len(sup_c) < 2:
                print("  🔄 Widening window to ±500 on 1Y data")
                try:
                    res_c, sup_c = _find_levels(highs_1yr, lows_1yr, current_price, 500)
                    print(f"  Wide window | res_c={len(res_c)} sup_c={len(sup_c)}")
                except Exception:
                    res_c, sup_c = [], []

            # Calculate levels — no hardcoding, N/A if genuinely nothing found
            if len(res_c) >= 2:
                r1 = round(float(np.percentile(res_c, 25)) / 25) * 25
                r2 = round(float(np.percentile(res_c, 65)) / 25) * 25
                if r1 <= current_price:
                    r1 = round(float(np.percentile(res_c, 50)) / 25) * 25
                if r2 and r1 and r2 <= r1:
                    r2 = round(float(np.percentile(res_c, 80)) / 25) * 25
            else:
                print("  ⚠️  No resistance levels found — will show N/A")

            if len(sup_c) >= 2:
                s1 = round(float(np.percentile(sup_c, 75)) / 25) * 25
                s2 = round(float(np.percentile(sup_c, 35)) / 25) * 25
                if s1 >= current_price:
                    s1 = round(float(np.percentile(sup_c, 50)) / 25) * 25
                if s2 and s1 and s2 >= s1:
                    s2 = round(float(np.percentile(sup_c, 20)) / 25) * 25
            else:
                print("  ⚠️  No support levels found — will show N/A")

            print(f"  ✓ Final Levels | S2={s2} S1={s1} | Price={current_price:.0f} | R1={r1} R2={r2}")

            # Assign to technical dict — None means N/A, no fallback invented
            resistance        = r1
            support           = s1
            strong_resistance = r2
            strong_support    = s2
            # ── Previous candle OHLC for pivot point calculation ───────────────
            prev_row   = df.iloc[-2] if len(df) >= 2 else latest
            prev_high  = float(prev_row['High'])
            prev_low   = float(prev_row['Low'])
            prev_close = float(prev_row['Close'])

            technical = {
                'current_price':    current_price,
                'sma_20':           latest['SMA_20'],
                'sma_50':           latest['SMA_50'],
                'sma_200':          latest['SMA_200'],
                'rsi':              latest['RSI'],
                'macd':             macd_val,
                'signal':           signal_val,
                'macd_prev':        macd_prev_val,
                'signal_prev':      signal_prev_val,
                'resistance':       resistance,
                'support':          support,
                'strong_resistance':strong_resistance,
                'strong_support':   strong_support,
                'prev_high':        prev_high,
                'prev_low':         prev_low,
                'prev_close':       prev_close,
            }
            print(f"✓ Technical | Price: {technical['current_price']:.2f} | RSI: {technical['rsi']:.1f}")
            return technical
        except Exception as e:
            print(f"Technical error: {e}"); return None

    def calculate_smart_stop_loss(self, current_price, support, resistance, bias):
        if bias == "BULLISH": return round(max(support - 30, current_price - 150), 0)
        elif bias == "BEARISH": return round(min(resistance + 30, current_price + 150), 0)
        return None

    def generate_analysis_data(self, technical, option_analysis):
        if not technical:
            self.log("⚠️  Technical data unavailable"); return
        current    = technical['current_price']
        support    = technical['support']
        resistance = technical['resistance']
        ist_now    = datetime.now(pytz.timezone('Asia/Kolkata'))
        bullish_score = bearish_score = 0
        for sma in ['sma_20','sma_50','sma_200']:
            if current > technical[sma]: bullish_score += 1
            else: bearish_score += 1
        rsi = technical['rsi']
        if   rsi > 70: bearish_score += 1
        elif rsi < 30: bullish_score += 2
        # ── MACD: histogram slope fires BEFORE full crossover ──────────────────
        macd_hist      = technical['macd']      - technical['signal']
        macd_hist_prev = technical['macd_prev'] - technical['signal_prev']
        if technical['macd'] > technical['signal']:
            bullish_score += 1          # full crossover — confirmed bull
        elif macd_hist > macd_hist_prev:
            bullish_score += 1          # histogram building — early bull momentum
        else:
            bearish_score += 1
        if option_analysis:
            pcr = option_analysis['pcr_oi']; max_pain = option_analysis['max_pain']
            if   pcr > 1.2: bullish_score += 2
            elif pcr < 0.7: bearish_score += 2
            if   current > max_pain+100: bearish_score += 1
            elif current < max_pain-100: bullish_score += 1
        score_diff = bullish_score - bearish_score
        print(f"  📊 Bullish: {bullish_score} | Bearish: {bearish_score} | Diff: {score_diff} | MACD hist: {macd_hist:.2f} prev: {macd_hist_prev:.2f}")
        if   score_diff >= 3:  bias,bias_icon,bias_class="BULLISH","📈","bullish";    confidence="HIGH" if score_diff >= 4 else "MEDIUM"
        elif score_diff == 2:  bias,bias_icon,bias_class="WATCH BULL","⚡","watchbull"; confidence="MEDIUM"
        elif score_diff == -2: bias,bias_icon,bias_class="WATCH BEAR","⚠️","watchbear"; confidence="MEDIUM"
        elif score_diff <= -3: bias,bias_icon,bias_class="BEARISH","📉","bearish";    confidence="HIGH" if score_diff <= -4 else "MEDIUM"
        else:                  bias,bias_icon,bias_class="SIDEWAYS","↔️","sideways";   confidence="LOW"
        if   rsi > 70: rsi_status,rsi_badge,rsi_icon="Overbought","bearish","🔴"
        elif rsi < 30: rsi_status,rsi_badge,rsi_icon="Oversold","bullish","🟢"
        else:          rsi_status,rsi_badge,rsi_icon="Neutral","neutral","🟡"
        macd_bullish = technical['macd'] > technical['signal']
        if option_analysis:
            pcr = option_analysis['pcr_oi']
            if   pcr > 1.2: pcr_status,pcr_badge,pcr_icon="Bullish","bullish","🟢"
            elif pcr < 0.7: pcr_status,pcr_badge,pcr_icon="Bearish","bearish","🔴"
            else:           pcr_status,pcr_badge,pcr_icon="Neutral","neutral","🟡"
        else:
            pcr_status,pcr_badge,pcr_icon="N/A","neutral","🟡"
        if option_analysis:
            max_ce_strike=option_analysis['max_ce_oi_strike']; max_pe_strike=option_analysis['max_pe_oi_strike']
            atm_strike=option_analysis['atm_strike']
        else:
            atm_strike=int(current/50)*50; max_ce_strike=atm_strike+200; max_pe_strike=atm_strike-200
        if bias == "BULLISH":
            mid=((support+resistance)/2); entry_low=current-100 if current>mid else current-50
            entry_high=current-50 if current>mid else current; target_1=resistance; target_2=max_ce_strike
            stop_loss=self.calculate_smart_stop_loss(current,support,resistance,"BULLISH")
        elif bias == "BEARISH":
            mid=((support+resistance)/2); entry_low=current
            entry_high=current+100 if current<mid else current+50; target_1=support; target_2=max_pe_strike
            stop_loss=self.calculate_smart_stop_loss(current,support,resistance,"BEARISH")
        else:
            entry_low=support; entry_high=resistance; target_1=resistance; target_2=support; stop_loss=None
        if stop_loss and bias != "SIDEWAYS":
            risk_points=abs(current-stop_loss); reward_points=abs(target_1-current)
            risk_reward_ratio=round(reward_points/risk_points,2) if risk_points>0 else 0
        else:
            risk_points=reward_points=risk_reward_ratio=0
        rsi_pct=min(100,max(0,rsi))
        def sma_bar(sma_val):
            diff=(current-sma_val)/sma_val*100; return min(100,max(0,50+diff*10))
        macd_val=technical['macd']; macd_pct=min(100,max(0,50+macd_val*2))
        pcr_pct=min(100,max(0,(option_analysis['pcr_oi']/2*100))) if option_analysis else 50
        if option_analysis:
            rng=resistance-support if resistance!=support else 1
            mp_pct=min(100,max(0,(option_analysis['max_pain']-support)/rng*100))
            total_oi=option_analysis['total_ce_oi']+option_analysis['total_pe_oi']
            ce_oi_pct=min(100,max(0,option_analysis['total_ce_oi']/total_oi*100)) if total_oi>0 else 50
            pe_oi_pct=100-ce_oi_pct
        else:
            mp_pct=ce_oi_pct=pe_oi_pct=50
        fii_dii_raw  = fetch_fii_dii_data()
        fii_dii_summ = compute_fii_dii_summary(fii_dii_raw)
        self.html_data = {
            'timestamp': ist_now.strftime('%d-%b-%Y %H:%M IST'),
            'current_price': current, 'expiry': option_analysis['expiry'] if option_analysis else 'N/A',
            'atm_strike': atm_strike, 'bias': bias, 'bias_icon': bias_icon, 'bias_class': bias_class,
            'confidence': confidence, 'bullish_score': bullish_score, 'bearish_score': bearish_score,
            'rsi': rsi, 'rsi_pct': rsi_pct, 'rsi_status': rsi_status, 'rsi_badge': rsi_badge, 'rsi_icon': rsi_icon,
            'sma_20': technical['sma_20'], 'sma_20_above': current>technical['sma_20'], 'sma_20_pct': sma_bar(technical['sma_20']),
            'sma_50': technical['sma_50'], 'sma_50_above': current>technical['sma_50'], 'sma_50_pct': sma_bar(technical['sma_50']),
            'sma_200': technical['sma_200'], 'sma_200_above': current>technical['sma_200'], 'sma_200_pct': sma_bar(technical['sma_200']),
            'macd': technical['macd'], 'macd_signal': technical['signal'], 'macd_bullish': macd_bullish, 'macd_pct': macd_pct,
            'pcr': option_analysis['pcr_oi'] if option_analysis else 0, 'pcr_pct': pcr_pct,
            'pcr_status': pcr_status, 'pcr_badge': pcr_badge, 'pcr_icon': pcr_icon,
            'max_pain': option_analysis['max_pain'] if option_analysis else 0, 'max_pain_pct': mp_pct,
            'max_ce_oi': max_ce_strike, 'max_pe_oi': max_pe_strike,
            'ce_oi_pct': ce_oi_pct, 'pe_oi_pct': pe_oi_pct,
            'total_ce_oi_change': option_analysis['total_ce_oi_change'] if option_analysis else 0,
            'total_pe_oi_change': option_analysis['total_pe_oi_change'] if option_analysis else 0,
            'net_oi_change': option_analysis['net_oi_change'] if option_analysis else 0,
            'oi_direction': option_analysis['oi_direction'] if option_analysis else 'N/A',
            'oi_signal': option_analysis['oi_signal'] if option_analysis else 'N/A',
            'oi_icon': option_analysis['oi_icon'] if option_analysis else '🟡',
            'oi_class': option_analysis['oi_class'] if option_analysis else 'neutral',
            'support': support, 'resistance': resistance,
            'strong_support': technical['strong_support'], 'strong_resistance': technical['strong_resistance'],
            'strategy_type': bias, 'entry_low': entry_low, 'entry_high': entry_high,
            'target_1': target_1, 'target_2': target_2, 'stop_loss': stop_loss,
            'risk_points': int(risk_points), 'reward_points': int(reward_points),
            'risk_reward_ratio': risk_reward_ratio,
            'has_option_data': option_analysis is not None,
            'df': option_analysis['df'] if option_analysis else None,
            'fii_dii_data': fii_dii_raw, 'fii_dii_summ': fii_dii_summ,
            'prev_high':  technical.get('prev_high', 0),
            'prev_low':   technical.get('prev_low', 0),
            'prev_close': technical.get('prev_close', 0),
        }

    def _bar_color_class(self, badge):
        return {'bullish':'bar-teal','bearish':'bar-red','neutral':'bar-gold'}.get(badge,'bar-teal')

    def _stat_card(self, icon, label, value, badge_text, badge_class, bar_pct, bar_type, sub_text=""):
        tag_map = {'bullish':('tag-bull','#00e5ff'),'bearish':('tag-bear','#ff5252'),'neutral':('tag-neu','#ffb74d')}
        tag_cls,_ = tag_map.get(badge_class, tag_map['neutral'])
        border_color = {'bullish':'rgba(0,229,255,0.35)','bearish':'rgba(255,82,82,0.35)'}.get(badge_class,'rgba(255,183,77,0.25)')
        top_color = {'bullish':'#00e5ff','bearish':'#ff5252'}.get(badge_class,'#ffb74d')

        # ── RSI: circular ring gauge ─────────────────────────────────────────
        if label.startswith('RSI'):
            try:    rsi_num = float(value)
            except: rsi_num = 50.0
            circumf = 138.2
            offset  = circumf * (1 - rsi_num / 100)
            ring_col = '#ff5252' if rsi_num > 70 else ('#00e676' if rsi_num < 30 else '#ffb74d')
            extra_visual = f"""
            <div style="display:flex;justify-content:center;margin:6px 0 8px;">
              <div style="position:relative;width:56px;height:56px;">
                <svg viewBox="0 0 56 56" style="width:100%;height:100%;">
                  <circle cx="28" cy="28" r="22" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="7"/>
                  <circle cx="28" cy="28" r="22" fill="none" stroke="{ring_col}" stroke-width="7"
                    stroke-linecap="round" stroke-dasharray="{circumf:.1f}" stroke-dashoffset="{offset:.1f}"
                    style="transform:rotate(-90deg);transform-origin:28px 28px;" opacity="0.85"/>
                </svg>
                <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
                  font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;color:{ring_col};">{rsi_num:.0f}</div>
              </div>
            </div>"""
        # ── MACD: mini histogram bars ────────────────────────────────────────
        elif label.startswith('MACD'):
            bar_color = '#ff5252' if badge_class == 'bearish' else '#00e676'
            heights = [30,45,55,68,78,88,95,100] if badge_class == 'bearish' else [100,90,75,60,48,35,22,12]
            hist_bars = ''.join(
                f'<div style="flex:1;height:{h}%;background:{bar_color};opacity:{0.4+i*0.075:.2f};'
                f'border-radius:2px 2px 0 0;min-width:3px;"></div>'
                for i,h in enumerate(heights)
            )
            extra_visual = f"""
            <div style="display:flex;align-items:flex-end;gap:2px;height:36px;padding:0 2px;margin:6px 0 8px;">
              {hist_bars}
            </div>"""
        # ── SMA: mini sparkline trend line ───────────────────────────────────
        elif label.startswith('SMA'):
            line_color = '#ff5252' if badge_class == 'bearish' else '#00e676'
            pts = "0,28 12,24 22,20 30,22 40,26 50,18 60,14 70,10 80,12 90,8 100,6" if badge_class == 'bullish' else "0,8 12,10 22,14 30,12 40,9 50,18 60,22 70,26 80,24 90,28 100,30"
            extra_visual = f"""
            <div style="height:32px;margin:6px 0 8px;position:relative;">
              <svg viewBox="0 0 100 32" preserveAspectRatio="none" style="width:100%;height:100%;overflow:visible;">
                <polyline points="{pts}" fill="none" stroke="{line_color}" stroke-width="1.8"
                  stroke-linejoin="round" opacity="0.7"/>
              </svg>
            </div>"""
        else:
            extra_visual = ''

        bg_map = {'bullish':'linear-gradient(145deg,rgba(10,30,20,0.9),rgba(4,14,10,0.95))',
                  'bearish':'linear-gradient(145deg,rgba(30,10,14,0.9),rgba(12,4,8,0.95))',
                  'neutral':'linear-gradient(145deg,rgba(28,22,8,0.9),rgba(12,10,4,0.95))'}
        card_bg = bg_map.get(badge_class, '#111827')

        return f"""
            <div class="g-compact" style="border-color:{border_color};background:{card_bg};">
                <div style="position:absolute;top:0;left:0;right:0;height:1px;
                  background:linear-gradient(90deg,transparent,{top_color},transparent);"></div>
                <div class="cc-top"><span class="cc-ico">{icon}</span><div class="cc-lbl">{label}</div>
                  <span class="tag {tag_cls}">{badge_text}</span></div>
                {extra_visual}
                <div class="cc-val">{value}</div>
                {f'<div class="cc-sub">{sub_text}</div>' if sub_text else ''}
                <div class="cc-bar"><div class="cc-bar-fill {bar_type}" style="width:{bar_pct:.1f}%"></div></div>
            </div>"""

    def _build_enhanced_oc_cards(self):
        """Enhanced Option Chain cards: PCR needle meter, Max Pain zone bar, CE/PE OI battle bars."""
        d = self.html_data
        if not d['has_option_data']:
            return '<div style="color:#80deea;padding:20px;">Option chain data unavailable</div>'

        pcr     = d['pcr']
        max_pain= d['max_pain']
        max_ce  = d['max_ce_oi']
        max_pe  = d['max_pe_oi']
        spot    = d['current_price']
        ce_pct  = d['ce_oi_pct']
        pe_pct  = d['pe_oi_pct']

        pcr_tag    = 'Bearish' if pcr < 0.7 else ('Bullish' if pcr > 1.2 else 'Neutral')
        pcr_col    = '#ff5252' if pcr < 0.7 else ('#00e676' if pcr > 1.2 else '#ffb74d')
        pcr_border = 'rgba(255,82,82,0.35)' if pcr < 0.7 else ('rgba(0,230,118,0.35)' if pcr > 1.2 else 'rgba(255,183,77,0.3)')
        pcr_tag_cls= 'tag-bear' if pcr < 0.7 else ('tag-bull' if pcr > 1.2 else 'tag-neu')
        pcr_needle_pct = round(min(97, max(3, pcr / 2.0 * 100)), 1)

        level_min = min(spot, max_pain) - 200
        level_max = max(spot, max_pain) + 200
        rng = level_max - level_min or 1
        spot_pct  = round((spot - level_min) / rng * 100, 1)
        pain_pct  = round((max_pain - level_min) / rng * 100, 1)
        pain_diff = int(max_pain - spot)
        pain_sign = '+' if pain_diff >= 0 else ''
        pain_col  = '#00e676' if pain_diff > 0 else '#ff5252'

        ce_oi_chg   = d.get('total_ce_oi_change', 0)
        pe_oi_chg   = d.get('total_pe_oi_change', 0)
        total_abs   = abs(ce_oi_chg) + abs(pe_oi_chg) or 1
        ce_bar_pct  = round(abs(ce_oi_chg) / total_abs * 100, 1)
        pe_bar_pct  = round(abs(pe_oi_chg) / total_abs * 100, 1)
        ce_chg_col  = '#ff5252' if ce_oi_chg > 0 else '#00e676'
        pe_chg_col  = '#00e676' if pe_oi_chg > 0 else '#ff5252'

        return f"""
        <!-- ── PCR Card ──────────────────────────────────────────────── -->
        <div class="g-compact" style="border-color:{pcr_border};background:linear-gradient(145deg,rgba(12,4,8,0.95),rgba(8,4,6,0.98));position:relative;overflow:hidden;">
          <div style="position:absolute;top:0;left:0;right:0;height:1px;
            background:linear-gradient(90deg,transparent,{pcr_col},transparent);"></div>
          <div class="cc-top">
            <span class="cc-ico">&#128308;</span>
            <div class="cc-lbl">PCR Ratio (OI)</div>
            <span class="tag {pcr_tag_cls}">{pcr_tag}</span>
          </div>
          <div class="cc-val" style="color:{pcr_col};">{pcr:.3f}</div>
          <div class="cc-sub">Put/Call OI Ratio</div>
          <div style="position:relative;margin:8px 0 4px;">
            <div style="height:8px;border-radius:4px;overflow:hidden;background:rgba(0,0,0,0.4);position:relative;">
              <div style="position:absolute;inset:0;border-radius:4px;
                background:linear-gradient(90deg,#ff3355 0%,#ff9900 35%,#ffcc00 50%,#88dd00 65%,#00e676 100%);opacity:0.75;"></div>
              <div style="position:absolute;left:35%;top:0;bottom:0;width:1px;background:rgba(255,255,255,0.4);"></div>
              <div style="position:absolute;left:60%;top:0;bottom:0;width:1px;background:rgba(255,255,255,0.4);"></div>
              <div style="position:absolute;top:-3px;left:{pcr_needle_pct}%;
                transform:translateX(-50%);width:3px;height:14px;
                background:white;border-radius:1.5px;box-shadow:0 0 8px white;"></div>
            </div>
            <div style="display:flex;justify-content:space-between;margin-top:4px;
              font-family:'JetBrains Mono',monospace;font-size:8px;">
              <span style="color:#ff5252;">&#60;0.7 Bear</span>
              <span style="color:rgba(180,210,230,0.35);">Neutral</span>
              <span style="color:#00e676;">&#62;1.2 Bull</span>
            </div>
          </div>
        </div>

        <!-- ── Max Pain Card ─────────────────────────────────────────── -->
        <div class="g-compact" style="border-color:rgba(255,183,77,0.3);background:linear-gradient(145deg,rgba(28,22,8,0.9),rgba(12,10,4,0.95));position:relative;overflow:hidden;">
          <div style="position:absolute;top:0;left:0;right:0;height:1px;
            background:linear-gradient(90deg,transparent,#ffb74d,transparent);"></div>
          <div class="cc-top">
            <span class="cc-ico">&#127919;</span>
            <div class="cc-lbl">Max Pain</div>
            <span class="tag tag-neu">Expiry Magnet</span>
          </div>
          <div class="cc-val" style="color:#ffb74d;">&#8377;{max_pain:,}</div>
          <div class="cc-sub">Price gravity level</div>
          <div style="position:relative;height:20px;border-radius:6px;overflow:hidden;
            background:linear-gradient(90deg,rgba(0,230,118,0.1),rgba(255,183,77,0.2),rgba(255,82,82,0.1));
            margin:8px 0 4px;">
            <div style="position:absolute;left:{pain_pct}%;top:50%;
              transform:translate(-50%,-50%);width:3px;height:16px;
              background:#ffb74d;box-shadow:0 0 8px #ffb74d;border-radius:1.5px;"></div>
            <div style="position:absolute;left:{spot_pct}%;top:50%;
              transform:translate(-50%,-50%);width:3px;height:16px;
              background:#4fc3f7;box-shadow:0 0 8px #4fc3f7;border-radius:1.5px;"></div>
          </div>
          <div style="display:flex;justify-content:space-between;font-family:'JetBrains Mono',monospace;font-size:8px;">
            <span style="color:#4fc3f7;">&#9632; Now &#8377;{spot:,.0f}</span>
            <span style="color:{pain_col};">{pain_sign}{pain_diff:,} pts to pain</span>
            <span style="color:#ffb74d;">&#9632; Pain &#8377;{max_pain:,}</span>
          </div>
        </div>

        <!-- ── Max CE OI (Resistance Wall) ──────────────────────────── -->
        <div class="g-compact" style="border-color:rgba(255,82,82,0.28);background:linear-gradient(145deg,rgba(30,10,14,0.9),rgba(12,4,8,0.95));position:relative;overflow:hidden;">
          <div style="position:absolute;top:0;left:0;right:0;height:1px;
            background:linear-gradient(90deg,transparent,#ff5252,transparent);"></div>
          <div class="cc-top">
            <span class="cc-ico">&#128308;</span>
            <div class="cc-lbl">Max Call OI</div>
            <span class="tag tag-bear">Resistance</span>
          </div>
          <div class="cc-val" style="color:#ff8899;">&#8377;{max_ce:,}</div>
          <div class="cc-sub">CE wall</div>
          <div style="margin-top:8px;">
            <div style="font-family:'JetBrains Mono',monospace;font-size:8px;letter-spacing:1.5px;
              color:rgba(120,160,180,0.4);text-transform:uppercase;margin-bottom:6px;">OI Change Today</div>
            <div style="display:flex;flex-direction:column;gap:5px;">
              <div style="display:flex;align-items:center;gap:7px;">
                <span style="font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;color:{ce_chg_col};width:22px;">CE</span>
                <div style="flex:1;height:5px;background:rgba(0,0,0,0.4);border-radius:3px;overflow:hidden;">
                  <div style="height:100%;width:{ce_bar_pct}%;border-radius:3px;background:linear-gradient(90deg,#ff5252,#ff6680);"></div>
                </div>
                <span style="font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;color:{ce_chg_col};width:30px;text-align:right;">{ce_bar_pct:.0f}%</span>
              </div>
              <div style="display:flex;align-items:center;gap:7px;">
                <span style="font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;color:{pe_chg_col};width:22px;">PE</span>
                <div style="flex:1;height:5px;background:rgba(0,0,0,0.4);border-radius:3px;overflow:hidden;">
                  <div style="height:100%;width:{pe_bar_pct}%;border-radius:3px;background:linear-gradient(90deg,#00e676,#44ffaa);"></div>
                </div>
                <span style="font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;color:{pe_chg_col};width:30px;text-align:right;">{pe_bar_pct:.0f}%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- ── Max PE OI (Support Floor) ────────────────────────────── -->
        <div class="g-compact" style="border-color:rgba(0,230,118,0.25);background:linear-gradient(145deg,rgba(10,30,20,0.9),rgba(4,14,10,0.95));position:relative;overflow:hidden;">
          <div style="position:absolute;top:0;left:0;right:0;height:1px;
            background:linear-gradient(90deg,transparent,#00e676,transparent);"></div>
          <div class="cc-top">
            <span class="cc-ico">&#128994;</span>
            <div class="cc-lbl">Max Put OI</div>
            <span class="tag tag-bull">Support</span>
          </div>
          <div class="cc-val" style="color:#44ffaa;">&#8377;{max_pe:,}</div>
          <div class="cc-sub">PE floor</div>
          <div style="margin-top:8px;">
            <div style="font-family:'JetBrains Mono',monospace;font-size:8px;letter-spacing:1.5px;
              color:rgba(120,160,180,0.4);text-transform:uppercase;margin-bottom:6px;">Total OI Ratio</div>
            <div style="display:flex;flex-direction:column;gap:5px;">
              <div style="display:flex;align-items:center;gap:7px;">
                <span style="font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;color:#ff8899;width:22px;">CE</span>
                <div style="flex:1;height:5px;background:rgba(0,0,0,0.4);border-radius:3px;overflow:hidden;">
                  <div style="height:100%;width:{ce_pct:.1f}%;border-radius:3px;background:linear-gradient(90deg,#ff5252,#ff6680);"></div>
                </div>
                <span style="font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;color:#ff8899;width:30px;text-align:right;">{ce_pct:.0f}%</span>
              </div>
              <div style="display:flex;align-items:center;gap:7px;">
                <span style="font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;color:#44ffaa;width:22px;">PE</span>
                <div style="flex:1;height:5px;background:rgba(0,0,0,0.4);border-radius:3px;overflow:hidden;">
                  <div style="height:100%;width:{pe_pct:.1f}%;border-radius:3px;background:linear-gradient(90deg,#00e676,#44ffaa);"></div>
                </div>
                <span style="font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;color:#44ffaa;width:30px;text-align:right;">{pe_pct:.0f}%</span>
              </div>
            </div>
          </div>
        </div>"""

    def _signal_summary_bar_html(self):
        d = self.html_data

        # ── 1. OI Signal ──────────────────────────────────────────────────
        oi_cls = d.get('oi_class', 'neutral') if d.get('has_option_data') else 'neutral'
        if   oi_cls == 'bullish':  oi_score=1;  oi_lbl='Bullish';  oi_sub='Put build dominant';       oi_col='#00e676'; oi_bg='rgba(0,230,118,0.12)';  oi_bdr='rgba(0,230,118,0.3)';  oi_arrow='&#9651;'
        elif oi_cls == 'bearish':  oi_score=-1; oi_lbl='Bearish';  oi_sub='Call build dominant';      oi_col='#ff4757'; oi_bg='rgba(255,71,87,0.12)';  oi_bdr='rgba(255,71,87,0.3)';  oi_arrow='&#9661;'
        else:                      oi_score=0;  oi_lbl='Neutral';  oi_sub='Both sides building';      oi_col='#ffb74d'; oi_bg='rgba(255,183,77,0.10)'; oi_bdr='rgba(255,183,77,0.25)'; oi_arrow='&#9711;'

        # ── 2. FII/DII Signal ─────────────────────────────────────────────
        fii_summ  = d.get('fii_dii_summ', {})
        fii_badge = fii_summ.get('badge_cls', 'fii-neu')
        fii_label = fii_summ.get('label', 'Neutral')
        fii_avg   = fii_summ.get('fii_avg', 0)
        dii_avg   = fii_summ.get('dii_avg', 0)
        if   fii_badge in ('fii-bull',):  fii_score=1;  fii_col='#00e676'; fii_bg='rgba(0,230,118,0.12)';   fii_bdr='rgba(0,230,118,0.3)';   fii_arrow='&#9651;'
        elif fii_badge in ('fii-cbull',): fii_score=1;  fii_col='#69f0ae'; fii_bg='rgba(105,240,174,0.10)'; fii_bdr='rgba(105,240,174,0.28)'; fii_arrow='&#9651;'
        elif fii_badge in ('fii-bear',):  fii_score=-1; fii_col='#ff4757'; fii_bg='rgba(255,71,87,0.12)';   fii_bdr='rgba(255,71,87,0.3)';   fii_arrow='&#9661;'
        else:                             fii_score=0;  fii_col='#ffb74d'; fii_bg='rgba(255,183,77,0.10)';  fii_bdr='rgba(255,183,77,0.25)'; fii_arrow='&#9711;'
        fii_sub = f"FII {'+' if fii_avg>=0 else ''}{fii_avg:,.0f} / DII {'+' if dii_avg>=0 else ''}{dii_avg:,.0f}"

        # ── 3. Technical Signal ───────────────────────────────────────────
        bias       = d.get('bias', 'SIDEWAYS')
        bull_score = d.get('bullish_score', 0)
        bear_score = d.get('bearish_score', 0)
        score_diff = bull_score - bear_score
        if   bias in ('BULLISH',):    tech_score=1;  tech_lbl='Bullish';    tech_col='#00e676'; tech_bg='rgba(0,230,118,0.12)';   tech_bdr='rgba(0,230,118,0.3)';   tech_arrow='&#9651;'
        elif bias in ('WATCH BULL',): tech_score=1;  tech_lbl='Watch Bull'; tech_col='#b5ea3a'; tech_bg='rgba(181,234,58,0.10)';  tech_bdr='rgba(181,234,58,0.28)'; tech_arrow='&#9651;'
        elif bias in ('BEARISH',):    tech_score=-1; tech_lbl='Bearish';    tech_col='#ff4757'; tech_bg='rgba(255,71,87,0.12)';   tech_bdr='rgba(255,71,87,0.3)';   tech_arrow='&#9661;'
        elif bias in ('WATCH BEAR',): tech_score=-1; tech_lbl='Watch Bear'; tech_col='#ff9800'; tech_bg='rgba(255,152,0,0.10)';   tech_bdr='rgba(255,152,0,0.28)';  tech_arrow='&#9661;'
        else:                         tech_score=0;  tech_lbl='Sideways';   tech_col='#ffb74d'; tech_bg='rgba(255,183,77,0.10)';  tech_bdr='rgba(255,183,77,0.25)'; tech_arrow='&#8596;'
        tech_sub = f"Score {score_diff:+d} / {bull_score+bear_score} signals"

        # ── 4. Strategy Checklist Score ───────────────────────────────────
        # Re-derive from existing html_data fields (same data checklist uses)
        pcr_val  = d.get('pcr') if d.get('has_option_data') else None
        rsi_val  = d.get('rsi')
        macd_b   = d.get('macd_bullish')
        sma20    = d.get('sma_20_above')
        sma50    = d.get('sma_50_above')
        sma200   = d.get('sma_200_above')
        oi_dir   = d.get('oi_class') if d.get('has_option_data') else None
        strat_sc = 0
        if pcr_val is not None:
            if   pcr_val > 1.5: strat_sc += 2
            elif pcr_val > 1.2: strat_sc += 1
            elif pcr_val < 0.5: strat_sc -= 2
            elif pcr_val < 0.8: strat_sc -= 1
        if rsi_val is not None:
            if   rsi_val > 70:  strat_sc -= 1
            elif rsi_val < 30:  strat_sc += 2
            elif rsi_val >= 55: strat_sc += 1
            elif rsi_val <= 45: strat_sc -= 1
        if macd_b is not None: strat_sc += 1 if macd_b else -1
        trend_pts = sum([1 if x else -1 for x in [sma20, sma50, sma200] if x is not None])
        strat_sc += (1 if trend_pts > 0 else -1 if trend_pts < 0 else 0)
        if oi_dir == 'bullish':  strat_sc += 1
        elif oi_dir == 'bearish': strat_sc -= 1
        if   strat_sc >= 3:  strat_score=1;  strat_lbl='Strong Bull'; strat_col='#00e676'; strat_bg='rgba(0,230,118,0.12)';  strat_bdr='rgba(0,230,118,0.3)';  strat_arrow='&#9651;'
        elif strat_sc >= 1:  strat_score=1;  strat_lbl='Mild Bull';   strat_col='#69f0ae'; strat_bg='rgba(105,240,174,0.10)';strat_bdr='rgba(105,240,174,0.28)';strat_arrow='&#9651;'
        elif strat_sc <= -3: strat_score=-1; strat_lbl='Strong Bear'; strat_col='#ff4757'; strat_bg='rgba(255,71,87,0.12)';  strat_bdr='rgba(255,71,87,0.3)';  strat_arrow='&#9661;'
        elif strat_sc <= -1: strat_score=-1; strat_lbl='Mild Bear';   strat_col='#fca5a5'; strat_bg='rgba(252,165,165,0.10)';strat_bdr='rgba(252,165,165,0.25)';strat_arrow='&#9661;'
        else:                strat_score=0;  strat_lbl='Neutral';     strat_col='#ffb74d'; strat_bg='rgba(255,183,77,0.10)'; strat_bdr='rgba(255,183,77,0.25)'; strat_arrow='&#9711;'
        strat_sub = f"Score {strat_sc:+d} / 5 factors"

        # ── 5. PCR Signal ─────────────────────────────────────────────────
        pcr_disp = d.get('pcr', 0) if d.get('has_option_data') else None
        if pcr_disp is not None:
            if   pcr_disp > 1.5: pcr_score=1;  pcr_lbl=f'{pcr_disp:.2f}'; pcr_sub='Strongly Bullish';  pcr_col='#00e676'; pcr_bg='rgba(0,230,118,0.12)';  pcr_bdr='rgba(0,230,118,0.3)'
            elif pcr_disp > 1.2: pcr_score=1;  pcr_lbl=f'{pcr_disp:.2f}'; pcr_sub='Bullish (>1.2)';    pcr_col='#69f0ae'; pcr_bg='rgba(105,240,174,0.10)';pcr_bdr='rgba(105,240,174,0.28)'
            elif pcr_disp < 0.5: pcr_score=-1; pcr_lbl=f'{pcr_disp:.2f}'; pcr_sub='Strongly Bearish';  pcr_col='#ff4757'; pcr_bg='rgba(255,71,87,0.12)';  pcr_bdr='rgba(255,71,87,0.3)'
            elif pcr_disp < 0.8: pcr_score=-1; pcr_lbl=f'{pcr_disp:.2f}'; pcr_sub='Bearish (<0.8)';    pcr_col='#ff9999'; pcr_bg='rgba(255,71,87,0.08)';  pcr_bdr='rgba(255,71,87,0.2)'
            else:                pcr_score=0;  pcr_lbl=f'{pcr_disp:.2f}'; pcr_sub='Neutral (0.8-1.2)'; pcr_col='#ffb74d'; pcr_bg='rgba(255,183,77,0.10)'; pcr_bdr='rgba(255,183,77,0.25)'
        else:
            pcr_score=0; pcr_lbl='N/A'; pcr_sub='No option data'; pcr_col='#8faabe'; pcr_bg='rgba(143,170,190,0.08)'; pcr_bdr='rgba(143,170,190,0.2)'

        # ── Overall Verdict ───────────────────────────────────────────────
        scores     = [oi_score, fii_score, tech_score, strat_score, pcr_score]
        bull_count = sum(1 for s in scores if s > 0)
        bear_count = sum(1 for s in scores if s < 0)
        neu_count  = sum(1 for s in scores if s == 0)
        total      = len(scores)
        bull_pct   = round(bull_count / total * 100)
        bear_pct   = round(bear_count / total * 100)

        if   bull_count >= 4: vrd_lbl='STRONGLY BULLISH'; vrd_col='#00e676'; vrd_bg='rgba(0,230,118,0.08)';  vrd_bdr='#00e676';  vrd_lbdr='rgba(0,230,118,0.6)'
        elif bull_count == 3: vrd_lbl='BULLISH';          vrd_col='#00e676'; vrd_bg='rgba(0,230,118,0.06)';  vrd_bdr='#00e676';  vrd_lbdr='rgba(0,230,118,0.5)'
        elif bull_count == 2 and bear_count == 0: vrd_lbl='CAUTIOUSLY BULLISH'; vrd_col='#69f0ae'; vrd_bg='rgba(105,240,174,0.06)'; vrd_bdr='#69f0ae'; vrd_lbdr='rgba(105,240,174,0.4)'
        elif bear_count >= 4: vrd_lbl='STRONGLY BEARISH'; vrd_col='#ff4757'; vrd_bg='rgba(255,71,87,0.08)';  vrd_bdr='#ff4757';  vrd_lbdr='rgba(255,71,87,0.6)'
        elif bear_count == 3: vrd_lbl='BEARISH';          vrd_col='#ff4757'; vrd_bg='rgba(255,71,87,0.06)';  vrd_bdr='#ff4757';  vrd_lbdr='rgba(255,71,87,0.5)'
        elif bear_count == 2 and bull_count == 0: vrd_lbl='CAUTIOUSLY BEARISH'; vrd_col='#fca5a5'; vrd_bg='rgba(252,165,165,0.06)'; vrd_bdr='#fca5a5'; vrd_lbdr='rgba(252,165,165,0.4)'
        else:                 vrd_lbl='NEUTRAL';          vrd_col='#ffb74d'; vrd_bg='rgba(255,183,77,0.06)'; vrd_bdr='#ffb74d';  vrd_lbdr='rgba(255,183,77,0.4)'

        # ── Dot indicators ────────────────────────────────────────────────
        dot_scores = [
            (oi_score,    'OI'),
            (fii_score,   'FII/DII'),
            (tech_score,  'Technical'),
            (strat_score, 'Strategy'),
            (pcr_score,   'PCR'),
        ]
        dots_html = ''
        for sc, name in dot_scores:
            if   sc > 0:  dc='#00e676'
            elif sc < 0:  dc='#ff4757'
            else:          dc='rgba(255,255,255,0.12)'
            dots_html += f'<div class="ssb-dot" style="background:{dc};" title="{name}"></div>'

        # ── Build one cell ────────────────────────────────────────────────
        def cell(lbl, badge_lbl, arrow, col, bg, bdr, sub):
            return (
                f'<div class="ssb-cell">'
                f'<span class="ssb-cell-lbl">{lbl}</span>'
                f'<span class="ssb-badge" style="color:{col};background:{bg};border:1px solid {bdr};">'
                f'{arrow} {badge_lbl}</span>'
                f'<span class="ssb-sub">{sub}</span>'
                f'</div>'
            )

        ts = d.get('timestamp', '')

        return f"""
<div class="section ssb-section" id="sec-signals">
  <div class="ssb-wrap">
    <div class="ssb-header">
      <span class="ssb-title">&#9889; SIGNAL SUMMARY</span>
      <span class="ssb-ts">{ts}</span>
    </div>
    <div class="ssb-grid">
      {cell('OI Signal',   oi_lbl,    oi_arrow,    oi_col,    oi_bg,    oi_bdr,    d.get('oi_signal','—') if d.get('has_option_data') else 'No data')}
      {cell('FII / DII',   fii_label, fii_arrow,   fii_col,   fii_bg,   fii_bdr,   fii_sub)}
      {cell('Technical',   tech_lbl,  tech_arrow,  tech_col,  tech_bg,  tech_bdr,  tech_sub)}
      {cell('Strategy',    strat_lbl, strat_arrow, strat_col, strat_bg, strat_bdr, strat_sub)}
      {cell('PCR',         pcr_lbl,   '',          pcr_col,   pcr_bg,   pcr_bdr,   pcr_sub)}
      <div class="ssb-verdict" style="background:{vrd_bg};border-left:3px solid {vrd_lbdr};">
        <span class="ssb-verdict-lbl" style="color:#80deea;">Overall Verdict</span>
        <span class="ssb-verdict-val" style="color:{vrd_col};">{vrd_lbl}</span>
        <div class="ssb-score-dots">{dots_html}</div>
        <div class="ssb-bar-wrap">
          <div class="ssb-bar-lbl">
            <span style="color:rgba(0,230,118,0.6);">Bull {bull_count}</span>
            <span style="color:rgba(255,183,77,0.5);">Neu {neu_count}</span>
            <span style="color:rgba(255,71,87,0.6);">Bear {bear_count}</span>
          </div>
          <div class="ssb-bar-track">
            <div style="height:100%;width:{bull_pct}%;background:#00e676;border-radius:2px;display:inline-block;"></div>
            <div style="height:100%;width:{bear_pct}%;background:#ff4757;border-radius:2px;float:right;"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
"""

    def _market_direction_widget_html(self):
        d          = self.html_data
        bias       = d['bias']
        confidence = d['confidence']
        bull_score = d['bullish_score']
        bear_score = d['bearish_score']

        if bias == 'BULLISH':
            dir_gradient  = 'linear-gradient(135deg,#00ff88,#00d4ff)'
            needle_rotate = '-60'
            widget_border = 'rgba(0,255,136,0.3)'
            top_line      = 'rgba(0,255,136,0.8)'
            pulse_color   = '#00ff88'
            score_color   = '#00ff88'
        elif bias == 'WATCH BULL':
            dir_gradient  = 'linear-gradient(135deg,#b5ea3a,#00d4ff)'
            needle_rotate = '-30'
            widget_border = 'rgba(181,234,58,0.35)'
            top_line      = 'rgba(181,234,58,0.8)'
            pulse_color   = '#b5ea3a'
            score_color   = '#b5ea3a'
        elif bias == 'WATCH BEAR':
            dir_gradient  = 'linear-gradient(135deg,#ff9800,#ff3355)'
            needle_rotate = '30'
            widget_border = 'rgba(255,152,0,0.35)'
            top_line      = 'rgba(255,152,0,0.8)'
            pulse_color   = '#ff9800'
            score_color   = '#ff9800'
        elif bias == 'BEARISH':
            dir_gradient  = 'linear-gradient(135deg,#ff3355,#ff9900)'
            needle_rotate = '60'
            widget_border = 'rgba(255,51,85,0.3)'
            top_line      = 'rgba(255,51,85,0.8)'
            pulse_color   = '#ff3355'
            score_color   = '#ff5252'
        else:
            dir_gradient  = 'linear-gradient(135deg,#ffcd3c,#f7931e)'
            needle_rotate = '0'
            widget_border = 'rgba(255,183,77,0.3)'
            top_line      = 'rgba(255,183,77,0.8)'
            pulse_color   = '#ffb74d'
            score_color   = '#ffb74d'

        total_score = bull_score - bear_score
        score_sign  = '+' if total_score > 0 else ''
        conf_cls    = ('md-pill-conf-high' if confidence == 'HIGH' else
                       'md-pill-conf-med'  if confidence == 'MEDIUM' else 'md-pill-conf-low')

        # ── Signal breakdown rows ────────────────────────────────────────────
        signals_meta = [
            ('SMA 20',  d.get('sma_20_above'),  'sma'),
            ('SMA 50',  d.get('sma_50_above'),  'sma'),
            ('SMA 200', d.get('sma_200_above'), 'sma'),
            ('RSI',     None,                   'rsi'),
            ('MACD',    d.get('macd_bullish'),  'macd'),
            ('PCR',     None,                   'pcr'),
        ]
        sig_rows_html = ''
        for name, is_bull, kind in signals_meta:
            if kind == 'rsi':
                rsi = d.get('rsi', 50)
                is_bull = rsi < 40; is_bear = rsi > 70
                score_val = '+1' if is_bull else ('-1' if is_bear else '0')
                bar_w = 45 if not is_bull and not is_bear else 80
                bar_cls = 'bull' if is_bull else ('bear' if is_bear else 'neutral')
                val_col = '#00ff88' if is_bull else ('#ff5252' if is_bear else '#ffb74d')
            elif kind == 'pcr':
                pcr = d.get('pcr', 1.0)
                is_bull = pcr > 1.2; is_bear = pcr < 0.7
                score_val = '+1' if is_bull else ('-1' if is_bear else '0')
                bar_w = 45 if not is_bull and not is_bear else 85
                bar_cls = 'bull' if is_bull else ('bear' if is_bear else 'neutral')
                val_col = '#00ff88' if is_bull else ('#ff5252' if is_bear else '#ffb74d')
            else:
                score_val = '+1' if is_bull else '-1'
                bar_w = 80; bar_cls = 'bull' if is_bull else 'bear'
                val_col = '#00ff88' if is_bull else '#ff5252'
            bar_color_css = (
                'linear-gradient(90deg,#00ff88,#00d4ff)' if bar_cls == 'bull' else
                'linear-gradient(90deg,#ff3355,#ff6680)' if bar_cls == 'bear' else
                'linear-gradient(90deg,#ffb74d,#ffdd66)'
            )
            sig_rows_html += f"""
            <div style="display:flex;align-items:center;gap:8px;">
              <span style="font-size:9px;letter-spacing:1px;color:rgba(180,210,230,0.55);width:48px;text-align:right;flex-shrink:0;">{name}</span>
              <div style="flex:1;height:5px;background:rgba(0,0,0,0.4);border-radius:3px;overflow:hidden;">
                <div style="height:100%;width:{bar_w}%;border-radius:3px;background:{bar_color_css};"></div>
              </div>
              <span style="font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;color:{val_col};width:22px;flex-shrink:0;">{score_val}</span>
            </div>"""

        # ── SVG needle angle: bear_score−bull_score mapped to ±80deg ────────
        max_s       = max(bull_score + bear_score, 1)
        needle_deg  = round(max(-80, min(80, (bear_score - bull_score) / max_s * 80)))

        # ── Confidence dots ──────────────────────────────────────────────────
        filled = 5 if confidence == 'HIGH' else 3 if confidence == 'MEDIUM' else 1
        dots_html = (
            ''.join(f'<div style="width:9px;height:9px;border-radius:50%;background:{pulse_color};box-shadow:0 0 6px {pulse_color};"></div>' for _ in range(filled)) +
            ''.join(f'<div style="width:9px;height:9px;border-radius:50%;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.1);"></div>' for _ in range(5 - filled))
        )

        # ── Neutral S1/R1 panel (only shown when bias is NEUTRAL) ───────────
        if bias not in ('BULLISH', 'BEARISH'):
            cp        = float(d.get('current_price') or 0)
            s1        = float(d['support'])    if d.get('support')    is not None else 0.0
            r1        = float(d['resistance']) if d.get('resistance') is not None else 0.0
            pts_to_s1 = round(cp - s1)   if s1 > 0 else None
            pts_to_r1 = round(r1 - cp)   if r1 > 0 else None
            # Proximity hint: which level is price closer to?
            if pts_to_s1 is not None and pts_to_r1 is not None:
                if pts_to_s1 < pts_to_r1:
                    proximity_hint = '&#9660; Closer to S1 — watch for bounce or breakdown'
                    hint_col = '#00e676'
                elif pts_to_r1 < pts_to_s1:
                    proximity_hint = '&#9650; Closer to R1 — watch for breakout or rejection'
                    hint_col = '#ff4d6d'
                else:
                    proximity_hint = '&#8596; Midway between S1 and R1'
                    hint_col = '#ffb74d'
            else:
                proximity_hint = ''
                hint_col = '#ffb74d'
            dist_s1_html = (f'<span style="font-size:9px;color:rgba(0,230,118,0.55);">{pts_to_s1} pts away</span>'
                            if pts_to_s1 is not None else '')
            dist_r1_html = (f'<span style="font-size:9px;color:rgba(255,77,109,0.55);">{pts_to_r1} pts away</span>'
                            if pts_to_r1 is not None else '')
            s1_display = f'&#8377;{s1:,.0f}' if s1 > 0 else 'N/A'
            r1_display = f'&#8377;{r1:,.0f}' if r1 > 0 else 'N/A'
            neutral_sr_html = f"""
                <div style="margin-top:6px;width:100%;display:flex;align-items:center;gap:6px;justify-content:center;flex-wrap:wrap;">
                  <div style="display:flex;align-items:center;gap:5px;padding:4px 10px;border-radius:6px;
                    background:rgba(0,230,118,0.07);border:1px solid rgba(0,230,118,0.2);">
                    <span style="font-size:8px;font-weight:700;color:rgba(0,230,118,0.6);letter-spacing:1px;">S1</span>
                    <span style="font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;color:#00e676;">{s1_display}</span>
                    {f'<span style="font-size:8px;color:rgba(0,230,118,0.45);">{pts_to_s1}pt</span>' if pts_to_s1 else ''}
                  </div>
                  <span style="font-size:9px;color:rgba(120,160,180,0.3);">·</span>
                  <div style="display:flex;align-items:center;gap:5px;padding:4px 10px;border-radius:6px;
                    background:rgba(255,77,109,0.07);border:1px solid rgba(255,77,109,0.2);">
                    <span style="font-size:8px;font-weight:700;color:rgba(255,77,109,0.6);letter-spacing:1px;">R1</span>
                    <span style="font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;color:#ff4d6d;">{r1_display}</span>
                    {f'<span style="font-size:8px;color:rgba(255,77,109,0.45);">{pts_to_r1}pt</span>' if pts_to_r1 else ''}
                  </div>
                  <div style="width:100%;text-align:center;font-size:8px;font-family:'JetBrains Mono',monospace;
                    color:{hint_col};opacity:0.75;margin-top:2px;">{proximity_hint}</div>
                </div>"""
        else:
            neutral_sr_html = ''  # Not NEUTRAL — show nothing

        return f"""
    <div class="section">
        <div class="section-title"><span>&#129517;</span> MARKET DIRECTION (Algorithmic)</div>

        <!-- Price Ticker Strip — compact -->
        <div style="background:linear-gradient(135deg,rgba(8,24,44,0.95),rgba(4,14,26,0.98));
          border:1px solid {widget_border};border-radius:14px;padding:8px 16px;
          display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;
          margin-bottom:12px;position:relative;overflow:hidden;">
          <div style="position:absolute;top:0;left:0;right:0;height:2px;
            background:linear-gradient(90deg,transparent,{top_line},transparent);"></div>
          <div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:7px;letter-spacing:2px;
              color:rgba(120,160,180,0.45);text-transform:uppercase;margin-bottom:2px;">NIFTY 50 · SPOT PRICE</div>
            <div style="display:flex;align-items:baseline;gap:10px;">
              <span style="font-family:'Orbitron',monospace;font-size:clamp(18px,2.8vw,26px);font-weight:900;
                color:{score_color};line-height:1;">&#8377;{d['current_price']:,.2f}</span>
              <span style="font-family:'JetBrains Mono',monospace;font-size:11px;color:rgba(180,210,230,0.5);">
                ATM &#8377;{d['atm_strike']:,} &nbsp;·&nbsp; {d.get('expiry','N/A')}</span>
            </div>
          </div>
          <div style="display:flex;gap:16px;flex-wrap:wrap;">
            {''.join([
              f'<div style="text-align:center;">'
              f'<div style="font-family:JetBrains Mono,monospace;font-size:7px;letter-spacing:1.5px;'
              f'color:rgba(120,160,180,0.4);text-transform:uppercase;margin-bottom:2px;">{lbl}</div>'
              f'<div style="font-family:Orbitron,monospace;font-size:12px;font-weight:700;color:{col};">{val}</div>'
              f'</div>'
              for lbl, val, col in [
                ('PCR (OI)', f"{d.get('pcr',0):.3f}" if d.get('has_option_data') else 'N/A',
                 '#ff5252' if d.get('pcr',1)<0.7 else '#00e676' if d.get('pcr',1)>1.2 else '#ffb74d'),
                ('Max Pain', f"&#8377;{d.get('max_pain',0):,}" if d.get('has_option_data') else 'N/A', '#ffb74d'),
                ('RSI (14)', f"{d.get('rsi',0):.1f}", '#ffb74d'),
                ('MACD', 'Bullish' if d.get('macd_bullish') else 'Bearish',
                 '#00e676' if d.get('macd_bullish') else '#ff5252'),
              ]
            ])}
          </div>
        </div>

        <!-- Main Direction Widget -->
        <div class="md-widget" style="border-color:{widget_border};">
            <div class="md-glow"></div>
            <div class="md-row-top">
                <div class="md-label">
                  <div class="md-live-dot" style="background:{pulse_color};box-shadow:0 0 8px {pulse_color};"></div>
                  MARKET DIRECTION &nbsp;·&nbsp; ALGORITHMIC
                </div>
                <div class="md-pills-top">
                  <span class="md-pill md-pill-bull">BULL {bull_score}</span>
                  <span class="md-pill md-pill-bear">BEAR {bear_score}</span>
                  <span class="md-pill {conf_cls}">{confidence} CONFIDENCE</span>
                </div>
            </div>

            <!-- Direction + Dial + Signals grid — compact -->
            <div style="display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center;margin-top:8px;">

              <!-- Left: Direction label + score + confidence dots -->
              <div style="display:flex;flex-direction:column;gap:5px;">
                <div class="md-direction" style="background:{dir_gradient};
                  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">
                  {bias}</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:rgba(180,210,230,0.4);">
                  Score: <span style="color:{score_color};font-weight:700;">{score_sign}{total_score}</span>
                  / {bull_score + bear_score} signals
                </div>
                <div style="display:flex;align-items:center;gap:5px;">
                  <span style="font-family:'JetBrains Mono',monospace;font-size:7px;letter-spacing:2px;
                    color:rgba(120,160,180,0.35);text-transform:uppercase;">Conf</span>
                  {dots_html}
                </div>
              </div>

              <!-- Centre: SVG Sentiment Dial — smaller -->
              <div style="display:flex;flex-direction:column;align-items:center;gap:2px;">
                <div style="font-family:'JetBrains Mono',monospace;font-size:7px;letter-spacing:1.5px;
                  color:rgba(120,160,180,0.35);text-transform:uppercase;">Sentiment</div>
                <svg width="110" height="65" viewBox="0 0 160 95" style="overflow:visible;">
                  <defs>
                    <linearGradient id="gaugeGradMD" x1="0%" y1="0%" x2="100%" y2="0%">
                      <stop offset="0%" stop-color="#00ff88"/>
                      <stop offset="45%" stop-color="#ffaa00"/>
                      <stop offset="100%" stop-color="#ff3355"/>
                    </linearGradient>
                  </defs>
                  <path d="M 15 82 A 65 65 0 0 1 145 82" fill="none"
                    stroke="rgba(255,255,255,0.06)" stroke-width="10" stroke-linecap="round"/>
                  <path d="M 15 82 A 65 65 0 0 1 145 82" fill="none"
                    stroke="url(#gaugeGradMD)" stroke-width="10" stroke-linecap="round" opacity="0.65"/>
                  <g style="transform:rotate({needle_deg}deg);transform-origin:80px 82px;">
                    <line x1="80" y1="82" x2="80" y2="28" stroke="{score_color}"
                      stroke-width="2.5" stroke-linecap="round"/>
                    <circle cx="80" cy="82" r="6" fill="{score_color}"
                      stroke="rgba(2,12,20,0.9)" stroke-width="2"/>
                    <circle cx="80" cy="82" r="2.5" fill="white"/>
                  </g>
                  <text x="10" y="96" fill="#00ff88" font-size="8"
                    font-family="JetBrains Mono" font-weight="700">BULL</text>
                  <text x="126" y="96" fill="#ff3355" font-size="8"
                    font-family="JetBrains Mono" font-weight="700">BEAR</text>
                </svg>
                <div style="text-align:center;margin-top:-2px;">
                  <div style="font-family:'Orbitron',monospace;font-size:18px;font-weight:900;
                    color:{score_color};line-height:1;">{score_sign}{total_score}</div>
                  <div style="font-family:'JetBrains Mono',monospace;font-size:7px;letter-spacing:1.5px;
                    color:rgba(120,160,180,0.35);text-transform:uppercase;">Score</div>
                </div>
                {neutral_sr_html}
              </div>

              <!-- Right: Signal breakdown bars — compact gaps -->
              <div style="display:flex;flex-direction:column;gap:5px;">
                <div style="font-family:'JetBrains Mono',monospace;font-size:7px;letter-spacing:1.5px;
                  color:rgba(120,160,180,0.4);text-transform:uppercase;margin-bottom:2px;">
                  Signal Breakdown</div>
                {sig_rows_html}
              </div>
            </div>
        </div>

        <!-- Scoring logic — compact single line -->
        <div style="margin-top:10px;padding:7px 14px;background:rgba(0,0,0,0.2);border:1px solid rgba(79,195,247,0.07);
          border-radius:8px;display:flex;gap:16px;flex-wrap:wrap;align-items:center;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:8px;letter-spacing:1.5px;
              color:rgba(79,195,247,0.5);text-transform:uppercase;font-weight:700;flex-shrink:0;">Scoring Logic</span>
            <span style="font-size:9px;color:rgba(176,190,197,0.5);"><span style="color:#00ff88;font-weight:700;">BULLISH</span> &nbsp;Diff &ge; +3</span>
            <span style="font-size:9px;color:rgba(176,190,197,0.5);"><span style="color:#ff5252;font-weight:700;">BEARISH</span> &nbsp;Diff &le; &minus;3</span>
            <span style="font-size:9px;color:rgba(176,190,197,0.5);"><span style="color:#ffb74d;font-weight:700;">SIDEWAYS</span> &nbsp;&minus;2 to +2</span>
            <span style="font-size:9px;color:rgba(176,190,197,0.5);"><span style="color:#4fc3f7;font-weight:700;">CONF</span> &nbsp;HIGH &ge; 4 gap &nbsp;&middot;&nbsp; OI: ATM &plusmn;10 only</span>
        </div>
    </div>
"""

    def _fiidii_section_html(self):
        data = self.html_data['fii_dii_data']
        summ = self.html_data['fii_dii_summ']
        badge_map = {
            'fii-bull':  ('#00e676','rgba(0,230,118,0.12)','rgba(0,230,118,0.3)'),
            'fii-cbull': ('#69f0ae','rgba(105,240,174,0.10)','rgba(105,240,174,0.28)'),
            'fii-neu':   ('#ffd740','rgba(255,215,64,0.10)','rgba(255,215,64,0.28)'),
            'fii-bear':  ('#ff5252','rgba(255,82,82,0.10)','rgba(255,82,82,0.28)'),
        }
        s_color,s_bg,s_border = badge_map.get(summ['badge_cls'],badge_map['fii-neu'])
        is_fallback = any(r.get('fallback') for r in data)
        date_range  = f"{data[0]['date']} \u2013 {data[-1]['date']}" if data else ''
        data_src_html = ('<span class="pf-live-badge pf-estimated">\u26a0 ESTIMATED</span>'
                         if is_fallback else '<span class="pf-live-badge pf-live">\u25cf LIVE</span>')
        max_abs = summ['max_abs'] or 1

        # ── Avg values ────────────────────────────────────────────────────
        fa=summ['fii_avg']; da=summ['dii_avg']; na=summ['net_avg']
        fs='+' if fa>=0 else ''; ds='+' if da>=0 else ''; ns='+' if na>=0 else ''
        fc='#00d4ff' if fa>=0 else '#ff4444'
        dc='#ffb300' if da>=0 else '#ff4444'
        nc='#c084fc' if na>=0 else '#f87171'

        # ── FII bar width (capped at 100%) ────────────────────────────────
        fii_bar_w = round(min(100, abs(fa) / max_abs * 100), 1)
        dii_bar_w = round(min(100, abs(da) / max_abs * 100), 1)
        fii_bar_col = '#ff4444' if fa < 0 else '#00d4ff'
        dii_bar_col = '#ffb300' if da >= 0 else '#ff4444'

        # ── Daily dot chips (10 days) ─────────────────────────────────────
        dots_html = ''
        for row in data:
            net_v = row['fii'] + row['dii']
            dot_col  = '#00e676' if net_v >= 0 else '#ff4757'
            dot_bg   = 'rgba(0,230,118,0.15)' if net_v >= 0 else 'rgba(255,71,87,0.15)'
            dot_bdr  = 'rgba(0,230,118,0.3)'  if net_v >= 0 else 'rgba(255,71,87,0.3)'
            net_sign = '+' if net_v >= 0 else ''
            net_fmt  = f"{net_v/1000:+.1f}k" if abs(net_v) >= 1000 else f"{net_sign}{net_v:.0f}"
            dots_html += (
                f'<div class="pf2-dot" style="border-color:{dot_bdr};background:{dot_bg};">'
                f'<div class="pf2-dot-date">{row["date"].split(" ")[1]}</div>'
                f'<div class="pf2-dot-net" style="color:{dot_col};">{net_fmt}</div>'
                f'</div>'
            )

        verdict_badge = (f'<span class="pf-verdict-badge" style="color:{s_color};background:{s_bg};border:1px solid {s_border};">'
                         f'{summ["emoji"]} {summ["label"]}</span>')
        n_days = len(data)

        return f"""
<div class="section">
    <div class="section-title">
        <span>&#127982;</span> FII / DII INSTITUTIONAL FLOW
        {data_src_html}
        <span class="pf-date-range">Last {n_days} Trading Days &nbsp;&middot;&nbsp; {date_range}</span>
    </div>

    <!-- FII Flow Meter -->
    <div class="pf2-meter-row">
        <div class="pf2-meter-head">
            <div class="pf2-meter-labels">
                <span class="pf2-lbl">FII</span>
                <span class="pf2-sublbl">{('Sellers' if fa < 0 else 'Buyers')}</span>
            </div>
            <span class="pf2-val" style="color:{fc};">{fs}{fa:,.0f} <span class="pf2-unit">Cr/day avg</span></span>
        </div>
        <div class="pf2-track">
            <div class="pf2-fill" style="width:{fii_bar_w}%;background:{fii_bar_col};{'float:right;' if fa < 0 else ''}"></div>
        </div>
    </div>

    <!-- DII Flow Meter -->
    <div class="pf2-meter-row">
        <div class="pf2-meter-head">
            <div class="pf2-meter-labels">
                <span class="pf2-lbl">DII</span>
                <span class="pf2-sublbl">{('Buyers' if da >= 0 else 'Sellers')}</span>
            </div>
            <span class="pf2-val" style="color:{dc};">{ds}{da:,.0f} <span class="pf2-unit">Cr/day avg</span></span>
        </div>
        <div class="pf2-track">
            <div class="pf2-fill" style="width:{dii_bar_w}%;background:{dii_bar_col};"></div>
        </div>
    </div>

    <!-- Daily net dot chips -->
    <div class="pf2-dots-wrap">{dots_html}</div>

    <!-- Avg strip -->
    <div class="pf-avg-strip">
        <div class="pf-avg-cell">
            <div class="pf-avg-eyebrow">FII {n_days}D Avg</div>
            <div class="pf-avg-val" style="color:{fc};">{fs}{fa:,.0f}</div>
            <div class="pf-avg-unit">&#8377; Cr / day</div>
        </div>
        <div class="pf-avg-sep"></div>
        <div class="pf-avg-cell">
            <div class="pf-avg-eyebrow">DII {n_days}D Avg</div>
            <div class="pf-avg-val" style="color:{dc};">{ds}{da:,.0f}</div>
            <div class="pf-avg-unit">&#8377; Cr / day</div>
        </div>
        <div class="pf-avg-sep"></div>
        <div class="pf-avg-cell">
            <div class="pf-avg-eyebrow">Net Combined</div>
            <div class="pf-avg-val" style="color:{nc};">{ns}{na:,.0f}</div>
            <div class="pf-avg-unit">&#8377; Cr / day</div>
        </div>
    </div>

    <!-- Insight box -->
    <div class="pf-insight-box" style="background:{s_bg};border:1px solid {s_border};">
        <div class="pf-insight-header">
            <span class="pf-insight-lbl" style="color:{s_color};">&#128202; {n_days}-DAY INSIGHT &amp; DIRECTION</span>
            {verdict_badge}
        </div>
        <div class="pf-insight-text">{summ['insight']}</div>
    </div>
</div>
"""

    def _oi_navy_command_section(self, d):
        oi_cls=d['oi_class']; direction=d['oi_direction']; signal=d['oi_signal']
        ce_raw=d['total_ce_oi_change']; pe_raw=d['total_pe_oi_change']
        bull_force=0; bear_force=0
        if ce_raw < 0: bull_force += abs(ce_raw)
        else:          bear_force += abs(ce_raw)
        if pe_raw > 0: bull_force += abs(pe_raw)
        else:          bear_force += abs(pe_raw)
        total_force=bull_force+bear_force
        bull_pct=round(bull_force/total_force*100) if total_force>0 else 50
        bear_pct=100-bull_pct
        if oi_cls=='bearish':
            dir_bg='rgba(30,10,14,0.92)';dir_border='rgba(239,68,68,0.35)';dir_left_bar='linear-gradient(180deg,#ef4444,#b91c1c)';dir_name_col='#fb7185';dir_desc_col='rgba(251,113,133,0.5)'
        elif oi_cls=='bullish':
            dir_bg='rgba(10,30,20,0.92)';dir_border='rgba(16,185,129,0.35)';dir_left_bar='linear-gradient(180deg,#10b981,#047857)';dir_name_col='#34d399';dir_desc_col='rgba(52,211,153,0.5)'
        else:
            dir_bg='rgba(20,20,10,0.92)';dir_border='rgba(251,191,36,0.3)';dir_left_bar='linear-gradient(180deg,#f59e0b,#d97706)';dir_name_col='#fbbf24';dir_desc_col='rgba(251,191,36,0.5)'
        ce_val=d['total_ce_oi_change']; pe_val=d['total_pe_oi_change']; net_val=d['net_oi_change']
        ce_is_bear=ce_val>0; pe_is_bull=pe_val>0
        ce_col='#fb7185' if ce_is_bear else '#34d399'; ce_dot_col='#ef4444' if ce_is_bear else '#10b981'
        ce_lbl='Bearish Signal' if ce_is_bear else 'Bullish Signal'; ce_btn_col='#ef4444' if ce_is_bear else '#10b981'
        ce_btn_bg='rgba(239,68,68,0.12)' if ce_is_bear else 'rgba(16,185,129,0.12)'; ce_btn_bdr='rgba(239,68,68,0.4)' if ce_is_bear else 'rgba(16,185,129,0.4)'
        pe_col='#34d399' if pe_is_bull else '#fb7185'; pe_dot_col='#10b981' if pe_is_bull else '#ef4444'
        pe_lbl='Bullish Signal' if pe_is_bull else 'Bearish Signal'; pe_btn_col='#10b981' if pe_is_bull else '#ef4444'
        pe_btn_bg='rgba(16,185,129,0.12)' if pe_is_bull else 'rgba(239,68,68,0.12)'; pe_btn_bdr='rgba(16,185,129,0.4)' if pe_is_bull else 'rgba(239,68,68,0.4)'
        if net_val > 0: net_col='#34d399';net_dot_col='#10b981';net_lbl='Bullish Net';net_btn_col='#10b981';net_btn_bg='rgba(16,185,129,0.12)';net_btn_bdr='rgba(16,185,129,0.4)'
        elif net_val < 0: net_col='#fb7185';net_dot_col='#ef4444';net_lbl='Bearish Net';net_btn_col='#ef4444';net_btn_bg='rgba(239,68,68,0.12)';net_btn_bdr='rgba(239,68,68,0.4)'
        else: net_col='#fbbf24';net_dot_col='#f59e0b';net_lbl='Balanced';net_btn_col='#f59e0b';net_btn_bg='rgba(245,158,11,0.12)';net_btn_bdr='rgba(245,158,11,0.4)'
        def nc_card(label,idc,value,val_col,sub,btn_lbl,btn_col,btn_bg,btn_bdr,icon_char):
            return (f'<div class="nc-card"><div class="nc-card-header">'
                    f'<span class="nc-card-label">{label}</span><span style="font-size:18px;line-height:1;color:{idc};">{icon_char}</span></div>'
                    f'<div class="nc-card-value" style="color:{val_col};">{value:+,}</div>'
                    f'<div class="nc-card-sub">{sub}</div>'
                    f'<div class="nc-card-btn" style="color:{btn_col};background:{btn_bg};border:1px solid {btn_bdr};">{btn_lbl}</div></div>')
        cards_html = (
            nc_card('CALL OI CHANGE',ce_dot_col,ce_val,ce_col,'CE open interest \u0394',ce_lbl,ce_btn_col,ce_btn_bg,ce_btn_bdr,'🔴' if ce_is_bear else '🟢') +
            nc_card('PUT OI CHANGE',pe_dot_col,pe_val,pe_col,'PE open interest \u0394',pe_lbl,pe_btn_col,pe_btn_bg,pe_btn_bdr,'🟢' if pe_is_bull else '🔴') +
            nc_card('NET OI CHANGE',net_dot_col,net_val,net_col,'PE \u0394 \u2212 CE \u0394',net_lbl,net_btn_col,net_btn_bg,net_btn_bdr,'\u2696\ufe0f')
        )
        dual_meters = (
            f'<div class="nc-meters-panel">'
            f'<div class="nc-meter-row"><div class="nc-meter-head-row"><span class="nc-meter-label">\U0001f7e2 Bull Strength</span><span class="nc-meter-pct" style="color:#34d399;">{bull_pct}%</span></div>'
            f'<div class="nc-meter-track"><div class="nc-meter-fill" style="width:{bull_pct}%;background:linear-gradient(90deg,#10b981,#34d399);"></div>'
            f'<div class="nc-meter-head" style="left:{bull_pct}%;background:#34d399;box-shadow:0 0 8px #34d399;"></div></div></div>'
            f'<div class="nc-meter-row"><div class="nc-meter-head-row"><span class="nc-meter-label">\U0001f534 Bear Strength</span><span class="nc-meter-pct" style="color:#fb7185;">{bear_pct}%</span></div>'
            f'<div class="nc-meter-track"><div class="nc-meter-fill" style="width:{bear_pct}%;background:linear-gradient(90deg,#ef4444,#f97316);"></div>'
            f'<div class="nc-meter-head" style="left:{bear_pct}%;background:#fb7185;box-shadow:0 0 8px #fb7185;"></div></div></div></div>'
        )
        # ── Compact single-row OI widget (space-saving redesign) ──
        # All values (ce_val, pe_val, net_val, direction, signal,
        # bull_pct, bear_pct, dir_name_col, dir_desc_col) come from
        # the logic above — nothing changed there.
        return f"""
<style>
/* ── OI Navy Command — responsive ── */
.nc-wrap {{
    background:#090f1c;
    border:1px solid rgba(0,200,255,0.1);
    border-radius:12px;
    overflow:hidden;
    font-family:'JetBrains Mono',monospace;
}}
.nc-header {{
    display:flex;align-items:center;justify-content:space-between;
    padding:8px 14px;
    background:rgba(0,0,0,0.35);
    border-bottom:1px solid rgba(0,200,255,0.08);
    flex-wrap:wrap;gap:6px;
}}
.nc-header-left {{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}}
.nc-header-title {{font-size:15px;font-weight:700;color:#e2eaf5;letter-spacing:.5px;}}
.nc-header-sub {{font-size:12px;color:#a8c4d8;letter-spacing:1px;}}
.nc-atm-badge {{
    font-size:9px;letter-spacing:1.5px;white-space:nowrap;
    background:rgba(0,212,255,0.08);border:1px solid rgba(0,212,255,0.2);
    color:#00d4ff;padding:3px 10px;border-radius:5px;
}}
/* Desktop: single row — direction+bars merged | divider | CE | PE | Net */
.nc-grid {{
    display:grid;
    grid-template-columns:2.2fr 1px minmax(0,1fr) minmax(0,1fr) minmax(0,1fr);
    min-height:90px;
}}
.nc-divider {{background:rgba(0,200,255,0.08);}}

/* Direction+bars unified cell — left:text  right:bars */
.nc-dir-cell {{
    padding:14px 18px;
    border-left:3px solid {dir_name_col};
    display:flex;flex-direction:row;align-items:center;gap:0;
}}
.nc-dir-text {{
    display:flex;flex-direction:column;justify-content:center;gap:3px;
    flex:0 0 auto; min-width:140px;
}}
.nc-dir-label {{font-size:10px;letter-spacing:1.5px;color:{dir_desc_col};text-transform:uppercase;}}
.nc-dir-name {{
    font-family:'Orbitron',monospace;font-size:22px;font-weight:900;
    color:{dir_name_col};text-shadow:0 0 18px {dir_name_col}77;line-height:1.2;
}}
.nc-dir-sig {{font-size:11px;color:{dir_desc_col};letter-spacing:.3px;margin-top:2px;}}

/* Bars block — fills remaining space of direction cell */
.nc-bars-block {{
    flex:1;
    display:flex;flex-direction:column;justify-content:center;gap:10px;
    padding:0 18px 0 24px;
    border-left:1px solid rgba(0,200,255,0.08);
    margin-left:16px;
}}
.nc-bar-row {{display:flex;align-items:center;gap:10px;}}
.nc-bar-lbl {{
    font-size:11px;font-weight:700;letter-spacing:1px;
    width:32px;flex-shrink:0;
}}
.nc-bar-track {{flex:1;height:6px;background:rgba(255,255,255,0.07);border-radius:99px;overflow:hidden;}}
.nc-bar-pct {{
    font-family:'Orbitron',monospace;font-size:15px;font-weight:900;
    min-width:42px;text-align:right;flex-shrink:0;
}}
.nc-oi-cell {{
    padding:14px 14px;
    border-left:1px solid rgba(0,200,255,0.08);
    display:flex;flex-direction:column;justify-content:center;gap:3px;
}}
.nc-oi-label {{font-size:10px;letter-spacing:1px;text-transform:uppercase;color:#a8c4d8;margin-bottom:2px;}}
.nc-oi-value {{font-family:'Orbitron',monospace;font-size:20px;font-weight:900;line-height:1.15;}}
.nc-oi-footer {{display:flex;align-items:center;justify-content:space-between;margin-top:4px;flex-wrap:wrap;gap:3px;}}
.nc-oi-sub {{font-size:10px;color:#a8c4d8;}}
.nc-oi-btn {{font-size:10px;padding:2px 7px;border-radius:3px;white-space:nowrap;}}
.nc-legend {{
    padding:8px 14px;
    background:rgba(0,0,0,0.25);
    border-top:1px solid rgba(0,200,255,0.06);
    display:flex;flex-wrap:wrap;align-items:center;gap:5px 10px;
    font-size:11px;color:#a8c4d8;
}}

/* ── MOBILE: stack into 2 rows ── */
@media (max-width:620px) {{
    .nc-grid {{
        display:grid;
        grid-template-columns:1fr 1fr 1fr;
        grid-template-rows:auto auto;
    }}
    .nc-divider {{ display:none; }}

    /* Direction+bars cell: spans full row 1 */
    .nc-dir-cell {{
        grid-column:1 / 4;
        grid-row:1;
        border-left:3px solid {dir_name_col};
        border-bottom:1px solid rgba(0,200,255,0.08);
        padding:12px 14px;
        flex-direction:row;
        align-items:center;
    }}
    .nc-dir-text {{ min-width:110px; }}
    .nc-dir-name {{ font-size:18px; }}
    .nc-bars-block {{
        padding:0 10px 0 16px;
        margin-left:12px;
    }}
    .nc-bar-pct {{ font-size:13px; min-width:36px; }}

    /* CE / PE / Net — equal thirds in row 2 */
    .nc-ce-cell {{
        grid-column:1 / 2; grid-row:2;
        border-top:2px solid {ce_col};
        border-right:1px solid rgba(0,200,255,0.08);
        padding:10px 10px;
    }}
    .nc-pe-cell {{
        grid-column:2 / 3; grid-row:2;
        border-top:2px solid {pe_col};
        border-right:1px solid rgba(0,200,255,0.08);
        padding:10px 10px;
    }}
    .nc-net-cell {{
        grid-column:3 / 4; grid-row:2;
        border-top:2px solid {net_col};
        padding:10px 10px;
    }}

    .nc-oi-value {{ font-size:13px; }}
    .nc-oi-footer {{ flex-direction:column; align-items:flex-start; gap:3px; }}
    .nc-legend-verbose {{ display:none; }}
}}
</style>

<div class="section">
<div class="nc-wrap">

  <!-- ── Header ── -->
  <div class="nc-header">
    <div class="nc-header-left">
      <span style="font-size:13px;">&#128202;</span>
      <span class="nc-header-title">Change in Open Interest</span>
      <span class="nc-header-sub">Today's Direction Analysis</span>
    </div>
    <div class="nc-atm-badge">ATM &#177;10</div>
  </div>

  <!-- ── Grid: Direction | divider | Bars | divider | CE | PE | Net ── -->
  <div class="nc-grid">

    <!-- Direction + Bars — unified cell -->
    <div class="nc-dir-cell" style="background:linear-gradient(135deg,{dir_bg},{dir_bg.replace('0.92','0.03')});">

      <!-- Left: text -->
      <div class="nc-dir-text">
        <div class="nc-dir-label">Market Direction</div>
        <div class="nc-dir-name">{direction}</div>
        <div class="nc-dir-sig">{signal}</div>
      </div>

      <!-- Right: bars -->
      <div class="nc-bars-block">
        <div class="nc-bar-row">
          <div class="nc-bar-lbl" style="color:#00ff88;">&#9679; Bull</div>
          <div class="nc-bar-track">
            <div style="height:100%;width:{bull_pct}%;background:linear-gradient(90deg,#00c96b,#00ff88);border-radius:99px;box-shadow:0 0 6px rgba(0,255,136,0.5);"></div>
          </div>
          <div class="nc-bar-pct" style="color:#00ff88;">{bull_pct}%</div>
        </div>
        <div class="nc-bar-row">
          <div class="nc-bar-lbl" style="color:#ff3b5c;">&#9679; Bear</div>
          <div class="nc-bar-track">
            <div style="height:100%;width:{bear_pct}%;background:linear-gradient(90deg,#c9003a,#ff3b5c);border-radius:99px;box-shadow:0 0 6px rgba(255,59,92,0.5);"></div>
          </div>
          <div class="nc-bar-pct" style="color:#ff3b5c;">{bear_pct}%</div>
        </div>
      </div>

    </div>

    <!-- Divider -->
    <div class="nc-divider"></div>

    <!-- Call OI -->
    <div class="nc-oi-cell nc-ce-cell" style="border-top:2px solid {ce_col};">
      <div class="nc-oi-label">Call OI &#916;</div>
      <div class="nc-oi-value" style="color:{ce_col};">{ce_val:+,}</div>
      <div class="nc-oi-footer">
        <div class="nc-oi-sub">CE open interest</div>
        <div class="nc-oi-btn" style="background:{ce_btn_bg};border:1px solid {ce_btn_bdr};color:{ce_btn_col};">{ce_lbl}</div>
      </div>
    </div>

    <!-- Put OI -->
    <div class="nc-oi-cell nc-pe-cell" style="border-top:2px solid {pe_col};">
      <div class="nc-oi-label">Put OI &#916;</div>
      <div class="nc-oi-value" style="color:{pe_col};">{pe_val:+,}</div>
      <div class="nc-oi-footer">
        <div class="nc-oi-sub">PE open interest</div>
        <div class="nc-oi-btn" style="background:{pe_btn_bg};border:1px solid {pe_btn_bdr};color:{pe_btn_col};">{pe_lbl}</div>
      </div>
    </div>

    <!-- Net OI -->
    <div class="nc-oi-cell nc-net-cell" style="border-top:2px solid {net_col};">
      <div class="nc-oi-label">Net OI &#916;</div>
      <div class="nc-oi-value" style="color:{net_col};">{net_val:+,}</div>
      <div class="nc-oi-footer">
        <div class="nc-oi-sub">PE &#916; &#8722; CE &#916;</div>
        <div class="nc-oi-btn" style="background:{net_btn_bg};border:1px solid {net_btn_bdr};color:{net_btn_col};">&#9878; {net_lbl}</div>
      </div>
    </div>

  </div>

  <!-- ── Legend ── -->
  <div class="nc-legend">
    <span>&#128214;</span>
    <span style="background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.25);border-radius:4px;padding:2px 8px;color:#dde8f0;">Call OI +</span>
    <span class="nc-legend-verbose">Writers selling calls</span>
    <span style="background:rgba(255,59,92,0.18);border:1px solid rgba(255,59,92,0.35);border-radius:4px;padding:2px 8px;color:#ff6b85;">Bearish</span>
    <span style="color:rgba(255,255,255,0.3);" class="nc-legend-verbose">|</span>
    <span style="background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.25);border-radius:4px;padding:2px 8px;color:#dde8f0;" class="nc-legend-verbose">Call OI &#8722;</span>
    <span class="nc-legend-verbose">Unwinding</span>
    <span style="background:rgba(0,255,136,0.15);border:1px solid rgba(0,255,136,0.35);border-radius:4px;padding:2px 8px;color:#00ff88;" class="nc-legend-verbose">Bullish</span>
    <span style="color:rgba(255,255,255,0.3);" class="nc-legend-verbose">|</span>
    <span style="background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.25);border-radius:4px;padding:2px 8px;color:#dde8f0;">Put OI +</span>
    <span class="nc-legend-verbose">Writers selling puts</span>
    <span style="background:rgba(0,255,136,0.15);border:1px solid rgba(0,255,136,0.35);border-radius:4px;padding:2px 8px;color:#00ff88;">Bullish</span>
    <span style="color:rgba(255,255,255,0.3);" class="nc-legend-verbose">|</span>
    <span style="background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.25);border-radius:4px;padding:2px 8px;color:#dde8f0;">Net OI</span>
    <span style="background:rgba(0,255,136,0.15);border:1px solid rgba(0,255,136,0.35);border-radius:4px;padding:2px 8px;color:#00ff88;">+ = Bullish</span>
    <span style="background:rgba(255,59,92,0.18);border:1px solid rgba(255,59,92,0.35);border-radius:4px;padding:2px 8px;color:#ff6b85;">&#8722; = Bearish</span>
    <span style="color:rgba(255,255,255,0.3);" class="nc-legend-verbose">|</span>
    <span style="background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.25);border-radius:4px;padding:2px 8px;color:#dde8f0;" class="nc-legend-verbose">Bull % + Bear %</span>
    <span class="nc-legend-verbose">= 100% &middot; relative dominance</span>
  </div>

</div>
</div>
"""

    def _top10_oi_widget_html(self, d):
        """
        TOP 10 OPEN INTEREST widget — same format as Neon Ledger image.
        Shows Top 5 CE (calls) and Top 5 PE (puts) by Open Interest.
        Reads from d['df'] — zero logic changes anywhere.
        """
        _df = d.get('df', None)
        atm = d.get('atm_strike', 0)
        spot = d.get('current_price', 0)

        if _df is None or _df.empty:
            return ''

        # ── Top 5 CE by OI (resistance side — above ATM) ──
        ce_top5 = _df.nlargest(5, 'CE_OI')[['Strike','CE_OI','CE_OI_Change','CE_LTP','CE_Vol']].reset_index(drop=True)
        # ── Top 5 PE by OI (support side — below ATM) ──
        pe_top5 = _df.nlargest(5, 'PE_OI')[['Strike','PE_OI','PE_OI_Change','PE_LTP','PE_Vol']].reset_index(drop=True)

        # Max OI for bar width scaling
        ce_max_oi = ce_top5['CE_OI'].max() or 1
        pe_max_oi = pe_top5['PE_OI'].max() or 1

        def strike_type(strike, atm_s):
            if strike == atm_s:   return 'ATM', '#00d4ff', 'rgba(0,212,255,0.12)', 'rgba(0,212,255,0.4)'
            elif strike > atm_s:  return 'OTM', '#546e7a', 'rgba(84,110,122,0.1)', 'rgba(84,110,122,0.3)'
            else:                 return 'ITM', '#ffb74d', 'rgba(255,183,77,0.12)', 'rgba(255,183,77,0.35)'

        def fmt_oi(v):
            if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
            if v >= 1_000:     return f"{v/1_000:.1f}K"
            return str(v)

        def fmt_vol(v):
            if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
            if v >= 1_000:     return f"{v/1_000:.1f}K"
            return str(int(v))

        def chg_color(v):
            return '#00e676' if v > 0 else ('#ff5252' if v < 0 else '#546e7a')

        def chg_fmt(v):
            return f"+{int(v):,}" if v > 0 else f"{int(v):,}"

        # ── Build CE rows ──
        ce_rows = ''
        for i, row in ce_top5.iterrows():
            strike   = int(row['Strike'])
            oi_val   = int(row['CE_OI'])
            oi_chg   = row['CE_OI_Change']
            ltp      = row['CE_LTP']
            vol      = row['CE_Vol']
            bar_w    = round(oi_val / ce_max_oi * 100)
            stype, sc, sbg, sbdr = strike_type(strike, atm)
            rank_bg  = 'rgba(255,51,85,0.2)' if i == 0 else 'rgba(255,255,255,0.05)'
            ce_rows += f"""
                <tr style="border-bottom:1px solid rgba(255,255,255,0.04);">
                  <td style="padding:9px 10px;text-align:center;">
                    <span style="display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:5px;background:{rank_bg};font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;color:#ff3355;">{i+1}</span>
                  </td>
                  <td style="padding:9px 10px;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:#e2eaf5;">&#8377;{strike:,}</td>
                  <td style="padding:9px 10px;">
                    <span style="font-size:9px;padding:2px 7px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-weight:700;
                                 color:{sc};background:{sbg};border:1px solid {sbdr};">{stype}</span>
                  </td>
                  <td style="padding:9px 14px 9px 10px;min-width:130px;">
                    <div style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:#ff3355;margin-bottom:4px;">{fmt_oi(oi_val)}</div>
                    <div style="height:3px;background:rgba(255,255,255,0.06);border-radius:99px;overflow:hidden;">
                      <div style="height:100%;width:{bar_w}%;background:linear-gradient(90deg,#ff3355,#ff6b6b);border-radius:99px;"></div>
                    </div>
                  </td>
                  <td style="padding:9px 10px;font-family:'JetBrains Mono',monospace;font-size:12px;color:{chg_color(oi_chg)};">{chg_fmt(oi_chg)}</td>
                  <td style="padding:9px 10px;font-family:'JetBrains Mono',monospace;font-size:12px;color:#c8d8e0;">&#8377;{ltp:.2f}</td>
                  <td style="padding:9px 10px;font-family:'JetBrains Mono',monospace;font-size:12px;color:#8faabe;">{fmt_vol(vol)}</td>
                </tr>"""

        # ── Build PE rows ──
        pe_rows = ''
        for i, row in pe_top5.iterrows():
            strike   = int(row['Strike'])
            oi_val   = int(row['PE_OI'])
            oi_chg   = row['PE_OI_Change']
            ltp      = row['PE_LTP']
            vol      = row['PE_Vol']
            bar_w    = round(oi_val / pe_max_oi * 100)
            stype, sc, sbg, sbdr = strike_type(strike, atm)
            rank_bg  = 'rgba(0,230,118,0.18)' if i == 0 else 'rgba(255,255,255,0.05)'
            pe_rows += f"""
                <tr style="border-bottom:1px solid rgba(255,255,255,0.04);">
                  <td style="padding:9px 10px;text-align:center;">
                    <span style="display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:5px;background:{rank_bg};font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;color:#00e676;">{i+1}</span>
                  </td>
                  <td style="padding:9px 10px;font-family:'JetBrains Mono',monospace;font-size:12px;font-weight:700;color:#e2eaf5;">&#8377;{strike:,}</td>
                  <td style="padding:9px 10px;">
                    <span style="font-size:9px;padding:2px 7px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-weight:700;
                                 color:{sc};background:{sbg};border:1px solid {sbdr};">{stype}</span>
                  </td>
                  <td style="padding:9px 14px 9px 10px;min-width:130px;">
                    <div style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:#00e676;margin-bottom:4px;">{fmt_oi(oi_val)}</div>
                    <div style="height:3px;background:rgba(255,255,255,0.06);border-radius:99px;overflow:hidden;">
                      <div style="height:100%;width:{bar_w}%;background:linear-gradient(90deg,#00e676,#69f0ae);border-radius:99px;"></div>
                    </div>
                  </td>
                  <td style="padding:9px 10px;font-family:'JetBrains Mono',monospace;font-size:12px;color:{chg_color(oi_chg)};">{chg_fmt(oi_chg)}</td>
                  <td style="padding:9px 10px;font-family:'JetBrains Mono',monospace;font-size:12px;color:#c8d8e0;">&#8377;{ltp:.2f}</td>
                  <td style="padding:9px 10px;font-family:'JetBrains Mono',monospace;font-size:12px;color:#8faabe;">{fmt_vol(vol)}</td>
                </tr>"""

        th_style = "padding:8px 10px;font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1.5px;text-transform:uppercase;color:#8faabe;font-weight:600;border-bottom:1px solid rgba(255,255,255,0.06);"

        return f"""
<style>
.top10-oi-widget {{ background:#060d18;border:1px solid rgba(0,200,255,0.1);border-radius:14px;overflow:hidden;margin-bottom:4px;font-family:'JetBrains Mono',monospace; }}
.top10-oi-header {{ display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;padding:11px 18px;background:rgba(0,0,0,0.3);border-bottom:1px solid rgba(0,200,255,0.08); }}
.top10-oi-header-left {{ display:flex;align-items:center;gap:10px; }}
.top10-oi-header-right {{ display:flex;align-items:center;gap:8px;flex-wrap:wrap; }}
.top10-oi-grid {{ display:grid;grid-template-columns:1fr 1fr;gap:0; }}
.top10-oi-table {{ width:100%;border-collapse:collapse;overflow-x:auto;display:block; }}
.top10-oi-sub-header {{ display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:4px;padding:8px 12px; }}
@media(max-width:900px) {{
  .top10-oi-grid {{ grid-template-columns:1fr !important; }}
  .top10-oi-ce-panel {{ border-right:none !important;border-bottom:1px solid rgba(255,255,255,0.06); }}
  .top10-oi-header {{ padding:8px 12px; }}
  .top10-oi-sub-header span:last-child {{ display:none; }}
}}
@media(max-width:600px) {{
  .top10-oi-table th:nth-child(3),
  .top10-oi-table td:nth-child(3),
  .top10-oi-table th:nth-child(6),
  .top10-oi-table td:nth-child(6) {{ display:none; }}
}}
</style>
<div class="top10-oi-widget">

  <!-- ── Widget Header ── -->
  <div class="top10-oi-header">
    <div class="top10-oi-header-left">
      <div style="width:32px;height:32px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;">&#9651;</div>
      <div>
        <div style="font-size:12px;font-weight:700;color:#e2eaf5;letter-spacing:1px;">TOP 10 OPEN INTEREST</div>
        <div style="font-size:9px;color:#8faabe;letter-spacing:1px;margin-top:1px;">NIFTY &middot; &plusmn;10 STRIKES FROM ATM &middot; HIGHEST OI IN WINDOW</div>
      </div>
    </div>
    <div class="top10-oi-header-right">
      <div style="font-size:10px;padding:4px 12px;border-radius:6px;background:rgba(255,51,85,0.12);border:1px solid rgba(255,51,85,0.3);color:#ff3355;font-weight:700;">5 CE</div>
      <div style="font-size:10px;padding:4px 14px;border-radius:6px;background:rgba(0,212,255,0.1);border:1px solid rgba(0,212,255,0.3);color:#00d4ff;font-weight:700;">ATM &#8377;{atm:,}</div>
      <div style="font-size:10px;padding:4px 12px;border-radius:6px;background:rgba(0,230,118,0.1);border:1px solid rgba(0,230,118,0.3);color:#00e676;font-weight:700;">5 PE</div>
      <div style="width:8px;height:8px;border-radius:50%;background:#00e676;box-shadow:0 0 6px #00e676;flex-shrink:0;"></div>
    </div>
  </div>

  <!-- ── Two-column table layout ── -->
  <div class="top10-oi-grid">

    <!-- LEFT: CE Table -->
    <div class="top10-oi-ce-panel" style="border-right:1px solid rgba(255,255,255,0.05);">
      <div class="top10-oi-sub-header" style="background:rgba(255,51,85,0.04);border-bottom:1px solid rgba(255,51,85,0.12);">
        <div style="display:flex;align-items:center;gap:6px;">
          <div style="width:7px;height:7px;border-radius:50%;background:#ff3355;box-shadow:0 0 5px #ff3355;flex-shrink:0;"></div>
          <span style="font-size:11px;font-weight:700;color:#ff3355;letter-spacing:1px;">TOP 5 CALL OPTIONS (CE)</span>
        </div>
        <span style="font-size:9px;color:#8faabe;letter-spacing:1px;">10 STRIKES ABOVE ATM</span>
      </div>
      <table class="top10-oi-table">
        <thead>
          <tr style="background:rgba(0,0,0,0.2);">
            <th style="{th_style}text-align:center;">#</th>
            <th style="{th_style}">Strike</th>
            <th style="{th_style}">Type</th>
            <th style="{th_style}">Open Interest</th>
            <th style="{th_style}">Chg OI</th>
            <th style="{th_style}">LTP</th>
            <th style="{th_style}">Volume</th>
          </tr>
        </thead>
        <tbody>{ce_rows}</tbody>
      </table>
    </div>

    <!-- RIGHT: PE Table -->
    <div>
      <div class="top10-oi-sub-header" style="background:rgba(0,230,118,0.04);border-bottom:1px solid rgba(0,230,118,0.12);">
        <div style="display:flex;align-items:center;gap:6px;">
          <div style="width:7px;height:7px;border-radius:50%;background:#00e676;box-shadow:0 0 5px #00e676;flex-shrink:0;"></div>
          <span style="font-size:11px;font-weight:700;color:#00e676;letter-spacing:1px;">TOP 5 PUT OPTIONS (PE)</span>
        </div>
        <span style="font-size:9px;color:#8faabe;letter-spacing:1px;">10 STRIKES BELOW ATM</span>
      </div>
      <table class="top10-oi-table">
        <thead>
          <tr style="background:rgba(0,0,0,0.2);">
            <th style="{th_style}text-align:center;">#</th>
            <th style="{th_style}">Strike</th>
            <th style="{th_style}">Type</th>
            <th style="{th_style}">Open Interest</th>
            <th style="{th_style}">Chg OI</th>
            <th style="{th_style}">LTP</th>
            <th style="{th_style}">Volume</th>
          </tr>
        </thead>
        <tbody>{pe_rows}</tbody>
      </table>
    </div>

  </div>

  <!-- ── Footer ── -->
  <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px;padding:7px 18px;background:rgba(0,0,0,0.25);border-top:1px solid rgba(0,200,255,0.06);">
    <span style="font-size:9px;color:#8899aa;letter-spacing:1.5px;text-transform:uppercase;">Neon Ledger &middot; Top OI &middot; &plusmn;10 ATM Strikes Window</span>
    <div style="display:flex;align-items:center;gap:5px;">
      <div style="width:6px;height:6px;border-radius:50%;background:#00e676;box-shadow:0 0 5px #00e676;"></div>
      <span style="font-size:9px;color:#00e676;letter-spacing:1px;">LIVE</span>
    </div>
  </div>

</div>
"""

    def _option_chain_pivot_section_html(self, d):
        """
        Renders TWO sub-panels:
          1. Option Chain Analysis  — PCR, OI sentiment, Max Pain, Call/Put buildup, OI walls
          2. Pivot Points (Traditional) — auto-calc from prev H/L/C stored in html_data
        Placed between KEY LEVELS and FII/DII sections in the main tab.
        """
        # ── Option Chain panel values ─────────────────────────────────────────
        pcr        = d.get('pcr', 0)
        pcr_str    = f"{pcr:.2f}" if pcr else "N/A"
        max_pain   = d.get('max_pain', 0)
        ce_chg     = d.get('total_ce_oi_change', 0)
        pe_chg     = d.get('total_pe_oi_change', 0)
        oi_dir     = d.get('oi_direction', 'N/A')
        oi_class   = d.get('oi_class', 'neutral')
        max_ce     = d.get('max_ce_oi', 0)
        max_pe     = d.get('max_pe_oi', 0)

        def _oi_color(cls):
            return {'bullish':'#26c6da','bearish':'#f44336','neutral':'#ffb74d'}.get(cls,'#ffb74d')

        oi_col = _oi_color(oi_class)

        # OI sentiment label
        if oi_class == 'bullish':
            sent_icon = '&#9650;'; sent_lbl = 'BULLISH'; sent_col = '#26c6da'
        elif oi_class == 'bearish':
            sent_icon = '&#9660;'; sent_lbl = 'BEARISH'; sent_col = '#f44336'
        else:
            sent_icon = '&#8596;'; sent_lbl = 'NEUTRAL'; sent_col = '#ffb74d'

        # CE / PE bar widths (proportional, max bar = 100%)
        max_abs = max(abs(ce_chg), abs(pe_chg), 1)
        ce_w    = round(abs(ce_chg) / max_abs * 100)
        pe_w    = round(abs(pe_chg) / max_abs * 100)
        ce_k    = f"{ce_chg/1000:+.0f}K" if ce_chg else "0"
        pe_k    = f"{pe_chg/1000:+.0f}K" if pe_chg else "0"
        ce_col  = '#f44336' if ce_chg >= 0 else '#26c6da'   # call build = bearish
        pe_col  = '#26c6da' if pe_chg >= 0 else '#f44336'   # put build  = bullish

        # Max CE / PE OI wall bars (proportional to each other)
        wall_max = max(max_ce, max_pe, 1)
        ce_wall_w = round(max_ce / wall_max * 100)
        pe_wall_w = round(max_pe / wall_max * 100)

        # ── R2 / S2: 2nd highest CE OI strike (resistance) and PE OI strike (support) ──
        # Derived purely from the existing df — zero logic changes elsewhere
        _df = d.get('df', None)
        if _df is not None and not _df.empty and len(_df) >= 2:
            _ce_sorted = _df.nlargest(2, 'CE_OI')
            _pe_sorted = _df.nlargest(2, 'PE_OI')
            max_ce_r2  = int(_ce_sorted.iloc[1]['Strike']) if len(_ce_sorted) > 1 else max_ce
            max_pe_s2  = int(_pe_sorted.iloc[1]['Strike']) if len(_pe_sorted) > 1 else max_pe
            max_ce_r2_val = int(_ce_sorted.iloc[1]['CE_OI']) if len(_ce_sorted) > 1 else 0
            max_pe_s2_val = int(_pe_sorted.iloc[1]['PE_OI']) if len(_pe_sorted) > 1 else 0
        else:
            max_ce_r2 = max_ce; max_pe_s2 = max_pe
            max_ce_r2_val = 0;  max_pe_s2_val = 0

        # Bar widths for R2/S2 (relative to R1/S1 = 100%)
        ce_wall_r2_w = round(max_ce_r2_val / max(_df['CE_OI'].max(), 1) * 100) if _df is not None and not _df.empty else 60
        pe_wall_s2_w = round(max_pe_s2_val / max(_df['PE_OI'].max(), 1) * 100) if _df is not None and not _df.empty else 60

        pcr_badge_col = '#26c6da' if pcr > 1.0 else ('#f44336' if pcr < 0.8 else '#ffb74d')

        oc_panel = "" if not d['has_option_data'] else f"""
        <!-- ── Option Chain Analysis Sub-Panel · Sample 1 Command Terminal ── -->
        <div style="background:#080f18;border:1px solid rgba(0,200,255,0.15);border-radius:6px;flex:1;min-width:280px;overflow:hidden;">

            <!-- header bar -->
            <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 16px;background:rgba(0,0,0,0.5);border-bottom:1px solid rgba(0,200,255,0.1);">
                <span style="font-family:'Space Mono',monospace;font-size:10px;letter-spacing:3px;color:#00c8ff;text-transform:uppercase;">&#11043; Option Chain Analysis</span>
                <span style="font-family:'Space Mono',monospace;font-size:8px;padding:2px 8px;border-radius:2px;background:rgba(0,200,255,0.08);border:1px solid rgba(0,200,255,0.2);color:rgba(0,200,255,0.7);letter-spacing:1px;">NIFTY &middot; LIVE</span>
            </div>

            <div style="padding:16px;">

                <!-- PCR / Sentiment / MaxPain stats row -->
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;background:rgba(0,200,255,0.06);border-radius:4px;overflow:hidden;margin-bottom:14px;">
                    <div style="background:rgba(0,8,16,0.9);padding:14px 16px;">
                        <div style="font-family:'Space Mono',monospace;font-size:9px;letter-spacing:2px;color:rgba(0,200,255,0.6);text-transform:uppercase;margin-bottom:8px;">Put / Call</div>
                        <div style="font-family:'Orbitron',monospace;font-size:28px;font-weight:700;line-height:1;color:{pcr_badge_col};text-shadow:0 0 16px {pcr_badge_col}99;">{pcr_str}</div>
                        <div style="font-family:'Space Mono',monospace;font-size:9px;color:rgba(200,216,224,0.6);margin-top:6px;">PCR RATIO</div>
                    </div>
                    <div style="background:rgba(0,8,16,0.9);padding:14px 16px;">
                        <div style="font-family:'Space Mono',monospace;font-size:9px;letter-spacing:2px;color:rgba(0,200,255,0.6);text-transform:uppercase;margin-bottom:8px;">OI Sentiment</div>
                        <div style="font-family:'Orbitron',monospace;font-size:22px;font-weight:700;line-height:1;color:{sent_col};text-shadow:0 0 16px {sent_col}99;">{sent_icon} {sent_lbl}</div>
                        <div style="font-family:'Space Mono',monospace;font-size:9px;color:rgba(200,216,224,0.6);margin-top:6px;">{oi_dir}</div>
                    </div>
                    <div style="background:rgba(0,8,16,0.9);padding:14px 16px;">
                        <div style="font-family:'Space Mono',monospace;font-size:9px;letter-spacing:2px;color:rgba(0,200,255,0.6);text-transform:uppercase;margin-bottom:8px;">Max Pain</div>
                        <div style="font-family:'Orbitron',monospace;font-size:22px;font-weight:700;line-height:1;color:#ffd700;text-shadow:0 0 16px rgba(255,215,0,0.5);">&#8377;{max_pain:,}</div>
                        <div style="font-family:'Space Mono',monospace;font-size:9px;color:rgba(200,216,224,0.6);margin-top:6px;">Expiry magnet</div>
                    </div>
                </div>

                <!-- OI Direction bars -->
                <div style="margin-bottom:14px;">
                    <div style="font-family:'Space Mono',monospace;font-size:9px;letter-spacing:2px;color:rgba(0,200,255,0.6);text-transform:uppercase;margin-bottom:10px;display:flex;align-items:center;gap:8px;">
                        OI DIRECTION <span style="flex:1;height:1px;background:rgba(0,200,255,0.12);display:inline-block;"></span>
                    </div>
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
                        <div style="font-family:'Space Mono',monospace;font-size:11px;font-weight:700;color:#ff4d6d;width:26px;flex-shrink:0;">CE</div>
                        <div style="flex:1;height:7px;background:rgba(255,255,255,0.06);position:relative;overflow:hidden;">
                            <div style="height:100%;width:{ce_w}%;background:linear-gradient(90deg,rgba(255,77,109,0.4),#ff4d6d);position:relative;">
                                <span style="position:absolute;right:0;top:0;bottom:0;width:2px;background:#ff4d6d;filter:brightness(2);box-shadow:0 0 8px #ff4d6d;"></span>
                            </div>
                        </div>
                        <div style="font-family:'Orbitron',monospace;font-size:14px;font-weight:700;color:#ff6b85;width:64px;text-align:right;flex-shrink:0;">{ce_k}</div>
                    </div>
                    <div style="display:flex;align-items:center;gap:10px;">
                        <div style="font-family:'Space Mono',monospace;font-size:11px;font-weight:700;color:#00e676;width:26px;flex-shrink:0;">PE</div>
                        <div style="flex:1;height:7px;background:rgba(255,255,255,0.06);position:relative;overflow:hidden;">
                            <div style="height:100%;width:{pe_w}%;background:linear-gradient(90deg,rgba(0,230,118,0.4),#00e676);position:relative;">
                                <span style="position:absolute;right:0;top:0;bottom:0;width:2px;background:#00e676;filter:brightness(2);box-shadow:0 0 8px #00e676;"></span>
                            </div>
                        </div>
                        <div style="font-family:'Orbitron',monospace;font-size:14px;font-weight:700;color:#00e676;width:64px;text-align:right;flex-shrink:0;">{pe_k}</div>
                    </div>
                </div>

                <!-- OI Resistance Walls -->
                <div style="margin-bottom:12px;">
                    <div style="font-family:'Space Mono',monospace;font-size:9px;letter-spacing:2px;color:rgba(0,200,255,0.6);text-transform:uppercase;margin-bottom:10px;display:flex;align-items:center;gap:8px;">
                        OI RESISTANCE WALLS <span style="flex:1;height:1px;background:rgba(0,200,255,0.12);display:inline-block;"></span>
                    </div>
                    <div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid rgba(0,200,255,0.06);">
                        <span style="font-family:'Space Mono',monospace;font-size:10px;font-weight:700;padding:3px 8px;border-radius:2px;background:rgba(255,77,109,0.15);color:#ff4d6d;border:1px solid rgba(255,77,109,0.35);width:32px;text-align:center;flex-shrink:0;">R1</span>
                        <div style="flex:1;height:6px;background:rgba(255,255,255,0.04);">
                            <div style="height:100%;width:{ce_wall_w}%;background:linear-gradient(90deg,rgba(255,77,109,0.3),#ff4d6d);box-shadow:0 0 6px rgba(255,77,109,0.3);"></div>
                        </div>
                        <span style="font-family:'Orbitron',monospace;font-size:14px;font-weight:700;color:#ff6b85;flex-shrink:0;min-width:80px;text-align:right;">&#8377;{max_ce:,}</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:10px;padding:8px 0;">
                        <span style="font-family:'Space Mono',monospace;font-size:10px;font-weight:700;padding:3px 8px;border-radius:2px;background:rgba(255,77,109,0.08);color:rgba(255,100,130,0.85);border:1px solid rgba(255,77,109,0.2);width:32px;text-align:center;flex-shrink:0;">R2</span>
                        <div style="flex:1;height:6px;background:rgba(255,255,255,0.04);">
                            <div style="height:100%;width:{ce_wall_r2_w}%;background:linear-gradient(90deg,rgba(255,77,109,0.15),rgba(255,77,109,0.7));"></div>
                        </div>
                        <span style="font-family:'Orbitron',monospace;font-size:14px;font-weight:700;color:rgba(255,143,163,0.85);flex-shrink:0;min-width:80px;text-align:right;">&#8377;{max_ce_r2:,}</span>
                    </div>
                </div>

                <!-- OI Support Floors -->
                <div>
                    <div style="font-family:'Space Mono',monospace;font-size:9px;letter-spacing:2px;color:rgba(0,200,255,0.6);text-transform:uppercase;margin-bottom:10px;display:flex;align-items:center;gap:8px;">
                        OI SUPPORT FLOORS <span style="flex:1;height:1px;background:rgba(0,200,255,0.12);display:inline-block;"></span>
                    </div>
                    <div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid rgba(0,200,255,0.06);">
                        <span style="font-family:'Space Mono',monospace;font-size:10px;font-weight:700;padding:3px 8px;border-radius:2px;background:rgba(0,230,118,0.15);color:#00e676;border:1px solid rgba(0,230,118,0.35);width:32px;text-align:center;flex-shrink:0;">S1</span>
                        <div style="flex:1;height:6px;background:rgba(255,255,255,0.04);">
                            <div style="height:100%;width:{pe_wall_w}%;background:linear-gradient(90deg,rgba(0,230,118,0.3),#00e676);box-shadow:0 0 6px rgba(0,230,118,0.3);"></div>
                        </div>
                        <span style="font-family:'Orbitron',monospace;font-size:14px;font-weight:700;color:#00e676;flex-shrink:0;min-width:80px;text-align:right;">&#8377;{max_pe:,}</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:10px;padding:8px 0;">
                        <span style="font-family:'Space Mono',monospace;font-size:10px;font-weight:700;padding:3px 8px;border-radius:2px;background:rgba(0,230,118,0.08);color:rgba(0,200,100,0.85);border:1px solid rgba(0,230,118,0.2);width:32px;text-align:center;flex-shrink:0;">S2</span>
                        <div style="flex:1;height:6px;background:rgba(255,255,255,0.04);">
                            <div style="height:100%;width:{pe_wall_s2_w}%;background:linear-gradient(90deg,rgba(0,230,118,0.15),rgba(0,230,118,0.7));"></div>
                        </div>
                        <span style="font-family:'Orbitron',monospace;font-size:14px;font-weight:700;color:rgba(105,240,174,0.85);flex-shrink:0;min-width:80px;text-align:right;">&#8377;{max_pe_s2:,}</span>
                    </div>
                </div>

            </div>
        </div>"""

        # ── Pivot Points (Traditional) calculation ────────────────────────────
        ph = d.get('prev_high', 0)
        pl = d.get('prev_low', 0)
        pc = d.get('prev_close', 0)
        cp = d.get('current_price', 0)

        if ph and pl and pc:
            pp = round((ph + pl + pc) / 3, 2)
            r1p = round(2 * pp - pl, 2)
            r2p = round(pp + (ph - pl), 2)
            r3p = round(ph + 2 * (pp - pl), 2)
            s1p = round(2 * pp - ph, 2)
            s2p = round(pp - (ph - pl), 2)
            s3p = round(pl - 2 * (ph - pp), 2)
        else:
            pp = r1p = r2p = r3p = s1p = s2p = s3p = 0

        # ── Dynamic NEAREST R: lowest R level strictly ABOVE LTP ─────────────
        r_levels = [('R1', r1p), ('R2', r2p), ('R3', r3p)]
        above_r  = [(lbl, val) for lbl, val in r_levels if val > cp]
        nearest_r_lbl = above_r[0][0] if above_r else 'R3'
        nearest_r_val = dict(r_levels)[nearest_r_lbl]

        # ── Dynamic NEAREST S: highest level strictly BELOW LTP ──────────────
        s_candidates = [('R1', r1p), ('PP', pp), ('S1', s1p), ('S2', s2p), ('S3', s3p)]
        below_s  = [(lbl, val) for lbl, val in s_candidates if val < cp]
        nearest_s_lbl = below_s[0][0] if below_s else 'S1'
        nearest_s_val = dict(s_candidates)[nearest_s_lbl]

        # Position of LTP on the bar — uses NEAREST S and NEAREST R (not hardcoded S1/R1)
        if nearest_r_val and nearest_s_val and nearest_r_val != nearest_s_val:
            ltp_pct = round(max(3, min(97, (cp - nearest_s_val) / (nearest_r_val - nearest_s_val) * 100)), 1)
        else:
            ltp_pct = 50
        pp_dist = round(cp - pp, 2) if pp else 0
        # pp_dist = LTP minus PP  →  positive means LTP is ABOVE PP
        pp_dist_sign = '+' if pp_dist >= 0 else ''
        pp_dist_lbl  = f"{pp_dist_sign}{pp_dist:.2f} from PP"

        # ── Zone detection (which pivot band does LTP sit in) ─────────────────
        if pp and r3p and r2p and r1p and s1p and s2p and s3p:
            if   cp >= r3p: zone_lbl = "Above R3";          zone_col = "#ff1744"; zone_dot = "#ff1744"
            elif cp >= r2p: zone_lbl = "Between R2 and R3"; zone_col = "#ff4d6d"; zone_dot = "#ff4d6d"
            elif cp >= r1p: zone_lbl = "Between R1 and R2"; zone_col = "#ff6b85"; zone_dot = "#ff6b85"
            elif cp >= s1p: zone_lbl = "Between S1 and R1"; zone_col = "#4fc3f7"; zone_dot = "#26c6da"
            elif cp >= s2p: zone_lbl = "Between S2 and S1"; zone_col = "#26c6da"; zone_dot = "#26c6da"
            elif cp >= s3p: zone_lbl = "Between S3 and S2"; zone_col = "#00bcd4"; zone_dot = "#00bcd4"
            else:           zone_lbl = "Below S3";          zone_col = "#00e676"; zone_dot = "#00e676"
        else:
            zone_lbl = "N/A"; zone_col = "#8faabe"; zone_dot = "#8faabe"

        pp_above_below = "above PP" if pp_dist >= 0 else "below PP"

        pv_panel = f"""
        <!-- ── Pivot Points Widget · Neon Runway · Phantom Slate Edition ── -->
        <div style="background:#060d15;border:1px solid rgba(0,200,255,0.18);border-radius:6px;flex:1;min-width:320px;overflow:hidden;font-family:'Space Mono',monospace;">

            <!-- ── TOP BANNER ─────────────────────────────────────────────── -->
            <div style="background:rgba(0,25,45,0.95);border-bottom:1px solid rgba(0,200,255,0.2);padding:9px 18px;display:flex;align-items:center;justify-content:center;gap:10px;">
                <span style="color:rgba(0,200,255,0.5);font-size:9px;">&#9658;</span>
                <span style="font-size:9px;letter-spacing:3px;color:#00c8ff;font-weight:700;text-transform:uppercase;">PIVOT POINTS (TRADITIONAL - DAILY)</span>
                <span style="color:rgba(0,200,255,0.5);font-size:9px;">&#9658;</span>
            </div>

            <div style="padding:16px 18px;">

                <!-- ── TITLE ROW ───────────────────────────────────────────── -->
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:3px;">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span style="font-size:14px;">&#128205;</span>
                        <span style="font-size:12px;font-weight:700;color:#e2eaf5;letter-spacing:1.5px;">PIVOT POINTS</span>
                    </div>
                    <span style="font-size:8px;font-weight:700;padding:3px 10px;border-radius:3px;background:rgba(0,200,255,0.12);border:1px solid rgba(0,200,255,0.35);color:#00c8ff;letter-spacing:2px;">DAILY</span>
                </div>
                <div style="font-size:9px;color:rgba(200,216,224,0.75);letter-spacing:1px;margin-bottom:16px;">Traditional Method &middot; Daily Candle &middot; Auto-calculated</div>

                <!-- ── PROGRESS BAR (S1 ─── LTP ──→ R1) ──────────────────── -->
                <div style="position:relative;height:8px;background:linear-gradient(90deg,#00e676 0%,#00c8a0 30%,#4fc3f7 55%,#ff6b85 80%,#f44336 100%);border-radius:4px;margin-bottom:10px;box-shadow:0 0 8px rgba(0,200,255,0.2);">
                    <div style="position:absolute;left:{ltp_pct}%;top:50%;transform:translate(-50%,-50%);width:16px;height:16px;border-radius:50%;background:#0a1929;border:2.5px solid #00c8ff;box-shadow:0 0 12px rgba(0,200,255,0.9);z-index:5;"></div>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <!-- NEAREST SUPPORT (left) -->
                    <div style="text-align:left;">
                        <div style="font-size:8px;font-weight:700;color:#26c6da;letter-spacing:1px;margin-bottom:2px;">&#9660; NEAREST SUPPORT</div>
                        <div style="font-family:'Orbitron',monospace;font-size:13px;font-weight:800;color:#00e676;">&#8377;{nearest_s_val:,.2f} <span style="font-size:9px;font-weight:700;padding:1px 6px;border-radius:2px;background:rgba(0,230,118,0.15);border:1px solid rgba(0,230,118,0.4);color:#00e676;">{nearest_s_lbl}</span></div>
                    </div>
                    <!-- LTP centre -->
                    <div style="text-align:center;">
                        <div style="font-size:8px;font-weight:700;color:rgba(200,216,224,0.6);letter-spacing:1px;margin-bottom:2px;">CURRENT</div>
                        <div style="font-size:14px;font-weight:800;color:#e2eaf5;">&#9650; &#8377;{cp:,.2f} <span style="background:rgba(0,200,255,0.18);border:1px solid rgba(0,200,255,0.45);border-radius:2px;padding:2px 7px;color:#00c8ff;font-size:10px;font-weight:700;letter-spacing:1px;">LTP</span></div>
                    </div>
                    <!-- NEAREST RESISTANCE (right) -->
                    <div style="text-align:right;">
                        <div style="font-size:8px;font-weight:700;color:#f44336;letter-spacing:1px;margin-bottom:2px;">NEAREST RESISTANCE &#9650;</div>
                        <div style="font-family:'Orbitron',monospace;font-size:13px;font-weight:800;color:#ff6b85;"><span style="font-size:9px;font-weight:700;padding:1px 6px;border-radius:2px;background:rgba(255,77,109,0.15);border:1px solid rgba(255,77,109,0.4);color:#ff4d6d;">{nearest_r_lbl}</span> &#8377;{nearest_r_val:,.2f}</div>
                    </div>
                </div>

                <!-- ── ZONE LABEL + PP DISTANCE ───────────────────────────── -->
                <div style="display:flex;justify-content:space-between;align-items:center;background:rgba(0,200,255,0.04);border:1px solid rgba(0,200,255,0.1);border-radius:3px;padding:7px 12px;margin-bottom:14px;">
                    <span style="font-size:9px;color:{zone_col};display:flex;align-items:center;gap:6px;font-weight:700;">
                        <span style="width:7px;height:7px;border-radius:50%;background:{zone_dot};display:inline-block;flex-shrink:0;box-shadow:0 0 6px {zone_dot};"></span>
                        {zone_lbl}
                    </span>
                    <span style="font-size:9px;font-weight:600;color:rgba(200,216,224,0.85);">{'+' if pp_dist >= 0 else ''}{pp_dist:.2f} {pp_above_below}</span>
                </div>

                <!-- ── PREV HIGH / LOW / CLOSE ─────────────────────────────── -->
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;background:rgba(0,200,255,0.08);border-radius:4px;overflow:hidden;margin-bottom:14px;">
                    <div style="background:#07111c;padding:10px 12px;">
                        <div style="font-size:9px;letter-spacing:1.5px;font-weight:600;color:rgba(252,165,165,0.9);margin-bottom:5px;display:flex;align-items:center;gap:4px;">
                            <span style="color:#fca5a5;">&#9650;</span> PREV HIGH
                        </div>
                        <div style="font-family:'Orbitron',monospace;font-size:14px;font-weight:700;color:#fca5a5;">&#8377;{ph:,.2f}</div>
                    </div>
                    <div style="background:#07111c;padding:10px 12px;border-left:1px solid rgba(0,200,255,0.07);border-right:1px solid rgba(0,200,255,0.07);">
                        <div style="font-size:9px;letter-spacing:1.5px;font-weight:600;color:rgba(134,239,172,0.9);margin-bottom:5px;display:flex;align-items:center;gap:4px;">
                            <span style="color:#86efac;">&#9660;</span> PREV LOW
                        </div>
                        <div style="font-family:'Orbitron',monospace;font-size:14px;font-weight:700;color:#86efac;">&#8377;{pl:,.2f}</div>
                    </div>
                    <div style="background:#07111c;padding:10px 12px;">
                        <div style="font-size:9px;letter-spacing:1.5px;font-weight:600;color:rgba(200,216,224,0.85);margin-bottom:5px;display:flex;align-items:center;gap:4px;">
                            <span style="color:#94a3b8;">&#9679;</span> PREV CLOSE
                        </div>
                        <div style="font-family:'Orbitron',monospace;font-size:14px;font-weight:700;color:#c9d1d9;">&#8377;{pc:,.2f}</div>
                    </div>
                </div>

                <!-- ── MAIN 3-COLUMN GRID: R Levels | Pivot Centre | S Levels ── -->
                <div style="display:grid;grid-template-columns:1fr 130px 1fr;gap:1px;background:rgba(0,200,255,0.08);border-radius:4px;overflow:hidden;">

                    <!-- LEFT: Resistance R3 / R2 / R1 — NEAREST R is dynamic -->
                    <div style="background:#07111c;padding:12px 14px;">
                        <!-- R3 -->
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,77,109,0.07);{'background:rgba(255,77,109,0.06);border-radius:2px;' if nearest_r_lbl=='R3' else ''}">
                            <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;">
                                <span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:2px;background:rgba(255,77,109,{'0.18' if nearest_r_lbl=='R3' else '0.05'});color:{'#ff4d6d' if nearest_r_lbl=='R3' else 'rgba(255,100,130,0.5)'};border:1px solid rgba(255,77,109,{'0.4' if nearest_r_lbl=='R3' else '0.12'});">R3</span>
                                {'<span style="font-size:7px;font-weight:700;padding:1px 5px;border-radius:2px;background:rgba(255,77,109,0.1);border:1px solid rgba(255,77,109,0.28);color:#ff6b85;letter-spacing:0.5px;">NEAREST R</span>' if nearest_r_lbl=='R3' else ''}
                            </div>
                            <div style="display:flex;align-items:center;gap:4px;">
                                <span style="font-family:'Orbitron',monospace;font-size:{'14' if nearest_r_lbl=='R3' else '12'}px;font-weight:700;color:{'#ff6b85' if nearest_r_lbl=='R3' else 'rgba(255,143,163,0.5)'};">&#8377;{r3p:,.2f}</span>
                                {'<span style="color:#ff6b85;font-size:11px;">&#9650;</span>' if nearest_r_lbl=='R3' else ''}
                            </div>
                        </div>
                        <!-- R2 -->
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid rgba(255,77,109,0.1);{'background:rgba(255,77,109,0.06);border-radius:2px;' if nearest_r_lbl=='R2' else ''}">
                            <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;">
                                <span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:2px;background:rgba(255,77,109,{'0.18' if nearest_r_lbl=='R2' else '0.08'});color:{'#ff4d6d' if nearest_r_lbl=='R2' else 'rgba(255,100,130,0.8)'};border:1px solid rgba(255,77,109,{'0.4' if nearest_r_lbl=='R2' else '0.18'});">R2</span>
                                {'<span style="font-size:7px;font-weight:700;padding:1px 5px;border-radius:2px;background:rgba(255,77,109,0.1);border:1px solid rgba(255,77,109,0.28);color:#ff6b85;letter-spacing:0.5px;">NEAREST R</span>' if nearest_r_lbl=='R2' else ''}
                            </div>
                            <div style="display:flex;align-items:center;gap:4px;">
                                <span style="font-family:'Orbitron',monospace;font-size:{'14' if nearest_r_lbl=='R2' else '13'}px;font-weight:700;color:{'#ff6b85' if nearest_r_lbl=='R2' else 'rgba(255,143,163,0.85)'};">&#8377;{r2p:,.2f}</span>
                                {'<span style="color:#ff6b85;font-size:11px;">&#9650;</span>' if nearest_r_lbl=='R2' else ''}
                            </div>
                        </div>
                        <!-- R1 -->
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;{'background:rgba(255,77,109,0.04);border-radius:2px;margin-top:1px;' if nearest_r_lbl=='R1' else 'margin-top:1px;'}">
                            <div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;">
                                <span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:2px;background:rgba(255,77,109,{'0.18' if nearest_r_lbl=='R1' else '0.06'});color:{'#ff4d6d' if nearest_r_lbl=='R1' else 'rgba(255,100,130,0.45)'};border:1px solid rgba(255,77,109,{'0.4' if nearest_r_lbl=='R1' else '0.15'});">R1</span>
                                {'<span style="font-size:7px;font-weight:700;padding:1px 5px;border-radius:2px;background:rgba(255,77,109,0.1);border:1px solid rgba(255,77,109,0.28);color:#ff6b85;letter-spacing:0.5px;">NEAREST R</span>' if nearest_r_lbl=='R1' else ''}
                            </div>
                            <div style="display:flex;align-items:center;gap:4px;">
                                <span style="font-family:'Orbitron',monospace;font-size:{'14' if nearest_r_lbl=='R1' else '12'}px;font-weight:700;color:{'#ff6b85' if nearest_r_lbl=='R1' else 'rgba(255,143,163,0.38)'};">&#8377;{r1p:,.2f}</span>
                                {'<span style="color:#ff6b85;font-size:11px;">&#9650;</span>' if nearest_r_lbl=='R1' else ''}
                            </div>
                        </div>
                    </div>

                    <!-- CENTRE: Pivot Point + NEAREST R + LTP -->
                    <div style="background:#040c14;padding:10px 8px;display:flex;flex-direction:column;align-items:center;justify-content:space-between;gap:6px;border-left:1px solid rgba(79,195,247,0.14);border-right:1px solid rgba(79,195,247,0.14);">

                        <!-- Pivot Point block -->
                        <div style="text-align:center;width:100%;">
                            <div style="font-size:8px;letter-spacing:2px;font-weight:700;color:#4fc3f7;text-transform:uppercase;margin-bottom:4px;">PIVOT POINT</div>
                            <div style="font-family:'Orbitron',monospace;font-size:15px;font-weight:900;color:#4fc3f7;text-shadow:0 0 12px rgba(79,195,247,0.6);line-height:1;">&#8377;{pp:,.2f}</div>
                            <div style="font-size:9px;font-weight:700;color:{'#00e676' if pp_dist >= 0 else '#f44336'};margin-top:4px;">LTP {pp_dist_sign}{pp_dist:.2f} pts {'above' if pp_dist >= 0 else 'below'} PP</div>
                        </div>

                        <!-- NEAREST R block — highlighted in red -->
                        <div style="width:100%;background:rgba(255,77,109,0.1);border:1px solid rgba(255,77,109,0.38);border-radius:3px;padding:7px 8px;text-align:center;">
                            <div style="font-size:8px;letter-spacing:1.5px;font-weight:700;color:#ff6b85;margin-bottom:4px;">&#9650; NEXT RES ({nearest_r_lbl})</div>
                            <div style="font-family:'Orbitron',monospace;font-size:13px;font-weight:800;color:#ff4d6d;text-shadow:0 0 10px rgba(255,77,109,0.5);line-height:1;">&#8377;{dict(r_levels)[nearest_r_lbl]:,.2f}</div>
                            <div style="font-size:9px;font-weight:700;color:#fca5a5;margin-top:4px;">+{round(dict(r_levels)[nearest_r_lbl]-cp,2):,.2f} pts away</div>
                        </div>

                        <!-- LTP chip -->
                        <div style="background:rgba(79,195,247,0.12);border:1px solid rgba(79,195,247,0.35);border-radius:3px;padding:6px 8px;text-align:center;width:100%;">
                            <div style="font-size:8px;letter-spacing:2px;font-weight:700;color:#00c8ff;margin-bottom:3px;">LTP</div>
                            <div style="font-family:'Orbitron',monospace;font-size:13px;font-weight:700;color:#80deea;">&#8377;{cp:,.2f}</div>
                        </div>

                    </div>

                    <!-- RIGHT: Support S1 / S2 / S3 — NEAREST S is dynamic -->
                    <div style="background:#07111c;padding:12px 14px;">
                        <!-- S1 -->
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;{'background:rgba(0,230,118,0.04);border-radius:2px;' if nearest_s_lbl=='S1' else ''}margin-bottom:1px;">
                            <div style="display:flex;align-items:center;gap:4px;">
                                {'<span style="color:#26c6da;font-size:11px;">&#9660;</span>' if nearest_s_lbl=='S1' else ''}
                                {'<span style="font-size:7px;font-weight:700;padding:1px 5px;border-radius:2px;background:rgba(0,230,118,0.1);border:1px solid rgba(0,230,118,0.28);color:#00e676;letter-spacing:0.5px;">NEAREST S</span>' if nearest_s_lbl=='S1' else ''}
                            </div>
                            <div style="display:flex;align-items:center;gap:4px;">
                                <span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:2px;background:rgba(0,230,118,{'0.18' if nearest_s_lbl=='S1' else '0.06'});color:{'#00e676' if nearest_s_lbl=='S1' else 'rgba(0,200,100,0.5)'};border:1px solid rgba(0,230,118,{'0.4' if nearest_s_lbl=='S1' else '0.15'});">S1</span>
                                <span style="font-family:'Orbitron',monospace;font-size:{'14' if nearest_s_lbl=='S1' else '12'}px;font-weight:700;color:{'#00e676' if nearest_s_lbl=='S1' else 'rgba(105,240,174,0.45)'};">&#8377;{s1p:,.2f}</span>
                            </div>
                        </div>
                        <!-- S2 -->
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid rgba(0,230,118,0.1);border-top:1px solid rgba(0,230,118,0.07);{'background:rgba(0,230,118,0.04);border-radius:2px;' if nearest_s_lbl=='S2' else ''}">
                            <div style="display:flex;align-items:center;gap:4px;">
                                {'<span style="color:#26c6da;font-size:11px;">&#9660;</span>' if nearest_s_lbl=='S2' else ''}
                                {'<span style="font-size:7px;font-weight:700;padding:1px 5px;border-radius:2px;background:rgba(0,230,118,0.1);border:1px solid rgba(0,230,118,0.28);color:#00e676;letter-spacing:0.5px;">NEAREST S</span>' if nearest_s_lbl=='S2' else ''}
                            </div>
                            <div style="display:flex;align-items:center;gap:4px;">
                                <span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:2px;background:rgba(0,230,118,{'0.18' if nearest_s_lbl=='S2' else '0.08'});color:{'#00e676' if nearest_s_lbl=='S2' else 'rgba(0,200,100,0.8)'};border:1px solid rgba(0,230,118,{'0.4' if nearest_s_lbl=='S2' else '0.18'});">S2</span>
                                <span style="font-family:'Orbitron',monospace;font-size:{'14' if nearest_s_lbl=='S2' else '13'}px;font-weight:700;color:{'#00e676' if nearest_s_lbl=='S2' else 'rgba(105,240,174,0.85)'};">&#8377;{s2p:,.2f}</span>
                            </div>
                        </div>
                        <!-- S3 -->
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;{'background:rgba(0,230,118,0.04);border-radius:2px;' if nearest_s_lbl=='S3' else ''}">
                            <div style="display:flex;align-items:center;gap:4px;">
                                {'<span style="color:#26c6da;font-size:11px;">&#9660;</span>' if nearest_s_lbl=='S3' else ''}
                                {'<span style="font-size:7px;font-weight:700;padding:1px 5px;border-radius:2px;background:rgba(0,230,118,0.1);border:1px solid rgba(0,230,118,0.28);color:#00e676;letter-spacing:0.5px;">NEAREST S</span>' if nearest_s_lbl=='S3' else ''}
                            </div>
                            <div style="display:flex;align-items:center;gap:4px;">
                                <span style="font-size:9px;font-weight:700;padding:2px 7px;border-radius:2px;background:rgba(0,230,118,{'0.18' if nearest_s_lbl=='S3' else '0.05'});color:{'#00e676' if nearest_s_lbl=='S3' else 'rgba(0,230,118,0.5)'};border:1px solid rgba(0,230,118,{'0.4' if nearest_s_lbl=='S3' else '0.12'});">S3</span>
                                <span style="font-family:'Orbitron',monospace;font-size:{'14' if nearest_s_lbl=='S3' else '12'}px;font-weight:700;color:{'#00e676' if nearest_s_lbl=='S3' else 'rgba(105,240,174,0.45)'};">&#8377;{s3p:,.2f}</span>
                            </div>
                        </div>
                    </div>

                </div>
            </div>

            <!-- ── FOOTER BAR ──────────────────────────────────────────────── -->
            <div style="background:rgba(0,0,0,0.45);border-top:1px solid rgba(0,200,255,0.1);padding:8px 18px;display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:9px;font-weight:600;color:rgba(200,216,224,0.65);letter-spacing:1px;">Traditional &middot; Daily Candle</span>
                <span style="font-size:9px;color:rgba(79,195,247,0.6);font-weight:700;letter-spacing:1px;">LTP &#8377;{cp:,.2f}</span>
            </div>

        </div>"""

        return f"""
    <div class="section">
        <div class="section-title"><span>&#128204;</span> OPTION CHAIN &amp; PIVOT POINTS</div>
        <div style="display:flex;gap:2px;flex-wrap:wrap;background:rgba(0,200,255,0.06);border:1px solid rgba(0,200,255,0.15);border-radius:6px;overflow:hidden;">
            {oc_panel if d['has_option_data'] else '<div style="color:#8faabe;font-size:13px;padding:16px;">Option data unavailable</div>'}
            {pv_panel}
        </div>
    </div>
"""

    def _key_levels_visual_section(self, d, _pct_cp, _pts_to_res, _pts_to_sup, _mp_node):
        mp_row = f'<tr><td style="color:#ffb74d;">&#127919; Max Pain</td><td style="color:#ffb74d;">&#8377;{d["max_pain"]:,}</td></tr>' if d['has_option_data'] else ''
        return f"""
    <div class="section">
        <div class="section-title"><span>&#128202;</span> KEY LEVELS</div>

        <!-- Desktop/Tablet: visual bar (hidden on mobile <520px) -->
        <div class="kl-bar-section">
            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                <span style="font-size:11px;color:#26c6da;font-weight:700;letter-spacing:1px;">&#9668; SUPPORT ZONE</span>
                <span style="font-size:11px;color:#f44336;font-weight:700;letter-spacing:1px;">RESISTANCE ZONE &#9658;</span>
            </div>
            <div style="position:relative;height:62px;">
                <div class="rl-node-a" style="left:3%;"><div class="rl-lbl" style="color:#26c6da;">Strong<br>Support</div><div class="rl-val" style="color:#26c6da;">&#8377;{d['strong_support']:,.0f}</div><div class="rl-dot" style="background:#26c6da;margin:6px auto 0;"></div></div>
                <div class="rl-node-a" style="left:22%;"><div class="rl-lbl" style="color:#00bcd4;">Support</div><div class="rl-val" style="color:#00bcd4;">&#8377;{d['support']:,.0f}</div><div class="rl-dot" style="background:#00bcd4;box-shadow:0 0 8px #00bcd4;margin:6px auto 0;"></div></div>
                <div style="position:absolute;left:{_pct_cp}%;transform:translateX(-50%);bottom:4px;background:#4fc3f7;color:#000;font-size:11px;font-weight:700;padding:4px 13px;border-radius:6px;white-space:nowrap;z-index:10;box-shadow:0 0 16px rgba(79,195,247,0.7);">&#9660; NOW &nbsp;&#8377;{d['current_price']:,.0f}</div>
                <div class="rl-node-a" style="left:75%;"><div class="rl-lbl" style="color:#ff7043;">Resistance</div><div class="rl-val" style="color:#ff7043;">&#8377;{d['resistance']:,.0f}</div><div class="rl-dot" style="background:#ff7043;box-shadow:0 0 8px #ff7043;margin:6px auto 0;"></div></div>
                <div class="rl-node-a" style="left:95%;"><div class="rl-lbl" style="color:#f44336;">Strong<br>Resistance</div><div class="rl-val" style="color:#f44336;">&#8377;{d['strong_resistance']:,.0f}</div><div class="rl-dot" style="background:#f44336;margin:6px auto 0;"></div></div>
            </div>
            <div style="position:relative;height:8px;border-radius:4px;background:linear-gradient(90deg,#26c6da 0%,#00bcd4 20%,#4fc3f7 40%,#ffb74d 58%,#ff7043 76%,#f44336 100%);box-shadow:0 2px 14px rgba(0,0,0,0.5);">
                <div style="position:absolute;left:{_pct_cp}%;top:50%;transform:translate(-50%,-50%);width:4px;height:22px;background:#fff;border-radius:2px;box-shadow:0 0 16px rgba(255,255,255,1);z-index:10;"></div>
            </div>
            <div style="position:relative;height:58px;">{_mp_node}</div>
        </div>

        <!-- Mobile: compact table (shown only on <520px) -->
        <table class="kl-mobile-table">
            <tr><td style="color:#26c6da;">&#9660; Strong Support</td><td style="color:#26c6da;">&#8377;{d['strong_support']:,.0f}</td></tr>
            <tr><td style="color:#00bcd4;">&#9660; Support (S1)</td><td style="color:#00bcd4;">&#8377;{d['support']:,.0f}</td></tr>
            <tr><td style="color:#4fc3f7;font-weight:700;">&#9654; NOW</td><td style="color:#4fc3f7;font-weight:700;">&#8377;{d['current_price']:,.0f}</td></tr>
            {mp_row}
            <tr><td style="color:#ff7043;">&#9650; Resistance (R1)</td><td style="color:#ff7043;">&#8377;{d['resistance']:,.0f}</td></tr>
            <tr><td style="color:#f44336;">&#9650; Strong Resistance</td><td style="color:#f44336;">&#8377;{d['strong_resistance']:,.0f}</td></tr>
        </table>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px;">
            <div style="background:rgba(244,67,54,0.08);border:1px solid rgba(244,67,54,0.25);border-radius:8px;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;">
                <span style="font-size:12px;color:#c8d8e0;">&#128205; To Resistance</span>
                <span style="font-size:15px;font-weight:700;color:#f44336;">+{_pts_to_res:,} pts</span>
            </div>
            <div style="background:rgba(0,188,212,0.08);border:1px solid rgba(0,188,212,0.25);border-radius:8px;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;">
                <span style="font-size:12px;color:#c8d8e0;">&#128205; To Support</span>
                <span style="font-size:15px;font-weight:700;color:#00bcd4;">\u2212{_pts_to_sup:,} pts</span>
            </div>
        </div>
    </div>
"""

    def generate_html_email(self, vol_support=None, vol_resistance=None, global_bias=None, vol_view="normal"):
        d=self.html_data
        # ── Header derived values ─────────────────────────────────────────
        # Expiry countdown
        try:
            from datetime import datetime as _dt
            expiry_dt = _dt.strptime(d.get('expiry',''), '%d-%b-%Y')
            days_left = (expiry_dt.date() - _dt.now().date()).days
            expiry_days_str = f"{days_left}d left" if days_left >= 0 else "Expired"
            expiry_days_col = '#00e676' if days_left > 3 else ('#ff9800' if days_left > 0 else '#ff4757')
        except Exception:
            expiry_days_str = '—'; expiry_days_col = '#ffb74d'
        # VIX
        vix_val   = d.get('vix_val')
        vix_trend = d.get('vix_trend','')
        vix_str   = f"{vix_val:.1f}" if vix_val else 'N/A'
        vix_arrow = ' ▲' if vix_trend == 'rising' else (' ▼' if vix_trend == 'falling' else '')
        vix_col   = '#ff9800' if vix_val and vix_val > 16 else ('#00e676' if vix_val and vix_val < 13 else '#ffb74d')
        # FII/DII net
        fii_summ  = d.get('fii_dii_summ', {})
        fii_avg   = fii_summ.get('fii_avg', 0)
        dii_avg   = fii_summ.get('dii_avg', 0)
        fii_col   = '#ff4757' if fii_avg < 0 else '#00e676'
        dii_col   = '#00e676' if dii_avg >= 0 else '#ff4757'
        fii_hdr   = f"{'+'if fii_avg>=0 else ''}{fii_avg:,.0f}Cr"
        dii_hdr   = f"{'+'if dii_avg>=0 else ''}{dii_avg:,.0f}Cr"
        # Global bias
        gb_str  = (global_bias or 'N/A').upper()
        gb_col  = '#00e676' if gb_str=='BULLISH' else ('#ff4757' if gb_str=='BEARISH' else '#ffb74d')
        # Spot + PCR colours
        pcr_v   = d.get('pcr', 1.0) if d.get('has_option_data') else 1.0
        pcr_col = '#00e676' if pcr_v > 1.2 else ('#ff4757' if pcr_v < 0.7 else '#ffb74d')
        sma20_bar ='bar-teal' if d['sma_20_above']  else 'bar-red'
        sma50_bar ='bar-teal' if d['sma_50_above']  else 'bar-red'
        sma200_bar='bar-teal' if d['sma_200_above'] else 'bar-red'
        macd_bar  ='bar-teal' if d['macd_bullish']  else 'bar-red'
        sma20_badge ='bullish' if d['sma_20_above']  else 'bearish'
        sma50_badge ='bullish' if d['sma_50_above']  else 'bearish'
        sma200_badge='bullish' if d['sma_200_above'] else 'bearish'
        macd_badge  ='bullish' if d['macd_bullish']  else 'bearish'
        sma20_lbl ='Above'  if d['sma_20_above']  else 'Below'
        sma50_lbl ='Above'  if d['sma_50_above']  else 'Below'
        sma200_lbl='Above'  if d['sma_200_above'] else 'Below'
        macd_lbl  ='Bullish' if d['macd_bullish']  else 'Bearish'
        sma20_ico ='\u2705' if d['sma_20_above']  else '\u274c'
        sma50_ico ='\u2705' if d['sma_50_above']  else '\u274c'
        sma200_ico='\u2705' if d['sma_200_above'] else '\u274c'
        macd_ico  ='\U0001f7e2' if d['macd_bullish'] else '\U0001f534'
        # ── Technical Indicators: Option A pill strip ────────────────────
        def _pill(lbl, val, badge, badge_cls):
            if   badge_cls == 'bullish': col='#00e676'; bg='rgba(0,230,118,0.08)';  bdr='rgba(0,230,118,0.25)';  bdg_bg='rgba(0,230,118,0.14)';  bdg_col='#00e676'
            elif badge_cls == 'bearish': col='#ff4757'; bg='rgba(255,71,87,0.08)';  bdr='rgba(255,71,87,0.25)';  bdg_bg='rgba(255,71,87,0.14)';  bdg_col='#ff4757'
            else:                        col='#ffb74d'; bg='rgba(255,183,77,0.07)'; bdr='rgba(255,183,77,0.22)'; bdg_bg='rgba(255,183,77,0.14)'; bdg_col='#ffb74d'
            return (
                f'<div style="display:flex;align-items:center;gap:7px;padding:6px 13px;border-radius:20px;'
                f'border:1px solid {bdr};background:{bg};white-space:nowrap;">'
                f'<span style="font-size:9px;letter-spacing:1.5px;color:rgba(128,222,234,0.6);text-transform:uppercase;">{lbl}</span>'
                f'<span style="font-family:JetBrains Mono,monospace;font-size:13px;font-weight:700;color:{col};">{val}</span>'
                f'<span style="font-size:8px;font-weight:700;padding:1px 7px;border-radius:8px;letter-spacing:0.5px;'
                f'background:{bdg_bg};color:{bdg_col};">{badge}</span>'
                f'</div>'
            )
        rsi_val   = d['rsi'];      rsi_badge_cls = 'bullish' if rsi_val < 30 else ('bearish' if rsi_val > 70 else 'neutral')
        rsi_badge = d['rsi_status']
        tech_pills = (
            _pill('RSI 14',    f"{d['rsi']:.1f}",          rsi_badge,   rsi_badge_cls) +
            _pill('SMA 20',    f"\u20b9{d['sma_20']:,.0f}", sma20_lbl,   sma20_badge) +
            _pill('SMA 50',    f"\u20b9{d['sma_50']:,.0f}", sma50_lbl,   sma50_badge) +
            _pill('SMA 200',   f"\u20b9{d['sma_200']:,.0f}",sma200_lbl,  sma200_badge) +
            _pill('MACD',      f"{d['macd']:.0f}",          macd_lbl,    macd_badge)
        )
        if d.get('has_option_data'):
            pcr_v = d.get('pcr', 1.0)
            pcr_badge_cls = 'bullish' if pcr_v > 1.2 else ('bearish' if pcr_v < 0.7 else 'neutral')
            pcr_lbl = 'Bullish' if pcr_v > 1.2 else ('Bearish' if pcr_v < 0.7 else 'Neutral')
            tech_pills += _pill('PCR', f"{pcr_v:.3f}", pcr_lbl, pcr_badge_cls)
        tech_cards = tech_pills  # kept same variable name so injection point unchanged
        oc_cards = self._build_enhanced_oc_cards()
        _cp  = d['current_price']
        _ss  = d['strong_support']    if d.get('strong_support')    is not None else (_cp - 300)
        _sr  = d['strong_resistance'] if d.get('strong_resistance') is not None else (_cp + 300)
        _rng = (_sr - _ss) if _sr != _ss else 1
        def _pct_real(val): return round(max(3,min(97,(val-_ss)/_rng*100)),2)
        _pct_cp     = _pct_real(_cp)
        _pts_to_res = int(d['resistance'] - _cp) if d.get('resistance') is not None else 0
        _pts_to_sup = int(_cp - d['support'])     if d.get('support')    is not None else 0
        _mp_node=""
        if d['has_option_data']:
            _mp_node=(f'<div class="rl-node-b" style="left:43%;">'
                      f'<div class="rl-dot" style="background:#ffb74d;box-shadow:0 0 8px #ffb74d;margin:0 auto 5px;"></div>'
                      f'<div class="rl-lbl" style="color:#ffb74d;">Max Pain</div>'
                      f'<div class="rl-val" style="color:#ffb74d;">\u20b9{d["max_pain"]:,}</div></div>')

        checklist_tab_html = build_strategy_checklist_html(
            d, vol_support=vol_support, vol_resistance=vol_resistance,
            global_bias=global_bias, vol_view=vol_view,
            vix_val=d.get('vix_val'), vix_trend=d.get('vix_trend')
        )
        intraday_oi_tab_html = build_intraday_oi_tab_html()
        pretrade_tab_html = build_pretrade_checklist_tab_html()

        # ── Heatmap tab HTML ─────────────────────────────────────────
        heatmap_tab_html = build_heatmap_tab_html(
            self.heatmap_data,
            self.heatmap_timestamp,
            self.heatmap_advance,
            self.heatmap_decline,
            self.heatmap_neutral,
        )

        # ── Heatmap-specific CSS ─────────────────────────────────────
        heatmap_css = get_heatmap_css()
        pretrade_css = get_pretrade_checklist_css()

        # ── Heatmap JavaScript ───────────────────────────────────────
        heatmap_js = get_heatmap_javascript()

        # ── Main JavaScript (all tabs + OI trend logic) ──────────────
        all_js = """
<script>
(function() {
    var INTERVAL  = 30000;
    var countdown = INTERVAL / 1000;

    function istNow() { return new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Kolkata'})); }
    function pad(n){ return String(n).padStart(2,'0'); }
    function fmtTime(d){ return pad(d.getHours())+':'+pad(d.getMinutes())+':'+pad(d.getSeconds()); }
    function fmtDate(d){
        var M=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
        return pad(d.getDate())+'-'+M[d.getMonth()]+'-'+d.getFullYear();
    }
    function tick() {
        var now = istNow();
        var clockEl = document.getElementById('live-ist-clock');
        if (clockEl) clockEl.textContent = fmtDate(now) + '  ' + fmtTime(now) + ' IST';
        countdown--;
        if (countdown < 0) countdown = INTERVAL / 1000;
        var cdEl = document.getElementById('refresh-countdown');
        if (cdEl) { var s=countdown%60; var m=Math.floor(countdown/60); cdEl.textContent=(m>0?m+'m ':'')+s+'s'; }
    }
    setInterval(tick, 1000);
    tick();

    // ── Option 2: JSON timestamp polling ──────────────────────────────────
    // Polls latest_report.json every 30s. Only reloads the page when the
    // Python script has actually re-run and the timestamp changed.
    // Saves active tab before reload → restores it after → no tab jump.
    var _lastKnownTimestamp = null;

    function getActiveTab() {
        var active = document.querySelector('.tab-btn.active');
        return active ? active.getAttribute('data-tab') : null;
    }

    function pollForUpdate() {
        fetch('latest_report.json?_=' + Date.now())   // cache-bust
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var ts = data.timestamp || null;
                if (_lastKnownTimestamp === null) {
                    // First load — just store the current timestamp, don't reload
                    _lastKnownTimestamp = ts;
                } else if (ts && ts !== _lastKnownTimestamp) {
                    // Save active tab before reload so we can restore it after
                    var activeTab = getActiveTab();
                    if (activeTab) sessionStorage.setItem('activeTab', activeTab);
                    console.log('[AutoRefresh] New data detected (' + ts + ') — reloading… (tab: ' + activeTab + ')');
                    location.reload();
                }
                // else: same timestamp → do nothing
            })
            .catch(function(err) {
                // latest_report.json not found or server not running — silently ignore
                console.warn('[AutoRefresh] Could not fetch latest_report.json:', err);
            });
        countdown = INTERVAL / 1000;
    }
    setInterval(pollForUpdate, INTERVAL);
    pollForUpdate();   // run once immediately on page load to capture baseline timestamp

    // ── Restore tab after reload ───────────────────────────────────────────
    // Runs once on every page load. If a tab was saved before reload, switch to it.
    (function restoreTabAfterReload() {
        var savedTab = sessionStorage.getItem('activeTab');
        if (savedTab) {
            sessionStorage.removeItem('activeTab');   // clear so normal nav isn't affected
            // Wait for DOM to be fully ready before switching
            setTimeout(function() { switchTab(savedTab); }, 100);
        }
    })();
})();

function switchTab(tab) {
    document.querySelectorAll('.tab-panel').forEach(function(p){ p.classList.remove('active'); });
    document.querySelectorAll('.tab-btn').forEach(function(b){ b.classList.remove('active'); });
    var panel=document.getElementById('tab-'+tab);
    var btn=document.querySelector('[data-tab="'+tab+'"]');
    if(panel) panel.classList.add('active');
    if(btn)   btn.classList.add('active');
    if(tab==='oi-trend') loadOILog();
    if(tab==='heatmap') { window.renderHeatmap && window.renderHeatmap(); }
}

function filterStrats(type, btn) {
    document.querySelectorAll('.filter-btn').forEach(function(b){ b.classList.remove('active'); });
    btn.classList.add('active');
    // Close all open panels first
    document.querySelectorAll('.sc-dp').forEach(function(p){ p.classList.remove('sc-dp-open'); });
    document.querySelectorAll('.sc-row').forEach(function(r){ r.classList.remove('sc-selected'); });
    // Show/hide rows and their paired panels
    document.querySelectorAll('.sc-row').forEach(function(r){
        var show = (type === 'all' || r.dataset.type === type);
        r.style.display = show ? '' : 'none';
        var chev = r.querySelector('.sc-row-chevron');
        if (chev) {
            var pid = chev.id.replace('chev-', '');
            var panel = document.getElementById(pid);
            if (panel) panel.style.display = show ? '' : 'none';
        }
    });
}

/* ── Compact row toggle / close / load ─────────────────────── */
function scToggle(row, panelId) {
    var panel      = document.getElementById(panelId);
    var wasOpen    = panel && panel.classList.contains('sc-dp-open');
    var wasSelected = row.classList.contains('sc-selected');
    // Close everything
    document.querySelectorAll('.sc-dp').forEach(function(p){ p.classList.remove('sc-dp-open'); });
    document.querySelectorAll('.sc-row').forEach(function(r){ r.classList.remove('sc-selected'); });
    // If it wasn't already open, open it
    if (!wasSelected || !wasOpen) {
        row.classList.add('sc-selected');
        if (panel) {
            panel.classList.add('sc-dp-open');
            setTimeout(function(){ panel.scrollIntoView({ behavior:'smooth', block:'nearest' }); }, 50);
        }
        selectStrat(row);
    }
}

function scClose(panelId, evt) {
    if (evt) evt.stopPropagation();
    var panel = document.getElementById(panelId);
    if (panel) panel.classList.remove('sc-dp-open');
    document.querySelectorAll('.sc-row').forEach(function(r){ r.classList.remove('sc-selected'); });
}

function scLoadPlan(safeName, evt) {
    if (evt) evt.stopPropagation();
    // Decode HTML entities
    var tmp = document.createElement('textarea');
    tmp.innerHTML = safeName;
    var stratName = tmp.value;
    var mapEl = document.getElementById('stratDataMap');
    var stratMap = {};
    try { stratMap = JSON.parse(mapEl.textContent || mapEl.innerHTML); } catch(e){}
    var info = stratMap[stratName] || {};
    _applyTradePlan(stratName, info.strike || 'N/A', info.rank || 'PRIMARY', typeof info.rr === 'number' ? info.rr : 0);
    // Button flash
    if (evt && evt.target) {
        var btn = evt.target, orig = btn.innerHTML;
        btn.innerHTML = '&#10003; Loaded!';
        btn.style.background = 'linear-gradient(135deg,#00e676,#00796b)';
        setTimeout(function(){ btn.innerHTML = orig; btn.style.background = ''; }, 1500);
    }
    // Scroll to trade plan
    var bannerEl = document.getElementById('tp-banner');
    if (bannerEl) { var s = bannerEl.closest('.section'); if (s) s.scrollIntoView({ behavior:'smooth', block:'start' }); }
}

function _applyTradePlan(stratName, strikeRec, rank, rr) {
    var nameEl   = document.getElementById('tp-strat-name');
    var strikeEl = document.getElementById('tp-strike-rec');
    var rankEl   = document.getElementById('tp-rank-badge');
    var bannerEl = document.getElementById('tp-banner');
    if (nameEl)   nameEl.textContent = stratName;
    if (strikeEl) strikeEl.innerHTML = '&#127919; ' + strikeRec;
    if (rankEl)   { rankEl.textContent = rank; rankEl.className = 'tp-rank-badge tp-rank-' + rank.toLowerCase(); }
    if (bannerEl) { bannerEl.classList.add('tp-banner-flash'); setTimeout(function(){ bannerEl.classList.remove('tp-banner-flash'); }, 600); }
}

function selectStrat(row) {
    if (!row || !row.dataset) return;
    var tmp = document.createElement('textarea');
    tmp.innerHTML = row.dataset.strat || '';
    var stratName = tmp.value;
    var mapEl = document.getElementById('stratDataMap');
    var stratMap = {};
    try { stratMap = JSON.parse(mapEl.textContent || mapEl.innerHTML); } catch(e){}
    var info = stratMap[stratName] || {};
    _applyTradePlan(stratName, info.strike || 'N/A', info.rank || 'PRIMARY', typeof info.rr === 'number' ? info.rr : 0);
}

var _oiInterval = 3;
var _oiData     = [];

function setOIInterval(mins, btn) {
    _oiInterval = mins;
    document.querySelectorAll('.oi-int-btn').forEach(function(b){ b.classList.remove('active'); });
    btn.classList.add('active');
    renderOITable(_oiData);
}

function fmtIN(n) {
    var abs = Math.abs(n);
    var sign = n < 0 ? '-' : '+';
    if (abs >= 10000000) return sign + (abs/10000000).toFixed(2) + ' Cr';
    if (abs >= 100000)   return sign + (abs/100000).toFixed(2)   + ' L';
    if (abs === 0)       return '0';
    return (n < 0 ? '-' : '+') + abs.toLocaleString('en-IN');
}

function signalHtml(sig) {
    var s = (sig||'').toUpperCase().trim();
    if (s === 'STRONG SELL') return '<span class="oi-signal-ssell">STRONG SELL</span>';
    if (s === 'SELL')        return '<span class="oi-signal-sell">SELL</span>';
    if (s === 'STRONG BUY')  return '<span class="oi-signal-sbuy">STRONG BUY</span>';
    if (s === 'BUY')         return '<span class="oi-signal-buy">BUY</span>';
    return '<span class="oi-signal-neutral">NEUTRAL</span>';
}

function vsigHtml(sig) {
    return (sig||'').toUpperCase() === 'BUY'
        ? '<span class="oi-vsig-buy">BUY</span>'
        : '<span class="oi-vsig-sell">SELL</span>';
}

function filterByInterval(data, mins) {
    // Step 1: Restrict to today only (use date from most-recent entry's timestamp)
    var todayData = data;
    if (data && data.length > 0) {
        var latestTs  = data[0].timestamp || '';
        var todayDate = latestTs.split(' ')[0]; // "04-Mar-2026"
        if (todayDate) {
            todayData = data.filter(function(row) {
                return (row.timestamp || '').startsWith(todayDate);
            });
        }
    }
    if (mins === 3) return todayData;
    // Step 2: Group by date+hour:slot so same time on different days never merges
    var grouped = {};
    todayData.forEach(function(row) {
        var ts      = row.timestamp || '';
        var dateKey = ts.split(' ')[0] || 'unknown';
        var parts   = (row.time||'00:00').split(':');
        var h       = parseInt(parts[0]||0);
        var m       = parseInt(parts[1]||0);
        var slotMin = Math.floor(m / mins) * mins;
        var key     = dateKey + '|' + String(h).padStart(2,'0') + ':' + String(slotMin).padStart(2,'0');
        if (!grouped[key]) grouped[key] = [];
        grouped[key].push(row);
    });
    var keys = Object.keys(grouped).sort().reverse();
    return keys.map(function(key) {
        var rows    = grouped[key];
        var last    = rows[rows.length - 1];
        var totalCE = rows.reduce(function(a,r){ return a+(r.call_oi_chg||0); }, 0);
        var totalPE = rows.reduce(function(a,r){ return a+(r.put_oi_chg||0); }, 0);
        var displayTime = key.split('|')[1] + ' IST';
        return {
            time:          displayTime,
            call_oi_chg:   totalCE,
            put_oi_chg:    totalPE,
            diff:          totalPE - totalCE,
            pcr:           last.pcr,
            opt_signal:    last.opt_signal,
            vwap:           last.vwap,
            spot_price:     last.spot_price,
            nifty_move_pct: last.nifty_move_pct,
            nearest_level:  last.nearest_level,
            nearest_label:  last.nearest_label,
            distance_pts:   last.distance_pts,
            vwap_signal:    last.vwap_signal,
            _isLive:       rows[0]._isLive,
        };
    });
}

/* ── FOCUS / DETAIL view toggle ───────────────────────────── */
var _oiViewMode = 'focus';
function setOIView(mode) {
    _oiViewMode = mode;
    var tableWrap = document.querySelector('.oi-table-wrap');
    if (!tableWrap) return;
    if (mode === 'detail') {
        tableWrap.classList.add('oi-detail-mode');
    } else {
        tableWrap.classList.remove('oi-detail-mode');
    }
    var btnFocus  = document.getElementById('btnFocus');
    var btnDetail = document.getElementById('btnDetail');
    if (btnFocus)  btnFocus.classList.toggle('oi-view-active',  mode === 'focus');
    if (btnDetail) btnDetail.classList.toggle('oi-view-active', mode === 'detail');
}
/* Apply FOCUS mode on page load */
window.addEventListener('load', function(){ setOIView('focus'); });

function renderOITable(data) {
    var tbody = document.getElementById('oiTableBody');
    if (!tbody) return;
    if (!data || data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="15" class="oi-empty-state">&#128218; No data yet.</td></tr>';
        return;
    }
    var filtered = filterByInterval(data, _oiInterval);
    var latest = filtered[0];

    // ── Update summary cards (text only, no DOM rebuild) ──
    if (latest) {
        var el;
        el = document.getElementById('oiLatestPCR'); if (el) el.textContent = latest.pcr || '—';
        el = document.getElementById('oiLatestDiff');
        if (el) { el.textContent = fmtIN(latest.diff || 0); el.className = 'oi-sum-val ' + ((latest.diff||0) >= 0 ? 'oi-diff-pos' : 'oi-diff-neg'); }
        el = document.getElementById('oiLatestSpot'); if (el) el.textContent = '₹' + ((latest.spot_price||0).toLocaleString('en-IN'));
        el = document.getElementById('oiLatestSignal'); if (el) el.innerHTML = signalHtml(latest.opt_signal);
    }
    var ce = document.getElementById('oiChartEntries');
    if (ce) ce.textContent = filtered.length + ' candles';

    // ── Redraw sparkline (canvas, no flicker) ──
    drawSparkline(filtered);

    // ── Table rebuild: full rebuild on interval change, smart append on same interval ──
    var existingRows = tbody.querySelectorAll('tr[data-time]');
    var existingTimes = {};
    existingRows.forEach(function(r){ existingTimes[r.getAttribute('data-time')] = r; });

    // Detect if the current table rows match the filtered set — if not, full rebuild
    var filteredTimes = filtered.map(function(r){ return r.time || ''; });
    var existingTimesList = Object.keys(existingTimes);
    var needsFullRebuild = (existingTimesList.length > 0) && (
        existingTimesList.length !== filteredTimes.length ||
        filteredTimes.some(function(t){ return !existingTimes[t]; }) ||
        existingTimesList.some(function(t){ return filteredTimes.indexOf(t) < 0; })
    );
    if (needsFullRebuild) {
        tbody.innerHTML = '';
        existingTimes = {};
    }

    // Remove LIVE badge from previous live row
    var prevLive = tbody.querySelector('.oi-live-row');
    if (prevLive) {
        prevLive.classList.remove('oi-live-row');
        var liveInd = prevLive.querySelector('.oi-live-ind');
        if (liveInd) liveInd.remove();
        var td = prevLive.querySelector('td:first-child');
        if (td) { var div = td.querySelector('.oi-time-cell'); if (div) td.textContent = div.textContent.replace('LIVE','').trim(); }
    }

    // Build new rows for times not yet in table, prepend them
    var newRowsHtml = '';
    filtered.forEach(function(row, idx) {
        var t = row.time || '';
        if (!existingTimes[t]) {
            var isLive  = (idx === 0);
            var diffCls = (row.diff||0) >= 0 ? 'oi-diff-pos' : 'oi-diff-neg';
            var timeCell = isLive
                ? '<div class="oi-time-cell"><span class="oi-time-val">' + t + '</span>&nbsp;<span class="oi-live-ind">LIVE</span></div>'
                : '<div class="oi-time-cell"><span class="oi-time-val">' + t + '</span></div>';
            var isBuy = (row.opt_signal||'').toUpperCase().indexOf('BUY') >= 0;
            var isSell = (row.opt_signal||'').toUpperCase().indexOf('SELL') >= 0;
            var nlabel = row.nearest_label || (isBuy ? 'R1' : isSell ? 'S1' : '—');
            var nval   = row.nearest_level ? '₹' + row.nearest_level.toLocaleString('en-IN') : '—';
            var nlevelHtml = row.nearest_level
                ? '<span class="oi-nlevel-badge ' + (isBuy ? 'oi-nlevel-res' : 'oi-nlevel-sup') + '">'
                  + '<span class="oi-nlevel-label">' + nlabel + '</span>'
                  + nval + '</span>'
                : '<span style="color:rgba(176,190,197,0.3);">—</span>';
            var distHtml = row.distance_pts != null
                ? '<span class="oi-dist-val ' + (isBuy ? 'oi-dist-res' : 'oi-dist-sup') + '">'
                  + (isBuy ? '+' : '-') + Math.abs(row.distance_pts) + ' pts'
                  + (row.nearest_label === 'S2' || row.nearest_label === 'R2'
                      ? ' <span style="font-size:8px;opacity:0.6;">(to ' + (row.nearest_label||'') + ')</span>'
                      : '')
                  + '</span>'
                : '<span style="color:rgba(176,190,197,0.3);">—</span>';

            // ── Spot Δ ──
            var prevRow = filtered[idx + 1];
            var spotDelta = (prevRow && prevRow.spot_price && row.spot_price)
                ? Math.round((row.spot_price - prevRow.spot_price) * 10) / 10
                : null;
            var spotDeltaHtml;
            if (spotDelta === null) {
                spotDeltaHtml = '<span style="color:rgba(176,190,197,0.2);">—</span>';
            } else if (Math.abs(spotDelta) < 0.5) {
                spotDeltaHtml = '<span class="oi-sdelta oi-sdelta-fl">→ 0.0</span>';
            } else if (spotDelta > 0) {
                spotDeltaHtml = '<span class="oi-sdelta oi-sdelta-up">▲ +' + spotDelta.toFixed(1) + '</span>';
            } else {
                spotDeltaHtml = '<span class="oi-sdelta oi-sdelta-dn">▼ ' + spotDelta.toFixed(1) + '</span>';
            }

            // ── Nifty Move % ──
            var nmp = row.nifty_move_pct;
            var niftyMovePctHtml;
            if (nmp === null || nmp === undefined) {
                niftyMovePctHtml = '<span style="color:rgba(176,190,197,0.2);">—</span>';
            } else {
                var sign  = nmp >= 0 ? '+' : '';
                var arrow, cls;
                if (Math.abs(nmp) < 0.1) {
                    arrow = '→'; cls = 'oi-nifty-flat';
                } else if (nmp >= 1.0) {
                    arrow = '▲'; cls = 'oi-nifty-up-strong';
                } else if (nmp >= 0.5) {
                    arrow = '▲'; cls = 'oi-nifty-up-mid';
                } else if (nmp > 0) {
                    arrow = '▲'; cls = 'oi-nifty-up-weak';
                } else if (nmp <= -1.0) {
                    arrow = '▼'; cls = 'oi-nifty-dn-strong';
                } else if (nmp <= -0.5) {
                    arrow = '▼'; cls = 'oi-nifty-dn-mid';
                } else {
                    arrow = '▼'; cls = 'oi-nifty-dn-weak';
                }
                niftyMovePctHtml = '<span class="oi-nifty-move ' + cls + '">'
                    + arrow + ' ' + sign + nmp.toFixed(2) + '%</span>';
            }

            // ── Signal Streak ──
            var streakCount = 1;
            var curSig = (row.opt_signal || '').toUpperCase();
            for (var si = idx + 1; si < filtered.length; si++) {
                if ((filtered[si].opt_signal || '').toUpperCase() === curSig) streakCount++;
                else break;
            }
            var streakCls = isBuy ? 'oi-streak-buy' : isSell ? 'oi-streak-sell' : 'oi-streak-neu';
            var streakLbl = streakCount === 1 ? 'NEW<br>signal' : 'streak';
            var pips = '';
            for (var pi = 0; pi < 6; pi++) {
                var pipIdx = idx + pi;
                var pipSig = pipIdx < filtered.length ? (filtered[pipIdx].opt_signal || '').toUpperCase() : '';
                var pipCls = pipSig.indexOf('BUY') >= 0 ? 'oi-pip-buy' : pipSig.indexOf('SELL') >= 0 ? 'oi-pip-sell' : pipSig ? 'oi-pip-neu' : 'oi-pip-old';
                pips += '<div class="oi-pip ' + pipCls + '"></div>';
            }
            var streakHtml = '<div class="oi-streak ' + streakCls + '">'
                + '<div><div class="oi-streak-num">×' + streakCount + '</div><div class="oi-streak-lbl">' + streakLbl + '</div></div>'
                + '<div class="oi-pips">' + pips + '</div>'
                + '</div>';

            newRowsHtml += '<tr class="' + (isLive ? 'oi-live-row' : '') + '" data-time="' + t + '">'
                + '<td>' + timeCell + '</td>'
                + '<td class="col-detail oi-call-val">' + fmtIN(row.call_oi_chg||0) + '</td>'
                + '<td class="col-detail oi-put-val">'  + fmtIN(row.put_oi_chg||0)  + '</td>'
                + '<td class="col-detail ' + diffCls + '">' + fmtIN(row.diff||0) + '</td>'
                + (function(){
                    var pcrV = parseFloat(row.pcr) || 0;
                    var pcrCls = pcrV >= 1.1 ? 'oi-pcr-bull' : pcrV <= 0.9 ? 'oi-pcr-bear' : 'oi-pcr-neu';
                    var barW = Math.min(100, Math.round((pcrV / 2) * 100));
                    return '<td class="oi-pcr-val ' + pcrCls + '"><span class="oi-pcr-cell">'
                        + (row.pcr || '—')
                        + '<span class="oi-pcr-bar-wrap"><span class="oi-pcr-bar ' + pcrCls + '-bar" style="width:' + barW + '%"></span></span>'
                        + '</span></td>';
                })()
                + '<td>' + signalHtml(row.opt_signal) + '</td>'
                + '<td class="oi-spot-cell">'+ (row.spot_price ? row.spot_price.toFixed(2) : '—') + '</td>'
                + '<td>' + spotDeltaHtml + '</td>'
                + '<td>' + niftyMovePctHtml + '</td>'
                + '<td>' + streakHtml + '</td>'
                + '<td>' + nlevelHtml + '</td>'
                + '<td>' + distHtml + '</td>'
                + (function(){
                    var rsi = row.rsi_15m;
                    if (rsi == null) return '<td><span style="color:rgba(176,190,197,0.25);">—</span></td>';
                    var rsiCol, rsiBg, rsiBdr, rsiLbl;
                    if (rsi >= 70) {
                        rsiCol='#ff4757'; rsiBg='rgba(255,71,87,0.12)'; rsiBdr='rgba(255,71,87,0.3)'; rsiLbl='OB';
                    } else if (rsi <= 30) {
                        rsiCol='#00e676'; rsiBg='rgba(0,230,118,0.12)'; rsiBdr='rgba(0,230,118,0.3)'; rsiLbl='OS';
                    } else if (rsi >= 55) {
                        rsiCol='#69f0ae'; rsiBg='rgba(105,240,174,0.08)'; rsiBdr='rgba(105,240,174,0.25)'; rsiLbl='';
                    } else if (rsi <= 45) {
                        rsiCol='#fca5a5'; rsiBg='rgba(252,165,165,0.08)'; rsiBdr='rgba(252,165,165,0.25)'; rsiLbl='';
                    } else {
                        rsiCol='#ffb74d'; rsiBg='rgba(255,183,77,0.08)'; rsiBdr='rgba(255,183,77,0.2)'; rsiLbl='';
                    }
                    var rsiBadge = rsiLbl
                        ? '<span style="font-size:8px;font-weight:700;letter-spacing:1px;padding:1px 5px;border-radius:3px;background:'+rsiBg+';color:'+rsiCol+';border:1px solid '+rsiBdr+';">'+rsiLbl+'</span>'
                        : '<span style="font-size:8px;color:rgba(128,222,234,0.3);">neutral</span>';
                    return '<td><div style="display:flex;flex-direction:column;align-items:center;gap:3px;">'
                        + '<span style="font-family:monospace;font-size:12px;font-weight:700;color:'+rsiCol+';">'+rsi.toFixed(1)+'</span>'
                        + rsiBadge
                        + '</div></td>';
                })()
                + (function(){
                    var emaSig = row.ema_signal;
                    var e5  = row.ema5;
                    var e13 = row.ema13;
                    if (!emaSig || e5 == null || e13 == null) return '<td><span style="color:rgba(176,190,197,0.25);">—</span></td>';
                    var emaIsBuy = emaSig === 'BUY';
                    var eCol = emaIsBuy ? '#00e676' : '#ff4757';
                    var eBg  = emaIsBuy ? 'rgba(0,230,118,0.12)' : 'rgba(255,71,87,0.12)';
                    var eBdr = emaIsBuy ? 'rgba(0,230,118,0.3)'  : 'rgba(255,71,87,0.3)';
                    var eArr = emaIsBuy ? '▲' : '▼';
                    var eGap = Math.abs(e5 - e13).toFixed(1);
                    return '<td><div style="display:flex;flex-direction:column;align-items:center;gap:3px;">'
                        + '<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 9px;border-radius:6px;font-size:11px;font-weight:700;background:'+eBg+';color:'+eCol+';border:1px solid '+eBdr+';">'
                        + eArr + ' ' + emaSig + '</span>'
                        + '<span style="font-size:8px;color:rgba(128,222,234,0.3);font-family:monospace;">gap '+eGap+'</span>'
                        + '</div></td>';
                })()
                + (function(){
                    var vwapVal = row.vwap;
                    if (vwapVal == null || vwapVal === 0) {
                        return '<td class="col-detail"><span style="color:rgba(176,190,197,0.3);">—</span></td>';
                    }
                    var spot = row.spot_price || 0;
                    var aboveVwap = spot >= vwapVal;
                    var vwapCls = aboveVwap ? 'oi-vwap-bull' : 'oi-vwap-bear';
                    var vwapArrow = aboveVwap ? '▲' : '▼';
                    var vwapColor = aboveVwap ? '#4ade80' : '#f87171';
                    return '<td class="col-detail oi-vwap-cell"><span style="color:' + vwapColor + ';font-weight:700;">'
                        + vwapArrow + ' ₹' + vwapVal.toLocaleString('en-IN', {minimumFractionDigits:2, maximumFractionDigits:2})
                        + '</span><br><span style="font-size:8px;color:rgba(147,197,253,0.5);letter-spacing:0.5px;">'
                        + (aboveVwap ? 'Above' : 'Below') + '</span></td>';
                })()
                + '</tr>';
        } else if (idx === 0) {
            // Mark existing top row as LIVE
            var r = existingTimes[t];
            r.classList.add('oi-live-row');
            var td = r.querySelector('td:first-child');
            if (td && !td.querySelector('.oi-live-ind')) {
                td.innerHTML = '<div class="oi-time-cell"><span class="oi-time-val">' + t + '</span>&nbsp;<span class="oi-live-ind">LIVE</span></div>';
            }
        }
    });

    if (newRowsHtml) {
        // ── Bulletproof no-scroll-jump insert ───────────────────────────
        // overflow-anchor:none on tbody stops Chrome's scroll anchoring from
        // auto-adjusting when rows are prepended (the main cause of jumps).
        // We also manually save + restore window.scrollY with double-rAF to
        // cover Firefox and Safari which don't support overflow-anchor.
        var winSy   = window.scrollY || window.pageYOffset;
        var docEl   = document.documentElement;
        var bodyEl  = document.body;
        // Disable CSS scroll-behavior so our scrollTo is truly instant
        var prevDocSB  = docEl.style.scrollBehavior;
        var prevBodySB = bodyEl.style.scrollBehavior;
        docEl.style.scrollBehavior  = 'auto';
        bodyEl.style.scrollBehavior = 'auto';
        // Disable browser scroll anchoring on the table body
        tbody.style.overflowAnchor = 'none';

        tbody.insertAdjacentHTML('afterbegin', newRowsHtml);

        // Double-rAF: frame 1 = layout/reflow, frame 2 = paint → scroll after both
        requestAnimationFrame(function() {
            requestAnimationFrame(function() {
                window.scrollTo(0, winSy);
                // Restore everything
                tbody.style.overflowAnchor = '';
                docEl.style.scrollBehavior  = prevDocSB;
                bodyEl.style.scrollBehavior = prevBodySB;
            });
        });
    }

    // Remove empty state row if present
    var emptyRow = tbody.querySelector('.oi-empty-state');
    if (emptyRow) emptyRow.closest('tr').remove();
}

function fmtOI(n) {
    var abs = Math.abs(n);
    var sign = n >= 0 ? '+' : '-';
    if (abs >= 10000000) return sign + (abs/10000000).toFixed(2) + ' Cr';
    if (abs >= 100000)   return sign + (abs/100000).toFixed(2) + ' L';
    if (n === 0) return '0';
    return (n >= 0 ? '+' : '') + n.toLocaleString('en-IN');
}

function drawSparkline(data) {
    var canvas = document.getElementById('oiSparklineCanvas');
    if (!canvas || !canvas.getContext) return;
    var dpr = window.devicePixelRatio || 1;

    var reversed = data.slice().reverse();
    var diffs = reversed.map(function(r){ return r.diff || 0; });
    if (diffs.length < 2) return;

    /* ── Stat boxes ── */
    var latest = diffs[diffs.length - 1];
    var high   = Math.max.apply(null, diffs);
    var low    = Math.min.apply(null, diffs);
    var isBull = latest >= 0;
    var el;
    el = document.getElementById('oiStatLatest');
    if (el) { el.textContent = fmtOI(latest); el.style.color = isBull ? '#34d399' : '#f87171'; }
    el = document.getElementById('oiStatHigh');   if (el) el.textContent = fmtOI(high);
    el = document.getElementById('oiStatLow');    if (el) el.textContent = fmtOI(low);
    el = document.getElementById('oiStatSignal');
    if (el) { el.textContent = isBull ? 'BUY' : 'SELL'; el.style.color = isBull ? '#34d399' : '#f87171'; }
    el = document.getElementById('oiStatSignalSub');
    if (el) el.textContent = isBull ? 'Bias improving' : 'Bias declining';

    /* ── Signal history bar ── */
    var bar = document.getElementById('oiSignalBar');
    if (bar) {
        bar.innerHTML = '';
        var absMax = Math.max(Math.abs(high), Math.abs(low)) || 1;
        reversed.forEach(function(r) {
            var seg = document.createElement('div');
            seg.style.flex = '1';
            seg.style.height = '100%';
            seg.style.borderRadius = '1px';
            seg.style.background = (r.diff || 0) >= 0 ? '#10b981' : '#ef4444';
            seg.style.opacity = Math.abs(r.diff || 0) / absMax * 0.75 + 0.25;
            bar.appendChild(seg);
        });
    }

    /* ── Canvas sizing ── */
    var wrap = canvas.parentElement;
    var W = wrap ? wrap.clientWidth : 600;
    var H = 200;
    canvas.width  = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width  = W + 'px';
    canvas.style.height = H + 'px';
    var ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, W, H);

    var padT = 16, padB = 20, padL = 4, padR = 16;
    var cW = W - padL - padR;
    var cH = H - padT - padB;
    var n  = diffs.length;

    var minV  = Math.min.apply(null, diffs.concat([0]));
    var maxV  = Math.max.apply(null, diffs.concat([0]));
    var range = (maxV - minV) || 1;

    function toX(i) { return padL + (i / (n - 1)) * cW; }
    function toY(v) { return padT + (1 - (v - minV) / range) * cH; }
    var zeroY = toY(0);

    /* ── Grid lines (5 levels) ── */
    var gridCount = 5;
    for (var g = 0; g <= gridCount; g++) {
        var gv = minV + (range / gridCount) * g;
        var gy = toY(gv);
        ctx.beginPath();
        ctx.strokeStyle = (Math.abs(gv) < range * 0.02)
            ? 'rgba(79,195,247,0.3)' : 'rgba(79,195,247,0.07)';
        ctx.lineWidth = (Math.abs(gv) < range * 0.02) ? 1 : 0.5;
        if (Math.abs(gv) < range * 0.02) ctx.setLineDash([6, 4]);
        else ctx.setLineDash([]);
        ctx.moveTo(padL, gy); ctx.lineTo(W - padR, gy);
        ctx.stroke();
    }
    ctx.setLineDash([]);

    /* ── Colored fill segments ── */
    for (var i = 0; i < n - 1; i++) {
        var x0 = toX(i),   y0 = toY(diffs[i]);
        var x1 = toX(i+1), y1 = toY(diffs[i+1]);
        var pos0 = diffs[i]   >= 0;
        var pos1 = diffs[i+1] >= 0;
        if (pos0 === pos1) {
            ctx.beginPath();
            ctx.moveTo(x0, zeroY); ctx.lineTo(x0, y0);
            ctx.lineTo(x1, y1);   ctx.lineTo(x1, zeroY);
            ctx.closePath();
            ctx.fillStyle = pos0 ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)';
            ctx.fill();
        } else {
            var ratio = Math.abs(diffs[i]) / (Math.abs(diffs[i]) + Math.abs(diffs[i+1]));
            var xMid  = x0 + ratio * (x1 - x0);
            ctx.beginPath();
            ctx.moveTo(x0, zeroY); ctx.lineTo(x0, y0); ctx.lineTo(xMid, zeroY);
            ctx.closePath();
            ctx.fillStyle = pos0 ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)';
            ctx.fill();
            ctx.beginPath();
            ctx.moveTo(xMid, zeroY); ctx.lineTo(x1, y1); ctx.lineTo(x1, zeroY);
            ctx.closePath();
            ctx.fillStyle = pos1 ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)';
            ctx.fill();
        }
    }

    /* ── Stroke line ── */
    for (var i = 0; i < n - 1; i++) {
        var bothPos = diffs[i] >= 0 && diffs[i+1] >= 0;
        var bothNeg = diffs[i] <  0 && diffs[i+1] <  0;
        ctx.beginPath();
        ctx.strokeStyle = bothPos ? '#34d399' : bothNeg ? '#f87171' : '#fbbf24';
        ctx.lineWidth = 2; ctx.lineJoin = 'round';
        ctx.moveTo(toX(i),   toY(diffs[i]));
        ctx.lineTo(toX(i+1), toY(diffs[i+1]));
        ctx.stroke();
    }

    /* ── Glowing endpoint ── */
    var lx = toX(n-1), ly = toY(diffs[n-1]);
    var dotCol = diffs[n-1] >= 0 ? '#34d399' : '#f87171';
    ctx.beginPath(); ctx.arc(lx, ly, 9, 0, Math.PI*2);
    ctx.fillStyle = dotCol + '22'; ctx.fill();
    ctx.beginPath(); ctx.arc(lx, ly, 5, 0, Math.PI*2);
    ctx.fillStyle = dotCol; ctx.fill();

    /* ── Y-axis labels ── */
    var yEl = document.getElementById('oiYLabels');
    if (yEl) {
        yEl.innerHTML = '';
        for (var g = gridCount; g >= 0; g--) {
            var gv  = minV + (range / gridCount) * g;
            var lbl = document.createElement('div');
            lbl.className   = 'oi-y-label';
            lbl.style.color = gv >= 0 ? 'rgba(52,211,153,0.4)' : 'rgba(248,113,113,0.4)';
            lbl.textContent = fmtOI(Math.round(gv));
            yEl.appendChild(lbl);
        }
    }

    /* ── X-axis time labels ── */
    var xEl = document.getElementById('oiXLabels');
    if (xEl) {
        xEl.innerHTML = '';
        var xStep = Math.max(1, Math.floor(n / 6));
        reversed.forEach(function(r, i) {
            if (i % xStep === 0 || i === n - 1) {
                var sp = document.createElement('span');
                sp.className   = 'oi-x-label';
                sp.textContent = r.time || '';
                xEl.appendChild(sp);
            }
        });
    }

    /* ── Tooltip + Crosshair ── */
    var tooltip   = document.getElementById('oiChartTooltip');
    var crosshair = document.getElementById('oiCrosshair');

    canvas.onmousemove = function(e) {
        if (!tooltip || !crosshair) return;
        var rect = canvas.getBoundingClientRect();
        var mx   = e.clientX - rect.left;
        var idx  = Math.round((mx - padL) / cW * (n - 1));
        if (idx < 0 || idx >= n) {
            tooltip.style.display = 'none';
            crosshair.style.display = 'none';
            return;
        }
        var row = reversed[idx];
        var dv  = row.diff || 0;
        var dc  = dv >= 0 ? '#34d399' : '#f87171';

        crosshair.style.display = 'block';
        crosshair.style.left    = toX(idx) + 'px';

        var ttTime = document.getElementById('oiTTTime');
        var ttDiff = document.getElementById('oiTTDiff');
        var ttCE   = document.getElementById('oiTTCE');
        var ttPE   = document.getElementById('oiTTPE');
        var ttSig  = document.getElementById('oiTTSignal');
        if (ttTime) ttTime.textContent = (row.time || '') + ' IST';
        if (ttDiff) { ttDiff.textContent = fmtOI(dv); ttDiff.style.color = dc; }
        if (ttCE)   ttCE.textContent   = fmtOI(row.call_oi_chg || 0);
        if (ttPE)   ttPE.textContent   = fmtOI(row.put_oi_chg  || 0);
        if (ttSig)  { ttSig.textContent = dv >= 0 ? 'BUY' : 'SELL'; ttSig.style.color = dc; }

        var wrapW = wrap ? wrap.clientWidth : W;
        var tx    = toX(idx) + 14;
        if (tx + 175 > wrapW) tx = toX(idx) - 189;
        tooltip.style.left    = tx + 'px';
        tooltip.style.top     = '10px';
        tooltip.style.display = 'block';
    };

    canvas.onmouseleave = function() {
        if (tooltip)   tooltip.style.display   = 'none';
        if (crosshair) crosshair.style.display = 'none';
    };
}

function loadOILog() {
    var url = 'oi_log.json?_t=' + Date.now();
    fetch(url, {cache:'no-store'})
        .then(function(r){ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(function(data) {
            if (Array.isArray(data) && data.length > 0) {
                data[0]._isLive = true;
                _oiData = data;
                window._oiData = data;
                renderOITable(data);
                var now = new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Kolkata'}));
                var el  = document.getElementById('oiLastFetch');
                if (el) el.textContent = 'Last fetch: ' + String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0') + ':' + String(now.getSeconds()).padStart(2,'0') + ' IST';
            }
        })
        .catch(function(e) {
            var tbody = document.getElementById('oiTableBody');
            if (tbody) tbody.innerHTML = '<tr><td colspan="15" class="oi-empty-state">&#9888; Could not load oi_log.json</td></tr>';
        });
}

window.addEventListener('load', function(){
    if (window.location.hash === '#oi-trend') { switchTab('oi-trend'); }
    else { loadOILog(); }
    // Auto-select first strategy row so Trade Plan is pre-filled
    var firstRow = document.querySelector('.sc-row');
    if (firstRow) { selectStrat(firstRow); }
});

window.addEventListener('resize', function(){
    if (_oiData.length > 0) drawSparkline(filterByInterval(_oiData, _oiInterval));
});

/* ══ SIDEBAR NAV JS ══════════════════════════════════════════════ */
var _nsbCollapsed = false;
var _nsbActiveId  = 'snapshot';
var _currentTab   = 'main';   /* ← tracks active tab so navSidebarTo works correctly */

/* Patch switchTab to keep _currentTab in sync */
var _origSwitchTab = switchTab;
switchTab = function(tab) {
    _origSwitchTab(tab);
    _currentTab = tab;
};

function _scrollToSec(secId) {
    var target = document.getElementById('sec-' + secId);
    if (!target) {
        window.scrollTo({ top: 0, behavior: 'smooth' });
        return;
    }
    /* Get height of sticky bars so we don't hide section title behind them */
    var offset = 0;
    var mobBar = document.getElementById('nsbMobBar');
    if (mobBar && mobBar.offsetParent !== null) {
        offset += mobBar.offsetHeight;
    }
    var header = document.querySelector('.header');
    /* Header is NOT sticky, so no need to add it */
    var rect   = target.getBoundingClientRect();
    var absTop = rect.top + window.pageYOffset - offset - 8;
    window.scrollTo({ top: absTop, behavior: 'smooth' });
}

function toggleNavSidebar() {
    _nsbCollapsed = !_nsbCollapsed;
    var sb = document.getElementById('navSidebar');
    if (sb) sb.classList.toggle('collapsed', _nsbCollapsed);
}

function navSidebarTo(secId, tabId) {
    /* 1. Switch tab if needed */
    if (tabId !== _currentTab) {
        switchTab(tabId);
    }
    /* 2. Set active sidebar item */
    document.querySelectorAll('.nsb-item').forEach(function(el){ el.classList.remove('active'); });
    var activeEl = document.getElementById('nsi-' + secId);
    if (activeEl) activeEl.classList.add('active');
    _nsbActiveId = secId;
    /* 3. Scroll after tab paint — 150ms is reliable across browsers */
    setTimeout(function(){ _scrollToSec(secId); }, 150);
}

function openNsbDrawer()  { document.getElementById('nsbDrawer').classList.add('open'); }
function closeNsbDrawer() { document.getElementById('nsbDrawer').classList.remove('open'); }

function mobNavTo(secId, tabId, label) {
    /* Update mobile drawer active state */
    document.querySelectorAll('.nsb-mob-item').forEach(function(el){ el.classList.remove('active'); });
    var el = document.getElementById('nsmd-' + secId);
    if (el) el.classList.add('active');
    /* Update mobile title bar */
    var titleEl = document.getElementById('nsbMobTitle');
    if (titleEl) titleEl.innerHTML = label;
    /* Close drawer first, then switch + scroll */
    closeNsbDrawer();
    /* Sync desktop sidebar active state */
    document.querySelectorAll('.nsb-item').forEach(function(el){ el.classList.remove('active'); });
    var deskEl = document.getElementById('nsi-' + secId);
    if (deskEl) deskEl.classList.add('active');
    _nsbActiveId = secId;
    /* Switch tab if needed */
    if (tabId !== _currentTab) { switchTab(tabId); }
    /* Scroll after drawer close animation + tab paint */
    setTimeout(function(){ _scrollToSec(secId); }, 200);
}
</script>
"""

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nifty 50 OI Analysis</title>
    <link href="https://fonts.googleapis.com/css2?family=Oxanium:wght@400;600;700;800&family=Rajdhani:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600;700&family=Outfit:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&family=Orbitron:wght@700;900&display=swap" rel="stylesheet">
    <style>
        *{{margin:0;padding:0;box-sizing:border-box;}}
        html{{scroll-behavior:smooth;}}
        body{{font-family:'Rajdhani',sans-serif;background:linear-gradient(135deg,#0f2027 0%,#203a43 50%,#2c5364 100%);min-height:100vh;padding:0;color:#c8d8e0;overflow-x:hidden;-webkit-text-size-adjust:100%;}}

        .tab-nav{{display:flex;gap:0;border-bottom:2px solid rgba(79,195,247,0.2);overflow-x:auto;scrollbar-width:none;background:linear-gradient(135deg,#0f2027,#203a43);}}
        .tab-nav::-webkit-scrollbar{{display:none;}}
        .tab-btn{{display:flex;align-items:center;gap:8px;padding:13px clamp(14px,2.5vw,28px);font-family:'Oxanium',sans-serif;font-size:clamp(10px,1.4vw,13px);font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:rgba(176,190,197,0.5);cursor:pointer;border:none;background:transparent;border-bottom:3px solid transparent;white-space:nowrap;transition:all 0.25s ease;position:relative;bottom:-2px;}}
        .tab-btn:hover{{color:#4fc3f7;background:rgba(79,195,247,0.05);}}
        .tab-btn.active{{color:#4fc3f7;border-bottom-color:#4fc3f7;background:rgba(79,195,247,0.08);}}
        .tab-dot{{width:7px;height:7px;border-radius:50%;background:rgba(79,195,247,0.3);flex-shrink:0;transition:all 0.25s ease;}}
        .tab-btn.active .tab-dot{{background:#4fc3f7;box-shadow:0 0 8px #4fc3f7;}}
        .tab-badge{{font-size:9px;padding:2px 7px;border-radius:10px;background:rgba(79,195,247,0.12);border:1px solid rgba(79,195,247,0.25);color:#4fc3f7;}}
        .new-badge .tab-badge{{background:rgba(0,230,118,0.12);border-color:rgba(0,230,118,0.3);color:#00e676;}}
        .tab-panel{{display:none;}}
        .tab-panel.active{{display:block;}}

        .container{{max-width:100%;width:100%;margin:0;background:rgba(15,32,39,0.85);backdrop-filter:blur(20px);border-radius:0;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,0.5);border:none;min-width:0;}}

        /* ══ OPTION B HEADER ══════════════════════════════════════════ */
        .header{{background:linear-gradient(180deg,#061828 0%,#04111f 100%);border-bottom:2px solid rgba(79,195,247,0.2);padding:0;position:relative;overflow:hidden;}}
        .header::before{{content:'';position:absolute;inset:0;background:radial-gradient(circle at 30% 50%,rgba(79,195,247,0.05) 0%,transparent 60%);pointer-events:none;}}

        /* Banner row */
        .hb-banner{{display:flex;align-items:center;justify-content:space-between;padding:14px 22px;border-bottom:1px solid rgba(79,195,247,0.12);flex-wrap:wrap;gap:12px;position:relative;z-index:1;}}
        .hb-left{{display:flex;align-items:center;gap:14px;}}
        .hb-nse-badge{{padding:5px 14px;border-radius:6px;font-family:'Oxanium',sans-serif;font-size:13px;font-weight:900;letter-spacing:2px;color:#000;background:linear-gradient(135deg,#4fc3f7,#00e5ff);flex-shrink:0;}}
        .hb-title-main{{font-family:'Oxanium',sans-serif;font-size:clamp(18px,2.5vw,26px);font-weight:900;color:#ffffff;letter-spacing:0.5px;}}
        .hb-title-sub{{font-size:11px;letter-spacing:2px;color:#4fc3f7;text-transform:uppercase;margin-top:4px;font-weight:700;}}
        .hb-chips{{display:flex;gap:8px;flex-wrap:wrap;}}
        .hb-chip{{text-align:center;padding:7px 16px;border-radius:9px;background:rgba(0,0,0,0.4);border:1px solid rgba(79,195,247,0.22);flex-shrink:0;}}
        .hb-chip-lbl{{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:1.5px;color:#80deea;text-transform:uppercase;margin-bottom:4px;font-weight:700;}}
        .hb-chip-val{{font-family:'Oxanium',sans-serif;font-size:17px;font-weight:800;line-height:1;}}

        /* Status row */
        .hb-status{{display:flex;align-items:center;justify-content:space-between;padding:9px 22px;background:rgba(0,0,0,0.3);flex-wrap:wrap;gap:8px;position:relative;z-index:1;border-bottom:1px solid rgba(79,195,247,0.08);}}
        .hb-s-item{{display:flex;align-items:center;gap:6px;font-family:'JetBrains Mono',monospace;font-size:12px;color:#c8dde8;white-space:nowrap;font-weight:600;}}
        .hb-s-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0;animation:sb-pulse 2s ease-in-out infinite;}}
        .hb-s-val{{font-weight:700;color:#ffffff;margin-left:3px;font-size:13px;}}

        /* Tabs */
        .tab-nav{{display:flex;gap:0;border-bottom:none;overflow-x:auto;scrollbar-width:none;background:rgba(0,0,0,0.2);position:relative;z-index:1;}}
        .tab-nav::-webkit-scrollbar{{display:none;}}
        .tab-btn{{display:flex;align-items:center;gap:8px;padding:13px clamp(14px,2vw,24px);font-family:'Oxanium',sans-serif;font-size:clamp(11px,1.4vw,13px);font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:rgba(200,221,232,0.65);cursor:pointer;border:none;background:transparent;border-bottom:2px solid transparent;white-space:nowrap;transition:all 0.2s ease;position:relative;bottom:-1px;}}
        .tab-btn:hover{{color:#4fc3f7;background:rgba(79,195,247,0.05);}}
        .tab-btn.active{{color:#4fc3f7;border-bottom-color:#4fc3f7;background:rgba(79,195,247,0.07);}}
        .tab-dot{{width:6px;height:6px;border-radius:50%;background:rgba(79,195,247,0.3);flex-shrink:0;transition:all 0.25s ease;}}
        .tab-btn.active .tab-dot{{background:#4fc3f7;box-shadow:0 0 8px #4fc3f7;}}
        .tab-badge{{font-size:8px;padding:2px 6px;border-radius:8px;background:rgba(79,195,247,0.12);border:1px solid rgba(79,195,247,0.25);color:#4fc3f7;}}
        .new-badge .tab-badge{{background:rgba(192,132,252,0.12);border-color:rgba(192,132,252,0.3);color:#c084fc;}}
        .tab-panel{{display:none;}}
        .tab-panel.active{{display:block;}}

        /* Status bar dots kept for JS compatibility */
        .sb-dot-gen{{background:#00e676;box-shadow:0 0 8px #00e676;}}
        .sb-dot-clock{{background:#4fc3f7;box-shadow:0 0 8px #4fc3f7;}}
        .sb-dot-cd{{background:#b388ff;box-shadow:0 0 8px #b388ff;}}
        @keyframes sb-pulse{{50%{{opacity:0.25;}}}}

        /* Responsive header */
        @media(max-width:900px){{
            .hb-chips .hb-chip:nth-child(n+4){{display:none;}}
        }}
        @media(max-width:600px){{
            .hb-banner{{padding:10px 12px;gap:8px;}}
            .hb-chips{{display:none;}}
            .hb-title-main{{font-size:13px;}}
            .hb-status{{padding:6px 12px;gap:4px;}}
            .hb-s-item{{font-size:9px;}}
            .tab-btn{{padding:9px 10px;font-size:9px;letter-spacing:0.8px;}}
        }}

        .section{{padding:clamp(14px,2.5vw,28px) clamp(12px,2.5vw,26px);border-bottom:1px solid rgba(79,195,247,0.08);}}
        .section:last-child{{border-bottom:none;}}
        .section-title{{font-family:'Oxanium',sans-serif;font-size:clamp(10px,1.5vw,13px);font-weight:700;letter-spacing:clamp(1px,0.3vw,2.5px);color:#4fc3f7;text-transform:uppercase;display:flex;align-items:center;gap:10px;margin-bottom:clamp(12px,2vw,20px);padding-bottom:12px;border-bottom:1px solid rgba(79,195,247,0.18);flex-wrap:wrap;}}
        .section-title span{{font-size:clamp(14px,2vw,18px);}}


        /* ── COMPACT STAT CARDS ─────────────────────────────────── */
        .g-compact{{background:#111827;border:1px solid #1e2a3a;border-radius:8px;padding:8px 10px;position:relative;overflow:hidden;transition:transform .2s,border-color .2s;}}
        .g-compact:hover{{transform:translateY(-2px);border-color:rgba(79,195,247,0.4)!important;}}
        /* ── ENHANCED STAT CARDS ──────────────────────────────────── */
        .g-compact{{transition:transform .25s ease,border-color .25s ease,box-shadow .25s ease;}}
        .g-compact:hover{{transform:translateY(-4px)!important;box-shadow:0 16px 40px rgba(0,0,0,0.45)!important;}}
        .cc-top{{display:flex;align-items:center;gap:6px;margin-bottom:4px;}}
        .cc-ico{{font-size:13px;line-height:1;flex-shrink:0;}}
        .cc-lbl{{font-size:8px;letter-spacing:.1em;text-transform:uppercase;color:#8896b3;font-weight:600;flex:1;}}
        .cc-val{{font-family:'JetBrains Mono',monospace;font-size:19px;font-weight:700;line-height:1;color:#e2e8f8;margin-bottom:4px;letter-spacing:-.02em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
        .cc-sub{{font-size:8px;color:#4a5578;margin-bottom:3px;font-family:'JetBrains Mono',monospace;}}
        .cc-bar{{height:2px;background:#1e2a3a;border-radius:1px;overflow:hidden;}}
        .cc-bar-fill{{height:100%;border-radius:1px;}}
        .cc-bar-fill.bar-teal{{background:linear-gradient(90deg,#00bcd4,#4fc3f7);}}
        .cc-bar-fill.bar-red{{background:linear-gradient(90deg,#f44336,#ff5722);}}
        .cc-bar-fill.bar-gold{{background:linear-gradient(90deg,#ffb74d,#ffd54f);}}
        .g-compact .tag{{font-size:8px;padding:1px 6px;border-radius:3px;white-space:nowrap;flex-shrink:0;}}
        .g{{background:rgba(255,255,255,0.04);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid rgba(79,195,247,0.18);border-radius:16px;position:relative;overflow:hidden;transition:all 0.35s cubic-bezier(0.4,0,0.2,1);min-width:0;}}
        .g::before{{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.25),transparent);z-index:1;}}
        .g::after{{content:'';position:absolute;top:-60%;left:-30%;width:50%;height:200%;background:linear-gradient(105deg,transparent,rgba(255,255,255,0.04),transparent);transform:skewX(-15deg);transition:left 0.6s ease;z-index:0;}}
        .g:hover::after{{left:130%;}}
        .g:hover{{background:rgba(79,195,247,0.09);border-color:rgba(79,195,247,0.45);box-shadow:0 12px 40px rgba(0,0,0,0.35),inset 0 1px 0 rgba(255,255,255,0.1);transform:translateY(-4px);}}
        .g-hi{{background:rgba(79,195,247,0.09);border-color:rgba(79,195,247,0.35);}}
        .g-red{{background:rgba(244,67,54,0.06);border-color:rgba(244,67,54,0.25);}}
        .g-red:hover{{background:rgba(244,67,54,0.1);border-color:rgba(244,67,54,0.45);}}
        .card-grid{{display:grid;gap:6px;}}
        .grid-5{{grid-template-columns:repeat(5,minmax(0,1fr));}}
        .grid-4{{grid-template-columns:repeat(4,minmax(0,1fr));}}
        .g .card-top-row{{display:flex;align-items:center;gap:10px;margin-bottom:10px;position:relative;z-index:2;padding:14px 16px 0;}}
        .card-ico{{font-size:clamp(16px,2vw,22px);line-height:1;flex-shrink:0;}}
        .lbl{{font-size:clamp(8px,1vw,9px);letter-spacing:2.5px;color:rgba(128,222,234,0.65);text-transform:uppercase;font-weight:600;line-height:1.3;word-break:break-word;}}
        .val{{font-family:'Oxanium',sans-serif;font-size:clamp(16px,2.5vw,24px);font-weight:700;color:#fff;display:block;margin-bottom:10px;position:relative;z-index:2;padding:0 16px;word-break:break-word;overflow:hidden;text-overflow:ellipsis;}}
        .bar-wrap{{height:5px;background:rgba(0,0,0,0.35);border-radius:3px;margin:0 16px 12px;overflow:hidden;position:relative;z-index:2;}}
        .bar-fill{{height:100%;border-radius:3px;transition:width 1.2s cubic-bezier(0.4,0,0.2,1);}}
        .bar-teal{{background:linear-gradient(90deg,#00bcd4,#4fc3f7);box-shadow:0 0 8px rgba(79,195,247,0.6);}}
        .bar-red{{background:linear-gradient(90deg,#f44336,#ff5722);box-shadow:0 0 8px rgba(244,67,54,0.5);}}
        .bar-gold{{background:linear-gradient(90deg,#ffb74d,#ffd54f);box-shadow:0 0 8px rgba(255,183,77,0.5);}}
        .card-foot{{display:flex;justify-content:space-between;align-items:center;padding:0 16px 14px;position:relative;z-index:2;flex-wrap:wrap;gap:4px;}}
        .sub{{font-size:10px;color:#8fa8b8;font-family:'JetBrains Mono',monospace;}}
        .tag{{display:inline-flex;align-items:center;padding:3px 11px;border-radius:20px;font-size:clamp(9px,1.2vw,11px);font-weight:700;letter-spacing:0.5px;font-family:'Rajdhani',sans-serif;white-space:nowrap;}}
        .tag-neu{{background:rgba(255,183,77,0.15);color:#ffb74d;border:1px solid rgba(255,183,77,0.35);}}
        .tag-bull{{background:rgba(0,229,255,0.12);color:#00e5ff;border:1px solid rgba(0,229,255,0.35);}}
        .tag-bear{{background:rgba(255,82,82,0.12);color:#ff5252;border:1px solid rgba(255,82,82,0.35);}}

        .snap-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;}}
        .snap-card{{padding:18px 16px;}}
        .snap-card .card-top-row{{margin-bottom:8px;padding:0;}}
        .snap-card .val{{font-size:clamp(18px,3vw,26px);padding:0;margin-bottom:0;}}

        .md-widget{{position:relative;overflow:hidden;background:linear-gradient(135deg,rgba(255,255,255,0.07),rgba(255,255,255,0.02));border:1px solid rgba(255,255,255,0.1);border-radius:16px;padding:10px 16px;backdrop-filter:blur(20px);display:flex;flex-direction:column;gap:4px;}}
        .md-glow{{position:absolute;top:-80%;left:-80%;width:260%;height:260%;background:conic-gradient(from 180deg,#ff6b35 0deg,#ffcd3c 120deg,#4ecdc4 240deg,#ff6b35 360deg);opacity:0.05;animation:md-rotate 8s linear infinite;border-radius:50%;pointer-events:none;}}
        @keyframes md-rotate{{to{{transform:rotate(360deg);}}}}
        .md-row-top{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;position:relative;z-index:1;}}
        .md-label{{display:flex;align-items:center;gap:7px;font-family:'Space Mono',monospace;font-size:clamp(7px,1vw,8px);letter-spacing:3px;color:rgba(255,255,255,0.3);text-transform:uppercase;}}
        .md-live-dot{{width:6px;height:6px;border-radius:50%;background:#4ecdc4;box-shadow:0 0 8px #4ecdc4;animation:md-pulse 2s ease-in-out infinite;flex-shrink:0;}}
        @keyframes md-pulse{{50%{{opacity:0.25;}}}}
        .md-pills-top{{display:flex;gap:8px;flex-wrap:wrap;}}
        .md-pill{{font-family:'Space Mono',monospace;font-size:clamp(8px,1.2vw,10px);font-weight:700;padding:4px clamp(8px,1.5vw,14px);border-radius:20px;letter-spacing:1px;white-space:nowrap;}}
        .md-pill-bull{{background:rgba(78,205,196,0.12);border:1px solid rgba(78,205,196,0.4);color:#4ecdc4;}}
        .md-pill-bear{{background:rgba(255,100,100,0.12);border:1px solid rgba(255,100,100,0.4);color:#ff6b6b;}}
        .md-pill-conf-high{{background:rgba(78,205,196,0.12);border:1px solid rgba(78,205,196,0.35);color:#4ecdc4;}}
        .md-pill-conf-med{{background:rgba(255,205,60,0.12);border:1px solid rgba(255,205,60,0.35);color:#ffcd3c;}}
        .md-pill-conf-low{{background:rgba(255,107,107,0.12);border:1px solid rgba(255,107,107,0.35);color:#ff6b6b;}}
        .md-row-bottom{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;position:relative;z-index:1;}}
        .md-direction{{font-family:'Orbitron',monospace;font-weight:900;font-size:clamp(16px,2.8vw,22px);letter-spacing:clamp(0.5px,0.2vw,1.5px);line-height:1;}}

        .logic-box{{background:rgba(79,195,247,0.04);border:1px solid rgba(79,195,247,0.14);border-left:3px solid #4fc3f7;border-radius:10px;padding:10px 16px;margin-top:12px;}}
        .logic-box-head{{font-family:'Oxanium',sans-serif;font-size:10px;font-weight:700;color:#4fc3f7;letter-spacing:2px;margin-bottom:7px;}}
        .logic-grid{{display:grid;grid-template-columns:1fr 1fr;gap:5px 20px;}}
        .logic-item{{display:flex;align-items:center;gap:7px;font-size:clamp(10px,1.3vw,11px);color:rgba(176,190,197,0.6);flex-wrap:wrap;}}
        .logic-item .lv{{font-family:'JetBrains Mono',monospace;font-size:10px;color:rgba(176,190,197,0.4);}}
        .lc-bull{{display:inline-flex;align-items:center;font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:600;padding:2px 8px;border-radius:4px;white-space:nowrap;background:rgba(0,230,118,0.1);color:#00e676;border:1px solid rgba(0,230,118,0.28);}}
        .lc-bear{{display:inline-flex;align-items:center;font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:600;padding:2px 8px;border-radius:4px;white-space:nowrap;background:rgba(255,82,82,0.1);color:#ff5252;border:1px solid rgba(255,82,82,0.28);}}
        .lc-side{{display:inline-flex;align-items:center;font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:600;padding:2px 8px;border-radius:4px;white-space:nowrap;background:rgba(255,183,77,0.1);color:#ffb74d;border:1px solid rgba(255,183,77,0.28);}}
        .lc-info{{display:inline-flex;align-items:center;font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:600;padding:2px 8px;border-radius:4px;white-space:nowrap;background:rgba(79,195,247,0.08);color:#4fc3f7;border:1px solid rgba(79,195,247,0.22);}}

        .rl-node-a{{position:absolute;bottom:0;transform:translateX(-50%);text-align:center;}}
        .rl-node-b{{position:absolute;top:0;transform:translateX(-50%);text-align:center;}}
        .rl-dot{{width:12px;height:12px;border-radius:50%;border:2px solid rgba(10,20,35,0.9);}}
        .rl-lbl{{font-size:clamp(7px,1vw,10px);font-weight:700;text-transform:uppercase;letter-spacing:0.4px;line-height:1.3;white-space:nowrap;color:#c8d8e0;}}
        .rl-val{{font-size:clamp(9px,1.3vw,13px);font-weight:700;color:#fff;white-space:nowrap;margin-top:2px;}}
        /* Mobile key levels: hide absolute labels, show compact table instead */
        .kl-mobile-table{{display:none;width:100%;border-collapse:collapse;font-family:'JetBrains Mono',monospace;font-size:11px;margin-top:10px;}}
        .kl-mobile-table td{{padding:6px 10px;border-bottom:1px solid rgba(79,195,247,0.08);}}
        .kl-mobile-table td:last-child{{text-align:right;font-weight:700;}}
        .kl-bar-section{{display:block;}}
        @media(max-width:520px){{
            .kl-bar-section{{display:none;}}
            .kl-mobile-table{{display:table;}}
        }}

        .pf-live-badge{{display:inline-block;padding:2px 10px;border-radius:10px;font-size:10px;font-weight:700;letter-spacing:1px;}}
        .pf-live{{background:rgba(0,230,118,0.1);color:#00e676;border:1px solid rgba(0,230,118,0.3);}}
        .pf-estimated{{background:rgba(255,138,101,0.1);color:#ff8a65;border:1px solid rgba(255,138,101,0.3);}}
        .pf-date-range{{font-size:11px;color:#80deea;font-weight:400;letter-spacing:1px;}}

        /* ── Option 2: Horizontal Flow Meters ── */
        .pf2-meter-row{{margin-bottom:16px;}}
        .pf2-meter-head{{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;flex-wrap:wrap;gap:6px;}}
        .pf2-meter-labels{{display:flex;align-items:baseline;gap:10px;}}
        .pf2-lbl{{font-family:'Oxanium',sans-serif;font-size:18px;font-weight:800;color:#e0f7fa;letter-spacing:1px;}}
        .pf2-sublbl{{font-size:11px;letter-spacing:1.5px;color:rgba(128,222,234,0.6);text-transform:uppercase;font-weight:600;}}
        .pf2-val{{font-family:'JetBrains Mono',monospace;font-size:clamp(16px,2.5vw,22px);font-weight:700;letter-spacing:-0.5px;}}
        .pf2-unit{{font-size:10px;color:rgba(128,222,234,0.4);font-weight:400;letter-spacing:1px;}}
        .pf2-track{{height:10px;background:rgba(0,0,0,0.4);border-radius:5px;overflow:hidden;}}
        .pf2-fill{{height:100%;border-radius:5px;transition:width 1s ease;}}

        /* Daily net dot chips */
        .pf2-dots-wrap{{display:grid;grid-template-columns:repeat(10,minmax(0,1fr));gap:6px;margin:16px 0;}}
        .pf2-dot{{border:1px solid;border-radius:8px;padding:6px 4px;text-align:center;}}
        .pf2-dot-date{{font-size:9px;letter-spacing:0.5px;color:rgba(128,222,234,0.45);margin-bottom:4px;font-family:'JetBrains Mono',monospace;}}
        .pf2-dot-net{{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;}}

        .pf-avg-strip{{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;align-items:center;background:rgba(6,13,20,0.75);border:1px solid rgba(79,195,247,0.1);border-radius:14px;padding:18px 24px;margin-bottom:16px;}}
        .pf-avg-cell{{text-align:center;min-width:0;}}
        .pf-avg-eyebrow{{font-size:10px;letter-spacing:2px;color:rgba(79,195,247,0.7);text-transform:uppercase;margin-bottom:6px;font-weight:700;}}
        .pf-avg-val{{font-family:'Oxanium',sans-serif;font-size:clamp(20px,3vw,28px);font-weight:800;line-height:1;letter-spacing:-0.5px;word-break:break-word;}}
        .pf-avg-unit{{font-size:9px;color:#8899aa;margin-top:3px;letter-spacing:1px;}}
        .pf-avg-sep{{width:1px;height:48px;background:rgba(79,195,247,0.2);margin:0 16px;flex-shrink:0;}}
        .pf-insight-box{{border-radius:12px;padding:16px 18px;}}
        .pf-insight-header{{display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap;}}
        .pf-insight-lbl{{font-size:10px;letter-spacing:2px;font-weight:700;text-transform:uppercase;}}
        .pf-verdict-badge{{display:inline-block;padding:3px 14px;border-radius:20px;font-size:clamp(10px,1.5vw,11px);font-weight:800;letter-spacing:1px;white-space:nowrap;}}
        .pf-insight-text{{font-size:clamp(12px,1.5vw,13px);color:#cfd8dc;line-height:1.85;font-weight:500;}}

        @media(max-width:768px){{
            .pf2-dots-wrap{{grid-template-columns:repeat(5,minmax(0,1fr));}}
            .pf2-lbl{{font-size:16px;}}
            .pf2-val{{font-size:15px;}}
            .pf-avg-strip{{grid-template-columns:1fr;gap:0;padding:14px;}}
            .pf-avg-sep{{display:none;}}
            .pf-avg-cell{{display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgba(79,195,247,0.07);}}
            .pf-avg-cell:last-child{{border-bottom:none;}}
            .pf-avg-eyebrow{{margin-bottom:0;}}
        }}
        @media(max-width:480px){{
            .pf2-dots-wrap{{grid-template-columns:repeat(5,minmax(0,1fr));gap:4px;}}
            .pf2-dot{{padding:5px 2px;}}
            .pf2-dot-net{{font-size:10px;}}
        }}

        .nc-section-header{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:18px;padding-bottom:14px;border-bottom:1px solid rgba(79,195,247,0.14);}}
        .nc-header-left{{display:flex;align-items:center;gap:14px;}}
        .nc-header-icon{{width:44px;height:44px;border-radius:10px;background:linear-gradient(135deg,#1e3a5f,#1a3052);border:1px solid rgba(79,195,247,0.3);display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0;box-shadow:0 4px 14px rgba(79,195,247,0.15);}}
        .nc-header-title{{font-family:'Outfit',sans-serif;font-size:clamp(15px,2vw,19px);font-weight:700;color:#e2eaf5;letter-spacing:0.3px;}}
        .nc-header-sub{{font-family:'Outfit',sans-serif;font-size:13px;font-weight:500;color:#a8c4d8;margin-top:2px;letter-spacing:0.5px;}}
        .nc-atm-badge{{background:#1f2a42;color:#60a5fa;font-family:'Outfit',sans-serif;font-size:12px;font-weight:700;padding:6px 16px;border-radius:20px;letter-spacing:1.5px;border:1px solid rgba(96,165,250,0.25);box-shadow:0 2px 10px rgba(96,165,250,0.1);white-space:nowrap;}}
        .nc-dir-box{{border-radius:14px;padding:clamp(14px,2vw,20px) clamp(14px,2vw,22px);margin-bottom:18px;box-shadow:0 4px 24px rgba(0,0,0,0.3);}}
        .nc-dir-bar{{width:4px;border-radius:2px;flex-shrink:0;min-height:60px;}}
        .nc-dir-tag{{font-family:'Outfit',sans-serif;font-size:11px;font-weight:700;letter-spacing:2px;color:#a8c4d8;text-transform:uppercase;margin-bottom:6px;}}
        .nc-dir-name{{font-family:'Outfit',sans-serif;font-size:clamp(18px,3vw,28px);font-weight:700;line-height:1;margin-bottom:6px;letter-spacing:-0.5px;}}
        .nc-dir-signal{{font-family:'Outfit',sans-serif;font-size:clamp(10px,1.3vw,12px);font-weight:400;}}
        .nc-meters-panel{{display:flex;flex-direction:column;gap:14px;min-width:180px;justify-content:center;}}
        .nc-meter-row{{display:flex;flex-direction:column;gap:5px;}}
        .nc-meter-head-row{{display:flex;justify-content:space-between;align-items:center;}}
        .nc-meter-label{{font-family:'Outfit',sans-serif;font-size:9px;font-weight:700;letter-spacing:2px;color:rgba(148,163,184,0.45);text-transform:uppercase;}}
        .nc-meter-track{{position:relative;height:8px;background:rgba(0,0,0,0.4);border-radius:4px;overflow:visible;width:clamp(120px,20vw,200px);}}
        .nc-meter-fill{{height:100%;border-radius:4px;}}
        .nc-meter-head{{position:absolute;top:50%;transform:translate(-50%,-50%);width:14px;height:14px;border-radius:50%;border:2px solid rgba(10,18,30,0.85);}}
        .nc-meter-pct{{font-family:'Oxanium',sans-serif;font-size:clamp(12px,1.8vw,15px);font-weight:700;letter-spacing:0.5px;}}
        .nc-cards-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;}}
        .nc-card{{background:rgba(20,28,45,0.85);border:1px solid rgba(79,195,247,0.12);border-radius:14px;padding:clamp(12px,2vw,18px) clamp(12px,2vw,18px) 14px;transition:all 0.3s ease;position:relative;overflow:hidden;min-width:0;}}
        .nc-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.1),transparent);}}
        .nc-card:hover{{border-color:rgba(79,195,247,0.3);background:rgba(25,35,55,0.9);transform:translateY(-3px);box-shadow:0 10px 30px rgba(0,0,0,0.3);}}
        .nc-card-header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;flex-wrap:wrap;gap:4px;}}
        .nc-card-label{{font-family:'Outfit',sans-serif;font-size:clamp(8px,1.2vw,10px);font-weight:700;letter-spacing:2px;color:rgba(148,163,184,0.6);text-transform:uppercase;}}
        .nc-card-value{{font-family:'Oxanium',sans-serif;font-size:clamp(20px,3.5vw,30px);font-weight:700;line-height:1;margin-bottom:6px;letter-spacing:-0.5px;word-break:break-word;}}
        .nc-card-sub{{font-family:'JetBrains Mono',monospace;font-size:10px;color:rgba(100,116,139,0.7);margin-bottom:14px;}}
        .nc-card-btn{{display:block;width:100%;padding:9px 14px;border-radius:7px;text-align:center;font-family:'Outfit',sans-serif;font-size:clamp(11px,1.5vw,13px);font-weight:700;letter-spacing:0.5px;cursor:default;}}

        .annot-badge{{font-size:9px;padding:2px 10px;border-radius:8px;background:rgba(0,230,118,0.1);border:1px solid rgba(0,230,118,0.25);color:#00e676;font-family:'JetBrains Mono',monospace;letter-spacing:1px;font-weight:700;white-space:nowrap;}}
        .na-inline{{color:rgba(176,190,197,0.3);font-family:'JetBrains Mono',monospace;font-size:13px;}}
        .o5-wrap{{border-radius:16px;overflow:hidden;border:1px solid rgba(239,68,68,0.2);background:rgba(6,10,18,0.97);margin-bottom:0;}}
        .o5-top-banner{{background:linear-gradient(90deg,rgba(239,68,68,0.12),rgba(185,28,28,0.06),transparent);border-bottom:1px solid rgba(239,68,68,0.12);padding:16px 22px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px;}}
        .o5-banner-left{{display:flex;align-items:center;gap:16px;flex-wrap:wrap;}}
        .o5-score-circle{{width:62px;height:62px;border-radius:50%;background:rgba(239,68,68,0.08);border:2px solid;display:flex;flex-direction:column;align-items:center;justify-content:center;flex-shrink:0;}}
        .o5-score-num{{font-family:'Orbitron',monospace;font-size:22px;font-weight:900;line-height:1;}}
        .o5-score-lbl{{font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1.5px;text-transform:uppercase;opacity:0.75;margin-top:2px;}}
        .o5-verdict{{font-family:'Orbitron',monospace;font-size:clamp(17px,2.4vw,24px);font-weight:900;letter-spacing:2px;}}
        .o5-sub{{font-size:12px;color:rgba(148,163,184,0.75);margin-top:4px;line-height:1.5;max-width:520px;}}
        .o5-pills{{display:flex;gap:8px;flex-wrap:wrap;}}
        .o5-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:rgba(255,255,255,0.04);}}
        .o5-tile{{padding:16px 16px 18px;position:relative;overflow:hidden;transition:filter 0.2s;}}
        .o5-tile:hover{{filter:brightness(1.2);}}
        .o5-bear{{background:rgba(14,4,6,0.97);}}
        .o5-bull{{background:rgba(4,14,10,0.97);}}
        .o5-neu{{background:rgba(14,12,4,0.97);}}
        .o5-na{{background:rgba(8,10,14,0.97);}}
        .o5-tile-bar{{position:absolute;bottom:0;left:0;right:0;height:2px;}}
        .o5-tile-top{{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;margin-bottom:10px;}}
        .o5-tile-label{{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;line-height:1.5;flex:1;}}
        .o5-bear .o5-tile-label{{color:rgba(248,113,113,0.85);}}
        .o5-bull .o5-tile-label{{color:rgba(52,211,153,0.85);}}
        .o5-neu  .o5-tile-label{{color:rgba(251,191,36,0.85);}}
        .o5-na   .o5-tile-label{{color:rgba(148,163,184,0.65);}}
        .o5-chip{{font-family:'Orbitron',monospace;font-size:12px;font-weight:900;min-width:30px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;flex-shrink:0;padding:0 8px;}}
        .o5-chip-bear{{background:rgba(239,68,68,0.2);color:#f87171;border:1px solid rgba(239,68,68,0.5);}}
        .o5-chip-bull{{background:rgba(16,185,129,0.2);color:#34d399;border:1px solid rgba(16,185,129,0.5);}}
        .o5-chip-neu{{background:rgba(245,158,11,0.2);color:#fbbf24;border:1px solid rgba(245,158,11,0.5);}}
        .o5-chip-na{{background:rgba(100,116,139,0.15);color:rgba(148,163,184,0.7);border:1px solid rgba(100,116,139,0.3);font-size:10px;}}
        .o5-val{{font-family:'Oxanium',sans-serif;font-size:clamp(15px,2vw,20px);font-weight:700;line-height:1;margin-bottom:6px;}}
        .o5-msg{{font-size:11px;color:rgba(148,163,184,0.75);line-height:1.4;font-family:'JetBrains Mono',monospace;}}
        .auto-badge{{font-size:8px;padding:1px 6px;border-radius:4px;background:rgba(0,230,118,0.1);border:1px solid rgba(0,230,118,0.25);color:#00e676;font-weight:700;letter-spacing:0.5px;}}
        .manual-badge{{font-size:8px;padding:1px 6px;border-radius:4px;background:rgba(79,195,247,0.08);border:1px solid rgba(79,195,247,0.2);color:#4fc3f7;font-weight:700;letter-spacing:0.5px;}}
        .sc-pill{{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;padding:4px 12px;border-radius:20px;letter-spacing:1px;}}
        .sc-pill-bull{{background:rgba(0,230,118,0.1);border:1px solid rgba(0,230,118,0.3);color:#00e676;}}
        .sc-pill-bear{{background:rgba(255,82,82,0.1);border:1px solid rgba(255,82,82,0.3);color:#ff5252;}}
        .sc-pill-neu{{background:rgba(255,183,77,0.1);border:1px solid rgba(255,183,77,0.3);color:#ffb74d;}}
        .sc-pill-na{{background:rgba(176,190,197,0.06);border:1px solid rgba(176,190,197,0.15);color:rgba(176,190,197,0.4);}}
        /* ══ COMPACT STRATEGY WIDGET ══════════════════════════════════════ */
        .sc-summary-strip{{display:flex;align-items:center;gap:12px;background:rgba(6,13,20,0.8);border:1px solid rgba(79,195,247,0.12);border-radius:10px;padding:10px 16px;margin-bottom:10px;flex-wrap:wrap;}}
        .sc-ss-item{{display:flex;align-items:center;gap:6px;}}
        .sc-ss-dot{{width:7px;height:7px;border-radius:50%;flex-shrink:0;}}
        .sc-ss-lbl{{font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:1px;color:rgba(128,222,234,0.7);}}
        .sc-ss-val{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;}}
        .sc-ss-sep{{width:1px;height:18px;background:rgba(79,195,247,0.12);}}
        /* 2-column compact grid */
        .sc-compact-grid{{display:grid;grid-template-columns:1fr 1fr;gap:6px;}}
        /* row card */
        .sc-row{{display:grid;grid-template-columns:3px 26px 1fr auto 18px;align-items:center;gap:0;background:rgba(10,18,32,0.9);border:1px solid rgba(79,195,247,0.1);border-radius:10px;cursor:pointer;transition:all 0.18s ease;overflow:hidden;min-height:50px;}}
        .sc-row:hover{{background:rgba(16,28,48,0.95);border-color:rgba(79,195,247,0.3);box-shadow:0 4px 18px rgba(0,0,0,0.4);}}
        .sc-row.sc-selected{{border-color:#00e5ff;background:rgba(0,229,255,0.06);box-shadow:0 0 0 1px #00e5ff44,0 6px 20px rgba(0,229,255,0.12);}}
        .sc-row-bar{{width:3px;height:100%;border-radius:10px 0 0 10px;align-self:stretch;min-height:50px;}}
        .sc-row-num{{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;color:rgba(176,190,197,0.45);text-align:center;padding:0 4px;}}
        .sc-row-body{{padding:10px 10px 10px 6px;min-width:0;}}
        .sc-row-name{{font-family:'Oxanium',sans-serif;font-size:14px;font-weight:700;color:#e0f7fa;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:3px;}}
        .sc-row-strike{{font-family:'JetBrains Mono',monospace;font-size:10px;color:rgba(128,222,234,0.75);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
        .sc-row-strike span{{color:#4fc3f7;}}
        .sc-row-meta{{display:flex;flex-direction:column;align-items:flex-end;gap:4px;padding:10px 8px 10px 6px;flex-shrink:0;}}
        .sc-row-tag{{font-size:10px;font-weight:700;letter-spacing:0.5px;padding:3px 8px;border-radius:8px;white-space:nowrap;}}
        .sc-rb{{font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;letter-spacing:0.5px;padding:2px 7px;border-radius:4px;white-space:nowrap;}}
        .sc-rb-primary{{background:rgba(0,229,255,0.12);border:1px solid rgba(0,229,255,0.4);color:#00e5ff;}}
        .sc-rb-secondary{{background:rgba(255,183,77,0.12);border:1px solid rgba(255,183,77,0.4);color:#ffb74d;}}
        .sc-rb-advanced{{background:rgba(124,77,255,0.1);border:1px solid rgba(124,77,255,0.35);color:#b39dff;}}
        .sc-row-rr{{font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;}}
        .sc-row-chevron{{font-size:16px;color:rgba(79,195,247,0.3);padding-right:8px;transition:transform 0.2s ease;line-height:1;user-select:none;}}
        .sc-row.sc-selected .sc-row-chevron{{transform:rotate(90deg);color:#00e5ff;}}
        /* expand detail panel — spans both columns */
        .sc-dp{{grid-column:1/-1;display:none;background:rgba(4,10,20,0.97);border:1px solid rgba(79,195,247,0.18);border-radius:12px;padding:14px 16px;position:relative;overflow:hidden;animation:scSlide 0.18s ease;}}
        .sc-dp::before{{content:'';position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,#4fc3f7,transparent);}}
        .sc-dp.sc-dp-open{{display:block;}}
        @keyframes scSlide{{from{{opacity:0;transform:translateY(-5px);}}to{{opacity:1;transform:translateY(0);}}}}
        .sc-dp-grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:10px;}}
        .sc-dp-box{{background:rgba(255,255,255,0.025);border:1px solid rgba(79,195,247,0.1);border-radius:8px;padding:9px 11px;}}
        .sc-dp-lbl{{font-family:'JetBrains Mono',monospace;font-size:7.5px;letter-spacing:2px;color:rgba(128,222,234,0.35);text-transform:uppercase;margin-bottom:3px;}}
        .sc-dp-val{{font-family:'Oxanium',sans-serif;font-size:15px;font-weight:700;line-height:1.2;}}
        .sc-dp-sub{{font-family:'JetBrains Mono',monospace;font-size:9px;color:rgba(176,190,197,0.35);margin-top:2px;}}
        .sc-dp-rr-track{{height:3px;background:rgba(0,0,0,0.4);border-radius:2px;overflow:hidden;margin-top:5px;}}
        .sc-dp-rr-fill{{height:100%;border-radius:2px;}}
        .sc-dp-strike-box{{background:rgba(0,0,0,0.3);border-left:3px solid rgba(79,195,247,0.4);border-radius:0 7px 7px 0;padding:7px 11px;font-family:'JetBrains Mono',monospace;font-size:10px;color:rgba(176,190,197,0.75);line-height:1.65;margin-bottom:10px;word-break:break-word;}}
        .sc-dp-strike-lbl{{color:#80deea;font-weight:700;}}
        .sc-dp-actions{{display:flex;gap:8px;justify-content:flex-end;}}
        .sc-dp-btn{{font-family:'Oxanium',sans-serif;font-size:10px;font-weight:700;letter-spacing:1px;padding:6px 14px;border-radius:6px;cursor:pointer;border:none;transition:all 0.15s ease;}}
        .sc-dp-btn-load{{background:linear-gradient(135deg,#00bcd4,#006064);color:#fff;}}
        .sc-dp-btn-load:hover{{filter:brightness(1.2);}}
        .sc-dp-btn-close{{background:transparent;border:1px solid rgba(79,195,247,0.2);color:rgba(176,190,197,0.5);}}
        .sc-dp-btn-close:hover{{border-color:rgba(79,195,247,0.4);color:#4fc3f7;}}
        /* tag colours (reused) */
        .strat-tag-bull{{background:rgba(0,230,118,0.1);border:1px solid rgba(0,230,118,0.25);color:#00e676;}}
        .strat-tag-bear{{background:rgba(255,82,82,0.1);border:1px solid rgba(255,82,82,0.25);color:#ff5252;}}
        .strat-tag-neu{{background:rgba(255,183,77,0.1);border:1px solid rgba(255,183,77,0.25);color:#ffb74d;}}
        .strat-tag-vol{{background:rgba(124,77,255,0.1);border:1px solid rgba(124,77,255,0.25);color:#b388ff;}}
        .strat-tag-misc{{background:rgba(79,195,247,0.1);border:1px solid rgba(79,195,247,0.25);color:#4fc3f7;}}
        /* trade plan badges */
        .tp-rank-badge{{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:8px;font-weight:700;letter-spacing:1.5px;padding:2px 8px;border-radius:20px;margin-left:8px;vertical-align:middle;}}
        .tp-rank-primary{{background:rgba(0,230,118,0.15);border:1px solid rgba(0,230,118,0.4);color:#00e676;}}
        .tp-rank-secondary{{background:rgba(255,183,77,0.15);border:1px solid rgba(255,183,77,0.4);color:#ffb74d;}}
        .tp-rank-advanced{{background:rgba(179,136,255,0.15);border:1px solid rgba(179,136,255,0.4);color:#b388ff;}}
        @keyframes tpFlash{{0%{{box-shadow:0 0 0 0 rgba(0,229,255,0.6);}}50%{{box-shadow:0 0 0 8px rgba(0,229,255,0);}}100%{{box-shadow:none;}}}}
        .tp-banner-flash{{animation:tpFlash 0.6s ease-out;}}

        /* ── TRADE PLAN ─────────────────────────────────────────────── */
        .tp-wrap{{display:flex;flex-direction:column;gap:16px;}}
        .tp-banner{{display:flex;justify-content:space-between;align-items:flex-start;background:rgba(79,195,247,0.06);border:1px solid rgba(79,195,247,0.2);border-radius:14px;padding:18px 22px;gap:16px;}}
        .tp-banner-left{{flex:1;}}
        .tp-banner-label{{font-family:'JetBrains Mono',monospace;font-size:9px;color:rgba(128,222,234,0.4);letter-spacing:2px;margin-bottom:6px;}}
        .tp-banner-strat{{font-family:'Oxanium',sans-serif;font-size:clamp(15px,2vw,20px);font-weight:800;color:#80deea;margin-bottom:6px;}}
        .tp-banner-strike{{font-family:'JetBrains Mono',monospace;font-size:11px;color:rgba(176,190,197,0.7);}}
        .tp-banner-right{{text-align:right;}}
        .tp-banner-exp{{font-family:'Oxanium',sans-serif;font-size:16px;font-weight:700;color:#ffb74d;margin-top:6px;}}
        .tp-exits{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;}}
        .tp-exit{{border-radius:14px;padding:18px;display:flex;flex-direction:column;gap:6px;position:relative;overflow:hidden;}}
        .tp-exit::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:14px 14px 0 0;}}
        .tp-exit-profit{{background:rgba(0,230,118,0.05);border:1px solid rgba(0,230,118,0.2);}}
        .tp-exit-profit::before{{background:linear-gradient(90deg,#00e676,#00bfa5);}}
        .tp-exit-loss{{background:rgba(255,82,82,0.05);border:1px solid rgba(255,82,82,0.2);}}
        .tp-exit-loss::before{{background:linear-gradient(90deg,#ff5252,#b71c1c);}}
        .tp-exit-time{{background:rgba(255,183,77,0.05);border:1px solid rgba(255,183,77,0.2);}}
        .tp-exit-time::before{{background:linear-gradient(90deg,#ffb74d,#f57c00);}}
        .tp-exit-icon{{font-size:20px;}}
        .tp-exit-title{{font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:2px;color:rgba(176,190,197,0.4);margin-bottom:2px;}}
        .tp-exit-val{{font-family:'Oxanium',sans-serif;font-size:clamp(14px,1.8vw,18px);font-weight:800;color:#e0f7fa;}}
        .tp-exit-val2{{font-family:'Oxanium',sans-serif;font-size:13px;font-weight:700;color:rgba(224,247,250,0.6);margin-top:4px;}}
        .tp-exit-sub{{font-family:'JetBrains Mono',monospace;font-size:9px;color:rgba(176,190,197,0.4);}}
        .tp-exit-rule{{margin-top:8px;font-size:10px;color:rgba(176,190,197,0.55);line-height:1.5;border-top:1px solid rgba(255,255,255,0.05);padding-top:8px;}}
        .filter-btn{{padding:6px 14px;border-radius:20px;font-size:10px;font-weight:700;letter-spacing:1px;cursor:pointer;border:1px solid rgba(79,195,247,0.2);background:transparent;color:rgba(176,190,197,0.5);transition:all 0.2s ease;font-family:'Oxanium',sans-serif;}}
        .filter-btn.active,.filter-btn:hover{{background:rgba(79,195,247,0.1);border-color:rgba(79,195,247,0.4);color:#4fc3f7;}}

        .oi-controls{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:20px;}}
        .oi-interval-btns{{display:flex;gap:0;border:1px solid rgba(79,195,247,0.25);border-radius:10px;overflow:hidden;}}
        .oi-int-btn{{padding:9px 24px;font-family:'Oxanium',sans-serif;font-size:12px;font-weight:700;letter-spacing:2px;color:rgba(176,190,197,0.5);background:transparent;border:none;cursor:pointer;transition:all 0.2s ease;border-right:1px solid rgba(79,195,247,0.15);}}
        .oi-int-btn:last-child{{border-right:none;}}
        .oi-int-btn:hover{{background:rgba(79,195,247,0.12);color:#4fc3f7;}}
        .oi-int-btn.active{{background:rgba(79,195,247,0.22);color:#00e5ff;box-shadow:inset 0 0 12px rgba(79,195,247,0.1);}}
        .oi-live-badge{{display:flex;align-items:center;gap:7px;font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:2px;color:rgba(0,230,118,0.7);background:rgba(0,230,118,0.08);border:1px solid rgba(0,230,118,0.25);padding:6px 14px;border-radius:8px;}}
        .oi-live-dot{{width:7px;height:7px;border-radius:50%;background:#00e676;box-shadow:0 0 8px #00e676;animation:sb-pulse 1.5s ease-in-out infinite;}}
        .oi-summary-strip{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:20px;}}
        .oi-sum-card{{background:rgba(255,255,255,0.03);border:1px solid rgba(79,195,247,0.14);border-radius:12px;padding:14px 16px;text-align:center;}}
        .oi-sum-label{{font-size:9px;letter-spacing:2px;color:rgba(128,222,234,0.9);text-transform:uppercase;font-weight:700;margin-bottom:6px;}}
        .oi-sum-val{{font-family:'Oxanium',sans-serif;font-size:clamp(16px,2.5vw,22px);font-weight:700;line-height:1;}}
        .oi-chart-wrap{{background:rgba(6,13,20,0.7);border:1px solid rgba(79,195,247,0.14);border-radius:14px;padding:16px;margin-bottom:20px;}}
        .oi-chart-label{{font-size:9px;letter-spacing:2px;color:rgba(128,222,234,0.9);text-transform:uppercase;font-weight:700;}}
        /* ══ OPTION FLOW TABLE — POLISHED UI ════════════════════════════════ */
        .oi-table-wrap{{background:rgba(6,13,20,0.85);border:1px solid rgba(79,195,247,0.18);border-radius:16px;overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;box-shadow:0 4px 40px rgba(0,0,0,0.5);overflow-anchor:none;}}
        .oi-table{{width:100%;min-width:1160px;border-collapse:collapse;font-family:'JetBrains Mono',monospace;overflow-anchor:none;}}
        .oi-table-scroll-hint{{display:none;align-items:center;gap:6px;font-family:'JetBrains Mono',monospace;font-size:9px;letter-spacing:1.5px;color:rgba(79,195,247,0.4);padding:6px 14px 0;text-transform:uppercase;}}

        /* ── Header ── */
        .oi-table thead tr{{background:rgba(18,26,33,0.95);border-bottom:2px solid rgba(36,53,68,0.9);}}
        .oi-table thead th{{padding:12px 16px;font-size:9.5px;letter-spacing:1.5px;color:rgba(128,222,234,0.9);text-transform:uppercase;font-weight:700;text-align:right;white-space:nowrap;}}
        .oi-table thead th:first-child{{text-align:left;}}
        .oi-table thead th.oi-th-divider{{border-left:1px solid rgba(30,45,56,1);}}

        /* ── FOCUS / DETAIL toggle ── */
        .oi-view-btn{{padding:5px 16px;font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;letter-spacing:1.5px;color:rgba(128,222,234,0.4);background:transparent;border:1px solid rgba(79,195,247,0.2);border-radius:20px;cursor:pointer;transition:all 0.2s ease;}}
        .oi-view-btn:hover{{color:#4fc3f7;border-color:rgba(79,195,247,0.5);background:rgba(79,195,247,0.08);}}
        .oi-view-active{{color:#00e5ff!important;border-color:rgba(79,195,247,0.6)!important;background:rgba(79,195,247,0.14)!important;box-shadow:0 0 10px rgba(79,195,247,0.12);}}
        /* FOCUS mode: hide col-detail columns (default) */
        .col-detail{{display:none;}}
        /* DETAIL mode: show col-detail columns */
        .oi-detail-mode .col-detail{{display:table-cell;}}

        /* ── Body rows ── */
        .oi-table tbody tr{{border-bottom:1px solid rgba(30,45,56,0.8);transition:background 0.15s ease;}}
        .oi-table tbody tr:last-child{{border-bottom:none;}}
        .oi-table tbody tr:hover{{background:rgba(18,26,33,0.9);}}
        .oi-table tbody tr.oi-live-row{{background:linear-gradient(90deg,rgba(0,212,255,0.04) 0%,transparent 60%);border-bottom:1px solid rgba(0,212,255,0.18);}}
        .oi-table tbody td{{padding:13px 16px;font-size:12.5px;text-align:right;color:#c8dde8;white-space:nowrap;}}
        .oi-table tbody td:first-child{{text-align:left;}}
        .oi-table tbody td.oi-th-divider{{border-left:1px solid rgba(30,45,56,0.8);}}

        /* ── Time cell ── */
        .oi-time-cell{{display:flex;align-items:center;gap:10px;}}
        .oi-time-val{{font-size:13px;font-weight:700;color:#fff;letter-spacing:0.5px;}}
        .oi-live-ind{{display:inline-flex;align-items:center;gap:5px;background:rgba(0,230,118,0.1);border:1px solid rgba(0,230,118,0.5);border-radius:20px;padding:2px 8px;font-size:9px;color:#00e676;letter-spacing:1px;font-weight:700;}}
        .oi-live-ind::before{{content:'';display:inline-block;width:6px;height:6px;border-radius:50%;background:#00e676;box-shadow:0 0 6px #00e676;animation:sb-pulse 1.2s ease-in-out infinite;}}

        /* ── OI value cells ── */
        .oi-call-val{{color:#00e676;font-weight:500;}}
        .oi-put-val{{color:#c8dde8;}}
        .oi-diff-neg{{color:#ff4757;font-weight:700;}}
        .oi-diff-pos{{color:#00e676;font-weight:700;}}

        /* ── PCR with mini bar ── */
        .oi-pcr-val{{font-weight:700;font-size:12px;}}
        .oi-pcr-val.oi-pcr-bull,.oi-pcr-bull{{color:#00e676 !important;}}
        .oi-pcr-val.oi-pcr-bear,.oi-pcr-bear{{color:#ff4757 !important;}}
        .oi-pcr-val.oi-pcr-neu,.oi-pcr-neu{{color:#ffd32a !important;}}
        .oi-pcr-cell{{display:inline-flex;align-items:center;justify-content:flex-end;gap:6px;}}
        .oi-pcr-bar-wrap{{width:32px;height:4px;background:rgba(36,53,68,0.9);border-radius:2px;overflow:hidden;display:inline-block;vertical-align:middle;}}
        .oi-pcr-bar{{height:100%;border-radius:2px;}}
        .oi-pcr-bull-bar{{background:rgba(0,230,118,0.85);}}
        .oi-pcr-bear-bar{{background:rgba(255,71,87,0.85);}}
        .oi-pcr-neu-bar{{background:rgba(255,211,42,0.75);}}

        /* ── Signal badges — bigger, glowing ── */
        .oi-signal-ssell{{display:inline-block;padding:5px 14px;border-radius:7px;font-size:10.5px;font-weight:800;letter-spacing:1.2px;background:#ff3a4a;color:#fff;box-shadow:0 0 14px rgba(255,58,74,0.55);}}
        .oi-signal-sell{{display:inline-block;padding:5px 14px;border-radius:7px;font-size:10.5px;font-weight:800;letter-spacing:1.2px;background:#ff3a4a;color:#fff;box-shadow:0 0 10px rgba(255,58,74,0.35);}}
        .oi-signal-sbuy{{display:inline-block;padding:5px 14px;border-radius:7px;font-size:10.5px;font-weight:800;letter-spacing:1.2px;background:#00c853;color:#000;box-shadow:0 0 14px rgba(0,200,83,0.55);}}
        .oi-signal-buy{{display:inline-block;padding:5px 14px;border-radius:7px;font-size:10.5px;font-weight:800;letter-spacing:1.2px;background:#00c853;color:#000;box-shadow:0 0 10px rgba(0,200,83,0.35);}}
        .oi-signal-neutral{{display:inline-block;padding:5px 14px;border-radius:7px;font-size:10.5px;font-weight:800;letter-spacing:1.2px;background:rgba(245,158,11,0.15);color:#fde68a;border:1px solid rgba(245,158,11,0.3);}}

        /* ── Spot price ── */
        .oi-vwap-cell{{color:#93c5fd;font-weight:600;}}
        .oi-fut-cell{{color:#c4b5fd;}}
        .oi-spot-cell{{color:#fff;font-weight:700;font-size:13px;}}

        /* ── Spot Δ — pill style ── */
        .oi-sdelta{{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:6px;font-size:11.5px;font-weight:700;font-family:'JetBrains Mono',monospace;white-space:nowrap;}}
        .oi-sdelta-up{{background:rgba(0,230,118,0.12);color:#00e676;border:1px solid rgba(0,230,118,0.3);}}
        .oi-sdelta-dn{{background:rgba(255,71,87,0.12);color:#ff4757;border:1px solid rgba(255,71,87,0.3);}}
        .oi-sdelta-fl{{background:rgba(100,116,139,0.1);color:#64748b;border:1px solid rgba(100,116,139,0.2);}}

        /* ── Nifty Move % — rounded pill ── */
        .oi-nifty-move{{display:inline-flex;align-items:center;gap:4px;padding:4px 11px;border-radius:20px;font-size:11px;font-weight:700;font-family:'JetBrains Mono',monospace;white-space:nowrap;letter-spacing:0.3px;}}
        .oi-nifty-up-strong{{background:rgba(0,230,118,0.18);color:#00e676;border:1px solid rgba(0,230,118,0.35);}}
        .oi-nifty-up-mid{{background:rgba(0,200,83,0.12);color:#69f0ae;border:1px solid rgba(0,200,83,0.25);}}
        .oi-nifty-up-weak{{background:rgba(105,240,174,0.07);color:#a7f3d0;border:1px solid rgba(105,240,174,0.18);}}
        .oi-nifty-dn-strong{{background:rgba(255,71,87,0.18);color:#ff4757;border:1px solid rgba(255,71,87,0.35);}}
        .oi-nifty-dn-mid{{background:rgba(255,71,87,0.12);color:#fca5a5;border:1px solid rgba(255,71,87,0.25);}}
        .oi-nifty-dn-weak{{background:rgba(255,71,87,0.07);color:#fecaca;border:1px solid rgba(255,71,87,0.15);}}
        .oi-nifty-flat{{background:rgba(120,144,156,0.1);color:#a8c0cc;border:1px solid rgba(120,144,156,0.2);}}

        /* ── Signal Streak ── */
        .oi-streak{{display:inline-flex;flex-direction:column;align-items:flex-end;gap:4px;}}
        .oi-streak-num{{font-family:'Oxanium',sans-serif;font-size:11px;font-weight:800;line-height:1;letter-spacing:0.5px;}}
        .oi-streak-sell .oi-streak-num{{color:#ffd32a;}}
        .oi-streak-buy  .oi-streak-num{{color:#ffd32a;}}
        .oi-streak-neu  .oi-streak-num{{color:#ffd32a;}}
        .oi-streak-lbl{{font-size:8px;letter-spacing:0.8px;color:rgba(176,190,197,0.35);text-transform:uppercase;line-height:1.4;}}
        .oi-pips{{display:flex;gap:3px;align-items:center;}}
        .oi-pip{{width:7px;height:7px;border-radius:50%;flex-shrink:0;}}
        .oi-pip-sell{{background:#ff3a4a;opacity:0.85;}}
        .oi-pip-buy{{background:#00c853;opacity:0.85;}}
        .oi-pip-neu{{background:#fbbf24;opacity:0.85;}}
        .oi-pip-old{{background:rgba(74,100,120,0.3);}}

        /* ── Nearest Level badge ── */
        .oi-nlevel-badge{{display:inline-flex;align-items:center;gap:6px;background:rgba(10,26,37,0.9);border:1px solid rgba(36,53,68,1);border-radius:7px;padding:4px 10px;font-size:11.5px;font-weight:700;letter-spacing:0.3px;white-space:nowrap;}}
        .oi-nlevel-badge .oi-nlevel-label{{font-size:9px;font-weight:700;padding:1px 5px;border-radius:3px;letter-spacing:0.5px;}}
        .oi-nlevel-res{{color:#00d4ff;}}
        .oi-nlevel-res .oi-nlevel-label{{background:rgba(0,153,204,0.9);color:#000;}}
        .oi-nlevel-sup{{color:#00d4ff;}}
        .oi-nlevel-sup .oi-nlevel-label{{background:rgba(0,153,204,0.9);color:#000;}}

        /* ── Distance ── */
        .oi-dist-val{{display:inline-block;font-size:12px;font-weight:600;font-family:'JetBrains Mono',monospace;}}
        .oi-dist-res{{color:#ff4757;}}
        .oi-dist-sup{{color:#ff4757;}}

        /* ── Misc ── */
        .oi-vsig-sell{{display:inline-block;padding:2px 8px;border-radius:5px;font-size:9px;font-weight:700;background:rgba(239,68,68,0.12);color:#fca5a5;border:1px solid rgba(239,68,68,0.25);}}
        .oi-vsig-buy{{display:inline-block;padding:2px 8px;border-radius:5px;font-size:9px;font-weight:700;background:rgba(16,185,129,0.12);color:#6ee7b7;border:1px solid rgba(16,185,129,0.25);}}
        .oi-empty-state{{text-align:center;padding:60px 20px;color:rgba(176,190,197,0.3);font-family:'JetBrains Mono',monospace;font-size:13px;}}

        .disclaimer{{background:rgba(255,183,77,0.08);border:1px solid rgba(255,183,77,0.25);border-left:3px solid #ffb74d;border-radius:8px;padding:9px 16px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;}}
        .disc-icon{{font-size:13px;flex-shrink:0;line-height:1;}}
        .disc-label{{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;letter-spacing:1.5px;color:#ffb74d;text-transform:uppercase;flex-shrink:0;}}
        .disc-sep{{color:rgba(255,183,77,0.3);font-size:11px;flex-shrink:0;}}
        .disc-text{{font-size:12px;color:rgba(255,183,77,0.75);font-family:'Rajdhani',sans-serif;font-weight:500;white-space:nowrap;}}
        .disc-text strong{{color:#ffb74d;font-weight:700;}}
        @media(max-width:700px){{.disc-text{{white-space:normal;}}}}
        .footer{{text-align:center;padding:24px;color:#8faabe;font-size:clamp(10px,1.3vw,12px);background:rgba(10,20,28,0.4);}}

        /* ══ SIGNAL SUMMARY BAR ═══════════════════════════════════════════ */
        .ssb-section{{padding:0 clamp(12px,2.5vw,26px) 16px;border-bottom:none!important;}}
        .ssb-wrap{{background:rgba(6,13,20,0.9);border:1px solid rgba(79,195,247,0.18);border-radius:14px;overflow:hidden;}}
        .ssb-header{{display:flex;align-items:center;justify-content:space-between;padding:9px 16px;background:rgba(0,0,0,0.35);border-bottom:1px solid rgba(79,195,247,0.1);flex-wrap:wrap;gap:8px;}}
        .ssb-title{{font-family:'Oxanium',sans-serif;font-size:12px;letter-spacing:2.5px;color:#4fc3f7;text-transform:uppercase;font-weight:700;}}
        .ssb-ts{{font-size:12px;color:#80deea;letter-spacing:1px;font-family:'JetBrains Mono',monospace;font-weight:600;}}
        .ssb-grid{{display:grid;grid-template-columns:repeat(5,1fr) 1.5fr;}}
        .ssb-cell{{padding:14px 10px;border-right:1px solid rgba(79,195,247,0.08);display:flex;flex-direction:column;align-items:center;gap:6px;text-align:center;}}
        .ssb-cell:last-child{{border-right:none;}}
        .ssb-cell-lbl{{font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:2px;color:#e0f7fa;text-transform:uppercase;font-weight:700;}}
        .ssb-badge{{display:inline-flex;align-items:center;gap:4px;padding:5px 12px;border-radius:7px;font-family:'Oxanium',sans-serif;font-size:13px;font-weight:800;letter-spacing:0.5px;white-space:nowrap;}}
        .ssb-sub{{font-family:'JetBrains Mono',monospace;font-size:11px;color:rgba(200,221,232,0.85);letter-spacing:0.3px;max-width:110px;line-height:1.5;text-align:center;}}
        .ssb-verdict{{display:flex;flex-direction:column;align-items:center;gap:7px;padding:14px 12px;}}
        .ssb-verdict-lbl{{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:2.5px;text-transform:uppercase;font-weight:700;color:#e0f7fa;}}
        .ssb-verdict-val{{font-family:'Oxanium',sans-serif;font-size:clamp(13px,1.8vw,17px);font-weight:800;letter-spacing:1px;text-transform:uppercase;text-align:center;line-height:1.2;}}
        .ssb-score-dots{{display:flex;gap:5px;}}
        .ssb-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0;}}
        .ssb-bar-wrap{{width:100%;display:flex;flex-direction:column;gap:4px;}}
        .ssb-bar-track{{height:5px;background:rgba(0,0,0,0.5);border-radius:3px;overflow:hidden;width:100%;display:flex;}}
        .ssb-bar-lbl{{display:flex;justify-content:space-between;font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:700;letter-spacing:0.5px;}}
        @media(max-width:900px){{
            .ssb-grid{{grid-template-columns:repeat(3,1fr) !important;}}
            .ssb-cell:nth-child(3){{border-right:none;}}
            .ssb-cell:nth-child(4),.ssb-cell:nth-child(5){{border-top:1px solid rgba(79,195,247,0.08);}}
            .ssb-verdict{{grid-column:1/-1;border-left:none !important;border-top:1px solid rgba(79,195,247,0.1);flex-direction:row;flex-wrap:wrap;justify-content:center;gap:10px;padding:12px;}}
        }}
        @media(max-width:600px){{
            .ssb-grid{{grid-template-columns:repeat(2,1fr) !important;}}
            .ssb-cell:nth-child(2n){{border-right:none;}}
            .ssb-cell{{border-top:1px solid rgba(79,195,247,0.07);}}
            .ssb-cell:nth-child(1),.ssb-cell:nth-child(2){{border-top:none;}}
            .ssb-verdict-val{{font-size:13px;}}
        }}

        {heatmap_css}
        {pretrade_css}


        /* ══ OI CHART ENHANCEMENTS ════════════════════════════ */
        .oi-stat-strip{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px;}}
        .oi-stat-box{{background:rgba(255,255,255,0.025);border:1px solid rgba(79,195,247,0.1);border-radius:10px;padding:10px 14px;text-align:center;}}
        .oi-stat-label{{font-size:8px;letter-spacing:2px;color:rgba(128,222,234,0.9);text-transform:uppercase;font-weight:700;margin-bottom:4px;font-family:'JetBrains Mono',monospace;}}
        .oi-stat-val{{font-family:'Oxanium',monospace;font-size:clamp(14px,2vw,18px);font-weight:700;line-height:1.2;color:#e0f7fa;}}
        .oi-stat-pos{{color:#34d399!important;}}
        .oi-stat-neg{{color:#f87171!important;}}
        .oi-stat-sub{{font-family:'JetBrains Mono',monospace;font-size:9px;color:rgba(176,190,197,0.3);margin-top:3px;}}
        .oi-y-label{{font-family:'JetBrains Mono',monospace;font-size:9px;text-align:right;padding-right:6px;line-height:1;color:rgba(128,222,234,0.25);}}
        .oi-x-label{{font-family:'JetBrains Mono',monospace;font-size:9px;color:rgba(128,222,234,0.2);}}
        @media(max-width:600px){{.oi-stat-strip{{grid-template-columns:repeat(2,1fr);}}}}
        @media(max-width:380px){{.oi-stat-strip{{grid-template-columns:1fr;}}}}

        @media(max-width:1024px){{
            .grid-5{{grid-template-columns:repeat(3,minmax(0,1fr));}}
            .grid-4{{grid-template-columns:repeat(2,minmax(0,1fr));}}
            .pf-grid{{grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;}}
            .nc-cards-grid{{grid-template-columns:repeat(3,minmax(0,1fr));}}
            .nc-meter-track{{width:140px;}}
            .oi-summary-strip{{grid-template-columns:repeat(2,minmax(0,1fr));}}
        }}

        /* ══ SIDEBAR NAV ══════════════════════════════════════════════ */
        .page-body{{display:flex;align-items:flex-start;position:relative;}}
        .page-content{{flex:1;min-width:0;width:100%;}}
        .nav-sidebar{{
            width:190px;flex-shrink:0;
            background:#07111a;
            border-right:1px solid rgba(79,195,247,0.12);
            position:sticky;top:0;height:100vh;
            display:flex;flex-direction:column;
            transition:width 0.22s ease;
            z-index:100;overflow:hidden;
        }}
        .nav-sidebar.collapsed{{width:46px;}}
        .nsb-header{{display:flex;align-items:center;justify-content:space-between;padding:12px 10px;border-bottom:1px solid rgba(79,195,247,0.1);flex-shrink:0;}}
        .nsb-logo{{font-family:'Oxanium',sans-serif;font-size:11px;letter-spacing:3px;color:#4fc3f7;font-weight:700;white-space:nowrap;overflow:hidden;transition:opacity 0.2s;}}
        .nav-sidebar.collapsed .nsb-logo{{opacity:0;pointer-events:none;}}
        .nsb-toggle{{width:26px;height:26px;border-radius:6px;border:1px solid rgba(79,195,247,0.2);background:transparent;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;}}
        .nsb-toggle:hover{{background:rgba(79,195,247,0.1);}}
        .nsb-toggle svg{{transition:transform 0.22s;}}
        .nav-sidebar.collapsed .nsb-toggle svg{{transform:rotate(180deg);}}
        .nsb-nav{{flex:1;overflow-y:auto;overflow-x:hidden;padding:8px 0;scrollbar-width:thin;scrollbar-color:rgba(79,195,247,0.15) transparent;}}
        .nsb-nav::-webkit-scrollbar{{width:3px;}}
        .nsb-nav::-webkit-scrollbar-thumb{{background:rgba(79,195,247,0.2);border-radius:2px;}}
        .nsb-group{{font-size:9px;letter-spacing:2px;color:rgba(79,195,247,0.65);padding:10px 12px 4px;text-transform:uppercase;white-space:nowrap;overflow:hidden;transition:opacity 0.2s;font-weight:700;}}
        .nav-sidebar.collapsed .nsb-group{{opacity:0;}}
        .nsb-item{{display:flex;align-items:center;gap:9px;padding:8px 12px;cursor:pointer;border-left:2px solid transparent;transition:all 0.15s ease;position:relative;}}
        .nsb-item:hover{{background:rgba(79,195,247,0.06);border-left-color:rgba(79,195,247,0.3);}}
        .nsb-item.active{{background:rgba(79,195,247,0.1);border-left-color:#4fc3f7;}}
        .nsb-icon{{width:18px;height:18px;flex-shrink:0;display:flex;align-items:center;justify-content:center;color:rgba(128,222,234,0.45);}}
        .nsb-item.active .nsb-icon{{color:#4fc3f7;}}
        .nsb-icon svg{{width:15px;height:15px;}}
        .nsb-label{{font-family:'JetBrains Mono',monospace;font-size:10.5px;color:rgba(176,190,197,0.55);white-space:nowrap;overflow:hidden;transition:opacity 0.15s;letter-spacing:0.3px;}}
        .nsb-item.active .nsb-label{{color:#e0f7fa;}}
        .nav-sidebar.collapsed .nsb-label{{opacity:0;width:0;pointer-events:none;}}
        .nav-sidebar.collapsed .nsb-item{{padding:8px 14px;}}
        .nsb-tip{{display:none;position:absolute;left:48px;top:50%;transform:translateY(-50%);background:#0d1e2a;border:1px solid rgba(79,195,247,0.25);border-radius:6px;padding:4px 11px;font-family:'JetBrains Mono',monospace;font-size:10px;color:#80deea;white-space:nowrap;z-index:999;pointer-events:none;}}
        .nav-sidebar.collapsed .nsb-item:hover .nsb-tip{{display:block;}}

        /* ── Mobile nav bar + drawer ───────────────────────── */
        .nsb-mob-bar{{
            display:none;align-items:center;gap:10px;
            padding:10px 14px;
            background:#07111a;
            border-bottom:1px solid rgba(79,195,247,0.18);
            position:sticky;top:0;z-index:90;
            width:100%;
        }}
        .nsb-mob-btn{{
            width:36px;height:36px;border-radius:8px;
            border:1px solid rgba(79,195,247,0.3);
            background:rgba(79,195,247,0.06);
            cursor:pointer;display:flex;align-items:center;justify-content:center;
            flex-shrink:0;
        }}
        .nsb-mob-btn:active{{background:rgba(79,195,247,0.15);}}
        .nsb-mob-title{{
            font-family:'JetBrains Mono',monospace;
            font-size:12px;letter-spacing:1.5px;
            color:rgba(79,195,247,0.8);
            text-transform:uppercase;
            flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
        }}
        .nsb-drawer{{
            display:none;position:fixed;
            top:0;left:0;width:100%;height:100%;
            background:rgba(4,10,16,0.98);
            z-index:200;flex-direction:column;
        }}
        .nsb-drawer.open{{display:flex;}}
        .nsb-drawer-head{{
            display:flex;align-items:center;justify-content:space-between;
            padding:16px 18px;
            border-bottom:1px solid rgba(79,195,247,0.15);
            flex-shrink:0;
        }}
        .nsb-drawer-title{{
            font-family:'JetBrains Mono',monospace;font-size:10px;
            letter-spacing:3px;color:rgba(79,195,247,0.5);text-transform:uppercase;
        }}
        .nsb-drawer-close{{
            width:36px;height:36px;border-radius:8px;
            border:1px solid rgba(255,82,82,0.35);
            background:rgba(255,82,82,0.06);
            cursor:pointer;color:rgba(255,82,82,0.8);
            font-size:16px;display:flex;align-items:center;justify-content:center;
        }}
        .nsb-drawer-nav{{flex:1;overflow-y:auto;padding:6px 0;}}
        .nsb-mob-item{{
            padding:15px 20px;
            font-family:'JetBrains Mono',monospace;font-size:13px;
            color:rgba(176,190,197,0.65);
            cursor:pointer;border-left:3px solid transparent;
            letter-spacing:0.5px;
            transition:all 0.15s ease;
        }}
        .nsb-mob-item:active,
        .nsb-mob-item.active{{
            background:rgba(79,195,247,0.1);
            border-left-color:#4fc3f7;color:#e0f7fa;
        }}

        /* ══ MOBILE RESPONSIVE OVERRIDES ════════════════════════════ */
        @media(max-width:768px){{
            /* Hide desktop sidebar, show mobile bar */
            .nav-sidebar{{display:none;}}
            .nsb-mob-bar{{display:flex;}}
            .page-body{{flex-direction:column;}}
            .page-content{{width:100%;min-width:0;}}

            /* Header — Option B mobile */
            .hb-banner{{padding:10px 12px;gap:8px;}}
            .hb-chips{{display:none;}}
            .hb-title-main{{font-size:13px;}}
            .hb-status{{padding:5px 12px;gap:4px;flex-wrap:wrap;}}
            .hb-s-item{{font-size:9px;}}
            .tab-btn{{padding:9px 10px;font-size:9px;letter-spacing:0.8px;gap:5px;}}
            .tab-badge{{font-size:8px;padding:2px 5px;}}

            /* Sections */
            .section{{padding:12px 12px;}}
            .section-title{{font-size:11px;letter-spacing:1px;margin-bottom:12px;padding-bottom:8px;gap:6px;}}

            /* Grids → single or 2-col */
            .grid-5,.grid-4{{grid-template-columns:1fr 1fr!important;}}
            .snap-grid{{grid-template-columns:1fr 1fr!important;gap:8px;}}
            .card-grid{{gap:8px;}}

            /* OI table: full horizontal scroll */
            .oi-table-wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch;}}
            .oi-table{{min-width:520px;}}
            .oi-table thead th,.oi-table tbody td{{padding:7px 8px;font-size:10px;}}
            .oi-table-scroll-hint{{display:flex;}}
            .oi-view-btn{{padding:5px 10px;font-size:9px;}}

            /* OI summary strip */
            .oi-summary-strip{{grid-template-columns:1fr 1fr;gap:8px;}}
            .oi-stat-strip{{grid-template-columns:1fr 1fr;gap:8px;}}
            .oi-controls{{flex-direction:column;gap:8px;align-items:flex-start;}}
            .oi-chart-wrap{{padding:10px;}}

            /* NC / OI navy */
            .nc-cards-grid{{grid-template-columns:1fr!important;gap:8px;}}
            .nc-section-header{{flex-direction:column;align-items:flex-start;}}
            .nc-meters-panel{{width:100%;min-width:unset;}}
            .nc-meter-track{{width:100%;max-width:100%;}}
            .nc-dir-name{{font-size:18px;}}
            .nc-wrap{{padding:0;}}

            /* Key levels */
            div[style*="grid-template-columns:1fr 1fr"]{{grid-template-columns:1fr!important;}}

            /* FII / DII */
            .pf-grid{{grid-template-columns:1fr 1fr!important;gap:8px;}}
            .pf-avg-strip{{grid-template-columns:1fr;gap:0;padding:12px;}}
            .pf-avg-sep{{display:none;}}
            .pf-avg-cell{{display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgba(79,195,247,0.07);}}
            .pf-avg-cell:last-child{{border-bottom:none;}}
            .pf-date-range{{display:none;}}

            /* Market direction */
            .md-row-top,.md-row-bottom{{flex-direction:column;align-items:flex-start;}}
            .md-direction{{font-size:22px;}}

            /* Strategy checklist */
            .o5-grid{{grid-template-columns:1fr!important;}}
            .o5-top-banner{{flex-direction:column;align-items:flex-start;}}
            .strat-grid-legacy{{grid-template-columns:1fr!important;}}
            .sc-compact-grid{{grid-template-columns:1fr!important;}}
            .sc-dp-grid{{grid-template-columns:1fr 1fr;}}
            .logic-grid{{grid-template-columns:1fr;}}

            /* Pre-trade checklist */
            .ptc-item{{padding:10px 12px;gap:10px;}}
            .ptc-text{{font-size:13px;}}
            .ptc-mindset-box{{flex-direction:column;gap:10px;}}

            /* Heatmap */
            .hm-grid{{grid-template-columns:repeat(5,minmax(0,1fr))!important;gap:4px;}}
            .hm-cell{{min-height:56px;padding:6px 4px;}}
            .hm-cell-sym{{font-size:9px;}}
            .hm-cell-price{{font-size:7px;}}
            .hm-cell-chg{{font-size:9px;}}
            .hm-breadth-strip{{flex-direction:column;gap:12px;padding:14px;}}
            .hm-bs-donut-wrap{{align-self:center;}}

            /* Disclaimer */
            .disc-text{{white-space:normal;font-size:11px;}}

            /* Footer */
            .footer{{padding:16px 12px;font-size:11px;}}
        }}

        @media(max-width:480px){{
            .hb-title-main{{font-size:12px;}}
            .hb-s-item{{font-size:8px;}}
            .grid-5,.grid-4{{grid-template-columns:1fr!important;}}
            .snap-grid{{grid-template-columns:1fr!important;}}
            .pf-grid{{grid-template-columns:1fr!important;}}
            .oi-summary-strip{{grid-template-columns:1fr 1fr;}}
            .hm-grid{{grid-template-columns:repeat(4,minmax(0,1fr))!important;}}
            .tab-btn{{padding:9px 9px;font-size:9px;letter-spacing:0.5px;}}
        }}

        @media(max-width:360px){{
            .hb-title-main{{font-size:11px;}}
            .oi-summary-strip{{grid-template-columns:1fr;}}
            .hm-grid{{grid-template-columns:repeat(3,minmax(0,1fr))!important;}}
            .nsb-mob-title{{font-size:11px;}}
        }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">

        <!-- Banner row: brand + live market chips -->
        <div class="hb-banner">
            <div class="hb-left">
                <span class="hb-nse-badge">NSE</span>
                <div>
                    <div class="hb-title-main">&#128202; Nifty 50 &nbsp;&middot;&nbsp; OI Analysis &amp; Daily Sentiment</div>
                    <div class="hb-title-sub">Algorithmic &nbsp;&middot;&nbsp; Auto-refresh &nbsp;&middot;&nbsp; IST Timestamps &nbsp;&middot;&nbsp; Deep Ocean v2</div>
                </div>
            </div>
            <div class="hb-chips">
                <div class="hb-chip">
                    <div class="hb-chip-lbl">Spot Price</div>
                    <div class="hb-chip-val" style="color:#00e676;">&#8377;{d['current_price']:,.0f}</div>
                </div>
                <div class="hb-chip">
                    <div class="hb-chip-lbl">ATM Strike</div>
                    <div class="hb-chip-val" style="color:#4fc3f7;">&#8377;{d['atm_strike']:,}</div>
                </div>
                <div class="hb-chip">
                    <div class="hb-chip-lbl">PCR</div>
                    <div class="hb-chip-val" style="color:{pcr_col};">{pcr_v:.3f}</div>
                </div>
                <div class="hb-chip">
                    <div class="hb-chip-lbl">India VIX</div>
                    <div class="hb-chip-val" style="color:{vix_col};">{vix_str}{vix_arrow}</div>
                </div>
                <div class="hb-chip">
                    <div class="hb-chip-lbl">Max Pain</div>
                    <div class="hb-chip-val" style="color:#ffb74d;">&#8377;{d.get('max_pain',0):,}</div>
                </div>
                <div class="hb-chip">
                    <div class="hb-chip-lbl">Expiry</div>
                    <div class="hb-chip-val" style="color:#4fc3f7;font-size:11px;">{d.get('expiry','N/A')}</div>
                </div>
                <div class="hb-chip">
                    <div class="hb-chip-lbl">Days Left</div>
                    <div class="hb-chip-val" style="color:{expiry_days_col};">{expiry_days_str}</div>
                </div>
            </div>
        </div>

        <!-- Status row: generated, clock, refresh, global bias, FII/DII -->
        <div class="hb-status">
            <div class="hb-s-item">
                <div class="hb-s-dot" style="background:#00e676;box-shadow:0 0 6px #00e676;"></div>
                Generated <span class="hb-s-val" id="hb-gen">{d['timestamp']}</span>
            </div>
            <div class="hb-s-item">
                <div class="hb-s-dot" style="background:#4fc3f7;box-shadow:0 0 6px #4fc3f7;"></div>
                IST Now <span class="hb-s-val" style="color:#4fc3f7;" id="live-ist-clock">--:--:--</span>
            </div>
            <div class="hb-s-item" style="display:none;">
                <div class="hb-s-dot" style="background:#b388ff;box-shadow:0 0 6px #b388ff;"></div>
                Next Refresh <span class="hb-s-val" style="color:#b388ff;" id="refresh-countdown">30s</span>
            </div>
            <div class="hb-s-item">
                &#127760; Global <span class="hb-s-val" style="color:{gb_col};">{gb_str}</span>
            </div>
            <div class="hb-s-item">
                &#127982; FII <span class="hb-s-val" style="color:{fii_col};">{fii_hdr}</span>
            </div>
            <div class="hb-s-item">
                &#127982; DII <span class="hb-s-val" style="color:{dii_col};">{dii_hdr}</span>
            </div>
        </div>

        <!-- Tabs -->
        <div class="tab-nav" id="tabNav">
            <button class="tab-btn active" data-tab="main" onclick="switchTab('main')">
                <span class="tab-dot"></span> &#128200; Main Analysis <span class="tab-badge">LIVE</span>
            </button>
            <button class="tab-btn" data-tab="heatmap" onclick="switchTab('heatmap')">
                <span class="tab-dot"></span> &#127956; Heatmap <span class="tab-badge">LIVE</span>
            </button>
            <button class="tab-btn" data-tab="oi-trend" onclick="switchTab('oi-trend')">
                <span class="tab-dot"></span> &#128202; Intraday OI <span class="tab-badge">IST</span>
            </button>
            <button class="tab-btn new-badge" data-tab="checklist" onclick="switchTab('checklist')">
                <span class="tab-dot"></span> &#129504; Strategy <span class="tab-badge">NEW</span>
            </button>
            <button class="tab-btn" data-tab="pretrade" onclick="switchTab('pretrade')">
                <span class="tab-dot"></span> &#9989; Pre-Trade <span class="tab-badge">23</span>
            </button>
        </div>
    </div>

    <!-- ══ PAGE BODY: sidebar + content ══ -->
    <div class="page-body">

    <!-- LEFT SIDEBAR NAV -->
    <nav class="nav-sidebar" id="navSidebar">
        <div class="nsb-header">
            <span class="nsb-logo">NIFTY</span>
            <button class="nsb-toggle" id="nsbToggle" onclick="toggleNavSidebar()" title="Collapse">
                <svg viewBox="0 0 16 16" fill="none" stroke="rgba(79,195,247,0.6)" stroke-width="2" stroke-linecap="round"><polyline points="10,4 6,8 10,12"/></svg>
            </button>
        </div>
        <div class="nsb-nav">
            <div class="nsb-group">MAIN ANALYSIS</div>
            <div class="nsb-item active" id="nsi-snapshot" onclick="navSidebarTo('snapshot','main')">
                <div class="nsb-icon"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="2" y="2" width="5" height="5" rx="1"/><rect x="9" y="2" width="5" height="5" rx="1"/><rect x="2" y="9" width="5" height="5" rx="1"/><rect x="9" y="9" width="5" height="5" rx="1"/></svg></div>
                <span class="nsb-label">Snapshot</span>
                <span class="nsb-tip">Snapshot</span>
            </div>
            <div class="nsb-item" id="nsi-oi" onclick="navSidebarTo('oi','main')">
                <div class="nsb-icon"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="2" y="10" width="3" height="4"/><rect x="6.5" y="6" width="3" height="8"/><rect x="11" y="2" width="3" height="12"/></svg></div>
                <span class="nsb-label">OI Analysis</span>
                <span class="nsb-tip">OI Analysis</span>
            </div>
            <div class="nsb-item" id="nsi-keylevels" onclick="navSidebarTo('keylevels','main')">
                <div class="nsb-icon"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="2" y1="8" x2="14" y2="8"/><line x1="5" y1="5" x2="5" y2="11"/><line x1="11" y1="5" x2="11" y2="11"/></svg></div>
                <span class="nsb-label">Key Levels</span>
                <span class="nsb-tip">Key Levels</span>
            </div>
            <div class="nsb-item" id="nsi-fiidii" onclick="navSidebarTo('fiidii','main')">
                <div class="nsb-icon"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="2" y="5" width="5" height="9" rx="1"/><rect x="9" y="2" width="5" height="12" rx="1"/></svg></div>
                <span class="nsb-label">FII / DII</span>
                <span class="nsb-tip">FII / DII</span>
            </div>
            <div class="nsb-item" id="nsi-direction" onclick="navSidebarTo('direction','main')">
                <div class="nsb-icon"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="8" cy="8" r="5"/><polyline points="8,5 8,8 10,10"/></svg></div>
                <span class="nsb-label">Direction</span>
                <span class="nsb-tip">Market Direction</span>
            </div>
            <div class="nsb-item" id="nsi-technical" onclick="navSidebarTo('technical','main')">
                <div class="nsb-icon"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><polyline points="2,12 5,7 8,9 11,5 14,3"/></svg></div>
                <span class="nsb-label">Technical</span>
                <span class="nsb-tip">Technical Indicators</span>
            </div>
            <div class="nsb-item" id="nsi-optchain" onclick="navSidebarTo('optchain','main')">
                <div class="nsb-icon"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="8" cy="8" r="5"/><line x1="8" y1="3" x2="8" y2="5"/><line x1="8" y1="11" x2="8" y2="13"/><line x1="3" y1="8" x2="5" y2="8"/><line x1="11" y1="8" x2="13" y2="8"/></svg></div>
                <span class="nsb-label">Option Chain</span>
                <span class="nsb-tip">Option Chain</span>
            </div>
            <div class="nsb-group">OTHER VIEWS</div>
            <div class="nsb-item" id="nsi-heatmap" onclick="navSidebarTo('heatmap','heatmap')">
                <div class="nsb-icon"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="2" y="2" width="3" height="3" rx="0.5"/><rect x="6.5" y="2" width="3" height="3" rx="0.5"/><rect x="11" y="2" width="3" height="3" rx="0.5"/><rect x="2" y="6.5" width="3" height="3" rx="0.5"/><rect x="6.5" y="6.5" width="3" height="3" rx="0.5"/><rect x="11" y="6.5" width="3" height="3" rx="0.5"/><rect x="2" y="11" width="3" height="3" rx="0.5"/><rect x="6.5" y="11" width="3" height="3" rx="0.5"/><rect x="11" y="11" width="3" height="3" rx="0.5"/></svg></div>
                <span class="nsb-label">Heatmap</span>
                <span class="nsb-tip">Nifty 50 Heatmap</span>
            </div>
            <div class="nsb-item" id="nsi-oitrend" onclick="navSidebarTo('oitrend','oi-trend')">
                <div class="nsb-icon"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><polyline points="2,13 5,8 8,10 11,5 14,7"/><line x1="2" y1="13" x2="14" y2="13"/></svg></div>
                <span class="nsb-label">Intraday OI</span>
                <span class="nsb-tip">Intraday OI Trend</span>
            </div>
            <div class="nsb-item" id="nsi-checklist" onclick="navSidebarTo('checklist','checklist')">
                <div class="nsb-icon"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><polyline points="4,8 7,11 12,5"/><rect x="2" y="2" width="12" height="12" rx="2"/></svg></div>
                <span class="nsb-label">Strategy</span>
                <span class="nsb-tip">Strategy Checklist</span>
            </div>
            <div class="nsb-item" id="nsi-pretrade" onclick="navSidebarTo('pretrade','pretrade')">
                <div class="nsb-icon"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><line x1="5" y1="5" x2="13" y2="5"/><line x1="5" y1="8" x2="13" y2="8"/><line x1="5" y1="11" x2="13" y2="11"/><circle cx="2.5" cy="5" r="0.8" fill="currentColor"/><circle cx="2.5" cy="8" r="0.8" fill="currentColor"/><circle cx="2.5" cy="11" r="0.8" fill="currentColor"/></svg></div>
                <span class="nsb-label">Pre-Trade</span>
                <span class="nsb-tip">Pre-Trade Rules</span>
            </div>
        </div>
    </nav>
    <!-- MAIN PAGE CONTENT -->
    <div class="page-content" id="pageContent">
    <!-- MOBILE NAV BAR sticky top -->
    <div class="nsb-mob-bar" id="nsbMobBar">
        <button class="nsb-mob-btn" onclick="openNsbDrawer()">
            <svg viewBox="0 0 16 16" width="18" height="18" fill="none" stroke="rgba(79,195,247,0.8)" stroke-width="2" stroke-linecap="round"><line x1="2" y1="4" x2="14" y2="4"/><line x1="2" y1="8" x2="14" y2="8"/><line x1="2" y1="12" x2="14" y2="12"/></svg>
        </button>
        <span class="nsb-mob-title" id="nsbMobTitle">&#9889; Signal Summary</span>
    </div>

    <!-- TAB 1: MAIN ANALYSIS -->
    <div class="tab-panel active" id="tab-main">
"""
        html += self._signal_summary_bar_html()
        if d['has_option_data']:
            html += '<div id="sec-oi">' + self._oi_navy_command_section(d) + '</div>'
        html += '<div id="sec-keylevels">' + self._key_levels_visual_section(d,_pct_cp,_pts_to_res,_pts_to_sup,_mp_node) + '</div>'
        html += self._option_chain_pivot_section_html(d)
        html += '<div id="sec-fiidii">' + self._fiidii_section_html() + '</div>'
        html += '<div id="sec-direction">' + self._market_direction_widget_html() + '</div>'
        html += f"""
        <div class="section" id="sec-technical">
            <div class="section-title"><span>&#128269;</span> TECHNICAL INDICATORS</div>
            <div style="display:flex;align-items:center;flex-wrap:wrap;gap:7px;padding:4px 0;">
                {tech_cards}
            </div>
        </div>
"""
        if d['has_option_data']:
            html += f"""
        <div class="section" id="sec-optchain">
            <div class="section-title"><span>&#127919;</span> OPTION CHAIN ANALYSIS <span style="font-size:11px;color:#80deea;font-weight:400;letter-spacing:1px;">(ATM \u00b110 Strikes Only)</span></div>
            {self._top10_oi_widget_html(d)}
            <div class="card-grid grid-4">{oc_cards}</div>
        </div>
"""
        html += """
        <div class="section">
            <div class="disclaimer"><span class="disc-icon">⚠️</span><span class="disc-label">Disclaimer</span><span class="disc-sep">|</span><span class="disc-text">For <strong>EDUCATIONAL purposes only</strong> \u2014 NOT financial advice.</span><span class="disc-sep">|</span><span class="disc-text">Always use stop losses &amp; consult a SEBI registered advisor.</span><span class="disc-sep">|</span><span class="disc-text">Past performance does not guarantee future results.</span></div>
        </div>
    </div><!-- /tab-main -->
"""
        html += heatmap_tab_html
        html += intraday_oi_tab_html
        html += checklist_tab_html
        html += pretrade_tab_html
        html += """
    <div class="footer">
        <p>Automated Nifty 50 · Option Chain + Technical + Heatmap + Intraday OI Trend + Strategy Checklist</p>
        <p style="margin-top:6px;">&#169; 2026 · Deep Ocean Theme · Navy Command OI · Pulse Flow FII/DII · IST Timestamps · For Educational Purposes Only</p>
    </div>
    </div><!-- /page-content -->
    </div><!-- /page-body -->
</div>
<!-- MOBILE DRAWER — fixed overlay, direct child of body for position:fixed to work on iOS -->
<div class="nsb-drawer" id="nsbDrawer">
    <div class="nsb-drawer-head">
        <span class="nsb-drawer-title">NAVIGATE</span>
        <button class="nsb-drawer-close" onclick="closeNsbDrawer()">&#10005;</button>
    </div>
    <div class="nsb-drawer-nav" id="nsbDrawerNav">
        <div class="nsb-group" style="padding:10px 18px 4px;">MAIN ANALYSIS</div>
        <div class="nsb-mob-item active" id="nsmd-snapshot" onclick="mobNavTo('snapshot','main','&#128200; Snapshot')">&#128200; Snapshot</div>
        <div class="nsb-mob-item" id="nsmd-oi" onclick="mobNavTo('oi','main','&#128202; OI Analysis')">&#128202; OI Analysis</div>
        <div class="nsb-mob-item" id="nsmd-keylevels" onclick="mobNavTo('keylevels','main','&#128204; Key Levels')">&#128204; Key Levels</div>
        <div class="nsb-mob-item" id="nsmd-fiidii" onclick="mobNavTo('fiidii','main','&#127982; FII / DII')">&#127982; FII / DII</div>
        <div class="nsb-mob-item" id="nsmd-direction" onclick="mobNavTo('direction','main','&#129517; Direction')">&#129517; Direction</div>
        <div class="nsb-mob-item" id="nsmd-technical" onclick="mobNavTo('technical','main','&#128269; Technical')">&#128269; Technical</div>
        <div class="nsb-mob-item" id="nsmd-optchain" onclick="mobNavTo('optchain','main','&#127919; Option Chain')">&#127919; Option Chain</div>
        <div class="nsb-group" style="padding:10px 18px 4px;">OTHER VIEWS</div>
        <div class="nsb-mob-item" id="nsmd-heatmap" onclick="mobNavTo('heatmap','heatmap','&#127956; Heatmap')">&#127956; Heatmap</div>
        <div class="nsb-mob-item" id="nsmd-oitrend" onclick="mobNavTo('oitrend','oi-trend','&#128202; Intraday OI')">&#128202; Intraday OI</div>
        <div class="nsb-mob-item" id="nsmd-checklist" onclick="mobNavTo('checklist','checklist','&#129504; Strategy')">&#129504; Strategy</div>
        <div class="nsb-mob-item" id="nsmd-pretrade" onclick="mobNavTo('pretrade','pretrade','&#9989; Pre-Trade')">&#9989; Pre-Trade</div>
    </div>
</div>
"""
        html += all_js
        html += f"\n<script>\n{heatmap_js}\n</script>\n"
        html += "\n</body></html>"
        return html

    def save_html_to_file(self, filename='index.html', vol_support=None, vol_resistance=None, global_bias=None, vol_view="normal"):
        try:
            print(f"\n📄 Saving HTML to {filename}...")
            with open(filename,'w',encoding='utf-8') as f:
                f.write(self.generate_html_email(
                    vol_support=vol_support, vol_resistance=vol_resistance,
                    global_bias=global_bias, vol_view=vol_view
                ))
            print(f"   ✅ Saved {filename}")
            metadata = {
                'timestamp':         self.html_data['timestamp'],
                'current_price':     float(self.html_data['current_price']),
                'bias':              self.html_data['bias'],
                'confidence':        self.html_data['confidence'],
                'rsi':               float(self.html_data['rsi']),
                'pcr':               float(self.html_data['pcr']) if self.html_data['has_option_data'] else None,
                'stop_loss':         float(self.html_data['stop_loss']) if self.html_data['stop_loss'] else None,
                'risk_reward_ratio': self.html_data.get('risk_reward_ratio', 0),
                'heatmap_advance':   self.heatmap_advance,
                'heatmap_decline':   self.heatmap_decline,
            }
            with open('latest_report.json','w') as f:
                json.dump(metadata, f, indent=2)
            print("   ✅ Saved latest_report.json")
            return True
        except Exception as e:
            print(f"\n❌ Save failed: {e}"); return False

    def send_html_email_report(self, vol_support=None, vol_resistance=None, global_bias=None, vol_view="normal"):
        gmail_user=os.getenv('GMAIL_USER'); gmail_password=os.getenv('GMAIL_APP_PASSWORD')
        recipient1=os.getenv('RECIPIENT_EMAIL_1'); recipient2=os.getenv('RECIPIENT_EMAIL_2')
        if not all([gmail_user,gmail_password,recipient1,recipient2]):
            print("\n⚠️  Email credentials not set. Skipping."); return False
        try:
            ist_now=datetime.now(pytz.timezone('Asia/Kolkata'))
            msg=MIMEMultipart('alternative')
            msg['From']=gmail_user; msg['To']=f"{recipient1}, {recipient2}"
            msg['Subject']=f"📊 Nifty 50 OI & Technical Report — {ist_now.strftime('%d-%b-%Y %H:%M IST')}"
            msg.attach(MIMEText(self.generate_html_email(vol_support,vol_resistance,global_bias,vol_view),'html'))
            with smtplib.SMTP_SSL('smtp.gmail.com',465) as server:
                server.login(gmail_user,gmail_password); server.send_message(msg)
            print("   ✅ Email sent!"); return True
        except Exception as e:
            print(f"\n❌ Email failed: {e}"); return False

    def generate_full_report(self):
        ist_now=datetime.now(pytz.timezone('Asia/Kolkata'))
        print("="*70)
        print("Nifty 50 Open Interest (OI) Analysis & Daily Sentiment Report")
        print(f"Generated: {ist_now.strftime('%d-%b-%Y %H:%M IST')}")
        print("="*70)
        oc_data=self.fetch_nse_option_chain_silent()
        option_analysis=self.analyze_option_chain_data(oc_data) if oc_data else None
        if option_analysis:
            print(f"✅ Option data | Expiry: {option_analysis['expiry']} | Spot: {option_analysis['underlying_value']}")
        else:
            print("⚠️  No option data — technical-only mode")
        print("\nFetching technical data...")
        technical=self.get_technical_data()
        self.generate_analysis_data(technical, option_analysis)

        # ── Fetch Nifty 50 Heatmap data ────────────────────────────────
        print("\n🌡️  Fetching Nifty 50 heatmap data...")
        (self.heatmap_data,
         self.heatmap_timestamp,
         self.heatmap_advance,
         self.heatmap_decline,
         self.heatmap_neutral) = fetch_heatmap_data()

        # ── Log OI snapshot for Intraday OI Trend tab ─────────────────
        print("\n📊 Logging OI snapshot to oi_log.json...")
        key_levels = {
            "support":           self.html_data.get("support"),
            "resistance":        self.html_data.get("resistance"),
            "strong_support":    self.html_data.get("strong_support"),
            "strong_resistance": self.html_data.get("strong_resistance"),
        }
        log_oi_snapshot(option_analysis, technical, key_levels=key_levels)

        # Fetch India VIX and store in html_data
        vix_val, vix_trend = fetch_india_vix()
        self.html_data['vix_val']   = vix_val
        self.html_data['vix_trend'] = vix_trend
        
        return option_analysis


def main():
    try:
        print("\n🚀 Starting Nifty 50 Analysis...\n")
        analyzer = NiftyHTMLAnalyzer()
        analyzer.generate_full_report()

        # ── AUTO-calculate volume at support/resistance ────────────
        print("\n📦 Auto-calculating volume at key levels...")
        vol_support, vol_resistance = fetch_volume_at_levels(analyzer.html_data)
        global_bias = fetch_global_bias()
        vol_view    = "normal"
        # ──────────────────────────────────────────────────────────

        print("\n" + "=" * 70)
        save_ok = analyzer.save_html_to_file(
            'index.html',
            vol_support=vol_support, vol_resistance=vol_resistance,
            global_bias=global_bias, vol_view=vol_view
        )
        if save_ok:
            analyzer.send_html_email_report(vol_support, vol_resistance, global_bias, vol_view)
        else:
            print("\n⚠️  Skipping email due to save failure")
        print("\n✅ Done! Open index.html in your browser.")
        print("\n💡 AUTO-REFRESH (Option 2) is active.")
        print("   ➤ Serve the folder with:  python -m http.server 8000")
        print("   ➤ Then open:              http://localhost:8000")
        print("   ➤ Page will auto-reload whenever you re-run this script.\n")
    except Exception as e:
        print(f"\n❌ Critical Error: {e}")
        import traceback; traceback.print_exc()


if __name__ == "__main__":
    main()
