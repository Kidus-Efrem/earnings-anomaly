# scraper/fetch_filings.py
import urllib.request
import json
import time
from datetime import datetime
from postgres_db import get_pg_connection

# The SEC strictly requires a descriptive User-Agent header to avoid 403 blocks
SEC_HEADERS = {
    'User-Agent': 'EarningsAnomalyBot/1.0 (contact: backend-engineer@yourdomain.com)'
}

def get_pending_jobs(limit=10):
    """Retrieves chronological pending jobs where the target date has passed."""
    conn = get_pg_connection()
    cursor = conn.cursor()

    # Only fetch records up to today's date that haven't been downloaded yet
    current_date = datetime.now().date()

    cursor.execute("""
        SELECT ticker, cik, quarter, fiscal_year, target_date
        FROM earnings_calendar
        WHERE status = 'PENDING' AND target_date <= %s
        ORDER BY target_date DESC
        LIMIT %s;
    """, (current_date, limit))

    jobs = cursor.fetchall()
    cursor.close()
    conn.close()
    return jobs

def fetch_sec_filing_metadata(cik):
    """Pulls the entire structural filing submission history for a given CIK."""
    padded_cik = str(cik).zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{padded_cik}.json"

    try:
        req = urllib.request.Request(url, headers=SEC_HEADERS)
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"[!] SEC API Connection error for CIK {padded_cik}: {e}")
        return None

def process_filing_pipeline():
    """Processes historical pending entries and attempts to source filing documents."""
    jobs = get_pending_jobs(limit=5)
    if not jobs:
        print("[*] Zero historical pending calendar entries found up to this date.")
        return

    conn = get_pg_connection()
    cursor = conn.cursor()

    for ticker, cik, quarter, fiscal_year, target_date in jobs:
        print(f"[*] Processing {ticker} ({quarter} {fiscal_year}) - Target Date: {target_date}")

        # Pull company's historical filings index from the SEC
        filings_data = fetch_sec_filing_metadata(cik)
        if not filings_data:
            time.sleep(0.1)
            continue

        try:
            recent_filings = filings_data["filings"]["recent"]
            form_types = recent_filings["form"]
            accession_numbers = recent_filings["accessionNumber"]
            report_dates = recent_filings["reportDate"]

            # Map structural targets: Q1/Q2/Q3 are 10-Q, Q4 is 10-K
            target_form = "10-K" if quarter == "Q4" else "10-Q"
            match_found = False

            for i in range(len(form_types)):
                if form_types[i] == target_form:
                    filing_date_obj = datetime.strptime(report_dates[i], "%Y-%m-%d").date()

                    # Isolate filing dates within a reasonable window of our target matrix date
                    if abs((filing_date_obj - target_date).days) <= 45:
                        acc_num = accession_numbers[i].replace("-", "")

                        # Generate raw document text link structure
                        doc_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_num}/{accession_numbers[i]}.txt"
                        print(f"    [✓] Located text data block url: {doc_url}")

                        # Update database state using the composite key
                        cursor.execute("""
                            UPDATE earnings_calendar
                            SET status = 'COMPLETED', time_of_day = %s
                            WHERE ticker = %s AND target_date = %s
                        """, (doc_url, ticker, target_date))

                        match_found = True
                        break

            if not match_found:
                print(f"    [!] No precise match found for form {target_form} matching target timeline.")
                cursor.execute("""
                    UPDATE earnings_calendar
                    SET status = 'SKIPPED'
                    WHERE ticker = %s AND target_date = %s
                """, (ticker, target_date))

        except KeyError:
            print(f"    [!] Error processing structure mapping coordinates for symbol {ticker}")
            cursor.execute("""
                UPDATE earnings_calendar
                SET status = 'FAILED'
                WHERE ticker = %s AND target_date = %s
            """, (ticker, target_date))

        conn.commit()
        # Strictly obey the SEC policy limit of max 10 requests per second across scripts
        time.sleep(0.15)

    cursor.close()
    conn.close()
    print("[✓] Batch pipeline run sequence executed successfully.")

if __name__ == "__main__":
    process_filing_pipeline()