"""Browser automation tool — drives a headless Chromium via Puppeteer.

Unlike `web_fetch` (a plain HTTP GET that can't run JavaScript), this tool
renders the page in a real browser, so it works on JS-heavy / SPA sites and can
interact with the page (click, type, wait, run JS) before extracting content.

Implementation: the sync plugin shells out to a Node.js Puppeteer helper
(agent/browser/browser.js), passing the job as JSON over stdin and parsing the
JSON result from stdout. This fits the sync plugin model and keeps the
Node browser stack isolated from the Python process.
"""

import json
import os
import subprocess
import uuid

import config

from .base import ToolPlugin, ToolContext

_HELPER = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "browser", "browser.js")
)


class BrowserTool(ToolPlugin):
    name = "browser"
    description = (
        "Open a URL in a real headless browser (Chromium via Puppeteer) and "
        "return the JavaScript-rendered page text. Use this instead of web_fetch "
        "when a page needs JavaScript to render, is a single-page app, or when you "
        "must interact with it (click buttons, fill forms, wait for elements). "
        "Optionally run a sequence of actions before extracting, and/or capture a "
        "screenshot saved into the workspace."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to open.",
            },
            "actions": {
                "type": "array",
                "description": (
                    "Optional ordered steps to perform before extracting content. "
                    "Each item is an object with a 'type'."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["click", "type", "wait_for", "wait", "press", "evaluate", "goto"],
                            "description": "Action kind.",
                        },
                        "selector": {"type": "string", "description": "CSS selector (click/type/wait_for)."},
                        "text": {"type": "string", "description": "Text to type (type action)."},
                        "ms": {"type": "integer", "description": "Milliseconds to wait (wait action)."},
                        "key": {"type": "string", "description": "Key to press (press action), e.g. Enter."},
                        "script": {"type": "string", "description": "JS expression to evaluate (evaluate action)."},
                        "url": {"type": "string", "description": "URL to navigate to (goto action)."},
                    },
                    "required": ["type"],
                },
            },
            "screenshot": {
                "type": "boolean",
                "description": "If true, save a PNG screenshot into the workspace and return its path.",
            },
            "full_page": {
                "type": "boolean",
                "description": "Capture the full scrollable page (only with screenshot=true).",
            },
            "extract_text": {
                "type": "boolean",
                "description": "Return the rendered page text. Default true.",
            },
        },
        "required": ["url"],
    }

    def execute(self, tool_input: dict, context: ToolContext) -> str:
        if not getattr(config, "BROWSER_ENABLED", True):
            return "Error: browser tool is disabled (set BROWSER_ENABLED=true to enable)."

        url = tool_input.get("url")
        if not url:
            return "Error: 'url' is required."

        if not os.path.exists(_HELPER):
            return f"Error: browser helper not found at {_HELPER}."

        job = {
            "url": url,
            "actions": tool_input.get("actions") or [],
            "extractText": tool_input.get("extract_text", True),
            "timeout": min(context.timeout, 120) * 1000,
        }

        if tool_input.get("screenshot"):
            shot_path = self.resolve_path(f"browser_{uuid.uuid4().hex[:8]}.png", context.workspace)
            job["screenshot"] = True
            job["screenshotPath"] = shot_path
            job["fullPage"] = bool(tool_input.get("full_page"))

        node_bin = getattr(config, "BROWSER_NODE_BIN", "node")
        # Allow Chromium some startup headroom beyond the per-op timeout.
        proc_timeout = min(context.timeout, 120) + 30

        try:
            proc = subprocess.run(
                [node_bin, _HELPER],
                input=json.dumps(job),
                capture_output=True,
                text=True,
                timeout=proc_timeout,
                cwd=os.path.dirname(_HELPER),
            )
        except subprocess.TimeoutExpired:
            return f"Error: browser operation timed out after {proc_timeout}s for {url}"
        except FileNotFoundError:
            return f"Error: Node.js ('{node_bin}') not found — cannot run browser tool."

        stdout = (proc.stdout or "").strip()
        if not stdout:
            err = (proc.stderr or "").strip()
            return f"Error: browser helper produced no output. {err[:500]}"

        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            return f"Error: could not parse browser output: {stdout[:500]}"

        if not result.get("ok"):
            return f"Browser error for {url}: {result.get('error', 'unknown error')}"

        parts = [
            f"Title: {result.get('title') or 'No title'}",
            f"URL: {result.get('url') or url}",
        ]
        action_results = result.get("actionResults") or []
        if action_results:
            parts.append("Actions: " + " | ".join(str(a) for a in action_results))
        if result.get("screenshot"):
            parts.append(f"Screenshot saved: {result['screenshot']}")
        if result.get("text"):
            parts.append("\n" + result["text"])

        return self.truncate("\n".join(parts))
