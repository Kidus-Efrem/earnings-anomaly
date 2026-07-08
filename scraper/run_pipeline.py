import os
import re
import time
import random
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# Direct relative imports from database component scripts
from database import init_db, seed_mock_data, get_pending_jobs, update_job_status, save_transcript_content

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

def get_cached_sitemap(year_str: str, month_str: str) -> str | None:
    """Downloads monthly sitemap XML indexes and stores them in memory to prevent duplicate requests."""
    cache_key = f"{year_str}/{month_str}"
    if cache_key in SITEMAP_CACHE:
        return SITEMAP_CACHE[cache_key]

    archive_url = f"https://www.fool.com/sitemap/{year_str}/{month_str}"
    print(f"    [*] Fetching sitemap catalog for {cache_key}...")

    try:
        resp = requests.get(archive_url, headers=FOOL_HEADERS, timeout=15)
        if resp.status_code == 200:
            SITEMAP_CACHE[cache_key] = resp.text
            return resp.text
        else:
            print(f"    [!] Failed to pull map path index target. HTTP Status: {resp.status_code}")
    except Exception as e:
        print(f"    [!] Error caching sitemap {cache_key}: {type(e).__name__}")

    return None

def find_url_scaled(ticker: str, target_date_str: str) -> str | None:
    """Scans cached local maps to match the closest valid transcript URL location."""
    ticker_lower = ticker.lower()
    date_obj = datetime.strptime(target_date_str, "%Y-%m-%d")

    year_str = date_obj.strftime("%Y")
    month_str = date_obj.strftime("%m")

    xml_content = get_cached_sitemap(year_str, month_str)

    # Check the next month as well if the reporting date is near month end boundaries
    if date_obj.day > 24:
        next_m = date_obj + timedelta(days=10)
        xml_content_next = get_cached_sitemap(next_m.strftime("%Y"), next_m.strftime("%m"))
        if xml_content and xml_content_next:
            xml_content += xml_content_next
        elif xml_content_next:
            xml_content = xml_content_next

    if not xml_content:
        return None

    all_urls = re.findall(r"<loc>(.*?)</loc>", xml_content)
    candidate_urls = []

    # Strict hyphen-bounded regex patterns to prevent false-positives
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
    smallest_delta = timedelta(days=21) # Matches across up to 3 weeks delay gaps

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

        # Global multi-paragraph tracking fallbacks
        paragraphs = soup.find_all('p')
        return "\n".join([p.get_text() for p in paragraphs if len(p.get_text()) > 30])
    except Exception:
        return None

def scale_pipeline_runner():
    """Main pipeline loop executing across remaining elements sequential streams."""
    print("Starting production data pipeline loop automation profiles...")
    print("=" * 70)

    init_db()
    seed_mock_data() # Adds mock testing elements if table is freshly instantiated

    pending_jobs = get_pending_jobs()
    print(f"[#] Total Pending records found in catalog index ledger: {len(pending_jobs)}")

    for job in pending_jobs:
        ticker = job["ticker"]
        target_date = job["date"]

        print(f"\n[+] Actively processing target record: {ticker} ({target_date})")

        try:
            url = find_url_scaled(ticker, target_date)

            if url:
                print(f"    [✓] Matched address string destination path: {url}")
                # Throttling padding delay block directly before execution full text loads
                time.sleep(random.uniform(1.5, 3.5))

                text = download_and_parse_transcript(url)
                if text and len(text) > 3000:
                    save_transcript_content(ticker, target_date, text)
                    update_job_status(ticker, target_date, 'COMPLETED', url)
                    print(f"    [✓] Data block transaction stored safely. Size: {len(text)} characters.")
                else:
                    update_job_status(ticker, target_date, 'FAILED_PARSING', url)
                    print("    [!] Warning: Empty or abnormally small parsing text array payload gathered.")
            else:
                update_job_status(ticker, target_date, 'NO_TRANSCRIPT')
                print("    [-] Skipped: No transcript matching criteria found inside month maps.")

        except Exception as global_err:
            update_job_status(ticker, target_date, 'FAILED_CRITICAL')
            print(f"    [!!] Thread execution failure on runtime item: {global_err}")

        # Pacing step buffering delay
        time.sleep(random.uniform(0.5, 1.5))

if __name__ == "__main__":
    scale_pipeline_runner()