# scrape.py

import requests
from readability import Document
from bs4 import BeautifulSoup

# Optional imports for enhanced extraction
try:
    from newspaper import Article
except ImportError:
    Article = None

try:
    import trafilatura
except ImportError:
    trafilatura = None

class ScrapeError(Exception):
    pass

def fetch_page(url: str, timeout: int = 10) -> str:
    """
    Fetch HTML content from a URL with a realistic User-Agent.
    
    Raises:
        ScrapeError if the request fails.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        raise ScrapeError(f"Failed to fetch page: {e}")

def extract_with_newspaper(url: str) -> str:
    if not Article:
        raise ScrapeError("newspaper3k is not installed")
    try:
        article = Article(url)
        article.download()
        article.parse()
        text = article.text
        if text and len(text) > 200:  # sanity check for minimum length
            return text
        else:
            raise ScrapeError("newspaper3k extraction yielded too little content")
    except Exception as e:
        raise ScrapeError(f"newspaper3k extraction failed: {e}")

def extract_with_trafilatura(url: str) -> str:
    if not trafilatura:
        raise ScrapeError("trafilatura is not installed")
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            raise ScrapeError("trafilatura failed to fetch content")
        text = trafilatura.extract(downloaded)
        if text and len(text) > 200:
            return text
        else:
            raise ScrapeError("trafilatura extraction yielded too little content")
    except Exception as e:
        raise ScrapeError(f"trafilatura extraction failed: {e}")

def extract_main_text(html: str) -> str:
    """
    Extract main readable content from HTML using Readability.
    
    Returns plain text.
    
    Raises:
        ScrapeError if extraction fails.
    """
    try:
        doc = Document(html)
        content_html = doc.summary()
        soup = BeautifulSoup(content_html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        if text and len(text) > 200:
            return text
        else:
            raise ScrapeError("readability extraction yielded too little content")
    except Exception as e:
        raise ScrapeError(f"Failed to extract main text: {e}")

def extract_text_from_url(url: str) -> str:
    """
    Attempt to extract main article text from the URL using multiple methods:
    1. newspaper3k
    2. trafilatura
    3. readability (fallback)
    """
    # Try newspaper3k first
    try:
        return extract_with_newspaper(url)
    except ScrapeError:
        pass

    # Try trafilatura next
    try:
        return extract_with_trafilatura(url)
    except ScrapeError:
        pass

    # Last fallback: readability on fetched HTML
    html = fetch_page(url)
    return extract_main_text(html)

# Async helper for integration with async frameworks
import asyncio

async def async_extract_text_from_url(url: str) -> str:
    return await asyncio.to_thread(extract_text_from_url, url)

# For direct command line usage
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract main article text from a URL")
    parser.add_argument("url", type=str, help="URL to extract text from")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")
    args = parser.parse_args()

    try:
        text = extract_text_from_url(args.url)
        print(text)
    except ScrapeError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
