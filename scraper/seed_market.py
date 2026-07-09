import os
import sqlite3

DB_PATH = os.path.join("data", "transcripts.db")

def get_fallback_market_index():
    return [
        {"ticker": "AAPL", "cik": "0000320193"},
        {"ticker": "MSFT", "cik": "0000789019"},
        {"ticker": "AMZN", "cik": "0001018724"},
        {"ticker": "NVDA", "cik": "0001045810"},
        {"ticker": "GOOGL", "cik": "0001652044"},
        {"ticker": "META", "cik": "0001326801"},
        {"ticker": "TSLA", "cik": "0001318605"}
    ]

def bulk_seed():
    print("[*] Running completely offline seeder...")
    company_data = get_fallback_market_index()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    seeded_count = 0
    
    historical_windows = [
        ("Q1", 2026, "04", range(14, 28)),
        ("Q4", 2025, "01", range(18, 30))
    ]
    
    for item in company_data:
        ticker = item["ticker"]
        cik = item["cik"]
        for quarter, year, month, day_range in historical_windows:
            date_str = f"{year}-{month}-20"
            cursor.execute("""
                INSERT OR IGNORE INTO earnings_calendar (ticker, target_date, cik, quarter, fiscal_year, time_of_day, status)
                VALUES (?, ?, ?, ?, ?, 'UNKNOWN', 'PENDING')
            """, (ticker, date_str, cik, quarter, year))
            if cursor.rowcount > 0:
                seeded_count += 1
                
    conn.commit()
    conn.close()
    print(f"[?] Seeding complete! Added {seeded_count} entries offline.")

if __name__ == "__main__":
    bulk_seed()
