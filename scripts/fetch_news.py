#!/usr/bin/env python3
"""
fetch_news.py — INCREMENTAL news and announcements fetcher
----------------------------------------------------------
Runs hourly during market hours AND at 6 PM daily.
Only fetches announcements NOT already in today's news file.
Tracks seen announcement IDs to avoid duplicates.

Logic:
  1. Load today's existing news file (if any)
  2. Load seen_ids log — set of announcement IDs already stored
  3. Fetch latest announcements from NSE API
  4. Add only NEW ones (not in seen_ids)
  5. Save updated file + seen_ids log

Result: Each hourly run adds only NEW announcements — zero duplication.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta, timezone

def get_ist_now():
    """Always returns current time as IST — GitHub runners use UTC."""
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).replace(tzinfo=None)

import json, time, logging, hashlib
from pathlib import Path


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

try:
    from nse import NSE
    NSE_LIB = True
except ImportError:
    log.warning("nse library not installed. Run: pip install nse httpx[http2]")
    NSE_LIB = False

NIFTY500_SET = {
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
}

SCORE_MAP = [
    (20, ["order win","order bagged","order received","contract awarded","lakh crore","billion dollar"]),
    (18, ["index inclusion","added to nifty","nifty addition","sensex addition"]),
    (17, ["acquisition completed","merger approved","takeover"]),
    (15, ["large order","major order","significant order","order worth","crore order",
          "acquisition","major contract","strategic agreement"]),
    (13, ["quarterly results","q1 results","q2 results","q3 results","q4 results",
          "annual results","record profit","highest ever","all time high profit"]),
    (12, ["buyback","buy-back","regulatory approval","sebi approval","rbi approval",
          "drug approval","fda approval","ema approval"]),
    (10, ["dividend","bonus share","stock split","rights issue","record date",
          "capex","expansion","new plant","capacity addition"]),
    (8,  ["board meeting","agm","egm","fundraise","qip","preferential allotment"]),
    (5,  ["promoter buying","insider buying","bulk deal","block deal","fii buying"]),
    (3,  ["results","financial results","board outcome"]),
    (0,  ["penalty","fine","sebi action","fraud","default","insolvency","scam",
          "investigation","ban","suspension"]),
]

def impact_score(text):
    t = text.lower()
    for score, kws in SCORE_MAP:
        if score == 0 and any(k in t for k in kws):
            return 0
    for score, kws in SCORE_MAP:
        if score > 0 and any(k in t for k in kws):
            return score
    return 5

def ann_id(ann: dict) -> str:
    """Generate stable unique ID for an announcement."""
    key = f"{ann.get('symbol','')}{ann.get('exchdisstime','')}{ann.get('desc','')[:50]}"
    return hashlib.md5(key.encode()).hexdigest()[:12]

def safe(v) -> str:
    return str(v)[:300] if v else ""

SEEN_LOG  = Path("data/news/seen_ids.json")
NEWS_FILE = Path("data/news/news.json")   # single rolling file

def load_seen_ids() -> set:
    try:
        if SEEN_LOG.exists():
            data = json.loads(SEEN_LOG.read_text())
            # Only keep IDs from last 7 days
            cutoff = (get_ist_now() - timedelta(days=7)).strftime("%Y-%m-%d")
            return {k for k, v in data.items() if v >= cutoff}
    except Exception:
        pass
    return set()

def save_seen_ids(seen: set, existing_log: dict):
    today = get_ist_now().strftime("%Y-%m-%d")
    for sid in seen:
        existing_log[sid] = today
    # Prune old entries
    cutoff = (get_ist_now() - timedelta(days=7)).strftime("%Y-%m-%d")
    pruned = {k: v for k, v in existing_log.items() if v >= cutoff}
    SEEN_LOG.parent.mkdir(parents=True, exist_ok=True)
    SEEN_LOG.write_text(json.dumps(pruned, indent=2))

def load_news_file() -> dict:
    try:
        if NEWS_FILE.exists():
            return json.loads(NEWS_FILE.read_text())
    except Exception:
        pass
    return {
        "data_type":   "NEWS_ANNOUNCEMENTS",
        "description": "NSE corporate announcements — incremental, deduped, rolling 7 days",
        "source":      "NSE India official API",
        "symbols":     {}
    }

def main():
    log.info("=== News Incremental Fetch Start ===")
    today     = get_ist_now().strftime("%Y-%m-%d")
    now_str   = get_ist_now().strftime("%H:%M")
    from_dt   = get_ist_now() - timedelta(days=1)   # last 24 hours only

    # Load existing state
    try:
        seen_raw = json.loads(SEEN_LOG.read_text()) if SEEN_LOG.exists() else {}
    except Exception:
        seen_raw = {}
    seen_ids = load_seen_ids()
    news_data = load_news_file()

    log.info(f"Already seen: {len(seen_ids)} announcement IDs")

    new_count = 0

    if not NSE_LIB:
        log.warning("nse library not available — skipping")
        return

    try:
        with NSE("/tmp/nse_news_cache", server=True) as nse:

            # 1. Announcements (last 24 hours)
            try:
                anns = nse.announcements(
                    segment="equities",
                    from_date=from_dt,
                    to_date=get_ist_now()
                )
                log.info(f"NSE returned {len(anns)} raw announcements")
                for a in anns:
                    sym = (a.get("symbol") or "").upper().strip()
                    if sym not in NIFTY500_SET:
                        continue
                    aid = ann_id({"symbol": sym,
                                  "exchdisstime": a.get("exchdisstime",""),
                                  "desc": a.get("desc","")})
                    if aid in seen_ids:
                        continue   # already stored
                    subject = safe(a.get("desc") or a.get("subject") or "")
                    entry = {
                        "id":       aid,
                        "datetime": safe(a.get("exchdisstime","")),
                        "subject":  subject,
                        "category": safe(a.get("anncategory","")),
                        "score":    impact_score(subject),
                        "has_pdf":  bool(a.get("attchmntFile")),
                        "fetched":  now_str,
                    }
                    if sym not in news_data["symbols"]:
                        news_data["symbols"][sym] = {"announcements": [], "actions": [], "board_meeting": {}}
                    news_data["symbols"][sym]["announcements"].append(entry)
                    seen_ids.add(aid)
                    new_count += 1
            except Exception as e:
                log.error(f"Announcements fetch error: {e}")

            # 2. Corporate actions (dividend/bonus/split)
            try:
                actions = nse.actions(segment="equities")
                for a in actions:
                    sym = (a.get("symbol") or "").upper().strip()
                    if sym not in NIFTY500_SET:
                        continue
                    aid = ann_id({"symbol": sym,
                                  "exchdisstime": str(a.get("exDate","")),
                                  "desc": a.get("subject","")})
                    if aid in seen_ids:
                        continue
                    subject = safe(a.get("subject") or a.get("purpose") or "")
                    entry = {
                        "id":       aid,
                        "ex_date":  safe(a.get("exDate") or a.get("recordDate") or ""),
                        "action":   subject,
                        "score":    impact_score(subject),
                        "fetched":  now_str,
                    }
                    if sym not in news_data["symbols"]:
                        news_data["symbols"][sym] = {"announcements": [], "actions": [], "board_meeting": {}}
                    news_data["symbols"][sym]["actions"].append(entry)
                    seen_ids.add(aid)
                    new_count += 1
            except Exception as e:
                log.error(f"Actions fetch error: {e}")

            # 3. Board meetings
            try:
                meetings = nse.boardMeetings(fno=False)
                for m in meetings:
                    sym = (m.get("symbol") or "").upper().strip()
                    if sym not in NIFTY500_SET:
                        continue
                    purpose = safe(m.get("purpose") or m.get("bm_desc") or "")
                    date_   = safe(m.get("bm_date") or m.get("meetingDate") or "")
                    aid     = ann_id({"symbol": sym, "exchdisstime": date_, "desc": purpose})
                    if aid in seen_ids:
                        continue
                    if sym not in news_data["symbols"]:
                        news_data["symbols"][sym] = {"announcements": [], "actions": [], "board_meeting": {}}
                    news_data["symbols"][sym]["board_meeting"] = {
                        "meeting_date": date_,
                        "purpose":      purpose,
                        "score":        impact_score(purpose),
                        "fetched":      now_str,
                    }
                    seen_ids.add(aid)
                    new_count += 1
            except Exception as e:
                log.error(f"Board meetings error: {e}")

    except Exception as e:
        log.error(f"NSE client error: {e}")

    # Prune old announcements (keep last 30 days per symbol)
    cutoff = (get_ist_now() - timedelta(days=30)).strftime("%Y-%m-%d")
    for sym, data in news_data["symbols"].items():
        anns = data.get("announcements", [])
        data["announcements"] = [
            a for a in anns
            if a.get("datetime","") >= cutoff or not a.get("datetime","")
        ][-50:]  # max 50 per symbol

    # Update summary scores per symbol
    for sym, data in news_data["symbols"].items():
        all_scores = (
            [a.get("score",0) for a in data.get("announcements",[])] +
            [a.get("score",0) for a in data.get("actions",[])] +
            ([data["board_meeting"].get("score",0)] if data.get("board_meeting") else [])
        )
        data["news_impact_score"]      = max(all_scores) if all_scores else 0
        data["has_major_announcement"] = data["news_impact_score"] >= 15
        data["exclude_negative"]       = data["news_impact_score"] == 0 and bool(data.get("announcements"))

    news_data["last_updated"]    = f"{today} {now_str}"
    news_data["total_symbols"]   = len(news_data["symbols"])
    news_data["high_impact"]     = sum(1 for v in news_data["symbols"].values() if v.get("news_impact_score",0) >= 15)
    news_data["new_this_run"]    = new_count
    news_data["total_seen_ids"]  = len(seen_ids)

    NEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    NEWS_FILE.write_text(json.dumps(news_data, indent=2, default=str))
    save_seen_ids(seen_ids, seen_raw)

    log.info(f"=== News Done: +{new_count} new | {len(news_data['symbols'])} symbols | {news_data['high_impact']} high-impact ===")


if __name__ == "__main__":
    main()
