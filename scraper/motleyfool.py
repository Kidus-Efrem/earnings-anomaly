import requests
import time
import logging
import os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv(dotenv_path=r"C:\Users\Parzi\OneDrive\Documents\newparzival\earnings-anamoly\.env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COMPANIES = [
    {"ticker": "GS",   "name": "Goldman Sachs",     "sector": "financials", "cik": "0000886982", "slug": "goldman-sachs"},
    {"ticker": "JPM",  "name": "JPMorgan Chase",     "sector": "financials", "cik": "0000019617", "slug": "jpmorgan"},
    {"ticker": "MS",   "name": "Morgan Stanley",     "sector": "financials", "cik": "0000895421", "slug": "morgan-stanley"},
    {"ticker": "BAC",  "name": "Bank of America",    "sector": "financials", "cik": "0000070858", "slug": "bank-of-america"},
    {"ticker": "C",    "name": "Citigroup",          "sector": "financials", "cik": "0000831001", "slug": "citigroup"},
    {"ticker": "AAPL", "name": "Apple",              "sector": "technology", "cik": "0000320193", "slug": "apple"},
    {"ticker": "MSFT", "name": "Microsoft",          "sector": "technology", "cik": "0000789019", "slug": "microsoft"},
    {"ticker": "GOOGL","name": "Alphabet",           "sector": "technology", "cik": "0001652044", "slug": "alphabet"},
    {"ticker": "META", "name": "Meta",               "sector": "technology", "cik": "0001326801", "slug": "meta-platforms"},
    {"ticker": "ORCL", "name": "Oracle",             "sector": "technology", "cik": "0001341439", "slug": "oracle"},
    {"ticker": "XOM",  "name": "ExxonMobil",         "sector": "energy",     "cik": "0000034088", "slug": "exxonmobil"},
    {"ticker": "CVX",  "name": "Chevron",            "sector": "energy",     "cik": "0000093410", "slug": "chevron"},
    {"ticker": "COP",  "name": "ConocoPhillips",     "sector": "energy",     "cik": "0001163165", "slug": "conocophillips"},
    {"ticker": "SLB",  "name": "SLB",                "sector": "energy",     "cik": "0000087347", "slug": "slb"},
    {"ticker": "EOG",  "name": "EOG Resources",      "sector": "energy",     "cik": "0000821189", "slug": "eog-resources"},
    {"ticker": "JNJ",  "name": "Johnson & Johnson",  "sector": "healthcare", "cik": "0000200406", "slug": "johnson-johnson"},
    {"ticker": "UNH",  "name": "UnitedHealth",       "sector": "healthcare", "cik": "0000731766", "slug": "unitedhealth-group"},
    {"ticker": "PFE",  "name": "Pfizer",             "sector": "healthcare", "cik": "0000078003", "slug": "pfizer"},
    {"ticker": "ABBV", "name": "AbbVie",             "sector": "healthcare", "cik": "0001551152", "slug": "abbvie"},
    {"ticker": "MRK",  "name": "Merck",              "sector": "healthcare", "cik": "0000310158", "slug": "merck"},
]

SEC_HEADERS = {
    "User-Agent": "earnings-anomaly-research kidusefrem2@gmail.com",
    "Accept": "application/json"
}

FOOL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

QUARTER_LABELS = {
    1: "q1", 2: "q1", 3: "q1",
    4: "q2", 5: "q2", 6: "q2",
    7: "q3", 8: "q3", 9: "q3",
    10: "q4", 11: "q4", 12: "q4",
}


def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"), connect_timeout=10)


def get_earnings_dates(cik: str, ticker: str) -> list[str]:
    """Get 8-K filing dates from SEC EDGAR — these are earnings announcement dates."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    try:
        resp = requests.get(url, headers=SEC_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])

        results = []
        for i, form in enumerate(forms):
            if form == "8-K" and i < len(dates):
                if dates[i] >= "2024-01-01":
                    results.append(dates[i])

        logger.info(f"{ticker}: found {len(results)} 8-K dates since 2024")
        return sorted(results, reverse=True)[:12]

    except Exception as e:
        logger.error(f"{ticker}: EDGAR fetch failed — {e}")
        return []


def date_to_quarter(date_str: str) -> str:
    """Convert a date string to quarter label like 'q1-2026'."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    quarter = QUARTER_LABELS[d.month]
    # Fiscal year adjustment: Q4 filings in Jan are for previous year
    year = d.year
    if d.month == 1 and quarter == "q4":
        year -= 1
    return f"{quarter}-{year}"


def find_fool_url(slug: str, ticker: str, date_str: str) -> str | None:
    """
    Try to find a Motley Fool transcript URL for a given company and date.
    Try ±3 days around the filing date with both URL suffix variants.
    """
    d = datetime.strptime(date_str, "%Y-%m-%d")
    quarter = date_to_quarter(date_str)
    ticker_lower = ticker.lower()

    suffixes = [
        "-earnings-transcript/",
        "-earnings-call-transcript/",
        "-earnings-call-transcrip/",
    ]

    for delta in range(-3, 4):
        test_date = d + timedelta(days=delta)
        date_path = test_date.strftime("%Y/%m/%d")
        for suffix in suffixes:
            url = f"https://www.fool.com/earnings/call-transcripts/{date_path}/{slug}-{ticker_lower}-{quarter}{suffix}"
            try:
                r = requests.get(url, headers=FOOL_HEADERS, timeout=8, stream=True)
                r.close()
                if r.status_code == 200:
                    return url
            except Exception:
                pass
            time.sleep(0.3)

    return None


def scrape_fool_transcript(url: str, ticker: str, date_str: str) -> dict | None:
    """Scrape a confirmed Motley Fool transcript URL."""
    try:
        resp = requests.get(url, headers=FOOL_HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        title_tag = soup.select_one("h1")
        title = title_tag.get_text(strip=True) if title_tag else f"{ticker} Earnings Call {date_str}"

        # Find transcript body
        transcript_start = None
        for h2 in soup.find_all("h2"):
            if "full conference call transcript" in h2.get_text(strip=True).lower():
                transcript_start = h2
                break

        if not transcript_start:
            logger.warning(f"No transcript section at {url}")
            return None

        paragraphs = []
        for sibling in transcript_start.find_next_siblings():
            text = sibling.get_text(separator="\n", strip=True)
            if "read next" in text.lower():
                break
            if len(text) > 20:
                paragraphs.append(text)

        raw_text = "\n\n".join(paragraphs)
        if len(raw_text) < 500:
            return None

        try:
            call_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            call_date = None

        return {
            "title": title,
            "date": call_date,
            "raw_text": raw_text,
            "source_url": url
        }

    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")
        return None


def save_transcript(conn, company_id: int, transcript: dict):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM transcripts WHERE source_url = %s", (transcript["source_url"],))
        if cur.fetchone():
            logger.info(f"Already exists: {transcript['source_url']}")
            return
        cur.execute("""
            INSERT INTO transcripts (company_id, call_date, raw_html, full_text, source_url, scraped_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (company_id, transcript["date"], "", transcript["raw_text"], transcript["source_url"]))
        conn.commit()
        logger.info(f"Saved: {transcript['title']}")


def ensure_company(conn, company: dict) -> int:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id FROM companies WHERE ticker = %s", (company["ticker"],))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("""
            INSERT INTO companies (ticker, name, sector)
            VALUES (%s, %s, %s) RETURNING id
        """, (company["ticker"], company["name"], company["sector"]))
        conn.commit()
        return cur.fetchone()["id"]


def run_scraper():
    for company in COMPANIES:
        logger.info(f"\n=== Scraping {company['ticker']} ===")
        try:
            conn = get_db_connection()
            company_id = ensure_company(conn, company)

            # Step 1: get real earnings dates from SEC
            dates = get_earnings_dates(company["cik"], company["ticker"])

            saved = 0
            for date_str in dates:
                # Step 2: find the Motley Fool URL using real date
                url = find_fool_url(company["slug"], company["ticker"], date_str)
                if not url:
                    logger.warning(f"{company['ticker']}: no Fool URL found near {date_str}")
                    continue

                logger.info(f"{company['ticker']}: found URL {url}")

                # Step 3: scrape it
                transcript = scrape_fool_transcript(url, company["ticker"], date_str)
                if transcript:
                    save_transcript(conn, company_id, transcript)
                    saved += 1

                time.sleep(2)

            logger.info(f"{company['ticker']}: saved {saved} transcripts")
            conn.close()

        except Exception as e:
            logger.error(f"{company['ticker']}: failed — {e}")

        time.sleep(3)

    logger.info("\nScraping complete.")


if __name__ == "__main__":
    run_scraper()