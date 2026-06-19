"""Tool facade — delegates to the plugin system.

Provides both sync and async interfaces. The async version runs plugin
execution in a thread pool to avoid blocking the event loop.
"""

import asyncio

from plugins import get_definitions, execute as _execute, list_plugins
from plugins.base import ToolContext


def get_tool_definitions():
    return get_definitions()


TOOL_DEFINITIONS = get_tool_definitions()


def execute_tool(name: str, tool_input: dict, workspace: str, timeout: int = 60, sender: str = "") -> str:
    context = ToolContext(workspace=workspace, timeout=timeout, sender=sender)
    return _execute(name, tool_input, context)


async def execute_tool_async(name: str, tool_input: dict, workspace: str, timeout: int = 60, sender: str = "") -> str:
    context = ToolContext(workspace=workspace, timeout=timeout, sender=sender)
    return await asyncio.to_thread(_execute, name, tool_input, context)
