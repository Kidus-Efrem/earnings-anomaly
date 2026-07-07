import requests
import time
import logging
from bs4 import BeautifulSoup
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import re
import os
from dotenv import load_dotenv

# load_dotenv()
load_dotenv()
print("DATABASE_URL:", os.getenv("DATABASE_URL"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COMPANIES = [
    # Banks
    {"ticker": "GS",   "name": "Goldman Sachs",       "sector": "financials"},
    {"ticker": "JPM",  "name": "JPMorgan Chase",       "sector": "financials"},
    {"ticker": "MS",   "name": "Morgan Stanley",       "sector": "financials"},
    {"ticker": "BAC",  "name": "Bank of America",      "sector": "financials"},
    {"ticker": "C",    "name": "Citigroup",            "sector": "financials"},
    # Tech
    {"ticker": "AAPL", "name": "Apple",                "sector": "technology"},
    {"ticker": "MSFT", "name": "Microsoft",            "sector": "technology"},
    {"ticker": "GOOGL","name": "Alphabet",             "sector": "technology"},
    {"ticker": "META", "name": "Meta",                 "sector": "technology"},
    {"ticker": "ORCL", "name": "Oracle",               "sector": "technology"},
    # Energy
    {"ticker": "XOM",  "name": "ExxonMobil",           "sector": "energy"},
    {"ticker": "CVX",  "name": "Chevron",              "sector": "energy"},
    {"ticker": "COP",  "name": "ConocoPhillips",       "sector": "energy"},
    {"ticker": "SLB",  "name": "SLB",                  "sector": "energy"},
    {"ticker": "EOG",  "name": "EOG Resources",        "sector": "energy"},
    # Healthcare
    {"ticker": "JNJ",  "name": "Johnson & Johnson",    "sector": "healthcare"},
    {"ticker": "UNH",  "name": "UnitedHealth",         "sector": "healthcare"},
    {"ticker": "PFE",  "name": "Pfizer",               "sector": "healthcare"},
    {"ticker": "ABBV", "name": "AbbVie",               "sector": "healthcare"},
    {"ticker": "MRK",  "name": "Merck",                "sector": "healthcare"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (research project)"
}


def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


def search_transcripts(ticker: str) -> list[dict]:
    """
    Search Motley Fool using their search page filtered by ticker.
    """
    # Use the direct URL pattern we know works from the GS example
    # https://www.fool.com/earnings/call-transcripts/2026/04/13/goldman-sachs-gs-q1-2026-earnings-transcript/
    # Pattern: /earnings/call-transcripts/YYYY/MM/DD/{company}-{ticker}-{quarter}-earnings-transcript/

    search_url = f"https://www.fool.com/search/#q={ticker}%20earnings%20call%20transcript&type=13"

    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        for a in soup.select("a[href*='earnings/call-transcripts']"):
            href = a["href"]
            # Only include links that contain the ticker in the URL
            if f"-{ticker.lower()}-" not in href.lower():
                continue
            full_url = "https://www.fool.com" + href if href.startswith("/") else href
            if full_url not in [r["url"] for r in results]:
                results.append({"url": full_url, "title": a.get_text(strip=True)})

        logger.info(f"{ticker}: found {len(results)} transcript links")
        return results[:12]

    except Exception as e:
        logger.error(f"{ticker}: search failed — {e}")
        return []


def scrape_transcript(url: str) -> dict | None:
    """
    Scrape a single Motley Fool transcript page.
    Returns {title, date, raw_text, source_url} or None on failure.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Title
        title_tag = soup.select_one("h1")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Date — Motley Fool puts it under a "## Date" heading
        call_date = None
        for h2 in soup.find_all("h2"):
            if h2.get_text(strip=True).lower() == "date":
                next_p = h2.find_next_sibling()
                if next_p:
                    date_text = next_p.get_text(strip=True)
                    match = re.search(r'(\w+ \d+, \d{4})', date_text)
                    if match:
                        try:
                            call_date = datetime.strptime(match.group(1), "%B %d, %Y").date()
                        except Exception:
                            pass
                break

        # Find transcript body — starts after "Full Conference Call Transcript" heading
        transcript_start = None
        for h2 in soup.find_all("h2"):
            if "full conference call transcript" in h2.get_text(strip=True).lower():
                transcript_start = h2
                break

        if not transcript_start:
            logger.warning(f"No transcript section found at {url}")
            return None

        # Collect all text after that heading until "Read Next"
        paragraphs = []
        for sibling in transcript_start.find_next_siblings():
            text = sibling.get_text(separator="\n", strip=True)
            if "read next" in text.lower():
                break
            if len(text) > 20:
                paragraphs.append(text)

        raw_text = "\n\n".join(paragraphs)

        if len(raw_text) < 500:
            logger.warning(f"Transcript too short ({len(raw_text)} chars), skipping: {url}")
            return None

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
        cur.execute(
            "SELECT id FROM companies WHERE ticker = %s",
            (company["ticker"],)
        )
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
    conn = get_db_connection()
    logger.info("Connected to database.")

    for company in COMPANIES:
        logger.info(f"\n=== Scraping {company['ticker']} ===")

        company_id = ensure_company(conn, company)
        transcript_links = search_transcripts(company["ticker"])

        for link in transcript_links:
            transcript = scrape_transcript(link["url"])
            if transcript:
                save_transcript(conn, company_id, transcript)
            time.sleep(2)

        time.sleep(5)

    conn.close()
    logger.info("\nScraping complete.")


if __name__ == "__main__":
    run_scraper()