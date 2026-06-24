#!/usr/bin/env python3
"""
fetch_eod.py
------------
Fetches daily EOD OHLCV data for all NIFTY 500 symbols from Definedge Integrate API.
Saves output to data/daily/YYYY-MM-DD.json and commits via GitHub Actions.

Run: python scripts/fetch_eod.py
Env vars required: DEFINEDGE_API_TOKEN, DEFINEDGE_API_SECRET
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ─── Install check ────────────────────────────────────────────────────────────
try:
    from integrate import ConnectToIntegrate, IntegrateData
except ImportError:
    raise SystemExit("pyintegrate not installed. Run: pip install pyintegrate")

# ─── NIFTY 500 Universe ───────────────────────────────────────────────────────
# Full 500-symbol list — kept here so the script is self-contained
NIFTY500 = [
    "360ONE","3MINDIA","ABB","ACC","ACMESOLAR","AIAENG","APLAPOLLO","AUBANK","AWL",
    "AADHARHFC","AARTIIND","AAVAS","ABBOTINDIA","ACE","ACUTAAS","ADANIENSOL","ADANIENT",
    "ADANIGREEN","ADANIPORTS","ADANIPOWER","ATGL","ABCAPITAL","ABFRL","ABLBL","ABREL",
    "ABSLAMC","CPPLUS","AEGISLOG","AEGISVOPAK","AFCONS","AFFLE","AJANTPHARM","ALKEM",
    "ABDL","ARE&M","AMBER","AMBUJACEM","ANANDRATHI","ANANTRAJ","ANGELONE","ANTHEM",
    "ANURAS","APARINDS","APOLLOHOSP","APOLLOTYRE","APTUS","ASAHIINDIA","ASHOKLEY",
    "ASIANPAINT","ASTERDM","ASTRAL","ATHERENERG","ATUL","AUROPHARMA","AIIL","DMART",
    "AXISBANK","BEML","BLS","BSE","BAJAJ-AUTO","BAJFINANCE","BAJAJFINSV","BAJAJHLDNG",
    "BAJAJHFL","BALKRISIND","BALRAMCHIN","BANDHANBNK","BANKBARODA","BANKINDIA","MAHABANK",
    "BATAINDIA","BAYERCROP","BELRISE","BERGEPAINT","BDL","BEL","BHARATFORG","BHEL",
    "BPCL","BHARTIARTL","BHARTIHEXA","BIKAJI","GROWW","BIOCON","BSOFT","BLUEDART",
    "BLUEJET","BLUESTARCO","BBTC","BOSCHLTD","FIRSTCRY","BRIGADE","BRITANNIA",
    "MAPMYINDIA","CCL","CESC","CGPOWER","CIEINDIA","CRISIL","CANFINHOME","CANBK",
    "CANHLIFE","CAPLIPOINT","CGCL","CARBORUNIV","CARTRADE","CASTROLIND","CEATLTD",
    "CEMPRO","CENTRALBK","CDSL","CHALET","CHAMBLFERT","CHENNPETRO","CHOICEIN",
    "CHOLAHLDNG","CHOLAFIN","CIPLA","CUB","CLEAN","COALINDIA","COCHINSHIP","COFORGE",
    "COHANCE","COLPAL","CAMS","CONCORDBIO","CONCOR","COROMANDEL","CRAFTSMAN","CREDITACC",
    "CROMPTON","CUMMINSIND","CYIENT","DCMSHRIRAM","DLF","DOMS","DABUR","DALBHARAT",
    "DATAPATTNS","DEEPAKFERT","DEEPAKNTR","DELHIVERY","DEVYANI","DIVISLAB","DIXON",
    "LALPATHLAB","DRREDDY","EIDPARRY","EIHOTEL","EICHERMOT","ELECON","ELGIEQUIP",
    "EMAMILTD","EMCURE","EMMVEE","ENDURANCE","ENGINERSIN","ERIS","ESCORTS","ETERNAL",
    "EXIDEIND","NYKAA","FEDERALBNK","FACT","FINCABLES","FSL","FIVESTAR","FORCEMOT",
    "FORTIS","GAIL","GVT&D","GMRAIRPORT","GABRIEL","GALLANTT","GRSE","GICRE","GILLETTE",
    "GLAND","GLAXO","GLENMARK","MEDANTA","GODIGIT","GPIL","GODFRYPHLP","GODREJCP",
    "GODREJIND","GODREJPROP","GRANULES","GRAPHITE","GRASIM","GRAVITA","GESHIP",
    "FLUOROCHEM","GMDCLTD","HEG","HBLENGINE","HCLTECH","HDBFS","HDFCAMC","HDFCBANK",
    "HDFCLIFE","HFCL","HAVELLS","HEROMOTOCO","HEXT","HSCL","HINDALCO","HAL",
    "HINDCOPPER","HINDPETRO","HINDUNILVR","HINDZINC","POWERINDIA","HOMEFIRST","HONASA",
    "HONAUT","HUDCO","HYUNDAI","ICICIBANK","ICICIGI","ICICIAMC","ICICIPRULI","IDBI",
    "IDFCFIRSTB","IFCI","IIFL","IRB","IRCON","ITCHOTELS","ITC","ITI","INDGN",
    "INDIACEM","INDIAMART","INDIANB","IEX","INDHOTEL","IOC","IOB","IRCTC","IRFC",
    "IREDA","IGL","INDUSTOWER","INDUSINDBK","NAUKRI","INFY","INOXWIND","INTELLECT",
    "INDIGO","IGIL","IKS","IPCALAB","JBCHEPHARM","JKCEMENT","JBMA","JKTYRE",
    "JMFINANCIL","JSWCEMENT","JSWDULUX","JSWENERGY","JSWINFRA","JSWSTEEL","JAINREC",
    "JPPOWER","J&KBANK","JINDALSAW","JSL","JINDALSTEL","JIOFIN","JUBLFOOD","JUBLINGREA",
    "JUBLPHARMA","JWL","JYOTICNC","KPRMILL","KEI","KPITTECH","KAJARIACER","KPIL",
    "KALYANKJIL","KARURVYSYA","KAYNES","KEC","KFINTECH","KIRLOSENG","KOTAKBANK","KIMS",
    "LTF","LTTS","LGEINDIA","LICHSGFIN","LTFOODS","LTM","LT","LATENTVIEW","LAURUSLABS",
    "THELEELA","LEMONTREE","LENSKART","LICI","LINDEINDIA","LLOYDSME","LODHA","LUPIN",
    "MMTC","MRF","MGL","M&MFIN","M&M","MANAPPURAM","MRPL","MANKIND","MARICO","MARUTI",
    "MFSL","MAXHEALTH","MAZDOCK","MEESHO","MINDACORP","MSUMI","MOTILALOFS","MPHASIS",
    "MCX","MUTHOOTFIN","NATCOPHARM","NBCC","NCC","NHPC","NLCINDIA","NMDC","NSLNISP",
    "NTPCGREEN","NTPC","NH","NATIONALUM","NAVA","NAVINFLUOR","NESTLEIND","NETWEB",
    "NEULANDLAB","NEWGEN","NAM-INDIA","NIVABUPA","NUVAMA","NUVOCO","OBEROIROLTY",
    "ONGC","OIL","OLAELEC","OLECTRA","PAYTM","ONESOURCE","OFSS","POLICYBZR","PCBL",
    "PGEL","PIIND","PNBHOUSING","PTCIL","PVRINOX","PAGEIND","PARADEEP","PATANJALI",
    "PERSISTENT","PETRONET","PFIZER","PHOENIXLTD","PWL","PIDILITIND","PINELABS",
    "PIRAMALFIN","PPLPHARMA","POLYMED","POLYCAB","POONAWALLA","PFC","POWERGRID",
    "PREMIERENE","PRESTIGE","PNB","RRKABEL","RBLBANK","RECLTD","RHIM","RITES","RADICO",
    "RVNL","RAILTEL","RAINBOW","RKFORGE","REDINGTON","RELIANCE","RPOWER","SBFC",
    "SBICARD","SBILIFE","SJVN","SRF","SAGILITY","SAILIFE","SAMMAANCAP","MOTHERSON",
    "SAPPHIRE","SARDAEN","SAREGAMA","SCHAEFFLER","SCHNEIDER","SCI","SHREECEM",
    "SHRIRAMFIN","SHYAMMETL","ENRIN","SIEMENS","SIGNATURE","SOBHA","SOLARINDS",
    "SONACOMS","SONATSOFTW","STARHEALTH","SBIN","SAIL","SUMICHEM","SUNPHARMA","SUNTV",
    "SUNDARMFIN","SUPREMEIND","SPLPETRO","SUZLON","SWANCORP","SWIGGY","SYNGENE",
    "SYRMA","TBOTEK","TVSMOTOR","TATACAP","TATACHEM","TATACOMM","TCS","TATACONSUM",
    "TATAELXSI","TATAINVEST","TMCV","TMPV","TATAPOWER","TATASTEEL","TATATECH","TTML",
    "TECHM","TECHNOE","TEGA","TEJASNET","TENNIND","NIACL","RAMCOCEM","THERMAX",
    "TIMKEN","TITAGARH","TITAN","TORNTPHARM","TORNTPOWER","TARIL","TRAVELFOOD","TRENT",
    "TRIDENT","TRITURBINE","TIINDIA","UCOBANK","UNOMINDA","UPL","UTIAMC","ULTRACEMCO",
    "UNIONBANK","UBL","UNITDSPR","URBANCO","USHAMART","VTL","VBL","VAML","VISL",
    "VEDL","VOGL","VEDPOWER","VIJAYA","VMM","IDEA","VOLTAS","WAAREEENER","WELCORP",
    "WELSPUNLIV","WHIRLPOOL","WIPRO","WOCKPHARMA","YESBANK","ZFCVINDIA","ZEEL",
    "ZENTEC","ZENSARTECH","ZYDUSLIFE","ZYDUSWELL","ECLERX"
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_token_map() -> dict:
    """Load symbol→token mapping from master JSON if it exists."""
    map_path = Path("data/master/symbol_token_map.json")
    if map_path.exists():
        with open(map_path) as f:
            data = json.load(f)
        return data.get("symbols", {})
    return {}


def compute_rs(close: float, prev_close_65d: float, nifty_close: float, nifty_prev_65d: float) -> float:
    """Relative strength vs Nifty50 over ~65 trading days (~3 months)."""
    if prev_close_65d <= 0 or nifty_prev_65d <= 0:
        return 0.0
    stock_return = (close - prev_close_65d) / prev_close_65d
    nifty_return = (nifty_close - nifty_prev_65d) / nifty_prev_65d
    return round(stock_return / nifty_return if nifty_return != 0 else 0.0, 4)


def fetch_with_retry(ic, exchange, trading_symbol, timeframe, start, end, retries=3, delay=2):
    """Fetch historical data with exponential backoff retry."""
    for attempt in range(retries):
        try:
            gen = ic.historical_data(
                exchange=exchange,
                trading_symbol=trading_symbol,
                timeframe=timeframe,
                start=start,
                end=end,
            )
            return [c for c in gen]
        except Exception as e:
            if attempt < retries - 1:
                wait = delay * (2 ** attempt)
                log.warning(f"  Retry {attempt+1} for {trading_symbol}: {e} — wait {wait}s")
                time.sleep(wait)
            else:
                raise


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    api_token  = os.environ.get("DEFINEDGE_API_TOKEN")
    api_secret = os.environ.get("DEFINEDGE_API_SECRET")
    if not api_token or not api_secret:
        raise SystemExit("ERROR: DEFINEDGE_API_TOKEN and DEFINEDGE_API_SECRET must be set")

    # ── Login ──────────────────────────────────────────────────────────────
    log.info("Logging in to Definedge Integrate API...")
    conn = ConnectToIntegrate()
    conn.login(api_token=api_token, api_secret=api_secret)
    ic = IntegrateData(conn)
    log.info("Login successful")

    today     = datetime.today()
    start_1d  = today - timedelta(days=1)
    start_65d = today - timedelta(days=95)   # ~65 trading days buffer
    date_str  = today.strftime("%Y-%m-%d")

    # ── Fetch Nifty50 reference (for RS calculation) ───────────────────────
    log.info("Fetching NIFTY50 index for RS baseline...")
    nifty50_close    = 0.0
    nifty50_prev_65d = 0.0
    try:
        nifty_hist = fetch_with_retry(ic, conn.EXCHANGE_TYPE_NSE, "NIFTY50-EQ",
                                       conn.TIMEFRAME_TYPE_DAY, start_65d, today)
        if nifty_hist:
            nifty50_close    = nifty_hist[-1].get("close", 0.0)
            nifty50_prev_65d = nifty_hist[0].get("close", 0.0) if len(nifty_hist) >= 2 else 0.0
    except Exception as e:
        log.warning(f"Could not fetch Nifty50: {e} — RS will be 0.0 for all symbols")

    # ── Fetch each symbol ──────────────────────────────────────────────────
    output = {
        "fetch_date": date_str,
        "fetch_time": today.strftime("%H:%M:%S IST"),
        "source": "Definedge Integrate API",
        "nifty50_close": nifty50_close,
        "symbols": {}
    }

    token_map = load_token_map()
    failed = []

    for i, sym in enumerate(NIFTY500, 1):
        trading_sym = f"{sym}-EQ"
        log.info(f"[{i:3d}/{len(NIFTY500)}] Fetching {trading_sym}...")

        try:
            # 65-day history for DMA + RS
            hist_65d = fetch_with_retry(ic, conn.EXCHANGE_TYPE_NSE, trading_sym,
                                        conn.TIMEFRAME_TYPE_DAY, start_65d, today)

            # Today's candle
            hist_1d  = fetch_with_retry(ic, conn.EXCHANGE_TYPE_NSE, trading_sym,
                                        conn.TIMEFRAME_TYPE_DAY, start_1d, today)

            if not hist_65d and not hist_1d:
                log.warning(f"  No data for {trading_sym}")
                output["symbols"][sym] = {"error": "no_data", "data_grade": "C"}
                continue

            candles = hist_65d or hist_1d
            closes  = [c.get("close", 0) for c in candles if c.get("close")]

            today_c  = candles[-1]
            prev_c   = candles[-2] if len(candles) >= 2 else candles[-1]

            close_now      = today_c.get("close", 0.0)
            prev_close_val = prev_c.get("close", 0.0)
            prev_close_65d = closes[0] if closes else 0.0

            # Simple Moving Averages
            dma_50  = round(sum(closes[-50:])  / len(closes[-50:]),  2) if len(closes) >= 50  else None
            dma_150 = round(sum(closes[-150:]) / len(closes[-150:]), 2) if len(closes) >= 150 else None
            dma_200 = round(sum(closes[-200:]) / len(closes[-200:]), 2) if len(closes) >= 200 else None

            # 52-week range
            highs_52w = [c.get("high", 0) for c in candles]
            lows_52w  = [c.get("low", 0)  for c in candles if c.get("low", 0) > 0]
            week52_high = max(highs_52w) if highs_52w else close_now
            week52_low  = min(lows_52w)  if lows_52w  else close_now

            # Change %
            change_pct = round(((close_now - prev_close_val) / prev_close_val) * 100, 2) \
                         if prev_close_val > 0 else 0.0

            # RS
            rs_raw = compute_rs(close_now, prev_close_65d, nifty50_close, nifty50_prev_65d)

            # Volume
            volume = today_c.get("volume", 0)

            record = {
                "open":        today_c.get("open",  close_now),
                "high":        today_c.get("high",  close_now),
                "low":         today_c.get("low",   close_now),
                "close":       close_now,
                "volume":      volume,
                "prev_close":  prev_close_val,
                "change_pct":  change_pct,
                "52w_high":    round(week52_high, 2),
                "52w_low":     round(week52_low,  2),
                "dma_50":      dma_50,
                "dma_150":     dma_150,
                "dma_200":     dma_200,
                "rs_raw":      rs_raw,
                "data_grade":  "A",
            }
            output["symbols"][sym] = record
            time.sleep(0.3)   # polite rate-limiting: ~3 symbols/sec

        except Exception as e:
            log.error(f"  FAILED {trading_sym}: {e}")
            output["symbols"][sym] = {"error": str(e), "data_grade": "C"}
            failed.append(sym)
            time.sleep(1)

    # ── Save output ────────────────────────────────────────────────────────
    out_dir  = Path("data/daily")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date_str}.json"

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    success_count = sum(1 for v in output["symbols"].values() if v.get("data_grade") != "C")
    log.info(f"\n✓ Saved {out_path}  |  {success_count}/{len(NIFTY500)} symbols OK  |  {len(failed)} failed")
    if failed:
        log.warning(f"Failed symbols: {failed}")


if __name__ == "__main__":
    main()
