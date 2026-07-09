import sqlite3
import os

DB_PATH = os.path.join("data", "transcripts.db")

def inspect_database():
    if not os.path.exists(DB_PATH):
        print(f"[!] Database file not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Check aggregate stats
    cursor.execute("SELECT status, COUNT(*) FROM earnings_calendar GROUP BY status")
    stats = cursor.fetchall()
    print("\n=== PIPELINE STATUS METRICS ===")
    for status, count in stats:
        print(f"  {status}: {count} records")

    # 2. Pull the most recent successfully scraped transcripts
    cursor.execute("""
        SELECT c.ticker, c.target_date, length(t.transcript_text) as chars, substr(t.transcript_text, 1, 150)
        FROM earnings_calendar c
        JOIN transcripts_content t ON c.ticker = t.ticker AND c.target_date = t.target_date
        WHERE c.status = 'COMPLETED'
        LIMIT 10

    """)
    rows = cursor.fetchall()

    print("\n=== RECENTLY SCRAPED TRANSCRIPTS (SAMPLE) ===")
    if not rows:
        print("  No completed transcripts found yet. Wait for the scraper to finish a few!")
    for ticker, date, char_count, snippet in rows:
        clean_snippet = snippet.replace('\n', ' ')
        print(f"[{ticker} | {date}] ({char_count} chars) -> \"{clean_snippet}...\"")
        print("-" * 60)

    conn.close()

if __name__ == "__main__":
    inspect_database()