import os
import sys
import re
import nltk
import torch
import httpx
from bs4 import BeautifulSoup
from celery import Celery
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# Add project root to path for local imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.database import execute_query
from core.schemas import JobStatus
from scraper.base import DefaultScraper

# Ensure NLTK data is available
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)

# Initialize Celery app
celery_app = Celery(
    "earnings_workers",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# ==========================================
# 1. TEXT SPLITTING LOGIC (The Bulletproof Regex)
# ==========================================
QA_MARKERS = [
    r'open\s+the\s+call\s+up\s+for\s+questions',
    r'open\s+it\s+up\s+for\s+(?:your\s+)?questions',
    r'open\s+it\s+up\s+to\s+(?:your\s+)?questions',
    r'open\s+the\s+line\s+for\s+questions',
    r'let\'s\s+(?:now\s+)?go\s+to\s+questions',
    r'(?<!concludes the )(?<!concludes our )question-and-answer session\b',
    r'(?<!concludes the )(?<!concludes our )q&a session\b',
    r'we\s+will\s+now\s+(?:be\s+)?taking\s+(?:your\s+)?questions\b',
    r'we\'ll\s+now\s+open\s+the\s+(?:line|floor)\s+for\s+questions\b',
    r'at\s+this\s+time,\s+(?:we|i)\s+will\s+(?:open|begin)\s+the\s+(?:q&a|question-and-answer)\b',
    r'begin\s+(?:the\s+)?q&a\b',
    r'start\s+(?:the\s+)?q&a\b'
]
PATTERN = re.compile(r'(?:' + '|'.join(QA_MARKERS) + r')', re.IGNORECASE)

def split_transcript(text):
    if not text:
        return "", "", False
    match = PATTERN.search(text)
    if match:
        split_index = match.start()
        return text[:split_index].strip(), text[split_index:].strip(), True
    return text.strip(), "", False

# ==========================================
# 2. FINBERT INFERENCE (Lazy-Loaded for 4GB GPU)
# ==========================================
MODEL_NAME = "ProsusAI/finbert"
_tokenizer = None
_model = None

def get_model():
    global _tokenizer, _model
    if _tokenizer is None:
        print("[Worker] Loading FinBERT model into memory...")
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, use_safetensors=True)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        _model.to(device)
        _model.eval()
        print(f"[Worker] Model loaded successfully on {device}.")
    return _tokenizer, _model

def get_section_polarity(text):
    if not text or len(text.strip()) < 10:
        return 0.0

    sentences = nltk.sent_tokenize(text)
    if not sentences:
        return 0.0

    pos_score = 0.0
    neg_score = 0.0
    valid_sentences = 0

    tokenizer, model = get_model()
    device = next(model.parameters()).device
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
            with torch.amp.autocast(device_type="cuda" if torch.cuda.is_available() else "cpu"):
                outputs = model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits, dim=-1)

            pos_score += probs[:, 0].sum().item()
            neg_score += probs[:, 1].sum().item()
            valid_sentences += len(batch_sentences)

        del inputs, outputs, probs
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    if valid_sentences == 0:
        return 0.0

    avg_pos = pos_score / valid_sentences
    avg_neg = neg_score / valid_sentences
    return avg_pos - avg_neg

# ==========================================
# 3. CELERY TASK (The Real Pipeline)
# ==========================================
@celery_app.task(name="process_transcript_task", bind=True)
def process_transcript_task(self, job_id: str, ticker: str, target_date: str, url: str):
    print(f"[Worker] Starting job {job_id} for {ticker}...")

    # 1. Update DB to PROCESSING
    update_query = "UPDATE ingestion_jobs SET status = %s, updated_at = NOW() WHERE job_id = %s;"
    execute_query(update_query, (JobStatus.PROCESSING, job_id))

    try:
        # 2. Scrape the transcript
        print(f"[Worker] Scraping {url}...")
        scraper = DefaultScraper()
        raw_text = scraper.scrape(url)

        # 3. Split the transcript
        prepared_text, qa_text, is_verbatim = split_transcript(raw_text)

        if not is_verbatim:
            print(f"[Worker] Warning: Could not find Q&A markers. Treating as summary article.")

        # 4. Run FinBERT Inference
        print(f"[Worker] Running NLP inference...")
        prep_pol = get_section_polarity(prepared_text)
        qa_pol = get_section_polarity(qa_text)
        div_score = prep_pol - qa_pol

        # 5. Save split text to transcripts_content (Upsert)
        update_text_query = """
            INSERT INTO transcripts_content (ticker, target_date, prepared_text, qa_text)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (ticker, target_date)
            DO UPDATE SET prepared_text = EXCLUDED.prepared_text, qa_text = EXCLUDED.qa_text;
        """
        execute_query(update_text_query, (ticker, target_date, prepared_text, qa_text))

        # 6. Save scores to transcript_sentiment (Upsert)
        # We provide 0.0 for the overall scores to satisfy the NOT NULL constraints
        # on the original columns, while updating our new divergence columns.
        upsert_scores_query = """
            INSERT INTO transcript_sentiment (
                ticker, target_date,
                positive_score, negative_score, neutral_score, sentiment_polarity,
                prepared_polarity, qa_polarity, divergence_score
            )
            VALUES (%s, %s, 0.0, 0.0, 0.0, 0.0, %s, %s, %s)
            ON CONFLICT (ticker, target_date)
            DO UPDATE SET
                prepared_polarity = EXCLUDED.prepared_polarity,
                qa_polarity = EXCLUDED.qa_polarity,
                divergence_score = EXCLUDED.divergence_score;
        """
        execute_query(upsert_scores_query, (ticker, target_date, prep_pol, qa_pol, div_score))

        # 7. Update DB to COMPLETED
        update_query = "UPDATE ingestion_jobs SET status = %s, updated_at = NOW() WHERE job_id = %s;"
        execute_query(update_query, (JobStatus.COMPLETED, job_id))
        print(f"[Worker] Successfully completed job {job_id} with Div Score: {div_score:.4f}")
        return {"status": "success", "job_id": job_id, "divergence_score": div_score}

    except Exception as e:
        error_msg = str(e)
        print(f"[Worker] Job {job_id} failed: {error_msg}")
        update_query = "UPDATE ingestion_jobs SET status = %s, error_message = %s, updated_at = NOW() WHERE job_id = %s;"
        execute_query(update_query, (JobStatus.FAILED, error_msg, job_id))
        raise e