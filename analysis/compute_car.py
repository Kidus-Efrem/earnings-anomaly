import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pandas as pd
import yfinance as yf
from psycopg2.extras import execute_values
from scraper.postgres_db import get_pg_connection

def update_market_adjusted_returns():
    conn = get_pg_connection()
    cursor = conn.cursor()

    # 1. Pull all earnings dates
    query = "SELECT ticker, target_date, return_24h, return_48h FROM earnings_calendar WHERE return_24h IS NOT NULL;"
    df = pd.read_sql(query, conn)
    if df.empty:
        print("No records found to calculate CAR.")
        return

    min_date = df['target_date'].min().strftime('%Y-%m-%d')
    max_date = (df['target_date'].max() + pd.Timedelta(days=7)).strftime('%Y-%m-%d')

     # 2. Fetch SPY benchmark data
    print(f"Fetching SPY data from {min_date} to {max_date}...")
    spy = yf.Ticker("SPY").history(start=min_date, end=max_date)
    spy_returns = spy['Close'].pct_change().dropna()

    # --- THE FIX ---
    # yfinance returns timezone-aware timestamps (America/New_York).
    # Your database dates are timezone-naive. Pandas refuses to compare them.
    # We strip the timezone from the yfinance index to make them compatible.
    if spy_returns.index.tz is not None:
        spy_returns.index = spy_returns.index.tz_localize(None)
    # ---------------

    print("Calculating Cumulative Abnormal Returns (CAR)...")

    # Note: This logic assumes After-Market-Close (AMC) earnings.
    # If BMO, we would include the current day's return.

    updates_to_batch = []

    for _, row in df.iterrows():
        date = pd.Timestamp(row['target_date'])
        ticker = row['ticker']

        # Find the next 2 valid trading days following the earnings date
        spy_slice = spy_returns[spy_returns.index > date].head(2)

        if len(spy_slice) == 2:
            spy_24h = spy_slice.iloc[0]
            # Compound the 2-day return for the 48h benchmark
            spy_48h = (1 + spy_24h) * (1 + spy_slice.iloc[1]) - 1

            car_24h = float(row['return_24h'] - spy_24h)
            car_48h = float(row['return_48h'] - spy_48h)

            # Add to batch instead of executing immediately
            updates_to_batch.append((car_24h, car_48h, ticker, row['target_date']))

    # 3. BATCH UPDATE (The Senior Engineer Move)
    if updates_to_batch:
        update_query = """
            UPDATE earnings_calendar
            SET car_24h = data.car_24h, car_48h = data.car_48h
            FROM (VALUES %s) AS data(car_24h, car_48h, ticker, target_date)
            WHERE earnings_calendar.ticker = data.ticker
              AND earnings_calendar.target_date = data.target_date;
        """
        execute_values(cursor, update_query, updates_to_batch)
        conn.commit()
        print(f"Successfully batch-updated CAR for {len(updates_to_batch)} rows.")
    else:
        print("No valid CAR calculations to update.")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    update_market_adjusted_returns()