"""OpenAI-compatible provider — serves both OpenAI and Google Gemini.

Gemini exposes an OpenAI-compatible endpoint
(https://generativelanguage.googleapis.com/v1beta/openai/), so the same client
code works for both; only base_url + credentials differ.

Converts canonical (Anthropic-style) messages <-> OpenAI Chat Completions format.
"""

import json
import logging

from openai import AsyncOpenAI

from task_result import TokenUsage
from .base import LLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)


def _stringify(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                parts.append(b.get("text", "") or str(b))
            else:
                parts.append(str(b))
        return "\n".join(parts)
    return str(content)


def _convert_user_blocks(blocks):
    """Convert canonical user blocks (text/image) to OpenAI content."""
    parts = []
    for b in blocks:
        t = b.get("type")
        if t == "text":
            parts.append({"type": "text", "text": b.get("text", "")})
        elif t == "image":
            src = b.get("source", {})
            if src.get("type") == "base64":
                media = src.get("media_type", "image/jpeg")
                data = src.get("data", "")
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{media};base64,{data}"},
                })
    if len(parts) == 1 and parts[0]["type"] == "text":
        return parts[0]["text"]
    return parts


def to_openai_messages(messages, system):
    out = []
    if system:
        out.append({"role": "system", "content": system})

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")

        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue

        if role == "assistant":
            text_parts = []
            tool_calls = []
            for b in content:
                t = b.get("type")
                if t == "text":
                    text_parts.append(b.get("text", ""))
                elif t == "tool_use":
                    tool_calls.append({
                        "id": b.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": b.get("name", ""),
                            "arguments": json.dumps(b.get("input", {})),
                        },
                    })
                # 'thinking' blocks are dropped — OpenAI has no equivalent
            m = {"role": "assistant"}
            text = "\n".join(p for p in text_parts if p)
            m["content"] = text or None
            if tool_calls:
                m["tool_calls"] = tool_calls
            out.append(m)
        else:  # user
            tool_results = [b for b in content if b.get("type") == "tool_result"]
            if tool_results:
                for b in tool_results:
                    out.append({
                        "role": "tool",
                        "tool_call_id": b.get("tool_use_id", ""),
                        "content": _stringify(b.get("content", "")),
                    })
                others = [b for b in content if b.get("type") != "tool_result"]
                if others:
                    out.append({"role": "user", "content": _convert_user_blocks(others)})
            else:
                out.append({"role": "user", "content": _convert_user_blocks(content)})

    return out


def to_openai_tools(tools):
    out = []
    for t in tools:
        out.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        })
    return out


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, *args, provider_name: str = "openai", **kwargs):
        super().__init__(*args, **kwargs)
        self.name = provider_name
        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        self.client = AsyncOpenAI(**client_kwargs)

    def _is_reasoning(self, model: str) -> bool:
        m = model.lower()
        return m.startswith(("o1", "o3", "o4")) or "reasoning" in m

    async def create(self, messages, system=None, tools=None, max_tokens=None, model=None) -> LLMResponse:
        use_model = model or self.model
        kwargs = {
            "model": use_model,
            "messages": to_openai_messages(messages, system),
        }

        limit = max_tokens or self.max_tokens
        if self._is_reasoning(use_model):
            kwargs["max_completion_tokens"] = limit
        else:
            kwargs["max_tokens"] = limit

        if tools:
            kwargs["tools"] = to_openai_tools(tools)

        resp = await self.client.chat.completions.create(**kwargs)
        return self._to_response(resp)

    def _to_response(self, resp) -> LLMResponse:
        choice = resp.choices[0]
        msg = choice.message
        text = msg.content or ""

        tool_calls = []
        assistant_content = []
        if text:
            assistant_content.append({"type": "text", "text": text})

        for tc in (msg.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to parse tool arguments: %s", tc.function.arguments)
                args = {}
            tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, input=args))
            assistant_content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.function.name,
                "input": args,
            })

        stop_reason = "tool_use" if choice.finish_reason == "tool_calls" else "end_turn"

        usage = TokenUsage()
        if getattr(resp, "usage", None):
            usage.input_tokens = getattr(resp.usage, "prompt_tokens", 0) or 0
            usage.output_tokens = getattr(resp.usage, "completion_tokens", 0) or 0
            details = getattr(resp.usage, "prompt_tokens_details", None)
            if details:
                usage.cache_read_tokens = getattr(details, "cached_tokens", 0) or 0

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            assistant_content=assistant_content,
            stop_reason=stop_reason,
            usage=usage,
        )
