import os
import torch
import nltk
from nltk.tokenize import sent_tokenize
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from postgres_db import get_pg_connection

# Download the sentence tokenizer if not already present
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt_tab')

# Use GPU (CUDA) if available, otherwise CPU
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# Load FinBERT Model & Tokenizer
# We use use_safetensors=True to load the modern, secure tensor format.
# This bypasses the CVE-2025-32434 PyTorch vulnerability check.
print("Loading FinBERT from Hugging Face...")
tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
model = AutoModelForSequenceClassification.from_pretrained(
    "ProsusAI/finbert",
    use_safetensors=True
).to(device)
model.eval() # Set model to evaluation mode

def get_unprocessed_transcripts():
    """Fetches transcripts that do not have sentiment scores calculated yet."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tc.ticker, tc.target_date, tc.transcript_text
        FROM transcripts_content tc
        LEFT JOIN transcript_sentiment ts
          ON tc.ticker = ts.ticker AND tc.target_date = ts.target_date
        WHERE ts.sentiment_polarity IS NULL;
    """)
    records = [{"ticker": row[0], "date": row[1], "text": row[2]} for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return records

def save_sentiment_to_db(ticker, target_date, pos, neg, neu, polarity):
    """Saves raw sentiment calculations back to the database."""
    conn = get_pg_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO transcript_sentiment (ticker, target_date, positive_score, negative_score, neutral_score, sentiment_polarity)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, target_date)
            DO UPDATE SET
                positive_score = EXCLUDED.positive_score,
                negative_score = EXCLUDED.negative_score,
                neutral_score = EXCLUDED.neutral_score,
                sentiment_polarity = EXCLUDED.sentiment_polarity;
        """, (ticker, target_date, pos, neg, neu, polarity))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"    [!] Database write error for {ticker}: {e}")
    finally:
        cursor.close()
        conn.close()

def analyze_transcript(text):
    """Tokenizes text into sentences, runs FinBERT in mini-batches, and aggregates sentiment."""
    # Split the long transcript into clean, individual sentences
    sentences = sent_tokenize(text)

    # Filter out empty strings or very short artifacts (less than 15 characters)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 15]

    if not sentences:
        return 0.0, 0.0, 1.0, 0.0  # Default to Neutral if empty

    all_probs = []
    batch_size = 16 # Safe batch size for 4GB VRAM

    for i in range(0, len(sentences), batch_size):
        batch = sentences[i:i + batch_size]

        # Tokenize batch with truncation to handle maximum length of 512 tokens
        inputs = tokenizer(batch, padding=True, truncation=True, max_length=512, return_tensors="pt").to(device)

        with torch.no_grad():
            # Use autocast to execute in FP16 (speeds up your GTX 1650 & halves VRAM usage)
            with torch.amp.autocast(device_type="cuda" if "cuda" in device else "cpu"):
                outputs = model(**inputs)

            # Apply softmax to calculate probabilities for each class (Positive, Negative, Neutral)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1).cpu().numpy()
            all_probs.extend(probs)

    # Calculate average probability scores across all sentences in the transcript
    avg_scores = torch.tensor(all_probs).mean(dim=0).tolist()
    pos, neg, neu = avg_scores[0], avg_scores[1], avg_scores[2]

    # Polar sentiment score formula: Positive prob - Negative prob
    polarity = pos - neg
    return pos, neg, neu, polarity

def main():
    records = get_unprocessed_transcripts()
    print(f"Found {len(records)} transcripts waiting for FinBERT analysis.")

    for idx, record in enumerate(records):
        ticker = record["ticker"]
        target_date = record["date"]
        text = record["text"]

        print(f"[{idx+1}/{len(records)}] Analyzing {ticker} ({target_date})... Sentences: ~{len(text)//100}")
        try:
            pos, neg, neu, polarity = analyze_transcript(text)
            save_sentiment_to_db(ticker, target_date, pos, neg, neu, polarity)
            print(f"    [✓] Result: Polarity = {polarity:+.4f} (Pos: {pos:.2f}, Neg: {neg:.2f})")
        except Exception as e:
            print(f"    [!] Error processing {ticker} on {target_date}: {e}")
        finally:
            # Clean up GPU memory pool to prevent memory leaks over long loops
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

if __name__ == "__main__":
    main()