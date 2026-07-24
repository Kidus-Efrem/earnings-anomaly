import sys
import os
import re

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scraper.postgres_db import get_pg_connection

QA_MARKERS = [
    r'question-and-answer session', r'questions and answers', r'question & answer session',
    r'we will now (?:be )?taking (?:your )?questions', r'we\'ll now open the (?:line|floor) for questions',
    r'we will now open the (?:line|floor) for questions', r'at this time, (?:we|i) will (?:open|begin) the (?:q&a|question-and-answer)',
    r'q&a session', r'live questions and answers', r'we will now take your questions'
]
PATTERN = re.compile(r'(?:' + '|'.join(QA_MARKERS) + r')', re.IGNORECASE)

def inspect_failed():
    conn = get_pg_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, target_date, transcript_text FROM transcripts_content WHERE transcript_text IS NOT NULL;")
    records = cursor.fetchall()
    cursor.close()
    conn.close()

    failed_count = 0
    for ticker, target_date, text in records:
        if not PATTERN.search(text):
            failed_count += 1
            if failed_count <= 3: # Print the first 3 failures
                print(f"\n{'='*60}")
                print(f"FAILED: {ticker} | {target_date}")
                print(f"{'='*60}")
                # Print the last 800 characters to see how the article ends
                print("TAIL (Last 800 chars):")
                print(text[-800:].replace('\n', '\n'))
                print("\n")

if __name__ == "__main__":
    inspect_failed()