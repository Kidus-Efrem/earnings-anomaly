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
import feedparser
import random

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


def search_transcripts(ticker: str) -> list[dict]:
    """
    Fetch recent transcripts via Motley Fool's public RSS feed
    and filter for the requested ticker symbol.
    """
    logger.info(f"Fetching transcripts for {ticker} from RSS feed...")
    rss_url = "https://www.fool.com/legal/shopping/rss/earning-transcripts"

    try:
        # feedparser handles headers and extraction gracefully
        feed = feedparser.parse(rss_url)

        results = []
        for entry in feed.entries:
            title = entry.get("title", "")
            url = entry.get("link", "")

            # Match pattern like "Goldman Sachs (GS) Q2 2026 Earnings Call Transcript"
            if f"({ticker})" in title and "/earnings/call-transcripts/" in url:
                results.append({
                    "url": url,
                    "title": title
                })

        logger.info(f"Found {len(results)} RSS matching transcripts for {ticker}")
        return results

    except Exception as e:
        logger.error(f"RSS fetch failed for {ticker}: {e}")
        return []


def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


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
            logger.info(f"Processing: {link['url']}")
            transcript = scrape_transcript(link["url"])
            if transcript:
                save_transcript(conn, company_id, transcript)

            # Random delay between 3 to 7 seconds between page scrapes to evade rate limits
            jitter = random.uniform(3.0, 7.0)
            time.sleep(jitter)

        time.sleep(5)

    conn.close()
    logger.info("\nScraping complete.")



if __name__ == "__main__":
    run_scraper()

