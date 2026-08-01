# scraper/seed_postgres.py

from postgres_db import get_pg_connection, init_pg_db

import urllib.request
import urllib.parse
import json
import re

import urllib.request
import csv

def fetch_live_sp500_universe():
    """Retrieves S&P 500 constituents directly from a curated data repository."""
    print("[*] Fetching live S&P 500 ticker universe via raw CSV data stream...")

    # Direct raw link to a highly reliable, frequently updated open-source dataset repository
    csv_url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"

    try:
        req = urllib.request.Request(
            csv_url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )

        with urllib.request.urlopen(req) as response:
            # Decode stream lines to process via Python's native CSV engine
            csv_lines = [line.decode('utf-8') for line in response.readlines()]

        reader = csv.DictReader(csv_lines)
        ticker_list = []

        for row in reader:
            # Match standard columns: Symbol and CIK
            ticker = row.get("Symbol", "").strip().upper().replace('.', '-')
            cik = row.get("CIK", "").strip().zfill(10)

            if ticker and cik and ticker not in ["SYMBOL", "CIK"]:
                ticker_list.append({
                    "ticker": ticker,
                    "cik": cik
                })

        if len(ticker_list) < 400:
            raise ValueError(f"Extracted dataset size abnormally low: {len(ticker_list)} found.")

        print(f"[✓] Successfully retrieved {len(ticker_list)} tickers from raw data index.")
        return ticker_list

    except Exception as e:
        print(f"[!] Target data repository transmission failed: {e}")
        print("[*] Falling back to primary tech-heavy ticker matrix as backup safety...")
        fallback_tickers = ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "NFLX", "AMD", "INTC"]
        return [{"ticker": t, "cik": "0000000000"} for t in fallback_tickers]
def bulk_seed_postgres():
    init_pg_db()
    universe = fetch_live_sp500_universe()

    # 4-Year Quarter Reporting Matrix (2023 - 2026)
    quarters_map = [
        {"year": 2026, "quarter": "Q1", "month": "04", "approx_day": "24"},
        {"year": 2026, "quarter": "Q4", "month": "01", "approx_day": "22"},
        {"year": 2025, "quarter": "Q3", "month": "10", "approx_day": "25"},
        {"year": 2025, "quarter": "Q2", "month": "07", "approx_day": "24"},
        {"year": 2025, "quarter": "Q1", "month": "04", "approx_day": "25"},
        {"year": 2025, "quarter": "Q4", "month": "01", "approx_day": "23"},
        {"year": 2024, "quarter": "Q3", "month": "10", "approx_day": "24"},
        {"year": 2024, "quarter": "Q2", "month": "07", "approx_day": "23"},
        {"year": 2024, "quarter": "Q1", "month": "04", "approx_day": "26"},
        {"year": 2023, "quarter": "Q3", "month": "10", "approx_day": "26"},
    ]

    conn = get_pg_connection()
    cursor = conn.cursor()
    seeded_count = 0

    print(f"[*] Cross-referencing timelines. Generating database jobs for {len(universe)} symbols...")

    for item in universe:
        ticker = item["ticker"]
        cik = item["cik"]

        for q in quarters_map:
            date_str = f"{q['year']}-{q['month']}-{q['approx_day']}"

            cursor.execute("""
                INSERT INTO earnings_calendar (ticker, target_date, cik, quarter, fiscal_year, time_of_day, status)
                VALUES (%s, %s::DATE, %s, %s, %s, 'UNKNOWN', 'PENDING')
                ON CONFLICT (ticker, target_date) DO NOTHING
            """, (ticker, date_str, cik, q["quarter"], q["year"]))

            if cursor.rowcount > 0:
                seeded_count += 1

    conn.commit()
    cursor.close()
    conn.close()

    print(f"[✓] Scale seeder complete! Injected {seeded_count} total rows into PostgreSQL.")

if __name__ == "__main__":
    bulk_seed_postgres()