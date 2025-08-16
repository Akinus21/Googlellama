from akinus_utils.utils.logger  import log
import asyncio
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any
import time

# --------------------
# Brave Search
# --------------------
def brave_search(
    query: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    base_url = "https://search.brave.com/search"
    params = {"q": query, "page": 1}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Referer": "https://search.brave.com/",
    }

    results = []
    MAX_PAGES = 3

    while len(results) < limit and params["page"] <= MAX_PAGES:
        try:
            response = requests.get(base_url, params=params, headers=headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            items = soup.select("div[data-testid='result']")

            if not items:
                snippet = response.text[:1000]
                log("WARNING", "search.py", f"No results found on page {params['page']} for query: {query}\nResponse snippet: {snippet}")
                return results

            for item in items:
                if len(results) >= limit:
                    break
                title_tag = item.select_one("a[data-testid='result-title-a']")
                desc_tag = item.select_one("p[data-testid='result-snippet']")
                url = title_tag['href'] if title_tag else None
                title = title_tag.get_text(strip=True) if title_tag else None
                snippet = desc_tag.get_text(strip=True) if desc_tag else None
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
            asyncio.run(log("ERROR", "search.py", f"Brave search request failed: {e}"))
            return results

        params["page"] += 1
        time.sleep(1.5)  # small delay to be polite

    return results


# --------------------
# Async Brave Search
# --------------------
async def async_brave_search(query: str, max_results: int) -> List[Dict[str, Any]]:
    try:
        results = await asyncio.to_thread(brave_search, query, max_results)
        normalized = []
        for r in results:
            if isinstance(r, dict):
                normalized.append(r)
            else:
                normalized.append({
                    "title": str(r),
                    "authors": [],
                    "year": None,
                    "journal": None,
                    "doi": None,
                    "url": None,
                    "abstract": None
                })
        await log("INFO", "search.py", f"brave_search completed for query: {query}")
        return normalized
    except Exception as e:
        await log("ERROR", "search.py", f"brave_search failed: {e}")
        return []
