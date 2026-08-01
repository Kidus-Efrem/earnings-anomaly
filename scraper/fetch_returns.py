import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from postgres_db import get_pg_connection

def get_completed_jobs():
    """Fetches all completed scraper jobs that don't have return data calculated yet."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ticker, target_date, time_of_day
        FROM earnings_calendar
        WHERE status = 'COMPLETED'
          AND (return_24h IS NULL OR return_48h IS NULL);
    """)
    jobs = [{"ticker": row[0], "date": row[1], "time_of_day": row[2]} for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return jobs

def update_returns_in_db(ticker, target_date, ret_24, ret_48):
    """Saves the calculated returns back to the database."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE earnings_calendar
        SET return_24h = %s, return_48h = %s
        WHERE ticker = %s AND target_date = %s::DATE;
    """, (ret_24, ret_48, ticker, target_date))
    conn.commit()
    cursor.close()
    conn.close()

def calculate_returns():
    jobs = get_completed_jobs()
    print(f"Found {len(jobs)} records needing market returns data...")

    for idx, job in enumerate(jobs):
        ticker = job["ticker"]
        target_date = job["date"] # datetime.date object

        # We need a small window of stock data around the target date
        start_date = target_date - timedelta(days=5)
        end_date = target_date + timedelta(days=7)

        print(f"[{idx+1}/{len(jobs)}] Fetching {ticker} around {target_date}...")

        try:
            # Fetch daily stock data
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date)

            if df.empty or len(df) < 3:
                print(f"    [!] Insufficient price history found for {ticker}")
                continue

            # Ensure the target_date exists in our trading calendar, or find the closest trading day
            df.index = df.index.tz_localize(None) # Remove timezone for easy comparison
            target_dt = datetime.combine(target_date, datetime.min.time())

            # Find trading days
            trading_days = df.index.tolist()
            if target_dt in trading_days:
                idx_target = trading_days.index(target_dt)
            else:
                # If earnings fell on a weekend, find the next available trading day
                future_days = [d for d in trading_days if d > target_dt]
                if not future_days:
                    continue
                idx_target = trading_days.index(future_days[0])

            # Calculate base index (T-1, the last trading day before the earnings event)
            idx_prev = idx_target - 1 if idx_target > 0 else 0

            # T+0 (Close on day of/first trading day of earnings)
            idx_t0 = idx_target
            # T+1 (Close next trading day)
            idx_t1 = idx_target + 1 if idx_target + 1 < len(trading_days) else idx_target

            price_prev = df.iloc[idx_prev]['Close']
            price_t0 = df.iloc[idx_t0]['Close']
            price_t1 = df.iloc[idx_t1]['Close']

            # Calculate percentage returns
            return_24h = (price_t0 - price_prev) / price_prev
            return_48h = (price_t1 - price_prev) / price_prev

            update_returns_in_db(ticker, target_date, float(return_24h), float(return_48h))
            print(f"    [✓] Saved: 24h={return_24h:.2%}, 48h={return_48h:.2%}")

        except Exception as e:
            print(f"    [!] Error calculating returns for {ticker}: {e}")

if __name__ == "__main__":
    calculate_returns()