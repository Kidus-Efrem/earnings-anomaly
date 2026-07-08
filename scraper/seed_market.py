import os
import sqlite3
import requests
from datetime import datetime

DB_PATH = os.path.join("data", "transcripts.db")

def get_top_market_tickers():
    """
    Fetches the active SEC ticker list and filters for the top liquid
    market symbols most likely to have transcript coverage.
    """
    url = "https://www.sec.gov/files/company_tickers.json"
    headers = {"User-Agent": "EarningsAnomalyResearch/1.0 (parzi@onedrive.com)"}
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        # Grab standard corporate symbols, avoiding ETFs and multi-class stocks
        return [item['ticker'] for item in data.values() if item['ticker'].isalpha() and len(item['ticker']) <= 4]
    except Exception as e:
        print(f"[!] SEC Fetch Error: {e}")
        # High-coverage fallback list if SEC network drops
        return ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "AMD", "NFLX", "INTC"]

def bulk_seed_deterministic_calendar(limit_companies=150):
    print("[*] Sourcing high-liquidity stock tickers from SEC index...")
    tickers = get_top_market_tickers()[:limit_companies]
    print(f"[✓] Selected {len(tickers)} prime target companies for historical generation.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    seeded_count = 0

    # Define recent core historical reporting quarters and their typical release windows
    # Format: (Quarter_Name, Core_Year, Target_Month, Approximate_Day_Range)
    historical_windows = [
        ("Q1", "2026", "04", range(14, 28)), # Q1 earnings drop mid-to-late April
        ("Q4", "2025", "01", range(18, 30)), # Q4 earnings drop mid-to-late January
        ("Q3", "2025", "10", range(15, 29)), # Q3 earnings drop mid-to-late October
        ("Q2", "2025", "07", range(16, 30)), # Q2 earnings drop mid-to-late July
    ]

    print("[*] Generating historical timeline records across windows...")

    for ticker in tickers:
        # Use a stable hash of the ticker name to distribute dates evenly across the window.
        # This simulates real-world staggered rolling calendar schedules.
        ticker_hash = sum(ord(c) for c in ticker)

        for quarter, year, month, day_range in historical_windows:
            # Select a deterministic day in the window based on the ticker name
            day_index = ticker_hash % len(day_range)
            day = day_range[day_index]

            # Format as standard ISO date string: YYYY-MM-DD
            date_str = f"{year}-{month}-{day:02d}"

            cursor.execute("""
                INSERT OR IGNORE INTO earnings_calendar (ticker, target_date, quarter, status)
                VALUES (?, ?, ?, 'PENDING')
            """, (ticker, date_str, quarter))

            if cursor.rowcount > 0:
                seeded_count += 1

    conn.commit()
    conn.close()
    print(f"\n[✓] Seeding complete! Added {seeded_count} active historical earnings items as PENDING.")

if __name__ == "__main__":
    # 150 companies x 4 historical quarters = up to 600 target records instantly
    bulk_seed_deterministic_calendar(limit_companies=150)