import subprocess

from .base import ToolPlugin, ToolContext


class PythonTool(ToolPlugin):
    name = "python"
    description = (
        "Execute Python code. The code runs in a subprocess. "
        "Use print() to output results. Has access to standard library "
        "and any pip-installed packages."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute",
            }
        },
        "required": ["code"],
    }

    def execute(self, tool_input: dict, context: ToolContext) -> str:
        code = tool_input["code"]
        try:
            result = subprocess.run(
                ["python3", "-c", code],
                capture_output=True,
                text=True,
                timeout=context.timeout,
                cwd=context.workspace,
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += result.stderr
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return self.truncate(output) if output.strip() else "(no output)"
        except subprocess.TimeoutExpired:
            return f"Error: Python execution timed out after {context.timeout}s"
