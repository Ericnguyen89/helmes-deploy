import os
import subprocess

from .base import ToolPlugin, ToolContext


class BashTool(ToolPlugin):
    name = "bash"
    description = (
        "Execute a bash command on the server. "
        "Use for running programs, installing packages, git operations, "
        "compiling code, managing processes, etc. "
        "Working directory is /workspace."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute",
            }
        },
        "required": ["command"],
    }

    def execute(self, tool_input: dict, context: ToolContext) -> str:
        command = tool_input["command"]
        try:
            result = subprocess.run(
                ["bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=context.timeout,
                cwd=context.workspace,
                env={**os.environ, "HOME": context.workspace},
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
            return f"Error: command timed out after {context.timeout}s"
