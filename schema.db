CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(100),
    sector VARCHAR(50)
);

CREATE TABLE transcripts (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    call_date DATE NOT NULL,
    fiscal_quarter VARCHAR(10),
    raw_html TEXT,
    full_text TEXT,
    qa_text TEXT,
    qa_start_index INTEGER,
    source_url TEXT,
    scraped_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE speakers (
    id SERIAL PRIMARY KEY,
    transcript_id INTEGER REFERENCES transcripts(id),
    name VARCHAR(100),
    role VARCHAR(50),
    is_executive BOOLEAN,
    utterances TEXT[],
    word_count INTEGER
);

CREATE TABLE price_data (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    call_date DATE NOT NULL,
    price_1hr_before DECIMAL,
    price_24hr_after DECIMAL,
    price_48hr_after DECIMAL,
    realized_vol_24hr DECIMAL,
    realized_vol_48hr DECIMAL
);

CREATE TABLE anomaly_scores (
    id SERIAL PRIMARY KEY,
    transcript_id INTEGER REFERENCES transcripts(id),
    drift_score DECIMAL,
    ceo_drift_score DECIMAL,
    cfo_drift_score DECIMAL,
    analyst_hostility_score DECIMAL,
    changepoint_minute INTEGER,
    anomaly_rank DECIMAL,
    computed_at TIMESTAMP DEFAULT NOW()
);