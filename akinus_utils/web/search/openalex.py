from typing import List, Dict, Any
import httpx
from akinus_utils.utils.logger  import log

# --------------------
# OpenAlex Search (async)
# --------------------
async def openalex_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search OpenAlex API for scholarly works.
    """
    url = "https://api.openalex.org/works"
    params = {
        "filter": f"title.search:{query}",
        "per_page": max_results
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("results", []):
            try:
                authors = [auth['author']['display_name'] for auth in item.get("authorships", [])]
                results.append({
                    "title": item.get("title"),
                    "authors": authors,
                    "year": item.get("publication_year"),
                    "journal": item.get("host_venue", {}).get("display_name"),
                    "doi": item.get("doi"),
                    "url": item.get("id"),
                    "abstract": item.get("abstract"),
                })
            except Exception:
                raise
        return results



async def async_openalex_search(query: str, max_results: int) -> List[Dict[str, Any]]:
    try:
        results = await openalex_search(query, max_results)
        await log("INFO", "search.py", f"openalex_search completed for query: {query}")
        return results
    except Exception as e:
        await log("ERROR", "search.py", f"openalex_search failed: {e}")
        return []