import httpx
from bs4 import BeautifulSoup

from .base import ToolPlugin, ToolContext


class WebFetchTool(ToolPlugin):
    name = "web_fetch"
    description = (
        "Fetch and extract text content from a URL. "
        "Strips HTML tags and returns readable text. "
        "Use after web_search to read a specific page in detail."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch",
            },
        },
        "required": ["url"],
    }

    def execute(self, tool_input: dict, context: ToolContext) -> str:
        url = tool_input["url"]
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            }
            resp = httpx.get(url, timeout=15, headers=headers, follow_redirects=True)
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type and "text/" not in content_type:
                return f"Non-text content type: {content_type} ({len(resp.content)} bytes)"

            soup = BeautifulSoup(resp.text, "lxml")

            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                tag.decompose()

            title = soup.title.string.strip() if soup.title and soup.title.string else "No title"
            text = soup.get_text(separator="\n", strip=True)
            lines = [line for line in text.splitlines() if line.strip()]
            clean_text = "\n".join(lines)

            output = f"Title: {title}\nURL: {url}\n\n{clean_text}"
            return self.truncate(output)

        except httpx.TimeoutException:
            return f"Error: request timed out for {url}"
        except httpx.HTTPError as e:
            return f"Error fetching {url}: {e}"
