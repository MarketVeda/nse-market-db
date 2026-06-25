#!/usr/bin/env python3
"""
fetch_intraday.py — Full-day intraday candles for FnO universe (211 symbols)
-----------------------------------------------------------------------------
INCREMENTAL: Skips if today's file already complete (>200 symbols).
PRUNING:     Deletes previous day's file immediately after saving today's.
             Intraday is only useful for today — yesterday's is waste.
             Keep only last 2 days for safety (in case EOD pipeline reruns).
Output: data/intraday/YYYY-MM-DD.json  (keep last 2 days only)
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import json, time, logging
from datetime import datetime
from pathlib import Path
from kite_auth import get_kite

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

KEEP_DAYS = 2   # intraday: keep ONLY last 2 days — it's bulky (15 MB each)

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

TIMEFRAMES = {"15min":"15minute","5min":"5minute","1min":"minute"}


def prune_old_files(folder: Path, keep: int):
    files = sorted(folder.glob("*.json"))
    deleted = []
    for f in files[:-keep]:
        f.unlink()
        deleted.append(f.name)
    if deleted:
        log.info(f"Pruned intraday: {deleted}")


def c2d(c):
    dt = c["date"]
    t  = dt.strftime("%H:%M") if hasattr(dt,"strftime") else str(dt)[:16]
    return {"t":t,"o":round(c["open"],2),"h":round(c["high"],2),
            "l":round(c["low"],2),"c":round(c["close"],2),"v":c.get("volume",0)}


def intraday_stats(candles):
    if not candles:
        return {}
    highs = [c["h"] for c in candles]
    lows  = [c["l"] for c in candles if c["l"]>0]
    vols  = [c["v"] for c in candles]
    cls   = [c["c"] for c in candles]
    pv    = sum(((c["h"]+c["l"]+c["c"])/3)*c["v"] for c in candles if c["v"]>0)
    tv    = sum(c["v"] for c in candles if c["v"]>0)
    vwap  = round(pv/tv,2) if tv>0 else 0
    or_h  = max(c["h"] for c in candles[:2]) if len(candles)>=2 else candles[0]["h"]
    or_l  = min(c["l"] for c in candles[:2]) if len(candles)>=2 else candles[0]["l"]
    avg_v = sum(vols)/len(vols) if vols else 1
    surge = round(sum(vols[-4:])/(avg_v*4),2) if len(vols)>=4 else 0
    return {
        "day_open":           candles[0]["o"],
        "day_high":           max(highs),
        "day_low":            min(lows) if lows else 0,
        "day_close":          cls[-1],
        "day_change_pct":     round(((cls[-1]-candles[0]["o"])/candles[0]["o"])*100,2) if candles[0]["o"] else 0,
        "opening_range_high": or_h,
        "opening_range_low":  or_l,
        "vwap":               vwap,
        "vol_surge_last_hr":  surge,
        "day_range_pct":      round((max(highs)-min(lows))/cls[-1]*100,2) if cls[-1] and lows else 0,
        "total_volume":       sum(vols),
        "close_vs_vwap":      "above" if cls[-1]>vwap else "below",
        "close_vs_or_high":   "above" if cls[-1]>or_h else "below",
    }


def main():
    log.info("=== Intraday Fetch Start ===")
    kite     = get_kite()
    today    = datetime.today()
    date_str = today.strftime("%Y-%m-%d")
    out      = Path(f"data/intraday/{date_str}.json")

    # INCREMENTAL: skip if today's file already complete
    if out.exists():
        try:
            existing = json.loads(out.read_text())
            ok = sum(1 for v in existing.get("symbols",{}).values() if v.get("data_grade")=="A")
            if ok >= 200:
                log.info(f"Today's intraday already complete ({ok} symbols) — skipping")
                return
            log.info(f"Partial intraday file ({ok} symbols) — re-fetching")
        except Exception:
            pass

    mkt_s = today.replace(hour=9,  minute=15, second=0, microsecond=0)
    mkt_e = today.replace(hour=15, minute=30, second=0, microsecond=0)

    map_path = Path("data/master/instrument_map.json")
    if not map_path.exists():
        log.error("Instrument map missing — run fetch_eod.py first")
        sys.exit(1)
    token_map = json.loads(map_path.read_text())["tokens"]

    output = {
        "data_type":    "INTRADAY_CANDLES",
        "description":  "Full day intraday candles for FnO universe — 15min/5min/1min",
        "universe":     "NSE FnO (211 symbols)",
        "fetch_date":   date_str,
        "fetch_time":   today.strftime("%H:%M:%S IST"),
        "source":       "Zerodha Kite Connect Historical API",
        "note":         "Keep last 2 days only — pruned automatically",
        "symbols":      {}
    }

    failed = []
    for i, sym in enumerate(FNO_SYMBOLS, 1):
        inst = token_map.get(sym)
        if not inst:
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

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, default=str))
    ok = sum(1 for v in output["symbols"].values() if v.get("data_grade")=="A")
    log.info(f"=== Intraday Done: {ok}/{len(FNO_SYMBOLS)} OK | {len(failed)} failed ===")

    # PRUNE: delete all but last 2 intraday files (they are 15 MB each!)
    prune_old_files(out.parent, KEEP_DAYS)


if __name__ == "__main__":
    main()
