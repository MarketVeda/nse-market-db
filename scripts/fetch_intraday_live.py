#!/usr/bin/env python3
"""
fetch_intraday_live.py
----------------------
Runs every 15 minutes during market hours via GitHub Actions.

Fetches for ALL NIFTY 500 symbols:
  - Live LTP, OHLC, Volume, OI, Change% via Kite quotes API (1-2 API calls = instant)

Fetches for FnO 211 symbols:
  - 15min candles from 9:15 AM to current time

Saves:
  data/live/latest.json           ← Claude reads this (always current)
  data/live/YYYY-MM-DD/HH-MM.json ← Permanent timestamped archive

Per run time: ~2-3 min | GitHub Actions usage: ~1716 min/month (within 2000 free tier)
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import json, time, logging
from datetime import datetime
from pathlib import Path
from kite_auth import get_kite

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Full NIFTY 500 Universe ───────────────────────────────────────────────────
NIFTY500 = [
    "360ONE","3MINDIA","ABB","ACC","ACMESOLAR","AIAENG","APLAPOLLO","AUBANK","AWL",
    "AADHARHFC","AARTIIND","AAVAS","ABBOTINDIA","ACE","ACUTAAS","ADANIENSOL","ADANIENT",
    "ADANIGREEN","ADANIPORTS","ADANIPOWER","ATGL","ABCAPITAL","ABFRL","ABLBL","ABREL",
    "ABSLAMC","CPPLUS","AEGISLOG","AEGISVOPAK","AFCONS","AFFLE","AJANTPHARM","ALKEM",
    "ABDL","AMBER","AMBUJACEM","ANANDRATHI","ANANTRAJ","ANGELONE","APARINDS","APOLLOHOSP",
    "APOLLOTYRE","APTUS","ASAHIINDIA","ASHOKLEY","ASIANPAINT","ASTERDM","ASTRAL",
    "ATHERENERG","ATUL","AUROPHARMA","AIIL","DMART","AXISBANK","BEML","BLS","BSE",
    "BAJAJ-AUTO","BAJFINANCE","BAJAJFINSV","BAJAJHLDNG","BAJAJHFL","BALKRISIND",
    "BALRAMCHIN","BANDHANBNK","BANKBARODA","BANKINDIA","MAHABANK","BATAINDIA","BAYERCROP",
    "BELRISE","BERGEPAINT","BDL","BEL","BHARATFORG","BHEL","BPCL","BHARTIARTL",
    "BHARTIHEXA","BIKAJI","GROWW","BIOCON","BSOFT","BLUEDART","BLUEJET","BLUESTARCO",
    "BBTC","BOSCHLTD","FIRSTCRY","BRIGADE","BRITANNIA","MAPMYINDIA","CCL","CESC",
    "CGPOWER","CIEINDIA","CRISIL","CANFINHOME","CANBK","CANHLIFE","CAPLIPOINT","CGCL",
    "CARBORUNIV","CARTRADE","CASTROLIND","CEATLTD","CEMPRO","CENTRALBK","CDSL","CHALET",
    "CHAMBLFERT","CHENNPETRO","CHOICEIN","CHOLAHLDNG","CHOLAFIN","CIPLA","CUB","CLEAN",
    "COALINDIA","COCHINSHIP","COFORGE","COHANCE","COLPAL","CAMS","CONCORDBIO","CONCOR",
    "COROMANDEL","CRAFTSMAN","CREDITACC","CROMPTON","CUMMINSIND","CYIENT","DCMSHRIRAM",
    "DLF","DOMS","DABUR","DALBHARAT","DATAPATTNS","DEEPAKFERT","DEEPAKNTR","DELHIVERY",
    "DEVYANI","DIVISLAB","DIXON","LALPATHLAB","DRREDDY","EIDPARRY","EIHOTEL","EICHERMOT",
    "ELECON","ELGIEQUIP","EMAMILTD","EMCURE","EMMVEE","ENDURANCE","ENGINERSIN","ERIS",
    "ESCORTS","ETERNAL","EXIDEIND","NYKAA","FEDERALBNK","FACT","FINCABLES","FSL",
    "FIVESTAR","FORCEMOT","FORTIS","GAIL","GVT&D","GMRAIRPORT","GABRIEL","GALLANTT",
    "GRSE","GICRE","GILLETTE","GLAND","GLAXO","GLENMARK","MEDANTA","GODIGIT","GPIL",
    "GODFRYPHLP","GODREJCP","GODREJIND","GODREJPROP","GRANULES","GRAPHITE","GRASIM",
    "GRAVITA","GESHIP","FLUOROCHEM","GMDCLTD","HEG","HBLENGINE","HCLTECH","HDBFS",
    "HDFCAMC","HDFCBANK","HDFCLIFE","HFCL","HAVELLS","HEROMOTOCO","HEXT","HSCL",
    "HINDALCO","HAL","HINDCOPPER","HINDPETRO","HINDUNILVR","HINDZINC","POWERINDIA",
    "HOMEFIRST","HONASA","HONAUT","HUDCO","HYUNDAI","ICICIBANK","ICICIGI","ICICIAMC",
    "ICICIPRULI","IDBI","IDFCFIRSTB","IFCI","IIFL","IRB","IRCON","ITCHOTELS","ITC",
    "ITI","INDGN","INDIACEM","INDIAMART","INDIANB","IEX","INDHOTEL","IOC","IOB","IRCTC",
    "IRFC","IREDA","IGL","INDUSTOWER","INDUSINDBK","NAUKRI","INFY","INOXWIND","INTELLECT",
    "INDIGO","IGIL","IKS","IPCALAB","JBCHEPHARM","JKCEMENT","JBMA","JKTYRE","JMFINANCIL",
    "JSWCEMENT","JSWDULUX","JSWENERGY","JSWINFRA","JSWSTEEL","JAINREC","JPPOWER",
    "J&KBANK","JINDALSAW","JSL","JINDALSTEL","JIOFIN","JUBLFOOD","JUBLINGREA","JUBLPHARMA",
    "JWL","JYOTICNC","KPRMILL","KEI","KPITTECH","KAJARIACER","KPIL","KALYANKJIL",
    "KARURVYSYA","KAYNES","KEC","KFINTECH","KIRLOSENG","KOTAKBANK","KIMS","LTF","LTTS",
    "LGEINDIA","LICHSGFIN","LTFOODS","LTM","LT","LATENTVIEW","LAURUSLABS","THELEELA",
    "LEMONTREE","LENSKART","LICI","LINDEINDIA","LLOYDSME","LODHA","LUPIN","MMTC","MRF",
    "MGL","M&MFIN","M&M","MANAPPURAM","MRPL","MANKIND","MARICO","MARUTI","MFSL",
    "MAXHEALTH","MAZDOCK","MEESHO","MINDACORP","MSUMI","MOTILALOFS","MPHASIS","MCX",
    "MUTHOOTFIN","NATCOPHARM","NBCC","NCC","NHPC","NLCINDIA","NMDC","NSLNISP","NTPCGREEN",
    "NTPC","NH","NATIONALUM","NAVA","NAVINFLUOR","NESTLEIND","NETWEB","NEULANDLAB",
    "NEWGEN","NAM-INDIA","NIVABUPA","NUVAMA","NUVOCO","OBEROIROLTY","ONGC","OIL",
    "OLAELEC","OLECTRA","PAYTM","ONESOURCE","OFSS","POLICYBZR","PCBL","PGEL","PIIND",
    "PNBHOUSING","PTCIL","PVRINOX","PAGEIND","PARADEEP","PATANJALI","PERSISTENT",
    "PETRONET","PFIZER","PHOENIXLTD","PWL","PIDILITIND","PINELABS","PIRAMALFIN",
    "PPLPHARMA","POLYMED","POLYCAB","POONAWALLA","PFC","POWERGRID","PREMIERENE",
    "PRESTIGE","PNB","RRKABEL","RBLBANK","RECLTD","RHIM","RITES","RADICO","RVNL",
    "RAILTEL","RAINBOW","RKFORGE","REDINGTON","RELIANCE","RPOWER","SBFC","SBICARD",
    "SBILIFE","SJVN","SRF","SAGILITY","SAILIFE","SAMMAANCAP","MOTHERSON","SAPPHIRE",
    "SARDAEN","SAREGAMA","SCHAEFFLER","SCHNEIDER","SCI","SHREECEM","SHRIRAMFIN",
    "SHYAMMETL","ENRIN","SIEMENS","SIGNATURE","SOBHA","SOLARINDS","SONACOMS","SONATSOFTW",
    "STARHEALTH","SBIN","SAIL","SUMICHEM","SUNPHARMA","SUNTV","SUNDARMFIN","SUPREMEIND",
    "SPLPETRO","SUZLON","SWANCORP","SWIGGY","SYNGENE","SYRMA","TBOTEK","TVSMOTOR",
    "TATACAP","TATACHEM","TATACOMM","TCS","TATACONSUM","TATAELXSI","TATAINVEST","TMCV",
    "TMPV","TATAPOWER","TATASTEEL","TATATECH","TTML","TECHM","TECHNOE","TEGA","TEJASNET",
    "TENNIND","NIACL","RAMCOCEM","THERMAX","TIMKEN","TITAGARH","TITAN","TORNTPHARM",
    "TORNTPOWER","TARIL","TRAVELFOOD","TRENT","TRIDENT","TRITURBINE","TIINDIA","UCOBANK",
    "UNOMINDA","UPL","UTIAMC","ULTRACEMCO","UNIONBANK","UBL","UNITDSPR","URBANCO",
    "USHAMART","VTL","VBL","VAML","VISL","VEDL","VOGL","VEDPOWER","VIJAYA","VMM",
    "IDEA","VOLTAS","WAAREEENER","WELCORP","WELSPUNLIV","WHIRLPOOL","WIPRO","WOCKPHARMA",
    "YESBANK","ZFCVINDIA","ZEEL","ZENTEC","ZENSARTECH","ZYDUSLIFE","ZYDUSWELL","ECLERX"
]

# FnO universe for candle fetch
FNO_SYMBOLS = [
    "360ONE","ABB","APLAPOLLO","AUBANK","ADANIENSOL","ADANIENT","ADANIGREEN",
    "ADANIPORTS","ADANIPOWER","ABCAPITAL","ALKEM","AMBER","AMBUJACEM","ANGELONE",
    "APOLLOHOSP","ASHOKLEY","ASIANPAINT","ASTRAL","AUROPHARMA","DMART","AXISBANK",
    "BSE","BAJAJ-AUTO","BAJFINANCE","BAJAJFINSV","BAJAJHLDNG","BANDHANBNK","BANKBARODA",
    "BANKINDIA","BDL","BEL","BHARATFORG","BHEL","BPCL","BHARTIARTL","BIOCON",
    "BLUESTARCO","BOSCHLTD","BRITANNIA","CGPOWER","CANBK","CDSL","CHOLAFIN","CIPLA",
    "COALINDIA","COCHINSHIP","COFORGE","COLPAL","CAMS","CONCOR","CROMPTON","CUMMINSIND",
    "DLF","DABUR","DALBHARAT","DELHIVERY","DIVISLAB","DIXON","DRREDDY","ETERNAL",
    "EICHERMOT","EXIDEIND","FORCEMOT","NYKAA","FORTIS","GAIL","GVT&D","GMRAIRPORT",
    "GLENMARK","GODFRYPHLP","GODREJCP","GODREJPROP","GRASIM","HCLTECH","HDFCAMC",
    "HDFCBANK","HDFCLIFE","HAVELLS","HEROMOTOCO","HINDALCO","HAL","HINDPETRO",
    "HINDUNILVR","HINDZINC","POWERINDIA","HYUNDAI","ICICIBANK","ICICIGI","ICICIPRULI",
    "IDFCFIRSTB","ITC","INDIANB","IEX","IOC","IRFC","IREDA","INDUSTOWER","INDUSINDBK",
    "NAUKRI","INFY","INOXWIND","INDIGO","JINDALSTEL","JSWENERGY","JSWSTEEL","JIOFIN",
    "JUBLFOOD","KEI","KPITTECH","KALYANKJIL","KAYNES","KFINTECH","KOTAKBANK","LTF",
    "LICHSGFIN","LTM","LT","LAURUSLABS","LICI","LODHA","LUPIN","M&M","MANAPPURAM",
    "MANKIND","MARICO","MARUTI","MFSL","MAXHEALTH","MAZDOCK","MOTILALOFS","MPHASIS",
    "MCX","MUTHOOTFIN","NBCC","NHPC","NMDC","NTPC","NATIONALUM","NESTLEIND","NAM-INDIA",
    "NUVAMA","OBEROIROLTY","ONGC","OIL","PAYTM","OFSS","POLICYBZR","PGEL","PIIND",
    "PNBHOUSING","PAGEIND","PATANJALI","PERSISTENT","PETRONET","PIDILITIND","POLYCAB",
    "PFC","POWERGRID","PREMIERENE","PRESTIGE","PNB","RBLBANK","RECLTD","RADICO","RVNL",
    "RELIANCE","SBICARD","SBILIFE","SHREECEM","SRF","SAMMAANCAP","MOTHERSON","SHRIRAMFIN",
    "SIEMENS","SOLARINDS","SONACOMS","SBIN","SAIL","SUNPHARMA","SUPREMEIND","SUZLON",
    "SWIGGY","TATACONSUM","TVSMOTOR","TCS","TATAELXSI","TMPV","TATAPOWER","TATASTEEL",
    "TECHM","FEDERALBNK","INDHOTEL","PHOENIXLTD","TITAN","TORNTPHARM","TRENT","TIINDIA",
    "UNOMINDA","UPL","ULTRACEMCO","UNIONBANK","UNITDSPR","VBL","VEDL","VMM","IDEA",
    "VOLTAS","WAAREEENER","WIPRO","YESBANK","ZYDUSLIFE"
]


def fetch_all_quotes(kite, token_map: dict) -> dict:
    """
    Fetch live quotes for ALL 500 NIFTY500 symbols in batches of 500.
    Kite quotes API supports up to 500 instruments per call.
    Returns dict of symbol -> quote data.
    """
    log.info(f"Fetching live quotes for {len(NIFTY500)} NIFTY500 symbols...")
    all_keys = [f"NSE:{s}-EQ" for s in NIFTY500 if token_map.get(s)]
    results  = {}

    # Fetch in batches of 500 (Kite limit)
    for batch_start in range(0, len(all_keys), 500):
        batch = all_keys[batch_start:batch_start+500]
        try:
            quotes = kite.quote(batch)
            for key, q in quotes.items():
                sym = key.replace("NSE:","").replace("-EQ","")
                ohlc = q.get("ohlc", {})
                prev = ohlc.get("close", 0)
                ltp  = q.get("last_price", 0)
                results[sym] = {
                    "ltp":         ltp,
                    "open":        ohlc.get("open", 0),
                    "high":        ohlc.get("high", 0),
                    "low":         ohlc.get("low", 0),
                    "prev_close":  prev,
                    "change":      round(ltp - prev, 2),
                    "change_pct":  round(((ltp-prev)/prev)*100, 2) if prev else 0,
                    "volume":      q.get("volume", 0),
                    "avg_price":   q.get("average_price", 0),
                    "oi":          q.get("oi", 0),
                    "buy_qty":     q.get("buy_quantity", 0),
                    "sell_qty":    q.get("sell_quantity", 0),
                }
            log.info(f"Quotes batch [{batch_start}:{batch_start+500}]: {len(quotes)} returned")
            time.sleep(0.3)
        except Exception as e:
            log.error(f"Quotes batch [{batch_start}] failed: {e}")
            time.sleep(2)

    log.info(f"Total quotes fetched: {len(results)}/{len(NIFTY500)} symbols")
    return results


def fetch_fno_candles(kite, token_map: dict, mkt_start, now) -> dict:
    """
    Fetch 15min candles from market open to NOW for all FnO 211 symbols.
    Rate limit: 3 req/sec → 211 symbols ≈ 70 seconds.
    """
    log.info(f"Fetching 15min candles for {len(FNO_SYMBOLS)} FnO symbols...")
    candles_data = {}

    for i, sym in enumerate(FNO_SYMBOLS, 1):
        inst = token_map.get(sym)
        if not inst:
            continue
        try:
            candles = kite.historical_data(inst["token"], mkt_start, now, "15minute")
            cdicts  = []
            for c in candles:
                dt = c["date"]
                t  = dt.strftime("%H:%M") if hasattr(dt,"strftime") else str(dt)[:16]
                cdicts.append({
                    "t": t,
                    "o": round(c["open"],  2),
                    "h": round(c["high"],  2),
                    "l": round(c["low"],   2),
                    "c": round(c["close"], 2),
                    "v": c.get("volume", 0),
                })
            candles_data[sym] = cdicts

            # Compute quick stats from latest candles
            if cdicts:
                closes = [c["c"] for c in cdicts]
                vols   = [c["v"] for c in cdicts]
                highs  = [c["h"] for c in cdicts]
                lows   = [c["l"] for c in cdicts if c["l"] > 0]
                pv     = sum(((c["h"]+c["l"]+c["c"])/3)*c["v"] for c in cdicts if c["v"]>0)
                tv     = sum(c["v"] for c in cdicts if c["v"]>0)
                candles_data[f"{sym}_stats"] = {
                    "candles_so_far": len(cdicts),
                    "day_high":       max(highs),
                    "day_low":        min(lows) if lows else 0,
                    "vwap":           round(pv/tv, 2) if tv > 0 else 0,
                    "volume_so_far":  sum(vols),
                    "last_close":     closes[-1] if closes else 0,
                    "last_candle_t":  cdicts[-1]["t"] if cdicts else "",
                }

        except Exception as e:
            log.warning(f"[{i:3d}] {sym} candle failed: {e}")
            candles_data[sym] = []

        time.sleep(0.34)   # 3 req/sec rate limit

    ok = sum(1 for v in candles_data.values() if isinstance(v, list) and len(v) > 0)
    log.info(f"Candles fetched: {ok}/{len(FNO_SYMBOLS)} symbols OK")
    return candles_data


def main():
    log.info("=== Live Intraday Snapshot Start ===")
    kite      = get_kite()
    now       = datetime.now()
    date_str  = now.strftime("%Y-%m-%d")
    time_str  = now.strftime("%H:%M")
    mkt_start = now.replace(hour=9, minute=15, second=0, microsecond=0)

    # Load instrument map
    map_path  = Path("data/master/instrument_map.json")
    if not map_path.exists():
        log.error("Instrument map missing — run main pipeline first")
        sys.exit(1)
    token_map = json.loads(map_path.read_text())["tokens"]

    # 1. Fetch quotes for ALL 500 NIFTY500 symbols (fast — 1-2 API calls)
    quotes = fetch_all_quotes(kite, token_map)

    # 2. Fetch 15min candles for 211 FnO symbols (slower — 70 sec)
    candles = fetch_fno_candles(kite, token_map, mkt_start, now)

    # 3. Build output
    output = {
        "data_type":       "LIVE_INTRADAY_NIFTY500",
        "description":     "Live 15-min snapshot — quotes for 500 NIFTY500 + candles for 211 FnO",
        "snapshot_date":   date_str,
        "snapshot_time":   time_str,
        "source":          "Zerodha Kite Connect",
        "update_frequency":"Every 15 minutes during market hours (09:15–15:30 IST)",
        "quotes_universe": f"NIFTY500 — {len(quotes)} symbols",
        "candles_universe":f"FnO — {len(FNO_SYMBOLS)} symbols, 15min candles from 09:15 to {time_str}",
        "quote_fields":    ["ltp","open","high","low","prev_close","change","change_pct",
                            "volume","avg_price","oi","buy_qty","sell_qty"],
        "note":            "Use quotes for screening. Use candles for pattern/VCP analysis.",

        # All 500 NIFTY500 live quotes
        "quotes": quotes,

        # FnO 15min candles (sym -> [candle list], sym_stats -> stats dict)
        "candles_15min": candles,
    }

    # Save timestamped snapshot
    snap_dir  = Path(f"data/live/{date_str}")
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_file = snap_dir / f"{time_str.replace(':','-')}.json"
    snap_file.write_text(json.dumps(output, indent=2, default=str))

    # Overwrite latest.json — Claude always reads this
    latest = Path("data/live/latest.json")
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(json.dumps(output, indent=2, default=str))

    log.info(f"=== Snapshot Done ===")
    log.info(f"Quotes: {len(quotes)} symbols | Candles: {len([k for k in candles if not k.endswith('_stats')])} FnO symbols")
    log.info(f"Files: {snap_file} + data/live/latest.json")


if __name__ == "__main__":
    main()
