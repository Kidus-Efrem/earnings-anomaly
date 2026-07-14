# validate_market.py
import os
import sqlite3
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

DB_PATH = os.path.join("data", "transcripts.db")

def ensure_columns_exist():
    """Alters the database table to support 24h and 48h market metrics."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check existing columns
    cursor.execute("PRAGMA table_info(earnings_calendar)")
    columns = [col[1] for col in cursor.fetchall()]

    if "return_24h" not in columns:
        cursor.execute("ALTER TABLE earnings_calendar ADD COLUMN return_24h REAL")
        print("[*] Added column return_24h to earnings_calendar")
    if "return_48h" not in columns:
        cursor.execute("ALTER TABLE earnings_calendar ADD COLUMN return_48h REAL")
        print("[*] Added column return_48h to earnings_calendar")

    conn.commit()
    conn.close()

def calculate_returns():
    ensure_columns_exist()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Select completed transcripts that haven't been validated yet
    cursor.execute("""
        SELECT ticker, target_date FROM earnings_calendar
        WHERE status = 'COMPLETED' AND (return_24h IS NULL OR return_48h IS NULL)
    """)
    records = cursor.fetchall()

    if not records:
        print("[✓] All completed records have already been validated with market returns.")
        conn.close()
        return

    print(f"[*] Validating market performance for {len(records)} records using yfinance...")

    for ticker, date_str in records:
        try:
            # Parse target date
            target_date = datetime.strptime(date_str, "%Y-%m-%d")
            start_date = target_date - timedelta(days=3)  # Buffer before
            end_date = target_date + timedelta(days=6)    # Buffer after to cover weekends

            # Download stock candles
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date.strftime("%Y-%m-%d"),
                               end=end_date.strftime("%Y-%m-%d"))

            if df.empty or len(df) < 2:
                print(f"  [!] No ticker data found on yfinance for {ticker}")
                continue

            # Filter index to get target date or the closest trading day after it
            df.index = df.index.tz_localize(None)
            trading_days = df.index[df.index >= target_date]

            if len(trading_days) < 3:
                print(f"  [!] Not enough trading days post-earnings to evaluate {ticker} on {date_str}")
                continue

            # T_0 (Close on earnings day or first active day)
            p_0 = df.loc[trading_days[0], 'Close']
            # T_1 (24 hours out / next close)
            p_1 = df.loc[trading_days[1], 'Close']
            # T_2 (48 hours out / subsequent close)
            p_2 = df.loc[trading_days[2], 'Close']

            # Calculate mathematical returns
            return_24 = ((p_1 - p_0) / p_0) * 100
            return_48 = ((p_2 - p_0) / p_0) * 100

            cursor.execute("""
                UPDATE earnings_calendar
                SET return_24h = ?, return_48h = ?
                WHERE ticker = ? AND target_date = ?
            """, (return_24, return_48, ticker, date_str))

            print(f"  [➔] {ticker} [{date_str}] -> 24h: {return_24:.2f}%, 48h: {return_48:.2f}%")

        except Exception as e:
            print(f"  [!] Error validating {ticker} on {date_str}: {e}")

    conn.commit()
    conn.close()
    print("[✓] Market validation run complete.")

if __name__ == "__main__":
    calculate_returns()