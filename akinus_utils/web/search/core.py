import os
from dotenv import load_dotenv
from typing import List, Dict, Any
import httpx
from akinus_utils.utils.logger  import log
import re
from akinus_utils.utils.app_details import PROJECT_ROOT
import asyncio
import nest_asyncio


# Load environment variables from .env file in the project root
env_file = os.path.join(PROJECT_ROOT, '.env')
if os.path.exists(env_file):
    load_dotenv(env_file)
else:
    raise FileNotFoundError(f"Environment file not found: {env_file}")

CORE_API_KEY = os.getenv("CORE_API_KEY")

# --------------------
# CORE API Search
# --------------------
def core_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    if not CORE_API_KEY:
        raise RuntimeError("CORE_API_KEY not set in environment.")

    url = "https://api.core.ac.uk/v3/search/works/"  # <-- add trailing slash here
    headers = {"Authorization": f"Bearer {CORE_API_KEY}"}
    params = {
        "q": query,
        "page": 1,
        "pageSize": max_results
    }

    nest_asyncio.apply()  # to allow nested event loops if needed

    async def fetch():
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=headers, params=params, timeout=15)
            r.raise_for_status()
            return r.json()

    try:
        data = asyncio.run(fetch())
        results = []
        for item in data.get("results", []):
            authors = item.get("authors", [])
            results.append({
                "title": item.get("title"),
                "authors": authors,
                "year": item.get("year"),
                "journal": item.get("sourceTitle"),
                "doi": item.get("doi"),
                "url": item.get("downloadUrl") or item.get("url"),
                "abstract": item.get("abstract"),
            })
        return results
    except Exception as e:
        # Raise so async_core_search can handle/log
        raise e


# --------------------
# Async Core Search
# --------------------
async def async_core_search(query: str, max_results: int) -> List[Dict[str, Any]]:
    try:
        results = await asyncio.to_thread(core_search, query, max_results)
        await log("INFO", "search.py", f"core_search completed for query: {query}")
        return results
    except Exception as e:
        await log("ERROR", "search.py", f"core_search failed: {e}")
        return []
