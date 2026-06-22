"""Anthropic (Claude) provider. Canonical format is already Anthropic-native."""

import logging

from anthropic import AsyncAnthropic

from task_result import TokenUsage
from .base import LLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


def serialize_content(content_blocks) -> list[dict]:
    """Convert Anthropic SDK content blocks -> canonical dict blocks."""
    result = []
    for block in content_blocks:
        if block.type == "thinking":
            d = {"type": "thinking", "thinking": block.thinking}
            if hasattr(block, "signature") and block.signature:
                d["signature"] = block.signature
            result.append(d)
        elif block.type == "text":
            result.append({"type": "text", "text": block.text})
        elif block.type == "tool_use":
            result.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
    return result


def extract_text(content_blocks) -> str:
    parts = []
    for block in content_blocks:
        if block.type == "text" and block.text.strip():
            parts.append(block.text)
    return "\n".join(parts) if parts else ""


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        self.client = AsyncAnthropic(**client_kwargs)

    def _is_thinking(self) -> bool:
        return "thinking" in self.model.lower()

    async def create(self, messages, system=None, tools=None, max_tokens=None) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "messages": messages,
        }

        if self._is_thinking():
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget,
            }
            if kwargs["max_tokens"] < self.thinking_budget + 4096:
                kwargs["max_tokens"] = self.thinking_budget + 4096

        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        resp = await self.client.messages.create(**kwargs)

        return LLMResponse(
            text=extract_text(resp.content),
            tool_calls=[
                ToolCall(id=b.id, name=b.name, input=b.input)
                for b in resp.content if b.type == "tool_use"
            ],
            assistant_content=serialize_content(resp.content),
            stop_reason="tool_use" if resp.stop_reason == "tool_use" else "end_turn",
            usage=TokenUsage.from_api_response(resp),
        )
