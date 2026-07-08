import sqlite3
import os

DB_PATH = os.path.join("data", "transcripts.db")

def init_db():
    """Initializes the database schema and creates necessary directories."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Pipeline Execution Ledger Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS earnings_calendar (
            ticker TEXT,
            target_date TEXT,
            quarter TEXT,
            status TEXT DEFAULT 'PENDING', -- PENDING, COMPLETED, FAILED_PARSING, NO_TRANSCRIPT
            transcript_url TEXT,
            extracted_at TEXT,
            PRIMARY KEY (ticker, target_date)
        )
    """)

    # 2. Text Data Warehouse Table
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

def seed_mock_data():
    """Seeds the tracking table with data for testing validation tracks."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    test_jobs = [
        ("GS", "2026-04-13", "Q1"),
        ("JPM", "2026-04-11", "Q1")
    ]

    for ticker, target_date, quarter in test_jobs:
        cursor.execute("""
            INSERT OR IGNORE INTO earnings_calendar (ticker, target_date, quarter, status)
            VALUES (?, ?, ?, 'PENDING')
        """, (ticker, target_date, quarter))

    conn.commit()
    conn.close()

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
    print("[*] Initializing storage database file arrays...")
    init_db()
    seed_mock_data()
    print("[✓] Complete.")