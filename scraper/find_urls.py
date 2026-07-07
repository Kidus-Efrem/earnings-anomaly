import requests
import json
import time

def get_real_earnings_dates(ticker: str, email: str) -> list[str]:
    """
    Fetches official 8-K filing dates from the SEC EDGAR API,
    filtering strictly for Item 2.02 (Results of Operations & Financial Condition).
    """
    # 1. Fetch the absolute up-to-date CIK mapping from the SEC
    headers = {"User-Agent": f"ResearchInstance {email}"}
    ticker_url = "https://sec.gov/files/company_tickers.json"

    try:
        ticker_resp = requests.get(ticker_url, headers=headers)
        ticker_data = ticker_resp.json()
    except Exception as e:
        print(f"Failed to fetch ticker mappings: {e}")
        return []

    # Find the matching CIK number for your target ticker
    target_cik = None
    for entry in ticker_data.values():
        if entry['ticker'].upper() == ticker.upper():
            # SEC requires CIKs to be 10 digits, padded with leading zeros
            target_cik = str(entry['cik_str']).zfill(10)
            break

    if not target_cik:
        print(f"Ticker {ticker} not found in SEC database.")
        return []

    # 2. Query the submissions endpoint for this CIK
    submissions_url = f"https://data.sec.gov/submissions/CIK{target_cik}.json"

    # Optional safety sleep to respect the SEC's 10 req/sec rule
    time.sleep(0.1)

    try:
        resp = requests.get(submissions_url, headers=headers)
        if resp.status_code != 200:
            print(f"SEC API rejected query: Status {resp.status_code}")
            return []

        data = resp.json()
        filings = data['filings']['recent']
    except Exception as e:
        print(f"Failed to parse data for CIK {target_cik}: {e}")
        return []

    earnings_dates = []

    # 3. Zip and parse filing types, dates, and items fired
    for form, date, items in zip(filings['form'], filings['filingDate'], filings['items']):
        # We look for 8-K filings that explicitly contain '2.02' (Earnings Disclosures)
        if form == '8-K' and '2.02' in str(items):
            earnings_dates.append(date)

    return sorted(list(set(earnings_dates)), reverse=True)

# Example Usage:
# Replace with your actual email string to comply with SEC rules
my_email = "yourname@domain.com"
goldman_dates = get_real_earnings_dates("GS", my_email)

print(f"Verified Earnings Announcement Dates found: {goldman_dates[:5]}")