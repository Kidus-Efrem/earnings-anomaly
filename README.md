# 📈 Earnings Anomaly: Real-Time Alternative Data NLP Pipeline

> **An end-to-end quantitative alternative data pipeline evaluating executive sentiment asymmetry in earnings calls to generate market-adjusted return signals.**

---

## 💡 Quantitative Investment Thesis

In corporate earnings calls, management teams present carefully crafted **Prepared Remarks** before facing spontaneous analyst questions in the **Q&A Session**.

$$\Delta S = S_{\text{Prepared}} - S_{\text{Q\&A}}$$

Where $S$ represents the sentiment polarity score derived using **FinBERT** (Financial BERT). 

- **High Divergence ($\Delta S > 0$)**: Executive optimism in prepared statements is unbacked or contradicted by cautious responses during analyst Q&A, serving as a leading indicator of negative drift or volatility.
- **Low / Negative Divergence ($\Delta S \le 0$)**: Executive confidence remains consistent or improves under questioning, signaling fundamentally resilient operations.

---

## 🏗️ System Architecture

The system utilizes an asynchronous, decoupled microservices architecture designed to decouple fast API ingestion from compute-heavy deep learning inference.

```
                  ┌───────────────────────────────┐
                  │   FastAPI Ingestion Gateway   │
                  │       (POST /api/v1/ingest)   │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │   Redis Task Broker   │
                     └───────────┬───────────┘
                                 │
                                 ▼
                 ┌────────────────────────────────┐
                 │   Celery NLP Worker Cluster    │
                 │  - DefaultScraper (Retry logic)│
                 │  - Regex Section Splitter      │
                 │  - FinBERT FP16 Inference      │
                 └───────────────┬────────────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │ PostgreSQL Warehouse  │
                     └───────────┬───────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
  ┌─────────────────────────────┐   ┌───────────────────────────┐
  │     Streamlit Dashboard     │   │ Quantitative Tear Sheet   │
  │     (Interactive Web UI)    │   │  (SPY Benchmark Backtest) │
  └─────────────────────────────┘   └───────────────────────────┘
```

---

## 📊 Backtest Performance & Signals

Backtest outputs evaluating divergence score quartiles against market-adjusted short-term price returns ($24h$ and $48h$ windows) benchmarked against **SPY**:

| Metric / Chart | Artifact |
| :--- | :--- |
| **Cumulative Returns vs SPY Benchmark** | `analysis/divergence_cumulative_returns.png` |
| **Signal Efficacy Bar Chart** | `analysis/divergence_backtest_bars.png` |

---

## ⚡ Quickstart Guide

### 🐳 Option 1: Docker Compose (Recommended)

Launch the entire stack (Postgres, Redis, API, Celery Worker, Streamlit) with a single command:

```bash
docker-compose up -d
```

Access services:
- **FastAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Streamlit Dashboard**: [http://localhost:8501](http://localhost:8501)

---

### 💻 Option 2: Local Python Setup

1. **Clone repository & prepare environment**:
   ```bash
   git clone https://github.com/Kidus-Efrem/earnings-anomaly.git
   cd earnings-anomaly
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```

3. **Run database migrations**:
   ```bash
   alembic upgrade head
   ```

4. **Start local services**:
   ```bash
   # Terminal 1: FastAPI Server
   uvicorn api.main:app --reload

   # Terminal 2: Celery Worker
   celery -A workers.tasks worker --loglevel=info --pool=solo

   # Terminal 3: Streamlit Dashboard
   streamlit run dashboard/dashboard.py
   ```

---

## 🔌 API Endpoints

### 1. Submit Ingestion Job
`POST /api/v1/ingest`

**Request Body:**
```json
{
  "ticker": "AAPL",
  "target_date": "2026-04-24",
  "transcript_url": "https://www.fool.com/earnings/call/..."
}
```

**Response (`202 Accepted`):**
```json
{
  "job_id": "7b8e1f2a-3c4d-5e6f-7a8b-9c0d1e2f3a4b",
  "status": "PENDING",
  "message": "Transcript queued for processing."
}
```

### 2. Check Job Status
`GET /api/v1/jobs/{job_id}`

**Response:**
```json
{
  "job_id": "7b8e1f2a-3c4d-5e6f-7a8b-9c0d1e2f3a4b",
  "status": "COMPLETED",
  "error_message": null
}
```

---

## 🧪 Testing

Run the automated `pytest` test suite:

```bash
pytest tests/
```

Test coverage includes:
- Regex section splitter logic for verbatim vs. summary earnings transcripts.
- FastAPI REST gateway validation models and status response payloads.
- PostgreSQL connector context managers and connection leak prevention.

---

## 🛠️ Technology Stack

- **Core & API**: Python 3.10, FastAPI, Pydantic, Uvicorn
- **Distributed Computing**: Celery, Redis
- **Database & Migrations**: PostgreSQL, Alembic, psycopg2
- **Deep Learning & NLP**: PyTorch, HuggingFace Transformers (FinBERT), NLTK
- **Quantitative Analytics**: Pandas, NumPy, yfinance, Seaborn, Matplotlib
- **Visualization**: Streamlit
- **DevOps**: Docker, Docker Compose
