import requests
import time
import logging
import os
from datetime import datetime
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv(dotenv_path=r"C:\Users\Parzi\OneDrive\Documents\newparzival\earnings-anamoly\.env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COMPANIES = [
    {"ticker": "GS",   "name": "Goldman Sachs",     "sector": "financials", "cik": "0000886982"},
    {"ticker": "JPM",  "name": "JPMorgan Chase",     "sector": "financials", "cik": "0000019617"},
    {"ticker": "MS",   "name": "Morgan Stanley",     "sector": "financials", "cik": "0000895421"},
    {"ticker": "BAC",  "name": "Bank of America",    "sector": "financials", "cik": "0000070858"},
    {"ticker": "C",    "name": "Citigroup",          "sector": "financials", "cik": "0000831001"},
    {"ticker": "AAPL", "name": "Apple",              "sector": "technology", "cik": "0000320193"},
    {"ticker": "MSFT", "name": "Microsoft",          "sector": "technology", "cik": "0000789019"},
    {"ticker": "GOOGL","name": "Alphabet",           "sector": "technology", "cik": "0001652044"},
    {"ticker": "META", "name": "Meta",               "sector": "technology", "cik": "0001326801"},
    {"ticker": "ORCL", "name": "Oracle",             "sector": "technology", "cik": "0001341439"},
    {"ticker": "XOM",  "name": "ExxonMobil",         "sector": "energy",     "cik": "0000034088"},
    {"ticker": "CVX",  "name": "Chevron",            "sector": "energy",     "cik": "0000093410"},
    {"ticker": "COP",  "name": "ConocoPhillips",     "sector": "energy",     "cik": "0001163165"},
    {"ticker": "SLB",  "name": "SLB",                "sector": "energy",     "cik": "0000087347"},
    {"ticker": "EOG",  "name": "EOG Resources",      "sector": "energy",     "cik": "0000821189"},
    {"ticker": "JNJ",  "name": "Johnson & Johnson",  "sector": "healthcare", "cik": "0000200406"},
    {"ticker": "UNH",  "name": "UnitedHealth",       "sector": "healthcare", "cik": "0000731766"},
    {"ticker": "PFE",  "name": "Pfizer",             "sector": "healthcare", "cik": "0000078003"},
    {"ticker": "ABBV", "name": "AbbVie",             "sector": "healthcare", "cik": "0001551152"},
    {"ticker": "MRK",  "name": "Merck",              "sector": "healthcare", "cik": "0000310158"},
]

HEADERS = {
    "User-Agent": "earnings-anomaly-research kidusefrem2@gmail.com",
    "Accept": "application/json"
}


def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"), connect_timeout=10)


def get_earnings_transcripts(cik: str, ticker: str) -> list[dict]:
    """Fetch recent 8-K filings from SEC EDGAR."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        accession_numbers = filings.get("accessionNumber", [])

        results = []
        for i, form in enumerate(forms):
            if form == "8-K" and i < len(dates):
                filing_date = dates[i]
                if filing_date < "2024-01-01":
                    continue
                accession = accession_numbers[i].replace("-", "")
                results.append({
                    "date": filing_date,
                    "accession": accession_numbers[i],
                    "accession_clean": accession,
                    "cik": cik
                })

        logger.info(f"{ticker}: found {len(results)} 8-K filings since 2024")
        return sorted(results, key=lambda x: x["date"], reverse=True)[:12]

    except Exception as e:
        logger.error(f"{ticker}: EDGAR fetch failed — {e}")
        return []


def get_transcript_from_filing(filing: dict, ticker: str) -> dict | None:
    """Check an 8-K filing for an earnings call transcript exhibit."""
    cik = filing["cik"]
    accession = filing["accession_clean"]
    accession_dashed = filing["accession"]

    filing_index_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{accession_dashed}-index.htm"

    try:
        resp = requests.get(
            filing_index_url,
            headers={**HEADERS, "Accept": "text/html"},
            timeout=10
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Collect all .htm exhibit links
        exhibit_links = []
        for row in soup.find_all("tr"):
            link = row.find("a", href=True)
            if not link:
                continue
            href = link["href"]
            if href.endswith((".htm", ".html")) and "index" not in href.lower():
                full_url = f"https://www.sec.gov{href}" if href.startswith("/") else href
                exhibit_links.append(full_url)

        # Check each exhibit for transcript signals
        for url in exhibit_links[:8]:
            try:
                r = requests.get(
                    url,
                    headers={**HEADERS, "Accept": "text/html"},
                    timeout=15
                )
                if r.status_code != 200:
                    continue

                soup2 = BeautifulSoup(r.text, "html.parser")
                text = soup2.get_text(separator="\n", strip=True)

                has_qa = any(phrase in text.lower() for phrase in [
                    "question-and-answer",
                    "open for questions",
                    "open the line for questions",
                    "open the call for questions",
                    "operator instructions",
                    "our first question",
                    "first question comes from",
                    "take our first question",
                ])
                has_length = len(text) > 5000
                has_speakers = text.count(":") > 20

                if has_qa and has_length and has_speakers:
                    try:
                        call_date = datetime.strptime(filing["date"], "%Y-%m-%d").date()
                    except Exception:
                        call_date = None

                    logger.info(f"{ticker}: found transcript at {url}")
                    return {
                        "title": f"{ticker} Earnings Call {filing['date']}",
                        "date": call_date,
                        "raw_text": text,
                        "source_url": url
                    }

            except Exception:
                continue

        return None

    except Exception as e:
        logger.debug(f"Failed filing {accession_dashed}: {e}")
        return None


def save_transcript(conn, company_id: int, transcript: dict):
    """Save transcript to database, skip if already exists."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM transcripts WHERE source_url = %s",
            (transcript["source_url"],)
        )
        if cur.fetchone():
            logger.info(f"Already exists: {transcript['source_url']}")
            return

        cur.execute("""
            INSERT INTO transcripts
                (company_id, call_date, raw_html, full_text, source_url, scraped_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (
            company_id,
            transcript["date"],
            "",
            transcript["raw_text"],
            transcript["source_url"]
        ))
        conn.commit()
        logger.info(f"Saved: {transcript['title']}")


def ensure_company(conn, company: dict) -> int:
    """Insert company if not exists, return its id."""
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
    # Reconnect per company to avoid Neon idle timeout
    for company in COMPANIES:
        logger.info(f"\n=== Scraping {company['ticker']} ===")
        try:
            conn = get_db_connection()
            company_id = ensure_company(conn, company)
            filings = get_earnings_transcripts(company["cik"], company["ticker"])

            saved = 0
            for filing in filings:
                transcript = get_transcript_from_filing(filing, company["ticker"])
                if transcript:
                    save_transcript(conn, company_id, transcript)
                    saved += 1
                time.sleep(1)

            logger.info(f"{company['ticker']}: saved {saved} transcripts")
            conn.close()

        except Exception as e:
            logger.error(f"{company['ticker']}: failed — {e}")

        time.sleep(2)

    logger.info("\nScraping complete.")


if __name__ == "__main__":
    run_scraper()