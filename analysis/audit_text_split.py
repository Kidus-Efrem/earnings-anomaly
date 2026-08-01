import re
import sys
import os
import random
from collections import Counter

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scraper.postgres_db import get_pg_connection

# The exact same markers we are planning to use
QA_MARKERS = [
    # 1. The "Golden Handoff" Phrases (Found in 100% of your Motley Fool samples)
    r'open\s+the\s+call\s+up\s+for\s+questions',
    r'open\s+it\s+up\s+for\s+(?:your\s+)?questions',
    r'open\s+it\s+up\s+to\s+(?:your\s+)?questions',
    r'open\s+the\s+line\s+for\s+questions',
    r'let\'s\s+(?:now\s+)?go\s+to\s+questions',

    # 2. Standard Operator Phrases (Fixed-width negative lookbehinds to avoid the "concludes" trap)
    r'(?<!concludes the )question-and-answer session\b',
    r'(?<!concludes our )question-and-answer session\b',
    r'(?<!concludes the )q&a session\b',
    r'(?<!concludes our )q&a session\b',

    r'we\s+will\s+now\s+(?:be\s+)?taking\s+(?:your\s+)?questions\b',
    r'we\'ll\s+now\s+open\s+the\s+(?:line|floor)\s+for\s+questions\b',
    r'at\s+this\s+time,\s+(?:we|i)\s+will\s+(?:open|begin)\s+the\s+(?:q&a|question-and-answer)\b',
    r'begin\s+(?:the\s+)?q&a\b',
    r'start\s+(?:the\s+)?q&a\b'
]
PATTERN = re.compile(r'(?:' + '|'.join(QA_MARKERS) + r')', re.IGNORECASE)

def audit_transcripts():
    conn = get_pg_connection()
    cursor = conn.cursor()

    print("Fetching transcripts for audit...")
    cursor.execute("SELECT ticker, target_date, transcript_text FROM transcripts_content WHERE transcript_text IS NOT NULL;")
    records = cursor.fetchall()
    cursor.close()
    conn.close()

    total = len(records)
    print(f"Loaded {total} transcripts.\n")

    matched_count = 0
    unmatched_examples = []
    matched_examples = []
    matched_markers = Counter()

    for ticker, target_date, text in records:
        match = PATTERN.search(text)

        if match:
            matched_count += 1
            # Record which specific phrase triggered the match
            matched_markers[match.group()] += 1

            # Save a few examples of successful splits for visual inspection
            if len(matched_examples) < 3:
                start_idx = max(0, match.start() - 40)
                end_idx = min(len(text), match.end() + 40)
                context = text[start_idx:end_idx].replace('\n', ' ')
                matched_examples.append((ticker, target_date, match.group(), context))
        else:
            # Save examples of failures to see what the messy text looks like
            if len(unmatched_examples) < 3:
                snippet = text[:200].replace('\n', ' ')
                unmatched_examples.append((ticker, target_date, snippet))

    # ==========================================
    # PRINT THE AUDIT REPORT
    # ==========================================
    print("="*50)
    print("📊 TEXT SPLIT AUDIT REPORT")
    print("="*50)

    success_rate = (matched_count / total) * 100 if total > 0 else 0
    print(f"Total Transcripts: {total}")
    print(f"Successfully Split: {matched_count} ({success_rate:.1f}%)")
    print(f"Failed to Split:    {total - matched_count} ({100 - success_rate:.1f}%)")

    print("\n🏆 Most Common Markers Triggered:")
    for marker, count in matched_markers.most_common(5):
        print(f"  - '{marker}': {count} times")

    print("\n✅ EXAMPLES OF SUCCESSFUL SPLITS (Context around the match):")
    for ticker, date, marker, context in matched_examples:
        print(f"\n[{ticker} | {date}] Matched: '{marker}'")
        print(f"Context: ...{context}...")

    print("\n❌ EXAMPLES OF FAILED SPLITS (First 200 chars of text):")
    if not unmatched_examples:
        print("  (None! Every transcript was successfully split.)")
    else:
        for ticker, date, snippet in unmatched_examples:
            print(f"\n[{ticker} | {date}]")
            print(f"Snippet: {snippet}...")

    print("\n" + "="*50)

if __name__ == "__main__":
    audit_transcripts()