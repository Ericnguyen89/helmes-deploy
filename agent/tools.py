import subprocess
import os
import logging

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
        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        logger.exception("Tool execution error: %s", name)
        return f"Error: {e}"


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
