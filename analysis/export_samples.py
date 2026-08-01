import sys
import os
import re

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scraper.postgres_db import get_pg_connection

def export_clean_samples():
    conn = get_pg_connection()
    cursor = conn.cursor()

    # Grab 5 random transcripts
    cursor.execute("""
        SELECT ticker, target_date, transcript_text
        FROM transcripts_content
        WHERE transcript_text IS NOT NULL
        ORDER BY RANDOM()
        LIMIT 5;
    """)
    records = cursor.fetchall()
    cursor.close()
    conn.close()

    # The regex to kill the Motley Fool footer
    footer_pattern = re.compile(r'(?:assume any responsibility for your use|The Motley Fool has (?:positions in and recommends|no position in)).*', re.IGNORECASE | re.DOTALL)

    output_path = os.path.join(project_root, "analysis", "sample_transcripts.txt")

    with open(output_path, "w", encoding="utf-8") as f:
        for ticker, target_date, text in records:
            # Strip the footer
            clean_text = footer_pattern.split(text)[0].strip()

            f.write(f"\n{'='*80}\n")
            f.write(f"TICKER: {ticker} | DATE: {target_date}\n")
            f.write(f"{'='*80}\n")
            f.write(clean_text)
            f.write("\n\n")

    print(f"✅ Exported 5 clean transcripts to: {output_path}")
    print("Open this file in your text editor and look for the transition from Prepared Remarks to Q&A.")

if __name__ == "__main__":
    export_clean_samples()
	