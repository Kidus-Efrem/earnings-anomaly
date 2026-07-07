# save as scraper/find_urls.py
import requests
import time

HEADERS = {"User-Agent": "Mozilla/5.0 (research project)"}

COMPANIES = {
    "GS": "goldman-sachs",
    "JPM": "jpmorgan",
    "MS": "morgan-stanley",
    "BAC": "bank-of-america",
    "C": "citigroup",
    "AAPL": "apple",
    "MSFT": "microsoft",
    "GOOGL": "alphabet",
    "META": "meta-platforms",
    "ORCL": "oracle",
    "XOM": "exxonmobil",
    "CVX": "chevron",
    "COP": "conocophillips",
    "SLB": "slb",
    "EOG": "eog-resources",
    "JNJ": "johnson-johnson",
    "UNH": "unitedhealth-group",
    "PFE": "pfizer",
    "ABBV": "abbvie",
    "MRK": "merck",
}

# Approximate earnings dates — we'll try ±3 days around each
QUARTERS = [
    ("q1-2026", 2026, 4, 14),
    ("q4-2025", 2026, 1, 15),
    ("q3-2025", 2025, 10, 15),
    ("q2-2025", 2025, 7, 16),
    ("q1-2025", 2025, 4, 15),
    ("q4-2024", 2025, 1, 15),
    ("q3-2024", 2024, 10, 15),
    ("q2-2024", 2024, 7, 15),
]

def find_url(company_slug, ticker, quarter_label, year, month, day):
    suffixes = ["-earnings-transcript/", "-earnings-call-transcript/", "-earnings-call-transcrip/"]
    for delta in range(-5, 6):  # try ±5 days
        from datetime import date, timedelta
        d = date(year, month, day) + timedelta(days=delta)
        date_str = d.strftime("%Y/%m/%d")
        for suffix in suffixes:
            url = f"https://www.fool.com/earnings/call-transcripts/{date_str}/{company_slug}-{ticker.lower()}-{quarter_label}{suffix}"
            try:
                r = requests.head(url, headers=HEADERS, timeout=5, allow_redirects=True)
                if r.status_code == 200:
                    print(f"✓ {ticker} {quarter_label}: {url}")
                    return url
            except Exception:
                pass
            time.sleep(0.3)
    print(f"✗ {ticker} {quarter_label}: not found")
    return None

results = {}
for ticker, slug in COMPANIES.items():
    results[ticker] = []
    for quarter_label, year, month, day in QUARTERS:
        url = find_url(slug, ticker, quarter_label, year, month, day)
        if url:
            results[ticker].append(url)
    time.sleep(2)

# Print as Python dict you can paste into motleyfool.py
print("\n\nTRANSCRIPT_URLS = {")
for ticker, urls in results.items():
    print(f'    "{ticker}": [')
    for url in urls:
        print(f'        "{url}",')
    print("    ],")
print("}")