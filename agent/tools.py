import subprocess
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

import config

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS = [
    {
        "name": "bash",
        "description": (
            "Execute a bash command on the server. "
            "Use for running programs, installing packages, git operations, "
            "compiling code, managing processes, etc. "
            "Working directory is /workspace."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "file_read",
        "description": "Read the contents of a file. Returns the file content as text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path or relative path from /workspace",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "file_write",
        "description": (
            "Write content to a file. Creates parent directories if needed. "
            "Overwrites existing file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path or relative path from /workspace",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "python",
        "description": (
            "Execute Python code. The code runs in a subprocess. "
            "Use print() to output results. Has access to standard library "
            "and any pip-installed packages."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute",
                }
            },
            "required": ["code"],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Search the internet using DuckDuckGo. "
            "Returns a list of search results with title, URL, and snippet. "
            "Use this to find current information, documentation, news, etc."
        ),
        "input_schema": {
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
        },
    },
    {
        "name": "web_fetch",
        "description": (
            "Fetch and extract text content from a URL. "
            "Strips HTML tags and returns readable text. "
            "Use after web_search to read a specific page in detail."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "send_email",
        "description": (
            "Send an email via Gmail SMTP. "
            "Can send results, reports, code, or any text content to an email address. "
            "Supports plain text and HTML body."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line",
                },
                "body": {
                    "type": "string",
                    "description": "Email body content",
                },
                "html": {
                    "type": "boolean",
                    "description": "If true, body is treated as HTML (default: false)",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
]

MAX_OUTPUT_LENGTH = 15000


def _resolve_path(path: str, workspace: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(workspace, path)


def _truncate(text: str, max_len: int = MAX_OUTPUT_LENGTH) -> str:
    if len(text) <= max_len:
        return text
    half = max_len // 2
    return text[:half] + f"\n\n... ({len(text) - max_len} chars truncated) ...\n\n" + text[-half:]


def execute_tool(name: str, tool_input: dict, workspace: str, timeout: int = 60) -> str:
    logger.info("Tool call: %s(%s)", name, str(tool_input)[:200])
    try:
        if name == "bash":
            return _run_bash(tool_input["command"], workspace, timeout)
        elif name == "file_read":
            return _read_file(tool_input["path"], workspace)
        elif name == "file_write":
            return _write_file(tool_input["path"], tool_input["content"], workspace)
        elif name == "python":
            return _run_python(tool_input["code"], workspace, timeout)
        elif name == "web_search":
            return _web_search(tool_input["query"], tool_input.get("max_results", 5))
        elif name == "web_fetch":
            return _web_fetch(tool_input["url"])
        elif name == "send_email":
            return _send_email(
                tool_input["to"],
                tool_input["subject"],
                tool_input["body"],
                tool_input.get("html", False),
            )
        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        logger.exception("Tool execution error: %s", name)
        return f"Error: {e}"


# --- bash ---

def _run_bash(command: str, workspace: str, timeout: int) -> str:
    try:
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workspace,
            env={**os.environ, "HOME": workspace},
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return _truncate(output) if output.strip() else "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"


# --- file operations ---

def _read_file(path: str, workspace: str) -> str:
    resolved = _resolve_path(path, workspace)
    try:
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return _truncate(content)
    except FileNotFoundError:
        return f"Error: file not found: {resolved}"
    except IsADirectoryError:
        entries = os.listdir(resolved)
        return f"(directory with {len(entries)} entries)\n" + "\n".join(sorted(entries)[:100])


def _write_file(path: str, content: str, workspace: str) -> str:
    resolved = _resolve_path(path, workspace)
    os.makedirs(os.path.dirname(resolved) or ".", exist_ok=True)
    with open(resolved, "w", encoding="utf-8") as f:
        f.write(content)
    size = os.path.getsize(resolved)
    return f"Written {size} bytes to {resolved}"


# --- python ---

def _run_python(code: str, workspace: str, timeout: int) -> str:
    try:
        result = subprocess.run(
            ["python3", "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workspace,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return _truncate(output) if output.strip() else "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: Python execution timed out after {timeout}s"


# --- web search ---

def _web_search(query: str, max_results: int = 5) -> str:
    max_results = min(max_results, 10)
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


# --- web fetch ---

def _web_fetch(url: str) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, timeout=15, headers=headers)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
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
        return _truncate(output)

    except requests.exceptions.Timeout:
        return f"Error: request timed out for {url}"
    except requests.exceptions.RequestException as e:
        return f"Error fetching {url}: {e}"


# --- email ---

def _send_email(to: str, subject: str, body: str, html: bool = False) -> str:
    if not config.GMAIL_ADDRESS or not config.GMAIL_APP_PASSWORD:
        return (
            "Error: Gmail is not configured. "
            "Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env"
        )

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = config.GMAIL_ADDRESS
        msg["To"] = to
        msg["Subject"] = subject

        content_type = "html" if html else "plain"
        msg.attach(MIMEText(body, content_type, "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
            server.send_message(msg)

        logger.info("Email sent to %s: %s", to, subject)
        return f"Email sent successfully to {to}"

    except smtplib.SMTPAuthenticationError:
        return (
            "Error: Gmail authentication failed. "
            "Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD (use App Password, not regular password)"
        )
    except Exception as e:
        return f"Error sending email: {e}"
