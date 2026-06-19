import os


MAX_OUTPUT_LENGTH = 15000


class ToolContext:
    __slots__ = ("workspace", "timeout", "sender")

    def __init__(self, workspace: str = "/workspace", timeout: int = 120, sender: str = ""):
        self.workspace = workspace
        self.timeout = timeout
        self.sender = sender


class ToolPlugin:
    name: str = ""
    description: str = ""
    input_schema: dict = {}

    def execute(self, tool_input: dict, context: ToolContext) -> str:
        raise NotImplementedError

    def to_definition(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    @staticmethod
    def truncate(text: str, max_len: int = MAX_OUTPUT_LENGTH) -> str:
        if len(text) <= max_len:
            return text
        half = max_len // 2
        return (
            text[:half]
            + f"\n\n... ({len(text) - max_len} chars truncated) ...\n\n"
            + text[-half:]
        )

    @staticmethod
    def resolve_path(path: str, workspace: str) -> str:
        if os.path.isabs(path):
            return path
        return os.path.join(workspace, path)
