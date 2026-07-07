import os
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import psycopg2
from dotenv import load_dotenv

# 1. Load context from root .env file
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("CRITICAL ERROR: DATABASE_URL not found in your environment. Verify your root .env configuration.")


def get_or_create_company(cur, ticker: str) -> int:
    """
    Ensures the target ticker is anchored in the companies table
    and returns its primary key ID to satisfy foreign key constraints.
    """
    ticker = ticker.upper()
    cur.execute("""
        INSERT INTO companies (ticker, name)
        VALUES (%s, %s)
        ON CONFLICT (ticker) DO UPDATE SET ticker = EXCLUDED.ticker
        RETURNING id;
    """, (ticker, f"{ticker} Inc."))
    return cur.fetchone()[0]


def parse_and_store_transcript(ticker: str, call_date_str: str, url: str):
    """
    Scrapes the Motley Fool transcript page, splits content into prepared remarks
    vs Q&A, attributes conversations line-by-line to structured speaker arrays,
    and commits the pipeline atomically to PostgreSQL.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print(f"Scraping HTML: {url}")
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        raw_html = resp.text
    except Exception as e:
        print(f" [ERROR] Network download failed for {url}: {e}")
        return

    # Extract clean text arrays via BeautifulSoup elements
    soup = BeautifulSoup(raw_html, 'html.parser')
    body_container = soup.find('div', class_='tailwind-article-body') or soup.find('div', class_='article-body')

    if not body_container:
        print(f" [ERROR] Could not isolate main text block container inside webpage layouts for {url}")
        return

    paragraphs = [p.get_text().strip() for p in body_container.find_all('p') if p.get_text().strip()]
    full_text = "\n\n".join(paragraphs)

    if not paragraphs:
        print(" [ERROR] Parsing extracted an empty body block array.")
        return

    # Extract Fiscal Quarter context from page titles
    fiscal_quarter = "Unknown"
    title_text = soup.find('h1')
    if title_text:
        match = re.search(r'(Q[1-4]\s?\d{4})', title_text.get_text())
        if match:
            fiscal_quarter = match.group(1).replace(" ", "")

    # Slice raw lists between Prepared Executive Presentations vs Analyst Q&A
    qa_start_idx = None
    prepared_remarks_list = []
    qa_list = []

    for idx, p_text in enumerate(paragraphs):
        if "questions and answers" in p_text.lower() or "question-and-answer" in p_text.lower():
            qa_start_idx = idx
            break

    if qa_start_idx is not None:
        prepared_remarks_list = paragraphs[:qa_start_idx]
        qa_list = paragraphs[qa_start_idx + 1:]
    else:
        prepared_remarks_list = paragraphs

    qa_text = "\n\n".join(qa_list) if qa_list else ""

    # --- Robust Speaker Ingestion Pass ---
    speaker_data = {}
    current_speaker = None

    # Track known company executives from the top summary checklist if present
    executive_registry = set()
    role_mapping = {}

    # First pass: Identify metadata roles at the top of the article summary
    meta_pattern = re.compile(r'[-\u2014\u2013]\s*([A-Za-z\s,\/\d]+)\s+[\u2014\u2013-]\s+([A-Z][a-zA-Z\s\.\-\’]+)')
    for p_text in paragraphs[:20]:
        meta_match = meta_pattern.search(p_text)
        if meta_match:
            role, name = meta_match.group(1).strip(), meta_match.group(2).strip()
            role_mapping[name] = role
            executive_registry.add(name)

    # Second pass: Process actual spoken dialogue paragraphs with "Speaker Name:" pattern
    analyst_keywords = ['analyst', 'research', 'capital', 'management', 'bank', 'securities', 'investments']

    for p_text in paragraphs:
        # Check for clean "Speaker Name:" prefix markers
        if ":" in p_text and len(p_text.split(":")[0]) < 50:
            potential_speaker, utterance_text = p_text.split(":", 1)
            potential_speaker = potential_speaker.replace("**", "").replace("*", "").strip()

            # Verify clean proper title/name casing structure
            if re.match(r'^[A-Z][a-zA-Z\s\.\-\’\d]+$', potential_speaker):
                current_speaker = potential_speaker
                utterance_text = utterance_text.strip()

                if current_speaker not in speaker_data:
                    role = role_mapping.get(current_speaker, "Participant" if "operator" not in current_speaker.lower() else "Operator")
                    is_exec = current_speaker in executive_registry or not any(w in role.lower() for w in analyst_keywords)

                    if "operator" in current_speaker.lower():
                        is_exec = False

                    speaker_data[current_speaker] = {
                        "role": role,
                        "is_executive": is_exec,
                        "utterances": []
                    }

                if utterance_text:
                    speaker_data[current_speaker]["utterances"].append(utterance_text)
                continue

        # Continuation block attribution
        if current_speaker and current_speaker in speaker_data:
            speaker_data[current_speaker]["utterances"].append(p_text)

    # 4. Atomic PostgreSQL ingestion transaction block
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Pull parent foreign key structural link
        company_id = get_or_create_company(cur, ticker)

        # Populate principal transcript matrix row
        cur.execute("""
            INSERT INTO transcripts (company_id, call_date, fiscal_quarter, raw_html, full_text, qa_text, qa_start_index, source_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (company_id, call_date_str, fiscal_quarter, raw_html, full_text, qa_text, qa_start_idx, url))

        transcript_id = cur.fetchone()[0]

        # Inject sequential tracking records for conversation structures
        for s_name, s_info in speaker_data.items():
            combined_utterances = s_info["utterances"]
            if not combined_utterances:
                continue

            total_word_count = sum(len(utt.split()) for utt in combined_utterances)

            cur.execute("""
                INSERT INTO speakers (transcript_id, name, role, is_executive, utterances, word_count)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (transcript_id, s_name, s_info["role"], s_info["is_executive"], combined_utterances, total_word_count))

        conn.commit()
        print(f" [SUCCESS] Atomic transaction committed for {ticker} ({fiscal_quarter}). Ingestion complete.")

    except Exception as e:
        if 'conn' in locals() and conn:
            conn.rollback()
        print(f" [DATABASE ROLLBACK] Transaction aborted due to ingestion crash: {e}")
    finally:
        if 'cur' in locals() and cur:
            cur.close()
        if 'conn' in locals() and conn:
            conn.close()


# Runtime Execution Hook
if __name__ == "__main__":
    test_url = "https://www.fool.com/earnings/call-transcripts/2026/04/13/goldman-sachs-gs-q1-2026-earnings-transcript/"
    test_date = "2026-04-13"

    parse_and_store_transcript("GS", test_date, test_url)