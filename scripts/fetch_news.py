#!/usr/bin/env python3
"""
fetch_news.py
-------------
Fetches corporate announcements and news for NIFTY 500 from official NSE sources.
Sources (both FREE, no login):
  1. NSE India API (nse library) — official exchange filings
     Covers: announcements, board meetings, corporate actions, bulk/block deals
  2. nsefin library — clean DataFrames for announcements, insider trading, upcoming results

Schedule: Daily weekdays at 6:00 PM IST
Lookback: Last 7 trading days
Saves to: data/news/YYYY-MM-DD.json
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import json, time, logging
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# NSE India API (BennyThadikaran)
try:
    from nse import NSE
    NSE_LIB = True
except ImportError:
    log.warning("nse library not installed. Run: pip install nse httpx[http2]")
    NSE_LIB = False

# nsefin (supplementary)
try:
    import nsefin
    NSEFIN_LIB = True
except ImportError:
    log.warning("nsefin not installed. Run: pip install nsefin")
    NSEFIN_LIB = False

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

# Impact scoring keywords per your methodology
# Factor #1: Corporate Announcements (highest priority)
SCORE_MAP = [
    # (score, keywords)
    (20, ["order win", "order bagged", "order received", "contract awarded", "lakh crore", "billion dollar"]),
    (18, ["index inclusion", "added to nifty", "nifty addition", "sensex addition"]),
    (17, ["acquisition completed", "merger approved", "takeover"]),
    (15, ["large order", "major order", "significant order", "order worth", "crore order",
          "acquisition", "major contract", "strategic agreement"]),
    (13, ["quarterly results", "q1 results", "q2 results", "q3 results", "q4 results",
          "annual results", "record profit", "highest ever", "all time high profit"]),
    (12, ["buyback", "buy-back", "regulatory approval", "sebi approval", "rbi approval",
          "drug approval", "clinical trial", "fda approval", "ema approval"]),
    (10, ["dividend", "bonus share", "stock split", "rights issue", "record date",
          "capex", "expansion", "new plant", "capacity addition"]),
    (8,  ["board meeting", "agm", "egm", "fundraise", "qip", "preferential allotment"]),
    (5,  ["promoter buying", "insider buying", "bulk deal", "block deal", "fii buying"]),
    (3,  ["results", "financial results", "board outcome"]),
    (0,  ["penalty", "fine", "sebi action", "fraud", "default", "insolvency", "scam",
          "investigation", "ban", "suspension", "downgrade", "loss reported"]),
]

def news_impact_score(text: str) -> int:
    """Score 0-20 based on keyword match in announcement text."""
    t = text.lower()
    # Check negative first — returns 0
    for score, kws in SCORE_MAP:
        if score == 0 and any(k in t for k in kws):
            return 0
    # Check positive from highest to lowest
    for score, kws in SCORE_MAP:
        if score > 0 and any(k in t for k in kws):
            return score
    return 5  # default for any announcement


def safe_str(v) -> str:
    return str(v)[:300] if v else ""


def fetch_nse_announcements(nse_client, from_dt, to_dt) -> dict:
    """Official NSE announcements — order wins, results, agreements, etc."""
    log.info("Fetching NSE corporate announcements...")
    by_symbol = {}
    try:
        anns = nse_client.announcements(segment="equities", from_date=from_dt, to_date=to_dt)
        log.info(f"Total announcements: {len(anns)}")
        for a in anns:
            sym = (a.get("symbol") or "").upper().strip()
            if sym not in NIFTY500_SET:
                continue
            subject = safe_str(a.get("desc") or a.get("subject") or "")
            score   = news_impact_score(subject)
            entry = {
                "datetime": safe_str(a.get("exchdisstime") or a.get("bm_date") or ""),
                "subject":  subject,
                "category": safe_str(a.get("anncategory") or ""),
                "score":    score,
                "has_pdf":  bool(a.get("attchmntFile")),
            }
            by_symbol.setdefault(sym, []).append(entry)
    except Exception as e:
        log.error(f"NSE announcements error: {e}")
    log.info(f"Announcements for {len(by_symbol)} NIFTY500 symbols")
    return by_symbol


def fetch_nse_board_meetings(nse_client) -> dict:
    """Board meetings — dividend/results signals."""
    log.info("Fetching board meetings...")
    by_symbol = {}
    try:
        meetings = nse_client.boardMeetings(fno=False)
        for m in meetings:
            sym     = (m.get("symbol") or "").upper().strip()
            if sym not in NIFTY500_SET:
                continue
            purpose = safe_str(m.get("purpose") or m.get("bm_desc") or "")
            date_   = safe_str(m.get("bm_date") or m.get("meetingDate") or "")
            by_symbol[sym] = {
                "meeting_date": date_,
                "purpose":      purpose,
                "score":        news_impact_score(purpose),
            }
    except Exception as e:
        log.error(f"Board meetings error: {e}")
    log.info(f"Board meetings for {len(by_symbol)} symbols")
    return by_symbol


def fetch_nse_actions(nse_client) -> dict:
    """Corporate actions — dividends, bonus, splits, rights."""
    log.info("Fetching corporate actions...")
    by_symbol = {}
    try:
        actions = nse_client.actions(segment="equities")
        for a in actions:
            sym    = (a.get("symbol") or "").upper().strip()
            if sym not in NIFTY500_SET:
                continue
            subject = safe_str(a.get("subject") or a.get("purpose") or "")
            ex_date = safe_str(a.get("exDate") or a.get("recordDate") or "")
            by_symbol.setdefault(sym, []).append({
                "ex_date": ex_date,
                "action":  subject,
                "score":   news_impact_score(subject),
            })
    except Exception as e:
        log.error(f"Corporate actions error: {e}")
    log.info(f"Corporate actions for {len(by_symbol)} symbols")
    return by_symbol


def fetch_nse_bulk_block_deals(nse_client, from_dt, to_dt) -> dict:
    """Bulk and block deals — institutional activity signals."""
    log.info("Fetching bulk/block deals...")
    by_symbol = {}
    try:
        for deal_type in ["bulk_deals", "block_deals"]:
            deals = nse_client.bulkDeals(
                option_type=deal_type, fromdate=from_dt, todate=to_dt
            )
            for d in deals:
                sym = (d.get("symbol") or "").upper().strip()
                if sym not in NIFTY500_SET:
                    continue
                by_symbol.setdefault(sym, {}).setdefault(deal_type, []).append({
                    "date":     safe_str(d.get("mTrdDt") or ""),
                    "client":   safe_str(d.get("clientName") or ""),
                    "qty":      d.get("tradedQnty"),
                    "price":    d.get("trdPrc"),
                    "buy_sell": safe_str(d.get("buySell") or ""),
                })
    except Exception as e:
        log.error(f"Bulk/block deals error: {e}")
    log.info(f"Bulk/block deals for {len(by_symbol)} symbols")
    return by_symbol


def fetch_upcoming_results(nse_client) -> dict:
    """Upcoming quarterly result dates."""
    log.info("Fetching upcoming results schedule...")
    by_symbol = {}
    try:
        results = nse_client.boardMeetings(index="equities")
        for r in results:
            sym  = (r.get("symbol") or "").upper().strip()
            date = safe_str(r.get("bm_date") or "")
            desc = safe_str(r.get("purpose") or r.get("bm_desc") or "")
            if sym in NIFTY500_SET and ("result" in desc.lower() or "financial" in desc.lower()):
                by_symbol[sym] = {"result_date": date, "description": desc}
    except Exception as e:
        log.error(f"Upcoming results error: {e}")
    return by_symbol


def build_symbol_summary(announcements, board_meetings, corp_actions, bulk_deals) -> dict:
    """Build per-symbol consolidated news summary with highest impact score."""
    all_syms = (set(announcements) | set(board_meetings) |
                set(corp_actions)  | set(bulk_deals))
    summary  = {}

    for sym in all_syms:
        ann_list   = announcements.get(sym, [])
        meeting    = board_meetings.get(sym, {})
        act_list   = corp_actions.get(sym, [])
        deals      = bulk_deals.get(sym, {})

        all_scores = (
            [a["score"] for a in ann_list] +
            ([meeting.get("score", 0)] if meeting else []) +
            [a["score"] for a in act_list]
        )
        max_score = max(all_scores) if all_scores else 0

        summary[sym] = {
            "news_impact_score":       max_score,
            "has_major_announcement":  max_score >= 15,
            "exclude_negative":        max_score == 0 and bool(ann_list),
            "announcements":           sorted(ann_list, key=lambda x: x.get("score", 0), reverse=True)[:5],
            "board_meeting":           meeting,
            "corporate_actions":       act_list[:3],
            "bulk_block_deals":        deals,
        }

    return summary


def main():
    log.info("=== News & Announcements Fetch Start ===")
    today    = datetime.today()
    date_str = today.strftime("%Y-%m-%d")
    from_dt  = today - timedelta(days=7)

    announcements  = {}
    board_meetings = {}
    corp_actions   = {}
    bulk_deals     = {}

    if NSE_LIB:
        try:
            with NSE("/tmp/nse_news_cache", server=True) as nse_client:
                announcements  = fetch_nse_announcements(nse_client, from_dt, today)
                board_meetings = fetch_nse_board_meetings(nse_client)
                corp_actions   = fetch_nse_actions(nse_client)
                bulk_deals     = fetch_nse_bulk_block_deals(nse_client, from_dt, today)
        except Exception as e:
            log.error(f"NSE client error: {e}")
    else:
        log.warning("nse library unavailable — no announcements fetched")

    symbol_summary = build_symbol_summary(
        announcements, board_meetings, corp_actions, bulk_deals
    )

    output = {
        "data_type":        "NEWS_ANNOUNCEMENTS",
        "description":      "Official NSE exchange filings + corporate actions + bulk/block deals",
        "fetch_date":       date_str,
        "fetch_time":       today.strftime("%H:%M:%S IST"),
        "lookback_days":    7,
        "sources":          ["NSE India official API (announcements, board meetings, actions, bulk/block deals)"],
        "impact_score_guide": {
            "20": "Major order win with value (lakh crore / billion dollar)",
            "18": "Index inclusion (Nifty/Sensex addition)",
            "17": "Acquisition / major merger",
            "15": "Large order / strategic acquisition",
            "13": "Record quarterly results / highest ever profit",
            "12": "Buyback / regulatory approval / drug approval",
            "10": "Dividend / bonus / split / capex / expansion",
             "8": "Board meeting / AGM / QIP fundraise",
             "5": "Promoter/FII bulk buying",
             "3": "Routine results / board outcome",
             "0": "Negative — penalty / fraud / default (exclude)",
        },
        "total_symbols":        len(symbol_summary),
        "high_impact_count":    sum(1 for v in symbol_summary.values() if v["news_impact_score"] >= 15),
        "negative_exclude":     sum(1 for v in symbol_summary.values() if v["exclude_negative"]),
        "symbols": symbol_summary,
    }

    out = Path(f"data/news/{date_str}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, default=str))

    high = output["high_impact_count"]
    log.info(f"=== News Done: {out} | {len(symbol_summary)} symbols | {high} high-impact ===")


if __name__ == "__main__":
    main()
