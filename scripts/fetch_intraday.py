#!/usr/bin/env python3
"""
fetch_intraday.py — Intraday candles for FnO universe (211 symbols)
Timeframes: 15min, 5min, 1min + computed stats (VWAP, opening range, vol surge)
Output: data/intraday/YYYY-MM-DD.json
Runs after market close (3:35 PM IST) — fetches COMPLETE day's candles
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import json, time, logging
from datetime import datetime, timedelta
from pathlib import Path
from kite_auth import get_kite

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

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

TIMEFRAMES = {"15min": "15minute", "5min": "5minute", "1min": "minute"}


def c2d(c):
    dt = c["date"]
    t  = dt.strftime("%H:%M") if hasattr(dt,"strftime") else str(dt)[:16]
    return {"t":t,"o":round(c["open"],2),"h":round(c["high"],2),
            "l":round(c["low"],2),"c":round(c["close"],2),"v":c.get("volume",0)}


def intraday_stats(candles):
    if not candles:
        return {}
    o   = [c["h"] for c in candles]
    lo  = [c["l"] for c in candles if c["l"]>0]
    v   = [c["v"] for c in candles]
    cls = [c["c"] for c in candles]
    pv  = sum(((c["h"]+c["l"]+c["c"])/3)*c["v"] for c in candles if c["v"]>0)
    tv  = sum(c["v"] for c in candles if c["v"]>0)
    vwap= round(pv/tv,2) if tv>0 else 0
    or_h= max(c["h"] for c in candles[:2]) if len(candles)>=2 else candles[0]["h"]
    or_l= min(c["l"] for c in candles[:2]) if len(candles)>=2 else candles[0]["l"]
    lh_v= sum(v[-4:]) if len(v)>=4 else sum(v)
    avg_v=sum(v)/len(v) if v else 1
    surge=round(lh_v/(avg_v*4),2) if avg_v>0 else 0
    return {
        "day_open":           candles[0]["o"],
        "day_high":           max(o),
        "day_low":            min(lo) if lo else 0,
        "day_close":          cls[-1],
        "day_change_pct":     round(((cls[-1]-candles[0]["o"])/candles[0]["o"])*100,2) if candles[0]["o"] else 0,
        "opening_range_high": or_h,
        "opening_range_low":  or_l,
        "vwap":               vwap,
        "vol_surge_last_hr":  surge,
        "day_range_pct":      round((max(o)-min(lo))/cls[-1]*100,2) if cls[-1] and lo else 0,
        "total_volume":       sum(v),
        "close_vs_vwap":      "above" if cls[-1]>vwap else "below",
        "close_vs_or_high":   "above" if cls[-1]>or_h else "below",
    }


def main():
    log.info("=== Intraday Fetch Start ===")
    kite     = get_kite()
    today    = datetime.today()
    date_str = today.strftime("%Y-%m-%d")
    mkt_s    = today.replace(hour=9,  minute=15, second=0, microsecond=0)
    mkt_e    = today.replace(hour=15, minute=30, second=0, microsecond=0)

    map_path  = Path("data/master/instrument_map.json")
    if not map_path.exists():
        log.error("Instrument map missing — fetch_eod.py must run first")
        sys.exit(1)
    token_map = json.loads(map_path.read_text())["tokens"]

    output = {
        "data_type":   "INTRADAY_CANDLES",
        "description": "Complete intraday candle data for FnO universe — 15min, 5min, 1min",
        "universe":    "NSE FnO (211 symbols)",
        "fetch_date":  date_str,
        "fetch_time":  today.strftime("%H:%M:%S IST"),
        "source":      "Zerodha Kite Connect Historical API",
        "market_hours":"09:15 to 15:30 IST",
        "timeframes":  ["15min (25 candles/day)", "5min (75 candles/day)", "1min (375 candles/day)"],
        "stats_fields":["day_open","day_high","day_low","day_close","day_change_pct",
                        "opening_range_high","opening_range_low","vwap",
                        "vol_surge_last_hr","day_range_pct","total_volume",
                        "close_vs_vwap","close_vs_or_high"],
        "note":        "Data fetched after 3:30 PM — complete day candles only",
        "symbols":     {}
    }

    failed = []
    for i, sym in enumerate(FNO_SYMBOLS, 1):
        inst = token_map.get(sym)
        if not inst:
            log.warning(f"[{i:3d}] {sym}: not in map")
            continue

        log.info(f"[{i:3d}/{len(FNO_SYMBOLS)}] {sym}")
        sym_data = {}
        for tf_name, tf_kite in TIMEFRAMES.items():
            try:
                candles = kite.historical_data(inst["token"], mkt_s, mkt_e, tf_kite)
                cdicts  = [c2d(c) for c in candles]
                sym_data[tf_name] = cdicts
                if tf_name == "15min" and cdicts:
                    sym_data["stats"] = intraday_stats(cdicts)
                time.sleep(0.34)
            except Exception as e:
                log.error(f"  {sym} {tf_name}: {e}")
                sym_data[tf_name] = []
                time.sleep(1)

        sym_data["data_grade"] = "A" if sym_data.get("15min") else "C"
        output["symbols"][sym] = sym_data
        if sym_data["data_grade"] == "C":
            failed.append(sym)

    out = Path(f"data/intraday/{date_str}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, default=str))
    ok = sum(1 for v in output["symbols"].values() if v.get("data_grade")=="A")
    log.info(f"=== Intraday Done: {out} | {ok}/{len(FNO_SYMBOLS)} OK | {len(failed)} failed ===")


if __name__ == "__main__":
    main()
