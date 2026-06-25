#!/usr/bin/env python3
"""
fetch_intraday_live.py — Hourly live snapshot during market hours
-----------------------------------------------------------------
INCREMENTAL: Overwrites latest.json every run (no duplication).
PRUNING:     Keeps only today's timestamped snapshots + latest.json.
             Deletes yesterday's snapshot folder on each new day.
Output:
  data/live/latest.json              ← Claude reads this (always current)
  data/live/YYYY-MM-DD/HH-MM.json   ← today's hourly archive only
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import json, time, logging, shutil
from datetime import datetime
from pathlib import Path
from kite_auth import get_kite

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

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


def get_ist_now():
    """Always return current time in IST regardless of server timezone."""
    from datetime import timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(IST).replace(tzinfo=None)   # naive datetime in IST


def is_market_open(now):
    if now.weekday() >= 5:
        return False
    return now.replace(hour=9,minute=15,second=0,microsecond=0) <= now <= now.replace(hour=15,minute=30,second=0,microsecond=0)


def prune_old_live_folders(live_dir: Path, keep_today_only: bool = True):
    """Delete all day folders except today's. Always keep latest.json."""
    today_str = datetime.today().strftime("%Y-%m-%d")
    for d in live_dir.iterdir():
        if d.is_dir() and d.name != today_str:
            shutil.rmtree(d)
            log.info(f"Pruned live folder: {d.name}")


def fetch_all_quotes(kite, token_map):
    all_keys = [f"NSE:{s}-EQ" for s in NIFTY500 if token_map.get(s)]
    results  = {}
    for start in range(0, len(all_keys), 500):
        batch = all_keys[start:start+500]
        try:
            quotes = kite.quote(batch)
            for key, q in quotes.items():
                sym  = key.replace("NSE:","").replace("-EQ","")
                ohlc = q.get("ohlc",{})
                prev = ohlc.get("close",0)
                ltp  = q.get("last_price",0)
                results[sym] = {
                    "ltp":        ltp,
                    "open":       ohlc.get("open",0),
                    "high":       ohlc.get("high",0),
                    "low":        ohlc.get("low",0),
                    "prev_close": prev,
                    "change":     round(ltp-prev,2),
                    "change_pct": round(((ltp-prev)/prev)*100,2) if prev else 0,
                    "volume":     q.get("volume",0),
                    "avg_price":  q.get("average_price",0),
                    "oi":         q.get("oi",0),
                    "buy_qty":    q.get("buy_quantity",0),
                    "sell_qty":   q.get("sell_quantity",0),
                }
            time.sleep(0.3)
        except Exception as e:
            log.error(f"Quotes batch failed: {e}")
            time.sleep(2)
    log.info(f"Quotes: {len(results)}/{len(NIFTY500)} symbols")
    return results


def fetch_fno_candles(kite, token_map, mkt_start, now):
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
                cdicts.append({"t":t,"o":round(c["open"],2),"h":round(c["high"],2),
                               "l":round(c["low"],2),"c":round(c["close"],2),"v":c.get("volume",0)})
            candles_data[sym] = cdicts
            time.sleep(0.34)
        except Exception as e:
            log.warning(f"{sym}: {e}")
            candles_data[sym] = []
    ok = sum(1 for v in candles_data.values() if v)
    log.info(f"Candles: {ok}/{len(FNO_SYMBOLS)} FnO symbols")
    return candles_data


def main():
    log.info("=== Live Snapshot Start ===")
    now      = get_ist_now()   # IST time always — GitHub runners are UTC
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    if not is_market_open(now):
        log.info(f"Market closed at {time_str} IST — skipping")
        sys.exit(0)

    log.info(f"Market open — snapshot at {time_str} IST")
    kite      = get_kite()
    mkt_start = now.replace(hour=9,minute=15,second=0,microsecond=0)

    map_path = Path("data/master/instrument_map.json")
    if not map_path.exists():
        log.error("Instrument map missing — run EOD pipeline first")
        sys.exit(1)
    token_map = json.loads(map_path.read_text())["tokens"]

    quotes  = fetch_all_quotes(kite, token_map)
    candles = fetch_fno_candles(kite, token_map, mkt_start, now)

    output = {
        "data_type":       "LIVE_INTRADAY_NIFTY500",
        "description":     "Hourly live snapshot — 500 NIFTY500 quotes + 211 FnO candles",
        "snapshot_date":   date_str,
        "snapshot_time":   time_str,
        "source":          "Zerodha Kite Connect",
        "quotes_count":    len(quotes),
        "candles_count":   len(candles),
        "note":            "latest.json always current. Day folder pruned to today only.",
        "quotes":          quotes,
        "candles_15min":   candles,
    }

    live_dir = Path("data/live")

    # Save timestamped snapshot for today only
    snap_dir  = live_dir / date_str
    snap_dir.mkdir(parents=True, exist_ok=True)
    (snap_dir / f"{time_str.replace(':','-')}.json").write_text(
        json.dumps(output, indent=2, default=str))

    # Always overwrite latest.json
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / "latest.json").write_text(json.dumps(output, indent=2, default=str))

    # PRUNE: delete all day folders except today
    prune_old_live_folders(live_dir)

    log.info(f"=== Live Done: {time_str} | quotes={len(quotes)} | candles={len(candles)} ===")


if __name__ == "__main__":
    main()
