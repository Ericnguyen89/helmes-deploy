"""Tool for sending files/images back to the chat user as Signal attachments.

The browser/python/file tools produce files in the workspace (screenshots,
charts, PDFs, …). This tool lets the agent actually deliver one of those files
to the person it's chatting with — e.g. "chụp màn hình trang này rồi gửi cho tôi".

The SignalClient runs on the main asyncio loop while plugin `execute()` runs in
a worker thread (via asyncio.to_thread). We bridge the two with
`asyncio.run_coroutine_threadsafe`, scheduling the async send on the main loop
and blocking on its result.
"""

import asyncio
import os

from .base import ToolPlugin, ToolContext

_signal_client = None
_main_loop: "asyncio.AbstractEventLoop | None" = None


def set_signal_sender(client, loop):
    """Wire the SignalClient + main event loop into the send_file tool."""
    global _signal_client, _main_loop
    _signal_client = client
    _main_loop = loop


class SendFileTool(ToolPlugin):
    name = "send_file"
    description = (
        "Send a file or image from the workspace to the current chat user as a "
        "Signal attachment. Use this to deliver something the user asked to receive "
        "— e.g. a screenshot you captured with the browser tool, a chart, a PDF, or "
        "a generated file. The file must already exist (created by browser, python, "
        "or file_write). Send only when the user wants the file."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file in the workspace to send (e.g. the screenshot path returned by the browser tool).",
            },
            "caption": {
                "type": "string",
                "description": "Optional text caption to send together with the file.",
            },
        },
        "required": ["path"],
    }

    def execute(self, tool_input: dict, context: ToolContext) -> str:
        if _signal_client is None or _main_loop is None:
            return "Error: file sending is not available (Signal sender not configured)."

        if not context.sender:
            return "Error: no recipient for this conversation — cannot send the file."

        path = self.resolve_path(tool_input.get("path", ""), context.workspace)
        if not path or not os.path.exists(path):
            return f"Error: file not found: {path}"
        if not os.path.isfile(path):
            return f"Error: not a file: {path}"

        caption = (tool_input.get("caption") or "")[:1500]

        try:
            future = asyncio.run_coroutine_threadsafe(
                _signal_client.send_file(context.sender, path, caption),
                _main_loop,
            )
            future.result(timeout=120)
        except Exception as e:
            return f"Error sending file: {e}"

        name = os.path.basename(path)
        size = os.path.getsize(path)
        note = f" (caption: {caption[:60]})" if caption else ""
        return f"Sent '{name}' ({size} bytes) to the user as a Signal attachment.{note}"
