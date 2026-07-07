import requests
import time
import logging
from bs4 import BeautifulSoup
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import re
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=r"C:\Users\Parzi\OneDrive\Documents\newparzival\earnings-anamoly\.env")
print("DATABASE_URL:", os.getenv("DATABASE_URL"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COMPANIES = [
    {"ticker": "GS",   "name": "Goldman Sachs",     "sector": "financials"},
    {"ticker": "JPM",  "name": "JPMorgan Chase",     "sector": "financials"},
    {"ticker": "MS",   "name": "Morgan Stanley",     "sector": "financials"},
    {"ticker": "BAC",  "name": "Bank of America",    "sector": "financials"},
    {"ticker": "C",    "name": "Citigroup",          "sector": "financials"},
    {"ticker": "AAPL", "name": "Apple",              "sector": "technology"},
    {"ticker": "MSFT", "name": "Microsoft",          "sector": "technology"},
    {"ticker": "GOOGL","name": "Alphabet",           "sector": "technology"},
    {"ticker": "META", "name": "Meta",               "sector": "technology"},
    {"ticker": "ORCL", "name": "Oracle",             "sector": "technology"},
    {"ticker": "XOM",  "name": "ExxonMobil",         "sector": "energy"},
    {"ticker": "CVX",  "name": "Chevron",            "sector": "energy"},
    {"ticker": "COP",  "name": "ConocoPhillips",     "sector": "energy"},
    {"ticker": "SLB",  "name": "SLB",                "sector": "energy"},
    {"ticker": "EOG",  "name": "EOG Resources",      "sector": "energy"},
    {"ticker": "JNJ",  "name": "Johnson & Johnson",  "sector": "healthcare"},
    {"ticker": "UNH",  "name": "UnitedHealth",       "sector": "healthcare"},
    {"ticker": "PFE",  "name": "Pfizer",             "sector": "healthcare"},
    {"ticker": "ABBV", "name": "AbbVie",             "sector": "healthcare"},
    {"ticker": "MRK",  "name": "Merck",              "sector": "healthcare"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (research project)"
}

TRANSCRIPT_URLS = {
    "GS": [
        "https://www.fool.com/earnings/call-transcripts/2026/04/13/goldman-sachs-gs-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/01/15/goldman-sachs-gs-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/10/14/goldman-sachs-gs-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/07/14/goldman-sachs-gs-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/04/14/goldman-sachs-gs-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/01/15/goldman-sachs-gs-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/10/15/goldman-sachs-gs-q3-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/07/15/goldman-sachs-gs-q2-2024-earnings-transcript/",
    ],
    "JPM": [
        "https://www.fool.com/earnings/call-transcripts/2026/04/11/jpmorgan-chase-jpm-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/01/15/jpmorgan-chase-jpm-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/10/11/jpmorgan-chase-jpm-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/07/11/jpmorgan-chase-jpm-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/04/11/jpmorgan-chase-jpm-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/01/15/jpmorgan-chase-jpm-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/10/11/jpmorgan-chase-jpm-q3-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/07/12/jpmorgan-chase-jpm-q2-2024-earnings-transcript/",
    ],
    "MS": [
        "https://www.fool.com/earnings/call-transcripts/2026/04/16/morgan-stanley-ms-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/01/16/morgan-stanley-ms-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/10/16/morgan-stanley-ms-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/07/16/morgan-stanley-ms-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/04/16/morgan-stanley-ms-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/01/16/morgan-stanley-ms-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/10/16/morgan-stanley-ms-q3-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/07/16/morgan-stanley-ms-q2-2024-earnings-transcript/",
    ],
    "BAC": [
        "https://www.fool.com/earnings/call-transcripts/2026/04/15/bank-of-america-bac-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/01/16/bank-of-america-bac-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/10/15/bank-of-america-bac-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/07/15/bank-of-america-bac-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/04/15/bank-of-america-bac-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/01/16/bank-of-america-bac-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/10/15/bank-of-america-bac-q3-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/07/16/bank-of-america-bac-q2-2024-earnings-transcript/",
    ],
    "C": [
        "https://www.fool.com/earnings/call-transcripts/2026/04/15/citigroup-c-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/01/15/citigroup-c-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/10/15/citigroup-c-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/07/15/citigroup-c-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/04/15/citigroup-c-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/01/15/citigroup-c-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/10/15/citigroup-c-q3-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/07/12/citigroup-c-q2-2024-earnings-transcript/",
    ],
    "AAPL": [
        "https://www.fool.com/earnings/call-transcripts/2026/05/01/apple-aapl-q2-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/01/30/apple-aapl-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/10/30/apple-aapl-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/08/01/apple-aapl-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/05/01/apple-aapl-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/01/30/apple-aapl-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/10/31/apple-aapl-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/08/01/apple-aapl-q3-2024-earnings-transcript/",
    ],
    "MSFT": [
        "https://www.fool.com/earnings/call-transcripts/2026/04/30/microsoft-msft-q3-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/01/29/microsoft-msft-q2-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/10/29/microsoft-msft-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/07/29/microsoft-msft-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/04/30/microsoft-msft-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/01/29/microsoft-msft-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/10/30/microsoft-msft-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/07/30/microsoft-msft-q4-2024-earnings-transcript/",
    ],
    "GOOGL": [
        "https://www.fool.com/earnings/call-transcripts/2026/04/29/alphabet-googl-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/02/04/alphabet-googl-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/10/29/alphabet-googl-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/07/29/alphabet-googl-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/04/29/alphabet-googl-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/02/04/alphabet-googl-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/10/29/alphabet-googl-q3-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/07/29/alphabet-googl-q2-2024-earnings-transcript/",
    ],
    "META": [
        "https://www.fool.com/earnings/call-transcripts/2026/04/30/meta-platforms-meta-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/01/29/meta-platforms-meta-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/10/29/meta-platforms-meta-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/07/30/meta-platforms-meta-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/04/30/meta-platforms-meta-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/01/29/meta-platforms-meta-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/10/30/meta-platforms-meta-q3-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/07/31/meta-platforms-meta-q2-2024-earnings-transcript/",
    ],
    "ORCL": [
        "https://www.fool.com/earnings/call-transcripts/2026/06/10/oracle-orcl-q4-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/03/10/oracle-orcl-q3-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/12/09/oracle-orcl-q2-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/09/09/oracle-orcl-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/06/10/oracle-orcl-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/03/11/oracle-orcl-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/12/10/oracle-orcl-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/09/10/oracle-orcl-q1-2025-earnings-transcript/",
    ],
    "XOM": [
        "https://www.fool.com/earnings/call-transcripts/2026/05/02/exxonmobil-xom-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/02/04/exxonmobil-xom-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/11/01/exxonmobil-xom-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/08/01/exxonmobil-xom-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/05/02/exxonmobil-xom-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/02/04/exxonmobil-xom-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/11/01/exxonmobil-xom-q3-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/08/02/exxonmobil-xom-q2-2024-earnings-transcript/",
    ],
    "CVX": [
        "https://www.fool.com/earnings/call-transcripts/2026/05/02/chevron-cvx-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/02/07/chevron-cvx-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/11/01/chevron-cvx-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/08/02/chevron-cvx-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/05/02/chevron-cvx-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/02/07/chevron-cvx-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/11/01/chevron-cvx-q3-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/08/02/chevron-cvx-q2-2024-earnings-transcript/",
    ],
    "COP": [
        "https://www.fool.com/earnings/call-transcripts/2026/05/08/conocophillips-cop-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/02/06/conocophillips-cop-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/11/07/conocophillips-cop-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/08/07/conocophillips-cop-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/05/08/conocophillips-cop-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/02/06/conocophillips-cop-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/11/07/conocophillips-cop-q3-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/08/01/conocophillips-cop-q2-2024-earnings-transcript/",
    ],
    "SLB": [
        "https://www.fool.com/earnings/call-transcripts/2026/04/25/slb-slb-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/01/17/slb-slb-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/10/17/slb-slb-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/07/18/slb-slb-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/04/25/slb-slb-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/01/17/slb-slb-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/10/18/slb-slb-q3-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/07/19/slb-slb-q2-2024-earnings-transcript/",
    ],
    "EOG": [
        "https://www.fool.com/earnings/call-transcripts/2026/05/08/eog-resources-eog-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/02/27/eog-resources-eog-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/11/06/eog-resources-eog-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/08/07/eog-resources-eog-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/05/08/eog-resources-eog-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/02/27/eog-resources-eog-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/11/07/eog-resources-eog-q3-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/08/01/eog-resources-eog-q2-2024-earnings-transcript/",
    ],
    "JNJ": [
        "https://www.fool.com/earnings/call-transcripts/2026/04/15/johnson-johnson-jnj-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/01/22/johnson-johnson-jnj-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/10/15/johnson-johnson-jnj-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/07/16/johnson-johnson-jnj-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/04/15/johnson-johnson-jnj-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/01/22/johnson-johnson-jnj-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/10/15/johnson-johnson-jnj-q3-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/07/17/johnson-johnson-jnj-q2-2024-earnings-transcript/",
    ],
    "UNH": [
        "https://www.fool.com/earnings/call-transcripts/2026/04/17/unitedhealth-group-unh-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/01/16/unitedhealth-group-unh-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/10/15/unitedhealth-group-unh-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/07/15/unitedhealth-group-unh-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/04/17/unitedhealth-group-unh-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/01/16/unitedhealth-group-unh-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/10/15/unitedhealth-group-unh-q3-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/07/12/unitedhealth-group-unh-q2-2024-earnings-transcript/",
    ],
    "PFE": [
        "https://www.fool.com/earnings/call-transcripts/2026/05/01/pfizer-pfe-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/01/28/pfizer-pfe-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/10/29/pfizer-pfe-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/07/29/pfizer-pfe-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/05/01/pfizer-pfe-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/01/28/pfizer-pfe-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/10/29/pfizer-pfe-q3-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/07/30/pfizer-pfe-q2-2024-earnings-transcript/",
    ],
    "ABBV": [
        "https://www.fool.com/earnings/call-transcripts/2026/04/25/abbvie-abbv-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/01/31/abbvie-abbv-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/10/25/abbvie-abbv-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/07/25/abbvie-abbv-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/04/25/abbvie-abbv-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/01/31/abbvie-abbv-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/10/25/abbvie-abbv-q3-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/07/26/abbvie-abbv-q2-2024-earnings-transcript/",
    ],
    "MRK": [
        "https://www.fool.com/earnings/call-transcripts/2026/04/24/merck-mrk-q1-2026-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2026/01/28/merck-mrk-q4-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/10/24/merck-mrk-q3-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/07/24/merck-mrk-q2-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/04/24/merck-mrk-q1-2025-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2025/01/28/merck-mrk-q4-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/10/24/merck-mrk-q3-2024-earnings-transcript/",
        "https://www.fool.com/earnings/call-transcripts/2024/07/26/merck-mrk-q2-2024-earnings-transcript/",
    ],
}


def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))


def search_transcripts(ticker: str) -> list[dict]:
    urls = TRANSCRIPT_URLS.get(ticker, [])
    if not urls:
        logger.warning(f"{ticker}: no URLs configured")
        return []
    logger.info(f"{ticker}: using {len(urls)} hardcoded URLs")
    return [{"url": url, "title": ""} for url in urls]


def scrape_transcript(url: str) -> dict | None:
    # If URL ends in -transcript/, also try -call-transcript/
    urls_to_try = [url]
    if url.endswith("-transcript/"):
        urls_to_try.append(url.replace("-transcript/", "-call-transcript/"))
    elif url.endswith("-call-transcript/"):
        urls_to_try.append(url.replace("-call-transcript/", "-transcript/"))

    resp = None
    final_url = None
    for u in urls_to_try:
        try:
            r = requests.get(u, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                resp = r
                final_url = u
                break
        except Exception as e:
            logger.error(f"Request failed for {u}: {e}")
            continue

    if not resp:
        logger.error(f"Failed to scrape {url}: all URL variants returned non-200")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    title_tag = soup.select_one("h1")
    title = title_tag.get_text(strip=True) if title_tag else ""

    call_date = None
    for h2 in soup.find_all("h2"):
        if h2.get_text(strip=True).lower() == "date":
            next_p = h2.find_next_sibling()
            if next_p:
                date_text = next_p.get_text(strip=True)
                match = re.search(r'(\w+ \d+, \d{4})', date_text)
                if match:
                    try:
                        call_date = datetime.strptime(match.group(1), "%B %d, %Y").date()
                    except Exception:
                        pass
            break

    transcript_start = None
    for h2 in soup.find_all("h2"):
        if "full conference call transcript" in h2.get_text(strip=True).lower():
            transcript_start = h2
            break

    if not transcript_start:
        logger.warning(f"No transcript section found at {final_url}")
        return None

    paragraphs = []
    for sibling in transcript_start.find_next_siblings():
        text = sibling.get_text(separator="\n", strip=True)
        if "read next" in text.lower():
            break
        if len(text) > 20:
            paragraphs.append(text)

    raw_text = "\n\n".join(paragraphs)

    if len(raw_text) < 500:
        logger.warning(f"Transcript too short ({len(raw_text)} chars), skipping: {final_url}")
        return None

    return {
        "title": title,
        "date": call_date,
        "raw_text": raw_text,
        "source_url": final_url  # save the URL that actually worked
    }

def save_transcript(conn, company_id: int, transcript: dict):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM transcripts WHERE source_url = %s",
            (transcript["source_url"],)
        )
        if cur.fetchone():
            logger.info(f"Already exists: {transcript['source_url']}")
            return

        cur.execute("""
            INSERT INTO transcripts
                (company_id, call_date, raw_html, full_text, source_url, scraped_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (
            company_id,
            transcript["date"],
            "",
            transcript["raw_text"],
            transcript["source_url"]
        ))
        conn.commit()
        logger.info(f"Saved: {transcript['title']}")


def ensure_company(conn, company: dict) -> int:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id FROM companies WHERE ticker = %s",
            (company["ticker"],)
        )
        row = cur.fetchone()
        if row:
            return row["id"]

        cur.execute("""
            INSERT INTO companies (ticker, name, sector)
            VALUES (%s, %s, %s) RETURNING id
        """, (company["ticker"], company["name"], company["sector"]))
        conn.commit()
        return cur.fetchone()["id"]


def run_scraper():
    conn = get_db_connection()
    logger.info("Connected to database.")

    for company in COMPANIES:
        logger.info(f"\n=== Scraping {company['ticker']} ===")
        company_id = ensure_company(conn, company)
        transcript_links = search_transcripts(company["ticker"])

        for link in transcript_links:
            logger.info(f"Processing: {link['url']}")
            transcript = scrape_transcript(link["url"])
            if transcript:
                save_transcript(conn, company_id, transcript)
            time.sleep(3)

        time.sleep(5)

    conn.close()
    logger.info("\nScraping complete.")


if __name__ == "__main__":
    run_scraper()