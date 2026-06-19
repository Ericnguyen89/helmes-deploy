import logging

import requests

import config
from .base import ToolPlugin, ToolContext

logger = logging.getLogger(__name__)


class WebSearchTool(ToolPlugin):
    name = "web_search"
    description = (
        "Search the internet for information. "
        "Returns a list of search results with title, URL, and snippet. "
        "Use this to find current information, documentation, news, etc."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 5, max: 10)",
            },
        },
        "required": ["query"],
    }

    def execute(self, tool_input: dict, context: ToolContext) -> str:
        query = tool_input["query"]
        max_results = min(tool_input.get("max_results", 5), 10)

        if config.SEARCH_ENGINE == "google" and config.GOOGLE_API_KEY and config.GOOGLE_CSE_ID:
            return _google_search(query, max_results)
        return _duckduckgo_search(query, max_results)


def _google_search(query: str, max_results: int) -> str:
    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": config.GOOGLE_API_KEY,
                "cx": config.GOOGLE_CSE_ID,
                "q": query,
                "num": max_results,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])

        if not items:
            return f"No results found for: {query}"

        output_lines = [f"Search results for: {query} (via Google)\n"]
        for i, item in enumerate(items, 1):
            output_lines.append(f"{i}. {item.get('title', 'No title')}")
            output_lines.append(f"   URL: {item.get('link', 'N/A')}")
            output_lines.append(f"   {item.get('snippet', 'No description')}")
            output_lines.append("")

        return "\n".join(output_lines)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            logger.warning("Google API quota exceeded, falling back to DuckDuckGo")
            return _duckduckgo_search(query, max_results)
        return f"Google search error: {e}"
    except Exception as e:
        logger.warning("Google search failed, falling back to DuckDuckGo: %s", e)
        return _duckduckgo_search(query, max_results)


def _duckduckgo_search(query: str, max_results: int) -> str:
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return f"No results found for: {query}"

        output_lines = [f"Search results for: {query} (via DuckDuckGo)\n"]
        for i, r in enumerate(results, 1):
            output_lines.append(f"{i}. {r.get('title', 'No title')}")
            output_lines.append(f"   URL: {r.get('href', r.get('link', 'N/A'))}")
            output_lines.append(f"   {r.get('body', r.get('snippet', 'No description'))}")
            output_lines.append("")

        return "\n".join(output_lines)
    except Exception as e:
        return f"Search error: {e}"
