# postgres_db.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_pg_connection():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return psycopg2.connect(db_url)
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "password"),
        dbname=os.getenv("PGDATABASE", "transcripts_warehouse")
    )

def init_pg_db():
    """Initializes the production Postgres database schema layout."""
    conn = get_pg_connection()
    cursor = conn.cursor()

    # 1. Core Execution Ledger
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS earnings_calendar (
            ticker VARCHAR(12),
            target_date DATE,
            cik VARCHAR(20),
            quarter VARCHAR(4),
            fiscal_year INT,
            time_of_day VARCHAR(20) DEFAULT 'UNKNOWN',
            transcript_url TEXT,
            status VARCHAR(30) DEFAULT 'PENDING',
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            return_24h REAL,
            return_48h REAL,
            anomaly_score REAL,
            PRIMARY KEY (ticker, target_date)
        );
    """)

    # 2. Text Component Warehouse
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transcripts_content (
            ticker VARCHAR(12),
            target_date DATE,
            transcript_text TEXT,
            char_count INT,
            presentation_text TEXT,
            qa_text TEXT,
            PRIMARY KEY (ticker, target_date),
            FOREIGN KEY (ticker, target_date) REFERENCES earnings_calendar(ticker, target_date) ON DELETE CASCADE
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("[✓] PostgreSQL schema verified and fully initialized.")

def get_pending_jobs():
    conn = get_pg_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT ticker, to_char(target_date, 'YYYY-MM-DD') as date
        FROM earnings_calendar
        WHERE status = 'PENDING'
    """)
    jobs = [{"ticker": row["ticker"], "date": row["date"]} for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return jobs

def update_job_status(ticker: str, target_date: str, status: str, url: str = None):
    """Saves pipeline progression metrics back into your PostgreSQL state engine."""
    conn = get_pg_connection()
    cursor = conn.cursor()

    # 1. Force add the column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE earnings_calendar ADD COLUMN IF NOT EXISTS transcript_url VARCHAR(500);")
        conn.commit()
    except Exception:
        conn.rollback()

    # 2. Explicitly bind by name so psycopg2 cannot mismatch positions
    query = """
        UPDATE earnings_calendar
        SET
            status = %(status)s,
            transcript_url = COALESCE(%(url)s, transcript_url)
        WHERE
            ticker = %(ticker)s
            AND target_date = %(target_date)s::DATE;
    """

    try:
        cursor.execute(query, {
            "status": status[:20],  # Hard limit status string to 20 chars just in case
            "url": url,             # Goes straight to the newly added VARCHAR(500) column
            "ticker": ticker,
            "target_date": target_date
        })
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

def save_transcript_content(ticker: str, target_date: str, text: str):
    conn = get_pg_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transcripts_content (ticker, target_date, transcript_text, char_count)
        VALUES (%s, %s::DATE, %s, %s)
        ON CONFLICT (ticker, target_date)
        DO UPDATE SET transcript_text = EXCLUDED.transcript_text, char_count = EXCLUDED.char_count
    """, (ticker, target_date, text, len(text)))
    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    init_pg_db()