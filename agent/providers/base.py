"""LLM provider abstraction — unified interface over Anthropic, OpenAI, Gemini.

Canonical message format = Anthropic-style content blocks (already used across
the codebase). Each provider converts canonical -> native at request time, so
conversation history stays provider-agnostic and you can even switch providers
mid-conversation.

Canonical messages:
- {"role": "user"|"assistant", "content": str | [blocks]}
- blocks:
    {"type": "text", "text": ...}
    {"type": "thinking", "thinking": ..., "signature": ...}
    {"type": "tool_use", "id": ..., "name": ..., "input": {...}}
    {"type": "tool_result", "tool_use_id": ..., "content": "..."}
    {"type": "image", "source": {"type": "base64", "media_type": ..., "data": ...}}
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from task_result import TokenUsage


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class LLMResponse:
    """Provider-agnostic response."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    # Canonical assistant content blocks to append to the conversation history.
    assistant_content: list[dict] = field(default_factory=list)
    stop_reason: str = "end_turn"  # "tool_use" | "end_turn"
    usage: TokenUsage = field(default_factory=TokenUsage)

    @property
    def has_tool_calls(self) -> bool:
        return self.stop_reason == "tool_use" and bool(self.tool_calls)


class LLMProvider(ABC):
    """Base class for LLM providers."""

    name = "base"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        max_tokens: int = 4096,
        thinking_budget: int = 10000,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.thinking_budget = thinking_budget

    @abstractmethod
    async def create(
        self,
        messages: list[dict],
        system: str | None = None,
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
        model: str | None = None,
    ) -> LLMResponse:
        """Send a request and return a normalized response.

        `tools` is in Anthropic format ({name, description, input_schema}); the
        provider converts to its native format if needed. `model` overrides the
        provider's default model for this call (used by complexity-based routing).
        """
        raise NotImplementedError
