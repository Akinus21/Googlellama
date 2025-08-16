import asyncio
import json
from typing import List, Dict, Any
from akinus_utils.utils.logger  import log
import requests
from bs4 import BeautifulSoup

# --------------------
# CrossRef Search (with abstract parsing)
# --------------------
def crossref_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    url = "https://api.crossref.org/works"
    params = {"query": query, "rows": limit}
    
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()  # will raise HTTPError if bad response
    
    items = r.json().get("message", {}).get("items", [])
    
    results = []
    for item in items:
        try:
            authors = []
            for a in item.get("author", []):
                name_parts = [a.get("given", ""), a.get("family", "")]
                authors.append(" ".join([p for p in name_parts if p]))

            year = None
            if "published-print" in item:
                year = item["published-print"]["date-parts"][0][0]
            elif "published-online" in item:
                year = item["published-online"]["date-parts"][0][0]

            abstract_raw = item.get("abstract")
            abstract = None
            if abstract_raw:
                try:
                    soup = BeautifulSoup(abstract_raw, "html.parser")
                    abstract = soup.get_text(" ", strip=True)
                except Exception:
                    abstract = abstract_raw

            results.append({
                "title": item.get("title", [None])[0],
                "authors": authors,
                "year": year,
                "journal": item.get("container-title", [None])[0],
                "doi": item.get("DOI"),
                "url": item.get("URL"),
                "abstract": abstract,
            })
        except Exception:
            raise

    return results


# --------------------
# Async CrossRef Search
# --------------------
async def async_crossref_search(query: str, max_results: int) -> List[Dict[str, Any]]:
    try:
        results = await asyncio.to_thread(crossref_search, query, max_results)
        await log("INFO", "search.py", f"crossref_search completed for query: {query}")
        return results
    except Exception as e:
        await log("ERROR", "search.py", f"crossref_search failed: {e}")
        return []
