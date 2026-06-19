from duckduckgo_search import DDGS

from .base import ToolPlugin, ToolContext


class WebSearchTool(ToolPlugin):
    name = "web_search"
    description = (
        "Search the internet using DuckDuckGo. "
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
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            if not results:
                return f"No results found for: {query}"

            output_lines = [f"Search results for: {query}\n"]
            for i, r in enumerate(results, 1):
                output_lines.append(f"{i}. {r.get('title', 'No title')}")
                output_lines.append(f"   URL: {r.get('href', r.get('link', 'N/A'))}")
                output_lines.append(f"   {r.get('body', r.get('snippet', 'No description'))}")
                output_lines.append("")

            return "\n".join(output_lines)
        except Exception as e:
            return f"Search error: {e}"
