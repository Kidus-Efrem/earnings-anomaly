import re
import sys
import os
import nltk
import torch
import psycopg2
from psycopg2.extras import execute_values
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# Dynamically add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scraper.postgres_db import get_pg_connection

# Ensure NLTK sentence tokenizer data is downloaded
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)

# ==========================================
# 1. THE BULLETPROOF REGEX SPLITTER
# ==========================================
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

def split_transcript(text):
    """
    Splits transcript into prepared remarks and Q&A.
    Returns: (prepared_text, qa_text, is_verbatim)
    """
    if not text:
        return "", "", False

    match = PATTERN.search(text)

    if match:
        split_index = match.start()
        prepared_text = text[:split_index].strip()
        qa_text = text[split_index:].strip()
        return prepared_text, qa_text, True # True = Verbatim transcript

    # If no match, it's likely a Motley Fool summary article.
    return text.strip(), "", False # False = Not verbatim

# ==========================================
# 2. FINBERT INFERENCE (Optimized for 4GB GPU)
# ==========================================
MODEL_NAME = "ProsusAI/finbert"
print("Loading FinBERT model (using safetensors to bypass torch.load vulnerability block)...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, use_safetensors=True)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()
print(f"Model loaded successfully on {device}.")

def get_section_polarity(text):
    """Calculates the average sentiment polarity of a text section."""
    if not text or len(text.strip()) < 10:
        return 0.0

    sentences = nltk.sent_tokenize(text)
    if not sentences:
        return 0.0

    pos_score = 0.0
    neg_score = 0.0
    valid_sentences = 0

    # Process in small batches to prevent 4GB VRAM OOM
    batch_size = 8
    for i in range(0, len(sentences), batch_size):
        batch_sentences = sentences[i:i+batch_size]

        inputs = tokenizer(
            batch_sentences,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt"
        ).to(device)

        with torch.no_grad():
            # FP16 Mixed Precision for speed and memory efficiency
            with torch.amp.autocast(device_type="cuda"):
                outputs = model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits, dim=-1)

            # ProsusAI/finbert labels: [positive, negative, neutral]
            pos_score += probs[:, 0].sum().item()
            neg_score += probs[:, 1].sum().item()
            valid_sentences += len(batch_sentences)

        # Clear VRAM cache to prevent leaks over 1000+ transcripts
        del inputs, outputs, probs
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    if valid_sentences == 0:
        return 0.0

    avg_pos = pos_score / valid_sentences
    avg_neg = neg_score / valid_sentences

    # Polarity = Positive % - Negative %
    return avg_pos - avg_neg

# ==========================================
# 3. MAIN EXECUTION & DB UPDATE
# ==========================================
def process_divergence():
    conn = get_pg_connection()
    cursor = conn.cursor()

    query = """
        SELECT ticker, target_date, transcript_text
        FROM transcripts_content
        WHERE transcript_text IS NOT NULL;
    """
    print("Fetching transcripts from database...")
    cursor.execute(query)
    records = cursor.fetchall()
    print(f"Found {len(records)} total transcripts.")

    updates_to_batch = []
    skipped_summaries = 0
    processed_verbatim = 0

    for ticker, target_date, raw_text in tqdm(records, desc="Processing Divergence"):
        prepared_text, qa_text, is_verbatim = split_transcript(raw_text)

        # THE SENIOR ENGINEER FIX: Skip Motley Fool summary articles to prevent data corruption
        if not is_verbatim:
            skipped_summaries += 1
            continue

        processed_verbatim += 1

        # Run GPU inference on the cleanly split sections
        prep_pol = get_section_polarity(prepared_text)
        qa_pol = get_section_polarity(qa_text)

        div_score = prep_pol - qa_pol

        # Include the actual text in the batch for database storage
        updates_to_batch.append((
            prep_pol, qa_pol, div_score,
            prepared_text, qa_text,
            ticker, target_date
        ))

        # Flush every 50 to keep memory low and save progress
        if len(updates_to_batch) >= 50:
            flush_to_db(cursor, updates_to_batch)
            conn.commit()
            updates_to_batch = []

    # Flush any remaining records
    if updates_to_batch:
        flush_to_db(cursor, updates_to_batch)
        conn.commit()

    cursor.close()
    conn.close()

    print("\n" + "="*50)
    print("✅ DIVERGENCE CALCULATION COMPLETE!")
    print(f"Processed (Verbatim): {processed_verbatim}")
    print(f"Skipped (Summaries):  {skipped_summaries}")
    print("="*50)

def flush_to_db(cursor, batch):
    # 1. Update the numerical scores in transcript_sentiment
    score_query = """
        UPDATE transcript_sentiment AS ts
        SET prepared_polarity = data.prepared_polarity,
            qa_polarity = data.qa_polarity,
            divergence_score = data.divergence_score
        FROM (VALUES %s) AS data(prepared_polarity, qa_polarity, divergence_score, prepared_text, qa_text, ticker, target_date)
        WHERE ts.ticker = data.ticker
          AND ts.target_date = data.target_date;
    """
    execute_values(cursor, score_query, batch)

    # 2. Update the actual split text in transcripts_content
    text_query = """
        UPDATE transcripts_content AS tc
        SET prepared_text = data.prepared_text,
            qa_text = data.qa_text
        FROM (VALUES %s) AS data(prepared_polarity, qa_polarity, divergence_score, prepared_text, qa_text, ticker, target_date)
        WHERE tc.ticker = data.ticker
          AND tc.target_date = data.target_date;
    """
    execute_values(cursor, text_query, batch)

if __name__ == "__main__":
    process_divergence()