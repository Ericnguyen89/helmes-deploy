import os

from .base import ToolPlugin, ToolContext


class FileReadTool(ToolPlugin):
    name = "file_read"
    description = "Read the contents of a file. Returns the file content as text."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path or relative path from /workspace",
            }
        },
        "required": ["path"],
    }

    def execute(self, tool_input: dict, context: ToolContext) -> str:
        resolved = self.resolve_path(tool_input["path"], context.workspace)
        try:
            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return self.truncate(content)
        except FileNotFoundError:
            return f"Error: file not found: {resolved}"
        except IsADirectoryError:
            entries = os.listdir(resolved)
            return f"(directory with {len(entries)} entries)\n" + "\n".join(sorted(entries)[:100])


class FileWriteTool(ToolPlugin):
    name = "file_write"
    description = (
        "Write content to a file. Creates parent directories if needed. "
        "Overwrites existing file."
    )
    input_schema = {
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
    }

    def execute(self, tool_input: dict, context: ToolContext) -> str:
        resolved = self.resolve_path(tool_input["path"], context.workspace)
        os.makedirs(os.path.dirname(resolved) or ".", exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as f:
            f.write(tool_input["content"])
        size = os.path.getsize(resolved)
        return f"Written {size} bytes to {resolved}"
