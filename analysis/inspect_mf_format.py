import sys
import os
import re

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scraper.postgres_db import get_pg_connection

def inspect_mf_format():
    conn = get_pg_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker, target_date, transcript_text FROM transcripts_content WHERE transcript_text IS NOT NULL;")
    records = cursor.fetchall()
    cursor.close()
    conn.close()

    # Let's look for common Motley Fool Q&A patterns
    mf_patterns = [
        r'#+\s*q&a',                  # ## Q&A or ### Q&A
        r'#+\s*questions and answers', # ## Questions and Answers
        r'\*\*q:\*\*',                # **Q:**
        r'\*\*a:\*\*',                # **A:**
        r'question:\s',               # Question:
        r'answer:\s'                  # Answer:
    ]

    pattern = re.compile(r'(?:' + '|'.join(mf_patterns) + r')', re.IGNORECASE)

    found_count = 0
    for ticker, target_date, text in records:
        match = pattern.search(text)
        if match:
            found_count += 1
            if found_count <= 3: # Print the first 3 successes
                print(f"\n{'='*60}")
                print(f"FOUND Q&A FORMAT: {ticker} | {target_date}")
                print(f"Matched: '{match.group()}'")
                print(f"{'='*60}")

                # Print 600 characters BEFORE and AFTER the match to see the structure
                start_idx = max(0, match.start() - 600)
                end_idx = min(len(text), match.end() + 600)
                context = text[start_idx:end_idx]

                # Clean up newlines for readable terminal output
                print(context.replace('\n', '\n> '))
                print("\n")

    print(f"\nTotal transcripts with Motley Fool Q&A markers: {found_count} / {len(records)}")

if __name__ == "__main__":
    inspect_mf_format()