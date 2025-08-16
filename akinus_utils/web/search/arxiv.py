import asyncio
from typing import List, Dict, Any
from akinus_utils.utils.logger  import log
import arxiv

# --------------------
# arXiv Search
# --------------------
def arxiv_search(query: str, limit: int = 5):
    try:
        search = arxiv.Search(
            query=query,
            max_results=limit,
            sort_by=arxiv.SortCriterion.Relevance,
            sort_order=arxiv.SortOrder.Descending
        )
        results = []
        for result in search.results():
            authors = [author.name for author in result.authors]
            year = result.published.year if result.published else None
            results.append({
                "title": result.title,
                "authors": authors,
                "year": year,
                "journal": "arXiv preprint",
                "doi": result.doi,
                "url": result.pdf_url,
                "abstract": result.summary
            })
        return results
    except Exception as e:
        # Raise to let async_arxiv_search handle/log it
        raise e


# --------------------
# Async arXiv Search
# --------------------
async def async_arxiv_search(query: str, max_results: int) -> List[Dict[str, Any]]:
    try:
        results = await asyncio.to_thread(arxiv_search, query, max_results)
        await log("INFO", "search.py", f"arxiv_search completed for query: {query}")
        return results
    except Exception as e:
        await log("ERROR", "search.py", f"arxiv_search failed: {e}")
        return []
