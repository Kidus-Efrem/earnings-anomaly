from celery import Celery
from core.database import execute_query
from core.schemas import JobStatus

# Initialize Celery app
# broker_url points to Redis. If your Redis is on a different port/host, update this.
celery_app = Celery(
    "earnings_workers",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

# Configure Celery for Windows compatibility
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(name="process_transcript_task", bind=True)
def process_transcript_task(self, job_id: str, ticker: str, target_date: str, url: str):
    """
    The background task that scrapes, parses, and runs NLP on the transcript.
    """
    print(f"[Worker] Starting job {job_id} for {ticker}...")

    # 1. Update DB to PROCESSING
    update_query = "UPDATE ingestion_jobs SET status = %s, updated_at = NOW() WHERE job_id = %s;"
    execute_query(update_query, (JobStatus.PROCESSING, job_id))

    try:
        # ==========================================
        # TODO: THE HEAVY LIFTING GOES HERE
        # 1. Scrape text from `url` using BeautifulSoup/requests
        # 2. Run Regex Splitter (Prepared vs Q&A)
        # 3. Run FinBERT Inference
        # 4. Save results to `transcript_sentiment`
        # ==========================================

        # Simulating work for now
        import time
        time.sleep(3)

        # 2. Update DB to COMPLETED
        update_query = "UPDATE ingestion_jobs SET status = %s, updated_at = NOW() WHERE job_id = %s;"
        execute_query(update_query, (JobStatus.COMPLETED, job_id))
        print(f"[Worker] Successfully completed job {job_id}")
        return {"status": "success", "job_id": job_id}

    except Exception as e:
        # 3. Update DB to FAILED if anything breaks
        error_msg = str(e)
        update_query = "UPDATE ingestion_jobs SET status = %s, error_message = %s, updated_at = NOW() WHERE job_id = %s;"
        execute_query(update_query, (JobStatus.FAILED, error_msg, job_id))
        print(f"[Worker] Job {job_id} failed: {error_msg}")
        raise e
