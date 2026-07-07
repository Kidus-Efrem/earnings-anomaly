import requests
import time
import logging
from bs4 import BeautifulSoup
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# The 20 companies you're targeting
COMPANIES = [
    # Banks
    {"ticker": "GS",  "name": "Goldman Sachs",  "sector": "financials"},
    {"ticker": "JPM", "name": "JPMorgan Chase", "sector": "financials"},
    {"ticker": "MS",  "name": "Morgan Stanley", "sector": "financials"},
    {"ticker": "BAC", "name": "Bank of America","sector": "financials"},
    {"ticker": "C",   "name": "Citigroup",      "sector": "financials"},
    # Tech
    {"ticker": "AAPL","name": "Apple",          "sector": "technology"},
    {"ticker": "MSFT","name": "Microsoft",      "sector": "technology"},
    {"ticker": "GOOGL","name":"Alphabet",        "sector": "technology"},
    {"ticker": "META","name": "Meta",            "sector": "technology"},
    {"ticker": "ORCL","name": "Oracle",          "sector": "technology"},
    # Energy
    {"ticker": "XOM", "name": "ExxonMobil",     "sector": "energy"},
    {"ticker": "CVX", "name": "Chevron",         "sector": "energy"},
    {"ticker": "COP", "name": "ConocoPhillips", "sector": "energy"},
    {"ticker": "SLB", "name": "SLB",            "sector": "energy"},
    {"ticker": "EOG", "name": "EOG Resources",  "sector": "energy"},
    # Healthcare
    {"ticker": "JNJ", "name": "Johnson & Johnson","sector": "healthcare"},
    {"ticker": "UNH", "name": "UnitedHealth",   "sector": "healthcare"},
    {"ticker": "PFE", "name": "Pfizer",         "sector": "healthcare"},
    {"ticker": "ABBV","name": "AbbVie",         "sector": "healthcare"},
    {"ticker": "MRK", "name": "Merck",          "sector": "healthcare"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (research project)"
}

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def search_transcripts(ticker: str) -> list[dict]:
    """
    Scrape Motley Fool's transcript index for a given ticker.
    """
    url = f"https://www.fool.com/quote/nasdaq/{ticker.lower()}/#quote-earnings-transcripts"

    # Try their direct transcript listing URL instead
    url = f"https://www.fool.com/earnings-call-transcripts/?ticker={ticker}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        for a in soup.select("a[href*='earnings-call-transcript']"):
            href = a["href"]
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
    Scrape a single transcript page.
    Returns {title, date, raw_text} or None on failure.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Title
        title_tag = soup.select_one("h1.article-heading, h1.headline")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Date
        date_tag = soup.select_one("time[datetime], span.publication-date")
        date_str = date_tag.get("datetime", "") if date_tag else ""
        try:
            call_date = datetime.fromisoformat(date_str[:10]).date()
        except Exception:
            call_date = None

        # Full transcript text
        # Motley Fool wraps the transcript body in a div with class "article-body"
        body = soup.select_one("div.article-body, div[class*='article-content']")
        if not body:
            logger.warning(f"No body found at {url}")
            return None

        raw_text = body.get_text(separator="\n", strip=True)

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
    """Save raw transcript to database."""
    with conn.cursor() as cur:
        # Check if already exists
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
            "",              # raw_html — we store text only for now
            transcript["raw_text"],
            transcript["source_url"]
        ))
        conn.commit()
        logger.info(f"Saved: {transcript['title']}")

def ensure_company(conn, company: dict) -> int:
    """Insert company if not exists, return id."""
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

    for company in COMPANIES:
        logger.info(f"\n=== Scraping {company['ticker']} ===")

        company_id = ensure_company(conn, company)
        transcript_links = search_transcripts(company["ticker"])

        for link in transcript_links:
            transcript = scrape_transcript(link["url"])
            if transcript:
                save_transcript(conn, company_id, transcript)

            # Be polite — don't hammer the server
            time.sleep(2)

        # Pause between companies
        time.sleep(5)

    conn.close()
    logger.info("\nScraping complete.")

if __name__ == "__main__":
    run_scraper()