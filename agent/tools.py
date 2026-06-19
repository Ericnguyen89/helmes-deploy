"""Tool facade — delegates to the plugin system.

This module re-exports the symbols that ai_engine.py and other callers rely on
so they continue to work without changes beyond import paths.
"""

from plugins import get_definitions, execute as _execute, list_plugins
from plugins.base import ToolContext

TOOL_DEFINITIONS = get_definitions()


def execute_tool(name: str, tool_input: dict, workspace: str, timeout: int = 60, sender: str = "") -> str:
    context = ToolContext(workspace=workspace, timeout=timeout, sender=sender)
    return _execute(name, tool_input, context)
