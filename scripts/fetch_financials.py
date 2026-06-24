#!/usr/bin/env python3
"""
fetch_financials.py
-------------------
Scrapes COMPLETE financial data from screener.in for all NIFTY 500 symbols.
Source: screener.in (free, no API key, no login needed for public data)
Schedule: Weekly on Sunday at 8 AM IST

DATA COLLECTED PER SYMBOL (12 years where available):
  1. Key Metrics      : Market Cap, P/E, Book Value, ROCE, ROE, Div Yield, Face Value
  2. Quarterly P&L    : Last 12 quarters - Sales, Expenses, OP, OPM%, Interest, Dep, PBT, Tax, NP, EPS
  3. Annual P&L       : 12 years - Sales, Expenses, OP, OPM%, Other Inc, Interest, Dep, PBT, Tax, NP, EPS, Div Payout
  4. CAGR             : Sales 10/5/3yr, Profit 10/5/3yr, Stock Price 10/5/3/1yr, ROE 10/5/3yr
  5. Balance Sheet    : 12 years - Equity, Reserves, Borrowings, Liabilities, Fixed Assets, CWIP, Investments, Assets
  6. Cash Flow        : 12 years - CFO, CFI, CFF, Net CF, Free CF, CFO/OP%
  7. Ratios           : 12 years - Debtor Days, Inventory Days, Payable Days, CCC, Working Capital Days, ROCE%
  8. Shareholding     : Quarterly - Promoter%, FII%, DII%, Public%

Saves to: data/financials/YYYY-MM-DD.json
Size: ~15-25 MB for 500 symbols (rich data)
Time: ~20-25 min (2 sec sleep per symbol, polite scraping)
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
    raise SystemExit("BeautifulSoup not installed. Run: pip install beautifulsoup4 lxml")

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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.screener.in/",
}


def clean_num(text: str):
    """Convert screener.in text value to float. Returns None if not parseable."""
    if not text:
        return None
    t = text.strip().replace(",", "").replace("%", "").replace("Cr.", "").strip()
    if t in ("-", "", "—", "N/A", "NA", "#"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def parse_table(soup, section_id: str) -> dict:
    """
    Parse a screener.in financial table by section ID.
    Returns: {"headers": [...], "rows": {"RowName": {period: value, ...}}}
    """
    section = soup.find("section", {"id": section_id})
    if not section:
        return {}

    table = section.find("table")
    if not table:
        return {}

    # Get column headers (periods like "Mar 2015", "Mar 2016", etc.)
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
        cells = tr.find_all(["td", "th"])
        if not cells:
            continue
        row_name = cells[0].get_text(strip=True)
        if not row_name:
            continue
        # Remove trailing '+' or other decorators from row names
        row_name = row_name.rstrip("+").strip()
        values = {}
        for i, cell in enumerate(cells[1:], 1):
            if i - 1 < len(headers) - 1:
                period = headers[i] if i < len(headers) else f"col_{i}"
                values[period] = clean_num(cell.get_text(strip=True))
        rows[row_name] = values

    return {"headers": headers[1:], "rows": rows}


def parse_cagr_blocks(soup) -> dict:
    """Parse the CAGR/Growth summary blocks below the P&L table."""
    result = {}
    section = soup.find("section", {"id": "profit-loss"})
    if not section:
        return result

    # Each growth block is a <div class="ranges"> or similar
    for ul in section.find_all("ul", class_=lambda c: c and "spans" in c):
        heading = ul.find_previous_sibling(["h3", "h4", "p"])
        block_name = heading.get_text(strip=True) if heading else "unknown"
        items = {}
        for li in ul.find_all("li"):
            spans = li.find_all("span")
            if len(spans) >= 2:
                period = spans[0].get_text(strip=True)
                value  = clean_num(spans[1].get_text(strip=True))
                items[period] = value
        if items:
            result[block_name] = items

    return result


def parse_key_metrics(soup) -> dict:
    """Parse the key metrics panel at the top of the page."""
    metrics = {}
    # Screener.in puts key metrics in <li> tags within #top section
    top = soup.find("section", {"id": "top"})
    if not top:
        # Fallback: look for the summary panel
        top = soup.find("div", class_=lambda c: c and "company-ratios" in str(c))

    if top:
        for li in top.find_all("li"):
            spans = li.find_all("span")
            if len(spans) >= 2:
                key = spans[0].get_text(strip=True).rstrip(":")
                val = spans[-1].get_text(strip=True)
                metrics[key] = clean_num(val) if clean_num(val) is not None else val

    # Also grab from structured data if present
    for li in soup.select("#top li, .company-info li, .ranges li"):
        spans = li.find_all("span")
        if len(spans) >= 2:
            key = spans[0].get_text(strip=True).rstrip(":")
            val = spans[-1].get_text(strip=True)
            if key and val:
                metrics[key] = clean_num(val) if clean_num(val) is not None else val

    return metrics


def parse_shareholding(soup) -> dict:
    """Parse shareholding pattern section."""
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
            cells = tr.find_all(["td", "th"])
            if not cells:
                continue
            row_name = cells[0].get_text(strip=True)
            values = {}
            for i, cell in enumerate(cells[1:], 1):
                if i - 1 < len(headers) - 1:
                    period = headers[i] if i < len(headers) else f"col_{i}"
                    values[period] = clean_num(cell.get_text(strip=True))
            rows[row_name] = values

    return {"headers": headers[1:], "rows": rows}


def parse_pe_median(soup) -> dict:
    """Try to extract PE and median PE from the chart/ratio section."""
    pe_data = {}
    # PE is in the key metrics panel
    for li in soup.select("li"):
        text = li.get_text(strip=True)
        if "Stock P/E" in text or "P/E" in text:
            nums = re.findall(r'[\d,]+\.?\d*', text)
            if nums:
                pe_data["pe_current"] = clean_num(nums[0])
    return pe_data


def fetch_screener(sym: str, session: requests.Session) -> dict:
    """Fetch and parse ALL financial data for one symbol from screener.in."""
    # Try consolidated first, fallback to standalone
    for view in ["consolidated", ""]:
        url = f"https://www.screener.in/company/{sym}/{view}/"
        try:
            resp = session.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 404:
                continue
            if resp.status_code == 200:
                break
        except Exception as e:
            log.warning(f"  {sym} request failed: {e}")
            return {"error": str(e)[:100], "data_grade": "C"}
    else:
        return {"error": "not_found_on_screener", "data_grade": "C"}

    soup = BeautifulSoup(resp.text, "lxml")

    # Check if we got a valid page
    if not soup.find("section", {"id": "profit-loss"}):
        return {"error": "invalid_page", "data_grade": "C"}

    result = {
        "url":          url,
        "data_grade":   "A",
        "view":         "consolidated" if "consolidated" in url else "standalone",
    }

    # 1. Key Metrics
    result["key_metrics"] = parse_key_metrics(soup)

    # 2. Quarterly Results
    result["quarterly_results"] = parse_table(soup, "quarters")

    # 3. Annual Profit & Loss
    result["profit_loss_annual"] = parse_table(soup, "profit-loss")

    # 4. CAGR Blocks
    result["growth_cagr"] = parse_cagr_blocks(soup)

    # 5. Balance Sheet
    result["balance_sheet"] = parse_table(soup, "balance-sheet")

    # 6. Cash Flow
    result["cash_flow"] = parse_table(soup, "cash-flow")

    # 7. Ratios (Debtor Days, ROCE, etc.)
    result["ratios_annual"] = parse_table(soup, "ratios")

    # 8. Shareholding
    result["shareholding"] = parse_shareholding(soup)

    # 9. PE current (from key metrics)
    result["pe_median"] = parse_pe_median(soup)

    # 10. Derived Minervini flags
    try:
        pl = result["profit_loss_annual"].get("rows", {})
        bs = result["balance_sheet"].get("rows", {})
        cf = result["cash_flow"].get("rows", {})
        ra = result["ratios_annual"].get("rows", {})
        qr = result["quarterly_results"].get("rows", {})

        # Get most recent annual values
        pl_headers = result["profit_loss_annual"].get("headers", [])
        latest_yr  = pl_headers[-1] if pl_headers else None

        sales_vals = list(pl.get("Sales", {}).values())
        np_vals    = list(pl.get("Net Profit", {}).values())
        roce_vals  = list(ra.get("ROCE %", {}).values())

        # Revenue growth (latest year vs prior year)
        rev_growth = None
        if len(sales_vals) >= 2 and sales_vals[-2] and sales_vals[-1]:
            rev_growth = round((sales_vals[-1] - sales_vals[-2]) / abs(sales_vals[-2]) * 100, 2)

        # Profit growth (latest year vs prior year)
        np_growth = None
        if len(np_vals) >= 2 and np_vals[-2] and np_vals[-1]:
            np_growth = round((np_vals[-1] - np_vals[-2]) / abs(np_vals[-2]) * 100, 2)

        # Latest ROCE
        roce_latest = roce_vals[-1] if roce_vals else None

        # Borrowings (D/E proxy)
        borrowings = list(bs.get("Borrowings", {}).values())
        reserves   = list(bs.get("Reserves", {}).values())
        de_ratio   = None
        if borrowings and reserves and reserves[-1]:
            de_ratio = round(borrowings[-1] / reserves[-1], 2) if reserves[-1] else None

        # Free cash flow positive?
        fcf_vals = list(cf.get("Free Cash Flow", {}).values())
        fcf_positive = (fcf_vals[-1] > 0) if fcf_vals and fcf_vals[-1] is not None else None

        # Quarterly EPS trend (last 4 quarters)
        q_eps = list(qr.get("EPS in Rs", {}).values())[-4:]

        result["minervini_flags"] = {
            "revenue_growth_pct":    rev_growth,
            "profit_growth_pct":     np_growth,
            "roce_latest_pct":       roce_latest,
            "de_ratio":              de_ratio,
            "fcf_positive":          fcf_positive,
            "strong_revenue":        rev_growth is not None and rev_growth > 15,
            "strong_profit":         np_growth  is not None and np_growth  > 25,
            "high_roce":             roce_latest is not None and roce_latest > 15,
            "low_debt":              de_ratio is not None and de_ratio < 1.0,
            "eps_last_4q":           q_eps,
        }

        # Earnings score 0-10 for 120-pt rubric
        score = 0
        if np_growth  and np_growth  > 50: score += 5
        elif np_growth  and np_growth  > 25: score += 3
        elif np_growth  and np_growth  > 0:  score += 1
        if rev_growth and rev_growth > 25: score += 3
        elif rev_growth and rev_growth > 15: score += 2
        elif rev_growth and rev_growth > 0:  score += 1
        if roce_latest and roce_latest > 20: score += 2
        elif roce_latest and roce_latest > 15: score += 1
        result["earnings_score_10"] = score

    except Exception as e:
        log.warning(f"  {sym} derived metrics failed: {e}")
        result["minervini_flags"] = {}
        result["earnings_score_10"] = 0

    return result


def main():
    log.info("=== Screener.in Financials Fetch Start ===")
    today    = datetime.today()
    date_str = today.strftime("%Y-%m-%d")

    session = requests.Session()
    # Warm up session with homepage to get cookies
    try:
        session.get("https://www.screener.in/", headers=HEADERS, timeout=10)
        log.info("Session warmed up")
        time.sleep(1)
    except Exception as e:
        log.warning(f"Warmup failed: {e}")

    output = {
        "data_type":     "FUNDAMENTALS_SCREENER",
        "description":   "Complete financial data from screener.in — P&L, BS, CF, Ratios, Shareholding (12yr history)",
        "universe":      "NIFTY500 (500 symbols)",
        "fetch_date":    date_str,
        "source":        "screener.in (consolidated view, 12 years history)",
        "update_note":   "Weekly Sunday — full refresh of all financial history",
        "data_sections": [
            "key_metrics (current PE, ROCE, ROE, Book Value, Market Cap etc.)",
            "quarterly_results (last 12 quarters — Sales, OP, NP, EPS)",
            "profit_loss_annual (12 years — full P&L)",
            "growth_cagr (Sales/Profit CAGR 3/5/10yr, Stock Price CAGR, ROE history)",
            "balance_sheet (12 years — Equity, Reserves, Borrowings, Assets)",
            "cash_flow (12 years — CFO, CFI, CFF, Free CF)",
            "ratios_annual (12 years — ROCE, Debtor Days, Inventory Days, CCC)",
            "shareholding (quarterly — Promoter, FII, DII, Public %)",
            "minervini_flags (computed — strong_revenue, strong_profit, high_roce, low_debt)",
            "earnings_score_10 (0-10 for 120-pt scoring rubric)",
        ],
        "symbols": {}
    }

    failed = []
    for i, sym in enumerate(NIFTY500, 1):
        log.info(f"[{i:3d}/{len(NIFTY500)}] {sym}")
        result = fetch_screener(sym, session)
        output["symbols"][sym] = result
        if result.get("data_grade") != "A":
            failed.append(sym)

        # Polite rate limiting — 2 seconds between requests
        # Total time: ~500 × 2s = ~17 min (well within Sunday budget)
        time.sleep(2.0)

        # Extra pause every 50 symbols to avoid rate limiting
        if i % 50 == 0:
            log.info(f"Pause after {i} symbols...")
            time.sleep(5)

    ok = sum(1 for v in output["symbols"].values() if v.get("data_grade") == "A")
    output["summary"] = {
        "total":          len(NIFTY500),
        "success":        ok,
        "failed":         len(failed),
        "failed_symbols": failed[:30],
    }

    out = Path(f"data/financials/{date_str}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, default=str))

    log.info(f"=== Financials Done: {out} | {ok}/{len(NIFTY500)} OK | {len(failed)} failed ===")
    if failed:
        log.warning(f"Failed: {failed[:20]}")


if __name__ == "__main__":
    main()
