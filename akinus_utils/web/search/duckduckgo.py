from akinus_utils.utils.logger  import log
import asyncio
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from akinus_utils.web.utils.scrape import async_extract_text_from_url

# --------------------
# DuckDuckGo Search
# --------------------
def duckduckgo_search(
    query: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    base_url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Referer": "https://duckduckgo.com/",
    }

    params = {
        "q": query,
    }

    results = []
    try:
        response = requests.post(base_url, headers=headers, data=params, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # DuckDuckGo HTML search results container selector
        items = soup.select("div.result")

        for item in items:
            if len(results) >= limit:
                break
            title_tag = item.select_one("a.result__a")
            snippet_tag = item.select_one("a.result__snippet, div.result__snippet, div.result__body > p")
            url = title_tag['href'] if title_tag else None
            title = title_tag.get_text(strip=True) if title_tag else None
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else None

            results.append({
                "title": title,
                "authors": [],
                "year": None,
                "journal": None,
                "doi": None,
                "url": url,
                "abstract": snippet
            })

    except requests.RequestException as e:
        log("ERROR", "search.py", f"DuckDuckGo search request failed: {e}")

    return results


# --------------------
# Async DuckDuckGo Search
# --------------------
async def async_duckduckgo_search(query: str, max_results: int) -> List[Dict[str, Any]]:
    try:
        # Run synchronous search in a thread
        results = await asyncio.to_thread(duckduckgo_search, query, max_results)
        # Don't scrape here; only basic info for now.
        await log("INFO", "search.py", f"duckduckgo_search completed for query: {query}")
        return results
    except Exception as e:
        await log("ERROR", "search.py", f"duckduckgo_search failed: {e}")
        return []
