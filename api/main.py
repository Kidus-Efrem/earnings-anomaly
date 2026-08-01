from fastapi import FastAPI, HTTPException, status
from core.schemas import IngestRequest, JobResponse, JobStatus
from core.database import execute_query
from workers.tasks import process_transcript_task
import uuid

app = FastAPI(
    title="Earnings Anomaly Ingestion API",
    description="Real-time alternative data pipeline for financial transcripts.",
    version="1.0.0"
)

@app.post("/api/v1/ingest", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_transcript(request: IngestRequest):
    job_id = uuid.uuid4()

    insert_query = """
        INSERT INTO ingestion_jobs (job_id, ticker, target_date, transcript_url, status)
        VALUES (%s, %s, %s, %s, %s)
    """
    try:
        execute_query(insert_query, (str(job_id), request.ticker, request.target_date, request.transcript_url, JobStatus.PENDING))
    except Exception as e:
        # THIS PRINT STATEMENT WILL REVEAL THE EXACT DATABASE ERROR
        print(f"❌ DATABASE ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    process_transcript_task.delay(str(job_id), request.ticker, str(request.target_date), request.transcript_url)

    return JobResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        message="Transcript queued for processing."
    )
@app.get("/api/v1/jobs/{job_id}", response_model=dict)
async def get_job_status(job_id: uuid.UUID):
    """Checks the current status of an ingestion job."""
    query = "SELECT status, error_message FROM ingestion_jobs WHERE job_id = %s;"
    result = execute_query(query, (job_id,), fetch=True)

    if not result:
        raise HTTPException(status_code=404, detail="Job not found")

    job = result[0]
    return {
        "job_id": str(job_id),
        "status": job['status'],
        "error_message": job['error_message']
    }