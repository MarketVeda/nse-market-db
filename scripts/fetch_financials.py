#!/usr/bin/env python3
"""
fetch_financials.py
-------------------
INCREMENTAL scraper for screener.in financial data.

Strategy:
  - Maintains a cache file: data/financials/fetch_log.json
  - Tracks last_fetched date per symbol
  - Skips symbols fetched today
  - Only fetches symbols not yet fetched today
  - Full refresh happens naturally over multiple daily runs

Schedule: Daily at 4:30 PM IST (after market close)
Per run: fetches remaining symbols not yet done today
Time per symbol: 2 sec sleep → ~500 symbols = ~17 min first run, ~0 min subsequent runs same day
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import json, time, re, logging, requests
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise SystemExit("Run: pip install beautifulsoup4 lxml")

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

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer":         "https://www.screener.in/",
}

LOG_FILE  = Path("data/financials/fetch_log.json")
DATA_FILE = Path("data/financials/financials.json")  # single master file


def load_fetch_log() -> dict:
    """Load log of when each symbol was last fetched."""
    try:
        if LOG_FILE.exists():
            return json.loads(LOG_FILE.read_text())
    except Exception:
        pass
    return {}


def save_fetch_log(log_data: dict):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(json.dumps(log_data, indent=2))


def load_master_data() -> dict:
    """Load existing master financials file."""
    try:
        if DATA_FILE.exists():
            return json.loads(DATA_FILE.read_text())
    except Exception:
        pass
    return {
        "data_type":   "FUNDAMENTALS_SCREENER",
        "description": "Complete financial data from screener.in — P&L, BS, CF, Ratios, Shareholding (12yr)",
        "source":      "screener.in (consolidated, 12 years history)",
        "symbols":     {}
    }


def clean_num(text):
    if not text:
        return None
    t = text.strip().replace(",","").replace("%","").replace("Cr.","").strip()
    if t in ("-","","—","N/A","NA","#"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def parse_table(soup, section_id):
    section = soup.find("section", {"id": section_id})
    if not section:
        return {}
    table = section.find("table")
    if not table:
        return {}
    headers = []
    thead = table.find("thead")
    if thead:
        for th in thead.find_all("th"):
            headers.append(th.get_text(strip=True))
    rows = {}
    tbody = table.find("tbody")
    if not tbody:
        return {"headers": headers, "rows": rows}
    for tr in tbody.find_all("tr"):
        cells = tr.find_all(["td","th"])
        if not cells:
            continue
        row_name = cells[0].get_text(strip=True).rstrip("+").strip()
        if not row_name:
            continue
        values = {}
        for i, cell in enumerate(cells[1:], 1):
            if i-1 < len(headers)-1:
                period = headers[i] if i < len(headers) else f"col_{i}"
                values[period] = clean_num(cell.get_text(strip=True))
        rows[row_name] = values
    return {"headers": headers[1:], "rows": rows}


def parse_shareholding(soup):
    section = soup.find("section", {"id": "shareholding"})
    if not section:
        return {}
    table = section.find("table")
    if not table:
        return {}
    headers = []
    thead = table.find("thead")
    if thead:
        for th in thead.find_all("th"):
            headers.append(th.get_text(strip=True))
    rows = {}
    tbody = table.find("tbody")
    if tbody:
        for tr in tbody.find_all("tr"):
            cells = tr.find_all(["td","th"])
            if not cells:
                continue
            row_name = cells[0].get_text(strip=True)
            values = {}
            for i, cell in enumerate(cells[1:], 1):
                if i-1 < len(headers)-1:
                    period = headers[i] if i < len(headers) else f"col_{i}"
                    values[period] = clean_num(cell.get_text(strip=True))
            rows[row_name] = values
    return {"headers": headers[1:], "rows": rows}


def parse_key_metrics(soup):
    metrics = {}
    for li in soup.select("#top li, .company-ratios li"):
        spans = li.find_all("span")
        if len(spans) >= 2:
            key = spans[0].get_text(strip=True).rstrip(":")
            val = spans[-1].get_text(strip=True)
            if key and val:
                metrics[key] = clean_num(val) if clean_num(val) is not None else val
    return metrics


def fetch_screener(sym, session):
    for view in ["consolidated", ""]:
        url = f"https://www.screener.in/company/{sym}/{view}/"
        try:
            resp = session.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 404:
                continue
            if resp.status_code == 200:
                break
        except Exception as e:
            return {"error": str(e)[:100], "data_grade": "C"}
    else:
        return {"error": "not_found", "data_grade": "C"}

    soup = BeautifulSoup(resp.text, "lxml")
    if not soup.find("section", {"id": "profit-loss"}):
        return {"error": "invalid_page", "data_grade": "C"}

    result = {
        "url":              url,
        "data_grade":       "A",
        "last_fetched":     datetime.today().strftime("%Y-%m-%d"),
        "view":             "consolidated" if "consolidated" in url else "standalone",
        "key_metrics":      parse_key_metrics(soup),
        "quarterly_results":parse_table(soup, "quarters"),
        "profit_loss":      parse_table(soup, "profit-loss"),
        "balance_sheet":    parse_table(soup, "balance-sheet"),
        "cash_flow":        parse_table(soup, "cash-flow"),
        "ratios":           parse_table(soup, "ratios"),
        "shareholding":     parse_shareholding(soup),
    }

    # Derived Minervini flags
    try:
        pl     = result["profit_loss"].get("rows", {})
        bs     = result["balance_sheet"].get("rows", {})
        cf     = result["cash_flow"].get("rows", {})
        ra     = result["ratios"].get("rows", {})

        sales  = list(pl.get("Sales", {}).values())
        np_    = list(pl.get("Net Profit", {}).values())
        roce   = list(ra.get("ROCE %", {}).values())
        borr   = list(bs.get("Borrowings", {}).values())
        res_   = list(bs.get("Reserves", {}).values())
        fcf    = list(cf.get("Free Cash Flow", {}).values())

        rev_g  = round((sales[-1]-sales[-2])/abs(sales[-2])*100,2) if len(sales)>=2 and sales[-2] else None
        np_g   = round((np_[-1]-np_[-2])/abs(np_[-2])*100,2)      if len(np_)>=2  and np_[-2]   else None
        roce_l = roce[-1] if roce else None
        de     = round(borr[-1]/res_[-1],2) if borr and res_ and res_[-1] else None
        fcf_p  = (fcf[-1]>0) if fcf and fcf[-1] is not None else None

        result["minervini_flags"] = {
            "revenue_growth_pct": rev_g,
            "profit_growth_pct":  np_g,
            "roce_pct":           roce_l,
            "de_ratio":           de,
            "fcf_positive":       fcf_p,
            "strong_revenue":     rev_g is not None and rev_g > 15,
            "strong_profit":      np_g  is not None and np_g  > 25,
            "high_roce":          roce_l is not None and roce_l > 15,
            "low_debt":           de is not None and de < 1.0,
        }

        s = 0
        if np_g  and np_g  > 50: s += 5
        elif np_g  and np_g  > 25: s += 3
        elif np_g  and np_g  > 0:  s += 1
        if rev_g and rev_g > 25: s += 3
        elif rev_g and rev_g > 15: s += 2
        elif rev_g and rev_g > 0:  s += 1
        if roce_l and roce_l > 20: s += 2
        elif roce_l and roce_l > 15: s += 1
        result["earnings_score_10"] = s

    except Exception as e:
        result["minervini_flags"] = {}
        result["earnings_score_10"] = 0

    return result


def main():
    log.info("=== Financials Incremental Fetch Start ===")
    today     = datetime.today().strftime("%Y-%m-%d")
    fetch_log = load_fetch_log()
    master    = load_master_data()

    # Determine which symbols need fetching today
    pending = [s for s in NIFTY500 if fetch_log.get(s) != today]
    done    = len(NIFTY500) - len(pending)
    log.info(f"Already fetched today: {done} | Pending: {len(pending)}")

    if not pending:
        log.info("All symbols already fetched today — nothing to do")
        return

    session = requests.Session()
    try:
        session.get("https://www.screener.in/", headers=HEADERS, timeout=10)
        time.sleep(1)
    except Exception:
        pass

    fetched = 0
    failed  = []
    for i, sym in enumerate(pending, 1):
        log.info(f"[{i:3d}/{len(pending)}] {sym}")
        result = fetch_screener(sym, session)
        master["symbols"][sym] = result
        if result.get("data_grade") == "A":
            fetch_log[sym] = today
            fetched += 1
        else:
            failed.append(sym)
        time.sleep(2.0)
        if i % 50 == 0:
            # Save progress every 50 symbols so partial runs aren't lost
            master["last_updated"] = today
            DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            DATA_FILE.write_text(json.dumps(master, indent=2, default=str))
            save_fetch_log(fetch_log)
            log.info(f"  Progress saved at {i} symbols")

    master["last_updated"] = today
    master["fetch_summary"] = {
        "date":           today,
        "fetched_today":  fetched,
        "total_complete": sum(1 for s in NIFTY500 if fetch_log.get(s) == today),
        "failed":         failed[:20],
    }

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(master, indent=2, default=str))
    save_fetch_log(fetch_log)

    log.info(f"=== Done: fetched {fetched}/{len(pending)} new symbols | Total today: {sum(1 for s in NIFTY500 if fetch_log.get(s)==today)}/500 ===")
    if failed:
        log.warning(f"Failed: {failed}")


if __name__ == "__main__":
    main()
