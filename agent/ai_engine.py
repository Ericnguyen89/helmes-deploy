import asyncio
import logging

from anthropic import AsyncAnthropic

from tools import TOOL_DEFINITIONS, execute_tool_async
from summarizer import summarize_conversation
from memory import MemoryStore
from planner import get_enhanced_system_prompt

logger = logging.getLogger(__name__)


def _serialize_content(content_blocks) -> list[dict]:
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


def _extract_text(content_blocks) -> str:
    parts = []
    for block in content_blocks:
        if block.type == "text" and block.text.strip():
            parts.append(block.text)
    return "\n".join(parts) if parts else ""


class AIEngine:
    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int,
        default_system_prompt: str,
        base_url: str | None = None,
        tools_enabled: bool = False,
        workspace_dir: str = "/workspace",
        thinking_budget: int = 10000,
        max_tool_iterations: int = 30,
        tool_timeout: int = 120,
        context_summarize_threshold: int = 20,
        context_keep_recent: int = 6,
        summarize_model: str | None = None,
    ):
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncAnthropic(**kwargs)
        self.model = model
        self.max_tokens = max_tokens
        self.default_system_prompt = default_system_prompt
        self.tools_enabled = tools_enabled
        self.workspace_dir = workspace_dir
        self.thinking_budget = thinking_budget
        self.max_tool_iterations = max_tool_iterations
        self.tool_timeout = tool_timeout
        self.context_summarize_threshold = context_summarize_threshold
        self.context_keep_recent = context_keep_recent
        self.summarize_model = summarize_model
        self.memory_store: MemoryStore | None = None

    def _is_thinking_model(self) -> bool:
        return "thinking" in self.model.lower()

    def _build_kwargs(self, messages, system_prompt, use_tools):
        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }

        if self._is_thinking_model():
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget,
            }
            if self.max_tokens < self.thinking_budget + 4096:
                kwargs["max_tokens"] = self.thinking_budget + 4096

        if system_prompt:
            kwargs["system"] = system_prompt

        if use_tools:
            kwargs["tools"] = TOOL_DEFINITIONS

        return kwargs

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        use_tools: bool = False,
        sender: str = "",
    ) -> str:
        use_tools = use_tools and self.tools_enabled

        try:
            if use_tools and system_prompt:
                system_prompt = get_enhanced_system_prompt(system_prompt)

            if self.memory_store and sender:
                memory_context = self.memory_store.get_context(sender)
                if memory_context and system_prompt:
                    system_prompt = system_prompt + "\n\n" + memory_context

            if len(messages) > self.context_summarize_threshold:
                summary_model = self.summarize_model or self.model
                messages = await summarize_conversation(
                    self.client,
                    summary_model,
                    messages,
                    keep_recent=self.context_keep_recent,
                )
                logger.info("Context summarized: %d messages remaining", len(messages))

            kwargs = self._build_kwargs(messages, system_prompt, use_tools)
            current_messages = list(messages)

            for iteration in range(self.max_tool_iterations):
                kwargs["messages"] = current_messages
                response = await self.client.messages.create(**kwargs)

                if response.stop_reason == "tool_use":
                    current_messages.append({
                        "role": "assistant",
                        "content": _serialize_content(response.content),
                    })

                    tool_results = []
                    tool_tasks = []
                    tool_ids = []

                    for block in response.content:
                        if block.type == "tool_use":
                            tool_ids.append(block.id)
                            tool_tasks.append(
                                execute_tool_async(
                                    block.name,
                                    block.input,
                                    self.workspace_dir,
                                    self.tool_timeout,
                                    sender=sender,
                                )
                            )

                    results = await asyncio.gather(*tool_tasks, return_exceptions=True)

                    for tool_id, result in zip(tool_ids, results):
                        content = str(result) if isinstance(result, Exception) else result
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": content,
                        })

                    current_messages.append({
                        "role": "user",
                        "content": tool_results,
                    })

                    logger.info(
                        "Tool iteration %d/%d completed (%d tools)",
                        iteration + 1,
                        self.max_tool_iterations,
                        len(tool_results),
                    )
                    continue

                text = _extract_text(response.content)
                if text:
                    return text
                return "[Helmes] No response generated."

            return "[Helmes] Reached maximum tool iterations. Task may be incomplete."

        except Exception:
            logger.exception("AI engine error")
            return "[Helmes] An error occurred while processing your message. Please try again."
