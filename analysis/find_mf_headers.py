import sys
import os
import re

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scraper.postgres_db import get_pg_connection

def find_mf_headers():
    conn = get_pg_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, target_date, transcript_text FROM transcripts_content WHERE transcript_text IS NOT NULL;")
    records = cursor.fetchall()
    cursor.close()
    conn.close()

    # Look for ACTUAL structural headers, not the word "question" in a sentence
    mf_headers = [
        r'motley fool transcribers',
        r'#+\s*questions and answers',
        r'#+\s*q&a',
        r'\*\*questions and answers\*\*',
        r'\*\*q&a\*\*'
    ]

    pattern = re.compile(r'(?:' + '|'.join(mf_headers) + r')', re.IGNORECASE)

    found_count = 0
    for ticker, target_date, text in records:
        match = pattern.search(text)
        if match:
            found_count += 1
            if found_count <= 3:
                print(f"\n{'='*60}")
                print(f"FOUND HEADER: {ticker} | {target_date}")
                print(f"Matched: '{match.group()}'")
                print(f"{'='*60}")
                # Print 300 chars before and after to see the structure
                start_idx = max(0, match.start() - 300)
                end_idx = min(len(text), match.end() + 300)
                print(text[start_idx:end_idx].replace('\n', '\n> '))
                print("\n")

    print(f"\nTotal transcripts with clear structural headers: {found_count} / {len(records)}")

if __name__ == "__main__":
    find_mf_headers()