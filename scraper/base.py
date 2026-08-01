from abc import ABC, abstractmethod
import httpx
from bs4 import BeautifulSoup
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    def __init__(self, user_agent=None):
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        self.headers = {"User-Agent": self.user_agent}

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        stop=stop_after_attempt(5)
    )
    def fetch_page(self, url: str) -> str:
        """Fetches the URL with exponential backoff."""
        response = httpx.get(url, headers=self.headers, timeout=30.0)
        response.raise_for_status()
        return response.text

    @abstractmethod
    def extract_text(self, html: str) -> str:
        """Extract raw text from HTML."""
        pass

    def scrape(self, url: str) -> str:
        """End-to-end scrape."""
        html = self.fetch_page(url)
        return self.extract_text(html)

class DefaultScraper(BaseScraper):
    """Default basic scraper implementation."""
    
    def extract_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for element in soup(["script", "style", "footer"]):
            element.extract()
        return soup.get_text(separator=' ', strip=True)
