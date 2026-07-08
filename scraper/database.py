import sqlite3
import os

DB_PATH = os.path.join("data", "transcripts.db")

def init_db():
    """Initializes the database schema with exact market-data alignment fields."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Upgraded Pipeline Execution Ledger
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS earnings_calendar (
            ticker TEXT,
            target_date TEXT,          -- YYYY-MM-DD
            cik TEXT,                  -- SEC Central Index Key (vital for matching macro/market data)
            quarter TEXT,              -- e.g., Q1, Q2 (Named 'quarter' to match previous pipeline code)
            fiscal_year INTEGER,       -- e.g., 2026
            time_of_day TEXT DEFAULT 'UNKNOWN', -- BMO (Before Market Open), AMC (After Market Close), or UNKNOWN
            transcript_url TEXT,
            status TEXT DEFAULT 'PENDING',
            extracted_at TEXT,
            PRIMARY KEY (ticker, target_date)
        )
    """)

    # Text Data Warehouse Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transcripts_content (
            ticker TEXT,
            target_date TEXT,
            transcript_text TEXT,
            char_count INTEGER,
            PRIMARY KEY (ticker, target_date),
            FOREIGN KEY(ticker, target_date) REFERENCES earnings_calendar(ticker, target_date)
        )
    """)
    conn.commit()
    conn.close()
    print("[✓] Database schema initialized with market alignment fields.")

def get_pending_jobs():
    """Fetches remaining active task targets."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, target_date FROM earnings_calendar WHERE status = 'PENDING'")
    jobs = [{"ticker": row[0], "date": row[1]} for row in cursor.fetchall()]
    conn.close()
    return jobs

def update_job_status(ticker: str, target_date: str, status: str, url: str = None):
    """Updates status codes inside the execution tracker ledger logs."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE earnings_calendar
        SET status = ?, transcript_url = ?, extracted_at = datetime('now')
        WHERE ticker = ? AND target_date = ?
    """, (status, url, ticker, target_date))
    conn.commit()
    conn.close()

def save_transcript_content(ticker: str, target_date: str, text: str):
    """Stores the extracted text components inside the storage schema warehouses."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO transcripts_content (ticker, target_date, transcript_text, char_count)
        VALUES (?, ?, ?, ?)
    """, (ticker, target_date, text, len(text)))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()