"""Web search tool using Tavily API."""

import logging
from typing import Optional

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"


def search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    include_domains: Optional[list[str]] = None,
    exclude_domains: Optional[list[str]] = None,
) -> list[dict]:
    """
    Search the web using Tavily API.

    Args:
        query: Search query string
        max_results: Maximum number of results (default 5)
        search_depth: "basic" or "advanced"
        include_domains: Only search these domains
        exclude_domains: Exclude these domains

    Returns:
        List of search results with title, url, content
    """
    if not settings.tavily_api_key:
        logger.warning("Tavily API key not configured, returning empty results")
        return []

    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
    }

    if include_domains:
        payload["include_domains"] = include_domains
    if exclude_domains:
        payload["exclude_domains"] = exclude_domains

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(TAVILY_API_URL, json=payload)
            response.raise_for_status()
            data = response.json()

            results = []
            for result in data.get("results", []):
                results.append(
                    {
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "content": result.get("content", ""),
                        "score": result.get("score", 0),
                    }
                )

            logger.debug(f"Search for '{query}' returned {len(results)} results")
            return results

    except httpx.HTTPError as e:
        logger.error(f"Tavily search failed: {e}")
        return []


def search_competitors(product_category: str) -> list[dict]:
    """Search for competitors in a product category."""
    queries = [
        f"best {product_category} tools 2024",
        f"{product_category} software alternatives",
        f"{product_category} saas pricing",
    ]

    all_results = []
    for query in queries:
        results = search(query, max_results=3)
        all_results.extend(results)

    return all_results


def search_pain_points(target_audience: str, problem_area: str) -> list[dict]:
    """Search for pain points and complaints."""
    queries = [
        f"{problem_area} complaints site:reddit.com",
        f"{problem_area} frustrating {target_audience}",
        f"why {problem_area} software sucks",
    ]

    all_results = []
    for query in queries:
        results = search(query, max_results=3, include_domains=["reddit.com", "twitter.com"])
        all_results.extend(results)

    return all_results
