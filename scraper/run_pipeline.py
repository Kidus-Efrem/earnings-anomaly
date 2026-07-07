import os
import re
import sys
import time
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv(dotenv_path=r"C:\Users\Parzi\OneDrive\Documents\newparzival\earnings-anamoly\.env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env file.")

# ── Constants ──────────────────────────────────────────────────────────────────

TICKER_NAME_MAP = {
    "GS":    "goldman-sachs",
    "JPM":   "jpmorgan",
    "MS":    "morgan-stanley",
    "BAC":   "bank-of-america",
    "C":     "citigroup",
    "AAPL":  "apple",
    "MSFT":  "microsoft",
    "GOOGL": "alphabet",
    "META":  "meta-platforms",
    "ORCL":  "oracle",
    "XOM":   "exxonmobil",
    "CVX":   "chevron",
    "COP":   "conocophillips",
    "SLB":   "slb",
    "EOG":   "eog-resources",
    "JNJ":   "johnson-johnson",
    "UNH":   "unitedhealth-group",
    "PFE":   "pfizer",
    "ABBV":  "abbvie",
    "MRK":   "merck",
}

COMPANIES = {
    "GS":    {"name": "Goldman Sachs",     "sector": "financials"},
    "JPM":   {"name": "JPMorgan Chase",    "sector": "financials"},
    "MS":    {"name": "Morgan Stanley",    "sector": "financials"},
    "BAC":   {"name": "Bank of America",   "sector": "financials"},
    "C":     {"name": "Citigroup",         "sector": "financials"},
    "AAPL":  {"name": "Apple",             "sector": "technology"},
    "MSFT":  {"name": "Microsoft",         "sector": "technology"},
    "GOOGL": {"name": "Alphabet",          "sector": "technology"},
    "META":  {"name": "Meta",              "sector": "technology"},
    "ORCL":  {"name": "Oracle",            "sector": "technology"},
    "XOM":   {"name": "ExxonMobil",        "sector": "energy"},
    "CVX":   {"name": "Chevron",           "sector": "energy"},
    "COP":   {"name": "ConocoPhillips",    "sector": "energy"},
    "SLB":   {"name": "SLB",               "sector": "energy"},
    "EOG":   {"name": "EOG Resources",     "sector": "energy"},
    "JNJ":   {"name": "Johnson & Johnson", "sector": "healthcare"},
    "UNH":   {"name": "UnitedHealth",      "sector": "healthcare"},
    "PFE":   {"name": "Pfizer",            "sector": "healthcare"},
    "ABBV":  {"name": "AbbVie",            "sector": "healthcare"},
    "MRK":   {"name": "Merck",             "sector": "healthcare"},
}

EARNINGS_CALENDAR = {
    "GS":    ["2026-04-13", "2026-01-15", "2025-10-15", "2025-07-16", "2025-04-14", "2025-01-15", "2024-10-15", "2024-07-15"],
    "JPM":   ["2026-04-11", "2026-01-15", "2025-10-11", "2025-07-11", "2025-04-11", "2025-01-15", "2024-10-11", "2024-07-12"],
    "MS":    ["2026-04-16", "2026-01-16", "2025-10-16", "2025-07-16", "2025-04-16", "2025-01-16", "2024-10-16", "2024-07-16"],
    "BAC":   ["2026-04-15", "2026-01-16", "2025-10-15", "2025-07-15", "2025-04-15", "2025-01-16", "2024-10-15", "2024-07-16"],
    "C":     ["2026-04-15", "2026-01-15", "2025-10-15", "2025-07-15", "2025-04-15", "2025-01-15", "2024-10-15", "2024-07-12"],
    "AAPL":  ["2026-05-01", "2026-01-30", "2025-10-30", "2025-08-01", "2025-05-01", "2025-01-30", "2024-10-31", "2024-08-01"],
    "MSFT":  ["2026-04-30", "2026-01-29", "2025-10-29", "2025-07-29", "2025-04-30", "2025-01-29", "2024-10-30", "2024-07-30"],
    "GOOGL": ["2026-04-29", "2026-02-04", "2025-10-29", "2025-07-29", "2025-04-29", "2025-02-04", "2024-10-29", "2024-07-29"],
    "META":  ["2026-04-30", "2026-01-29", "2025-10-29", "2025-07-30", "2025-04-30", "2025-01-29", "2024-10-30", "2024-07-31"],
    "ORCL":  ["2026-06-10", "2026-03-10", "2025-12-09", "2025-09-09", "2025-06-10", "2025-03-11", "2024-12-10", "2024-09-10"],
    "XOM":   ["2026-05-02", "2026-02-04", "2025-11-01", "2025-08-01", "2025-05-02", "2025-02-04", "2024-11-01", "2024-08-02"],
    "CVX":   ["2026-05-02", "2026-02-07", "2025-11-01", "2025-08-02", "2025-05-02", "2025-02-07", "2024-11-01", "2024-08-02"],
    "COP":   ["2026-05-08", "2026-02-06", "2025-11-07", "2025-08-07", "2025-05-08", "2025-02-06", "2024-11-07", "2024-08-01"],
    "SLB":   ["2026-04-25", "2026-01-17", "2025-10-17", "2025-07-18", "2025-04-25", "2025-01-17", "2024-10-18", "2024-07-19"],
    "EOG":   ["2026-05-08", "2026-02-27", "2025-11-06", "2025-08-07", "2025-05-08", "2025-02-27", "2024-11-07", "2024-08-01"],
    "JNJ":   ["2026-04-15", "2026-01-22", "2025-10-15", "2025-07-16", "2025-04-15", "2025-01-22", "2024-10-15", "2024-07-17"],
    "UNH":   ["2026-04-17", "2026-01-16", "2025-10-15", "2025-07-15", "2025-04-17", "2025-01-16", "2024-10-15", "2024-07-12"],
    "PFE":   ["2026-05-01", "2026-01-28", "2025-10-29", "2025-07-29", "2025-05-01", "2025-01-28", "2024-10-29", "2024-07-30"],
    "ABBV":  ["2026-04-29", "2026-02-04", "2025-10-25", "2025-07-25", "2025-04-25", "2025-01-31", "2024-10-25", "2024-07-26"],
    "MRK":   ["2026-04-24", "2026-01-28", "2025-10-24", "2025-07-24", "2025-04-24", "2025-01-28", "2024-10-24", "2024-07-26"],
}

FOOL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ── Database helpers ───────────────────────────────────────────────────────────

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, connect_timeout=10)


def get_or_create_company(cur, ticker: str) -> int:
    company = COMPANIES[ticker]
    cur.execute("""
        INSERT INTO companies (ticker, name, sector)
        VALUES (%s, %s, %s)
        ON CONFLICT (ticker) DO UPDATE SET ticker = EXCLUDED.ticker
        RETURNING id;
    """, (ticker, company["name"], company["sector"]))
    return cur.fetchone()[0]


def transcript_exists(cur, url: str) -> bool:
    cur.execute("SELECT id FROM transcripts WHERE source_url = %s", (url,))
    return cur.fetchone() is not None

# ── URL finder ─────────────────────────────────────────────────────────────────
def find_fool_url(ticker: str, target_date_str: str) -> str | None:
    ticker_lower = ticker.lower()

    slug_options = [TICKER_NAME_MAP.get(ticker, ticker_lower)]
    if ticker == "JPM":
        slug_options.append("jpmorgan-chase")
    elif ticker == "GS":
        slug_options.append("goldman-sachs-group")

    try:
        date_obj = datetime.strptime(target_date_str, "%Y-%m-%d")
    except ValueError:
        return None

    # Determine quarter strings
    month = date_obj.month
    if month in [1, 2, 3]:
        quarter, year = "q4", date_obj.year - 1
    elif month in [4, 5, 6]:
        quarter, year = "q1", date_obj.year
    elif month in [7, 8, 9]:
        quarter, year = "q2", date_obj.year
    else:
        quarter, year = "q3", date_obj.year

    session = requests.Session()
    session.headers.update(FOOL_HEADERS)

    # STEP 1: Download the sitemap index for the target year (Fast text scan)
    # This acts as a map so we don't have to guess hundreds of URLs
    sitemap_url = f"https://www.fool.com/sitemaps/earnings/call-transcripts/{date_obj.year}/"
    print(f"    [*] Scanning Motley Fool {date_obj.year} index map to speed up search...")

    try:
        sitemap_resp = session.get(sitemap_url, timeout=10)
        sitemap_resp.raise_for_status()
        sitemap_text = sitemap_resp.text
    except Exception as e:
        print(f"    [!] Sitemap lookup failed ({e}), falling back to blind scan...")
        sitemap_text = ""

    suffixes = [
        "-earnings-transcript/",
        "-earnings-call-transcript/",
        "-earnings-call-transcrip/",
        "-earnings/",
    ]

    # STEP 2: Generate all possibilities
    possible_urls = []
    for offset in range(-2, 15):
        test_date = date_obj + timedelta(days=offset)
        date_path = test_date.strftime("%Y/%m/%d")

        for company_slug in slug_options:
            for suffix in suffixes:
                url = f"https://www.fool.com/earnings/call-transcripts/{date_path}/{company_slug}-{ticker_lower}-{quarter}-{year}{suffix}"

                # If we have the sitemap, only test URLs that are physically in it
                if sitemap_text:
                    # Strip the scheme and trailing slash to ensure robust substring pairing
                    clean_search = url.replace("https://", "").replace("http://", "").rstrip('/')
                    if clean_search in sitemap_text:
                        possible_urls.append(url)
                else:
                    possible_urls.append(url)

    # STEP 3: Ping only the highly probable candidate matches
    if sitemap_text and not possible_urls:
        print(f"    [-] No candidate matches found in the index for {ticker} near {target_date_str}")
        return None

    print(f"    [*] Pinging {len(possible_urls)} filtered candidate URLs...")
    for url in possible_urls:
        try:
            resp = session.get(url, timeout=7, allow_redirects=True, stream=True)
            if resp.status_code == 200 and "earnings/call-transcripts" in resp.url:
                return resp.url
        except Exception:
            pass
        time.sleep(0.1)

    return None
def scrape_and_save(ticker: str, call_date_str: str, url: str):
    """Scrape a Motley Fool transcript and save it to the database."""
    print(f"  Scraping: {url}")

    try:
        resp = requests.get(url, headers=FOOL_HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  [ERROR] Failed to fetch page: {e}")
        return

    # Extract body
    body = (
        soup.find("div", class_="tailwind-article-body") or
        soup.find("div", class_="article-body")
    )
    if not body:
        print(f"  [ERROR] No article body found at {url}")
        return

    paragraphs = [p.get_text().strip() for p in body.find_all("p") if p.get_text().strip()]
    full_text = "\n\n".join(paragraphs)

    if not paragraphs:
        print("  [ERROR] Empty transcript body.")
        return

    # Fiscal quarter
    fiscal_quarter = "Unknown"
    h1 = soup.find("h1")
    if h1:
        match = re.search(r'(Q[1-4]\s?\d{4})', h1.get_text())
        if match:
            fiscal_quarter = match.group(1).replace(" ", "")

    # Split prepared remarks vs Q&A
    qa_start_idx = None
    for idx, p_text in enumerate(paragraphs):
        if "questions and answers" in p_text.lower() or "question-and-answer" in p_text.lower():
            qa_start_idx = idx
            break

    prepared_remarks = paragraphs[:qa_start_idx] if qa_start_idx else paragraphs
    qa_paragraphs = paragraphs[qa_start_idx + 1:] if qa_start_idx else []
    qa_text = "\n\n".join(qa_paragraphs)

    # Speaker extraction
    speaker_data = {}
    current_speaker = None
    role_mapping = {}
    executive_registry = set()

    meta_pattern = re.compile(r'[-\u2014\u2013]\s*([A-Za-z\s,\/]+)\s*[\u2014\u2013-]\s*([A-Z][a-zA-Z\s\.\-\']+)')
    for p_text in paragraphs[:20]:
        m = meta_pattern.search(p_text)
        if m:
            role, name = m.group(1).strip(), m.group(2).strip()
            role_mapping[name] = role
            executive_registry.add(name)

    analyst_keywords = ["analyst", "research", "capital", "management", "bank", "securities"]

    for p_text in paragraphs:
        if ":" in p_text and len(p_text.split(":")[0]) < 50:
            potential_speaker, utterance = p_text.split(":", 1)
            potential_speaker = potential_speaker.replace("**", "").replace("*", "").strip()

            if re.match(r'^[A-Z][a-zA-Z\s\.\-\']+$', potential_speaker):
                current_speaker = potential_speaker
                utterance = utterance.strip()

                if current_speaker not in speaker_data:
                    role = role_mapping.get(current_speaker, "Participant")
                    is_exec = (
                        current_speaker in executive_registry or
                        not any(w in role.lower() for w in analyst_keywords)
                    )
                    if "operator" in current_speaker.lower():
                        is_exec = False

                    speaker_data[current_speaker] = {
                        "role": role,
                        "is_executive": is_exec,
                        "utterances": []
                    }

                if utterance:
                    speaker_data[current_speaker]["utterances"].append(utterance)
                continue

        if current_speaker and current_speaker in speaker_data:
            speaker_data[current_speaker]["utterances"].append(p_text)

    # Save to database
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if transcript_exists(cur, url):
            print(f"  [SKIP] Already exists: {url}")
            cur.close()
            conn.close()
            return

        company_id = get_or_create_company(cur, ticker)

        cur.execute("""
            INSERT INTO transcripts
                (company_id, call_date, fiscal_quarter, raw_html, full_text,
                 qa_text, qa_start_index, source_url, scraped_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id;
        """, (
            company_id,
            call_date_str,
            fiscal_quarter,
            resp.text,
            full_text,
            qa_text,
            qa_start_idx,
            url
        ))
        transcript_id = cur.fetchone()[0]

        for s_name, s_info in speaker_data.items():
            if not s_info["utterances"]:
                continue
            word_count = sum(len(u.split()) for u in s_info["utterances"])
            cur.execute("""
                INSERT INTO speakers (transcript_id, name, role, is_executive, utterances, word_count)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (
                transcript_id,
                s_name,
                s_info["role"],
                s_info["is_executive"],
                s_info["utterances"],
                word_count
            ))

        conn.commit()
        print(f"  [SAVED] {ticker} {fiscal_quarter} — {len(speaker_data)} speakers, {len(paragraphs)} paragraphs")

    except Exception as e:
        if "conn" in locals():
            conn.rollback()
        print(f"  [DB ERROR] {e}")
    finally:
        if "cur" in locals():
            cur.close()
        if "conn" in locals():
            conn.close()

# ── Main pipeline ──────────────────────────────────────────────────────────────

def run_pipeline():
    print("Starting earnings transcript pipeline...")
    print("=" * 60)

    total_found = 0
    total_saved = 0

    for ticker, dates in EARNINGS_CALENDAR.items():
        print(f"\n=== {ticker} ===")

        for target_date in dates:
            print(f"  Finding URL for {target_date}...")
            url = find_fool_url(ticker, target_date)

            if not url:
                print(f"  [!] No URL found near {target_date}")
                continue

            total_found += 1
            print(f"  [+] {url}")
            scrape_and_save(ticker, target_date, url)
            total_saved += 1
            time.sleep(2)

        time.sleep(3)

    print(f"\n{'=' * 60}")
    print(f"Done. Found {total_found} URLs, processed {total_saved} transcripts.")


if __name__ == "__main__":
    try:
        run_pipeline()
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user.")
        sys.exit(0)