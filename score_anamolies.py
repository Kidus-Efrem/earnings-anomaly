# score_anomalies.py
import os
import sqlite3
import re
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

DB_PATH = os.path.join("data", "transcripts.db")

# Initialize FinBERT
MODEL_NAME = "ProsusAI/finbert"
print("[*] Initializing FinBERT Transformer model context...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)

def ensure_nlp_columns_exist():
    """Alters the database tables to support NLP segmented text and anomaly scoring."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check transcripts_content table
    cursor.execute("PRAGMA table_info(transcripts_content)")
    content_columns = [col[1] for col in cursor.fetchall()]

    if "presentation_text" not in content_columns:
        cursor.execute("ALTER TABLE transcripts_content ADD COLUMN presentation_text TEXT")
        print("[*] Added column presentation_text to transcripts_content")
    if "qa_text" not in content_columns:
        cursor.execute("ALTER TABLE transcripts_content ADD COLUMN qa_text TEXT")
        print("[*] Added column qa_text to transcripts_content")

    # Check earnings_calendar table
    cursor.execute("PRAGMA table_info(earnings_calendar)")
    calendar_columns = [col[1] for col in cursor.fetchall()]

    if "anomaly_score" not in calendar_columns:
        cursor.execute("ALTER TABLE earnings_calendar ADD COLUMN anomaly_score REAL")
        print("[*] Added column anomaly_score to earnings_calendar")

    conn.commit()
    conn.close()

def split_transcript(text):
    """Slices raw transcript into formal presentation and Q&A blocks."""
    presentation_keywords = ["prepared remarks", "presentation", "safe harbor", "formal remarks"]
    qa_keywords = ["question-and-answer session", "q&a", "questions and answers", "questions and remarks"]

    text_lower = text.lower()
    qa_start = -1

    for kw in qa_keywords:
        pos = text_lower.find(kw)
        if pos != -1:
            qa_start = pos
            break

    if qa_start != -1:
        presentation = text[:qa_start]
        qa = text[qa_start:]
    else:
        presentation = text
        qa = ""

    return presentation, qa

def get_sentiment_score(text):
    """Calculates weighted sentiment using FinBERT."""
    if not text.strip():
        return 0.0

    # Limit token length per processing chunk to prevent memory blowout (max 512 tokens)
    chunks = [text[i:i+1200] for i in range(0, min(len(text), 12000), 1200)]
    scores = []

    for chunk in chunks:
        inputs = tokenizer(chunk, return_tensors="pt", truncation=True, max_length=512)
        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
            # FinBERT labels: [positive (0), negative (1), neutral (2)]
            # Anomaly Formula: Positive - Negative sentiment
            score = (probs[0][0] - probs[0][1]).item()
            scores.append(score)

    return sum(scores) / len(scores) if scores else 0.0

def process_anomalies():
    ensure_nlp_columns_exist()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Fetch completed records that do not have anomaly scores calculated yet
    cursor.execute("""
        SELECT tc.ticker, tc.target_date, tc.transcript_text
        FROM transcripts_content tc
        JOIN earnings_calendar ec ON tc.ticker = ec.ticker AND tc.target_date = ec.target_date
        WHERE ec.status = 'COMPLETED' AND (ec.anomaly_score IS NULL OR tc.presentation_text IS NULL)
    """)
    records = cursor.fetchall()

    if not records:
        print("[✓] All transcripts are already processed and scored.")
        conn.close()
        return

    print(f"[*] Processing deep-learning sentiment evaluation for {len(records)} transcripts...")

    for ticker, date_str, raw_text in records:
        try:
            # 1. Structural Text Slicing
            pres_text, qa_text = split_transcript(raw_text)

            # 2. Extract Sentiment Metrics
            pres_score = get_sentiment_score(pres_text)
            qa_score = get_sentiment_score(qa_text) if qa_text else pres_score

            # Delta shows discrepancy between scripted optimism vs unscripted stress
            anomaly_metric = abs(pres_score - qa_score)

            # 3. Store structures back to DB
            cursor.execute("""
                UPDATE transcripts_content
                SET presentation_text = ?, qa_text = ?
                WHERE ticker = ? AND target_date = ?
            """, (pres_text, qa_text, ticker, date_str))

            cursor.execute("""
                UPDATE earnings_calendar
                SET anomaly_score = ?
                WHERE ticker = ? AND target_date = ?
            """, (anomaly_metric, ticker, date_str))

            print(f"  [🧠] {ticker} [{date_str}] Sentiment Delta (Anomaly): {anomaly_metric:.4f}")

        except Exception as e:
            print(f"  [!] Error scoring {ticker} on {date_str}: {e}")

    conn.commit()
    conn.close()
    print("[✓] Deep learning anomaly run complete.")

if __name__ == "__main__":
    process_anomalies()