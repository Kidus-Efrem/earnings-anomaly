import os
import sys
import time
import requests
from datetime import datetime, timedelta

# List of common multi-word corporate names to ensure clean URL slug matching
# Extend this dictionary if other tickers return "not found" due to their business name
TICKER_NAME_MAP = {
    "A": "agilent",
    "AA": "alcoa",
    "AAPL": "apple",
    "ABBV": "abbvie",
    "ABT": "abbott-laboratories",
    "ACN": "accenture",
    "ADM": "archer-daniels-midland",
    "AMZN": "amazon",
    "GOOGL": "alphabet",
    "GOOG": "alphabet",
    "MSFT": "microsoft",
    "META": "meta-platforms",
    "NFLX": "netflix",
    "TSLA": "tesla"
}

def find_url_in_sitemap(ticker: str, target_date_str: str) -> str:
    """
    Directly predicts and verifies Motley Fool URL paths using rolling-date
    structural guessing, avoiding unstable sitemap xml indexing completely.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    ticker_upper = ticker.upper()
    ticker_lower = ticker.lower()
    company_slug = TICKER_NAME_MAP.get(ticker_upper, ticker_lower)

    try:
        date_obj = datetime.strptime(target_date_str, "%Y-%m-%d")
    except ValueError:
        print(f"   [!] Invalid date format received: {target_date_str}")
        return None

    # Check a 5-day window surrounding the date (-2 to +2 days) to absorb logging mismatches
    for offset in [-2, -1, 0, 1, 2]:
        current_date = date_obj + timedelta(days=offset)
        year = current_date.year
        month = str(current_date.month).zfill(2)
        day = str(current_date.day).zfill(2)

        # Calculate expected fiscal quarter relative to reporting month
        if current_date.month in [1, 2, 3, 4]:
            quarter = "4" if current_date.month in [1, 2] else "1"
        elif current_date.month in [5, 6, 7]:
            quarter = "1" if current_date.month == 5 else "2"
        elif current_date.month in [8, 9, 10]:
            quarter = "2" if current_date.month == 8 else "3"
        else:
            quarter = "3" if current_date.month == 11 else "4"

        # Adjust fiscal year context if looking at a Q4 report published in early Q1
        fiscal_year = year - 1 if (quarter == "4" and current_date.month in [1, 2, 3]) else year

        # Common variants Motley Fool uses to organize their transcript names
        slug_variants = [
            f"{company_slug}-{ticker_lower}-q{quarter}-{fiscal_year}-earnings-call-transcript",
            f"{company_slug}-{ticker_lower}-q{quarter}-{fiscal_year}-earnings-transcript",
            f"{company_slug}-q{quarter}-{fiscal_year}-earnings-call-transcript",
            f"{ticker_lower}-q{quarter}-{fiscal_year}-earnings-call-transcript"
        ]

        for slug in slug_variants:
            target_url = f"https://www.fool.com/earnings/call-transcripts/{year}/{month}/{day}/{slug}/"

            try:
                # Use HTTP HEAD to check URL life fast without triggering huge data downloads
                time.sleep(0.1)
                resp = requests.head(target_url, headers=headers, allow_redirects=True, timeout=7)

                if resp.status_code == 200 and "fool.com/earnings/call-transcripts/" in resp.url:
                    return resp.url
            except requests.RequestException:
                continue

    return None

def fetch_sp500_tickers() -> list:
    """Gets S&P 500 corporate tickers dynamically from Wikipedia."""
    print("[*] Dynamically downloading S&P 500 index ticker list from Wikipedia...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return ["A", "ABBV", "ABT", "ACN", "ADM"] # Fallback subset if Wiki fails

        # Simple extraction via split bounds to avoid heavy BeautifulSoup requirement
        html = resp.text
        table_start = html.find('id="constituents"')
        table_html = html[table_start:html.find('</table>', table_start)]

        tickers = []
        for row in table_html.split('<tr>')[1:]:
            cells = row.split('<td>')
            if len(cells) > 1:
                ticker = cells[1].split('">')[1].split('</a>')[0].strip()
                # Clean up formatting oddities
                ticker = ticker.replace('.', '-')
                if ticker and not ticker.startswith('<'):
                    tickers.append(ticker)
        return sorted(list(set(tickers)))
    except Exception as e:
        print(f"[!] Error fetching Wikipedia list: {e}. Using local sample.")
        return ["A", "ABBV", "ABT", "ACN", "ADM"]

def run_pipeline():
    """Main pipeline execution loop."""
    print("Starting Multi-Company Automated Pipeline Context...")
    print("=" * 60)

    tickers = fetch_sp500_tickers()
    print(f"[+] Successfully loaded {len(tickers)} corporate tickers.\n")

    # Mocking historical dates array you see in logs ('2026-05-27', etc)
    # Inside your real script, these targets are coming out of your earnings calendar engine
    mock_calendar = {
        "A": ['2026-05-27', '2026-02-25'],
        "ABBV": ['2026-04-29', '2026-02-04'],
        "ABT": ['2026-04-16', '2026-01-22'],
        "ACN": ['2026-06-18', '2026-03-19'],
        "ADM": ['2026-04-28']
    }

    for idx, ticker in enumerate(tickers, 1):
        # Fallback tracking if ticker doesn't exist in our mock dataset
        dates_to_fetch = mock_calendar.get(ticker.upper(), ['2026-04-15'])

        print(f"[{idx}/{len(tickers)}] Processing operational pipeline for: {ticker}")
        print(f"  -> Found {len(dates_to_fetch)} earnings calls to fetch: {dates_to_fetch}")

        for target_date in dates_to_fetch:
            print(f"  -> Locating target link for {ticker} on call date {target_date}...")

            resolved_url = find_url_in_sitemap(ticker, target_date)

            if resolved_url:
                print(f"   [+] MATCH FOUND: {resolved_url}")
                # YOUR DOWNSTREAM TRANSCRIPT PARSER AND SCRAPER LOGIC GOES HERE:
                # content = requests.get(resolved_url, headers=headers).text
                # save_to_database(content)
            else:
                print(f"   [!] Could not locate a matching transcript URL for {ticker} using rolling date validation.")
        print()

if __name__ == "__main__":
    try:
        run_pipeline()
    except KeyboardInterrupt:
        print("\n[!] Pipeline execution suspended by user control.")
        sys.exit(0)