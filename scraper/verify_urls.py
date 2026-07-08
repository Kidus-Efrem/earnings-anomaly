# save as scraper/verify_urls.py
import requests
import time

FOOL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

# Known confirmed GS URLs from search results
GS_URLS = [
    "https://www.fool.com/earnings/call-transcripts/2026/04/13/goldman-sachs-gs-q1-2026-earnings-transcript/",
    "https://www.fool.com/earnings/call-transcripts/2026/01/15/goldman-sachs-gs-q4-2025-earnings-transcript/",
    "https://www.fool.com/earnings/call-transcripts/2025/07/16/goldman-sachs-gs-q2-2025-earnings-call-transcript/",
    "https://www.fool.com/earnings/call-transcripts/2025/04/14/goldman-sachs-gs-q1-2025-earnings-call-transcript/",
    "https://www.fool.com/earnings/call-transcripts/2025/01/15/goldman-sachs-gs-q4-2024-earnings-call-transcript/",
    "https://www.fool.com/earnings/call-transcripts/2024/10/15/goldman-sachs-gs-q3-2024-earnings-call-transcript/",
    "https://www.fool.com/earnings/call-transcripts/2024/07/15/goldman-sachs-gs-q2-2024-earnings-call-transcript/",
    "https://www.fool.com/earnings/call-transcripts/2024/04/15/goldman-sachs-gs-q1-2024-earnings-call-transcript/",
	"https://www.fool.com/earnings/call-transcripts/2021/04/14/goldman-sachs-group-inc-gs-q1-2021-earnings-call-t/",
]

session = requests.Session()
session.headers.update(FOOL_HEADERS)

for url in GS_URLS:
    resp = session.get(url, timeout=10)
    status = "✓" if resp.status_code == 200 else f"✗ {resp.status_code}"
    print(f"{status} {url}")
    time.sleep(1)