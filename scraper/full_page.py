import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

def get_transcript_url_from_archive(ticker: str, target_date_str: str) -> str | None:
    """
    Scans Motley Fool's monthly chronological archive instead of trying to
    guess single URLs or parse dynamic quote hubs.
    """
    ticker_lower = ticker.lower()

    try:
        date_obj = datetime.strptime(target_date_str, "%Y-%m-%d")
    except ValueError:
        return None

    # Step 1: Target the specific month the earnings call happened
    year_str = date_obj.strftime("%Y")
    month_str = date_obj.strftime("%m")

    archive_url = f"https://www.fool.com/sitemaps/earnings/call-transcripts/{year_str}/{month_str}/"
    print(f"    [*] Scanning monthly archive directory: {archive_url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        resp = requests.get(archive_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"    [!] Failed to pull monthly archive page (Status: {resp.status_code})")
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        print(f"    [!] Connection error fetching archive map: {e}")
        return None

    # Step 2: Extract all transcript links on this page
    all_links = soup.find_all('a', href=True)
    candidate_urls = []

    # Compile patterns to catch standard or variation configurations matching your ticker symbol
    # This automatically matches '-gs-', '-jpm-', '-jpmorgan-', etc.
    patterns = [
        re.compile(rf"-{ticker_lower}-q\d-20\d\d"),
        re.compile(rf"-{ticker_lower}-earnings"),
    ]
    if ticker_lower == "jpm":
        patterns.append(re.compile(r"-jpmorgan-"))

    for link in all_links:
        href = link['href']
        if "/earnings/call-transcripts/" in href:
            if any(pattern.search(href) for pattern in patterns):
                candidate_urls.append(href)

    if not candidate_urls:
        print(f"    [-] No candidate URLs found for {ticker} in the {month_str}/{year_str} archive.")
        return None

    # Step 3: Parse dates from URLs to match the closest candidate to our target date
    # Motley Fool URLs look like: .../call-transcripts/2026/04/13/goldman-sachs-gs-q1-2026...
    best_url = None
    smallest_delta = timedelta(days=15) # Must be within 2 weeks of the calendar date

    for url in candidate_urls:
        # Regex out the YYYY/MM/DD fragment from the URL path string
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

    if best_url:
        print(f"    [+] Found direct match: {best_url} (Delta: {smallest_delta.days} days)")
        return best_url

    return None