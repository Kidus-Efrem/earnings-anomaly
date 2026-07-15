import os
import re
import time
import random
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import traceback

# Core relative imports from your PostgreSQL database component script
from postgres_db import get_pg_connection, init_pg_db

FOOL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

# Accurate explicit slug maps used by Motley Fool historically
TICKER_NAME_MAP = {
    "JPM": ["jpmorgan", "jpmorgan-chase"],
    "GS": ["goldman-sachs", "goldman-sachs-group"],
}

# Globals managing in-memory cache lookups across large scale lists
SITEMAP_CACHE = {}

def update_market_time_of_day(ticker: str, target_date: str, text: str):
    """Scans introductory text to deduce Before Market Open (BMO) or After Market Close (AMC)."""
    intro_snippet = text[:2500].lower()
    time_of_day = "UNKNOWN"

    bmo_signals = ["before the opening bell", "before market open", "morning call", "bmo", "prior to the market open"]
    amc_signals = ["after the closing bell", "after market close", "evening call", "amc", "after the market closes"]

    if any(sig in intro_snippet for sig in bmo_signals):
        time_of_day = "BMO"
    elif any(sig in intro_snippet for sig in amc_signals):
        time_of_day = "AMC"

    if time_of_day != "UNKNOWN":
        conn = get_pg_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE earnings_calendar
            SET time_of_day = %s
            WHERE ticker = %s AND target_date = %s::DATE
        """, (time_of_day, ticker, target_date))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"    [➔] Extracted market timing constraint alignment: {time_of_day}")

def get_cached_sitemap(year_str: str, month_str: str) -> str:
    """Downloads monthly sitemap XML indexes and stores them safely in memory."""
    cache_key = f"{year_str}/{month_str}"
    if cache_key in SITEMAP_CACHE:
        return SITEMAP_CACHE[cache_key]

    archive_url = f"https://www.fool.com/sitemap/{year_str}/{month_str}"
    print(f"    [*] Fetching sitemap catalog for {cache_key}...")

    try:
        resp = requests.get(archive_url, headers=FOOL_HEADERS, timeout=15)
        if resp.status_code == 200 and resp.text:
            SITEMAP_CACHE[cache_key] = resp.text
            return resp.text
        else:
            fallback_url = f"https://www.fool.com/sitemaps/{year_str}/{month_str}"
            resp_fb = requests.get(fallback_url, headers=FOOL_HEADERS, timeout=15)
            if resp_fb.status_code == 200 and resp_fb.text:
                SITEMAP_CACHE[cache_key] = resp_fb.text
                return resp_fb.text
            print(f"    [!] Failed to pull map path index target. HTTP Status: {resp.status_code}")
    except Exception as e:
        print(f"    [!] Error caching sitemap {cache_key}: {type(e).__name__}")
    return ""

def find_url_scaled(ticker: str, target_date_str: str) -> str | None:
    """Scans cached local maps across primary and neighboring months to match valid transcripts."""
    ticker_lower = ticker.lower()
    date_obj = datetime.strptime(target_date_str, "%Y-%m-%d")

    year_str = date_obj.strftime("%Y")
    month_str = date_obj.strftime("%m")
    xml_content = str(get_cached_sitemap(year_str, month_str) or "")

    next_month_obj = (date_obj.replace(day=28) + timedelta(days=5))
    next_year_str = next_month_obj.strftime("%Y")
    next_month_str = next_month_obj.strftime("%m")
    xml_content += str(get_cached_sitemap(next_year_str, next_month_str) or "")

    if date_obj.day < 7:
        prev_month_obj = date_obj - timedelta(days=10)
        prev_year_str = prev_month_obj.strftime("%Y")
        prev_month_str = prev_month_obj.strftime("%m")
        xml_content += str(get_cached_sitemap(prev_year_str, prev_month_str) or "")

    if not xml_content or len(xml_content.strip()) == 0:
        return None

    all_urls = re.findall(r"<loc>(.*?)</loc>", xml_content)
    candidate_urls = []

    strict_patterns = [
        re.compile(rf"-{ticker_lower}-q\d-20\d\d"),
        re.compile(rf"-{ticker_lower}-earnings-"),
    ]
    if ticker in TICKER_NAME_MAP:
        for mapped_slug in TICKER_NAME_MAP[ticker]:
            strict_patterns.append(re.compile(rf"-{mapped_slug}-"))

    for url in all_urls:
        if "/earnings/call-transcripts/" in url:
            if any(pattern.search(url) for pattern in strict_patterns):
                candidate_urls.append(url)

    best_url = None
    smallest_delta = timedelta(days=45)

    for url in candidate_urls:
        date_match = re.search(r"/call-transcripts/(\d{4})/(\d{2})/(\d{2})/", url)
        if date_match:
            url_date_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
            try:
                url_date = datetime.strptime(url_date_str, "%Y-%m-%d")
                delta = abs(url_date - date_obj)
                if delta < smallest_delta:
                    smallest_delta = delta
                    best_url = url
            except ValueError:
                continue
    return best_url

def download_and_parse_transcript(url: str) -> str | None:
    """Downloads individual document bodies and cleans the extracted text segments."""
    try:
        resp = requests.get(url, headers=FOOL_HEADERS, timeout=12)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')
        content_div = soup.find('div', class_='tail-wrapper') or soup.find('div', class_='page-content')
        if content_div:
            return content_div.get_text(separator="\n", strip=True)

        paragraphs = soup.find_all('p')
        return "\n".join([p.get_text() for p in paragraphs if len(p.get_text()) > 30])
    except Exception:
        return None

def get_pending_jobs(limit=10):
    """Retrieves pending jobs out of the PostgreSQL cluster store."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    current_date = datetime.now().date()

    cursor.execute("""
        SELECT ticker, target_date
        FROM earnings_calendar
        WHERE status = 'PENDING' AND target_date <= %s
        ORDER BY target_date DESC
        LIMIT %s;
    """, (current_date, limit))

    jobs = [{"ticker": row[0], "date": str(row[1])} for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return jobs

def update_job_status(ticker: str, target_date: str, status: str, url: str = None):
    """Saves pipeline progression metrics back safely into your explicit transcript_url column."""
    conn = get_pg_connection()
    cursor = conn.cursor()

    # REPAIRED QUERY: Uses explicitly named fields to put the URL in transcript_url instead of time_of_day
    query = """
        UPDATE earnings_calendar
        SET
            status = %(status)s,
            transcript_url = COALESCE(%(url)s, transcript_url)
        WHERE
            ticker = %(ticker)s
            AND target_date = %(target_date)s::DATE;
    """
    try:
        cursor.execute(query, {
            "status": status,
            "url": url,
            "ticker": ticker,
            "target_date": target_date
        })
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def save_transcript_content(ticker: str, target_date: str, text: str):
    """Saves parsed transcript content directly into the transcripts_content table."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO transcripts_content (ticker, target_date, transcript_text, char_count)
            VALUES (%s, %s::DATE, %s, %s)
            ON CONFLICT (ticker, target_date)
            DO UPDATE SET
                transcript_text = EXCLUDED.transcript_text,
                char_count = EXCLUDED.char_count;
        """, (ticker, target_date, text, len(text)))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"    [!] Failed to save transcript text to DB for {ticker}: {e}")
        raise e
    finally:
        cursor.close()
        conn.close()
def scale_pipeline_runner():
    """Main pipeline loop executing across remaining elements sequential streams."""
    print("Starting production data pipeline loop automation profiles...")
    print("=" * 70)

    init_pg_db()

    pending_jobs = get_pending_jobs(limit=500)
    print(f"[#] Total Pending records found in catalog index ledger: {len(pending_jobs)}")

    for job in pending_jobs:
        ticker = job["ticker"]
        target_date = job["date"]

        print(f"\n[+] Actively processing target record: {ticker} ({target_date})")

        try:
            url = find_url_scaled(ticker, target_date)

            if url:
                print(f"    [✓] Matched address string destination path: {url}")
                time.sleep(random.uniform(1.5, 3.5))

                text = download_and_parse_transcript(url)
                if text and len(text) > 3000:
                    save_transcript_content(ticker, target_date, text)
                    update_job_status(ticker, target_date, 'COMPLETED', url)
                    print(f"    [✓] Data block transaction stored safely. Size: {len(text)} characters.")

                    update_market_time_of_day(ticker, target_date, text)
                else:
                    update_job_status(ticker, target_date, 'FAILED_PARSING', url)
                    print("    [!] Warning: Empty or abnormally small parsing text array payload gathered.")
            else:
                update_job_status(ticker, target_date, 'NO_TRANSCRIPT')
                print("    [-] Skipped: No transcript matching criteria found inside month maps.")

        except Exception as global_err:
            update_job_status(ticker, target_date, 'FAILED_CRITICAL')
            print(f"    [!!] Thread execution failure on runtime item: {global_err}")
            print(traceback.format_exc())

        time.sleep(random.uniform(0.5, 1.5))

if __name__ == "__main__":
    scale_pipeline_runner()