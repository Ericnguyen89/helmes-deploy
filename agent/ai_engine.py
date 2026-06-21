import asyncio
import logging

from anthropic import AsyncAnthropic

from tools import TOOL_DEFINITIONS, execute_tool_async
from summarizer import summarize_conversation
from memory import MemoryStore
from planner import get_enhanced_system_prompt
from skills import SkillRegistry
from task_result import TaskResult, TokenUsage
from sub_agent import SubAgentExecutor

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
        self.skill_registry = SkillRegistry()
        self.sub_agent = SubAgentExecutor(
            client=self.client,
            model=self.model,
            max_tokens=self.max_tokens,
            tools_enabled=self.tools_enabled,
            tool_definitions=TOOL_DEFINITIONS,
            workspace_dir=self.workspace_dir,
            tool_timeout=self.tool_timeout,
            thinking_budget=self.thinking_budget,
            execute_tool_fn=execute_tool_async,
        )
        self._last_task_result: TaskResult | None = None

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

    def _budget_note(self, iteration: int) -> str:
        remaining = self.max_tool_iterations - iteration - 1
        if remaining <= max(2, int(self.max_tool_iterations * 0.1)):
            return (
                f"\n\n[⚠️ CRITICAL: Only {remaining} tool call(s) remaining! "
                "You MUST provide your final answer NOW. Summarize everything "
                "you have found so far and respond to the user immediately. "
                "Do NOT make more tool calls.]"
            )
        if remaining <= int(self.max_tool_iterations * 0.3):
            return (
                f"\n\n[⚠️ Tool budget running low: {remaining}/{self.max_tool_iterations} remaining. "
                "Start wrapping up. Consolidate your findings and prepare your final response. "
                "Only use tools if absolutely essential.]"
            )
        if remaining <= int(self.max_tool_iterations * 0.5):
            return (
                f"\n\n[Tool budget: {remaining}/{self.max_tool_iterations} iterations remaining. "
                "Be efficient with remaining tool calls.]"
            )
        return ""

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

            # Skill-based prompt enhancement
            user_message = ""
            skill = None
            if messages:
                last = messages[-1]
                if isinstance(last.get("content"), str):
                    user_message = last["content"]

            if use_tools and user_message:
                skill = self.skill_registry.classify(user_message)
                if skill and system_prompt:
                    system_prompt += f"\n\n{skill.content}"
                    logger.info("Skill activated: %s", skill.name)

                # Try task decomposition for complex tasks
                if len(user_message) > 50:
                    sub_tasks = await self.sub_agent.try_decompose(user_message)
                    if sub_tasks:
                        logger.info("Task decomposed into %d sub-tasks", len(sub_tasks))
                        text, task_result = await self.sub_agent.execute_decomposed(
                            sub_tasks,
                            self.skill_registry,
                            sender=sender,
                            total_budget=self.max_tool_iterations,
                        )
                        self._last_task_result = task_result
                        logger.info("Decomposed task completed: %s", task_result.to_summary())
                        return text

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
            task_result = TaskResult(task_id="main")
            task_result.start()
            if skill:
                task_result.skill_used = skill.name

            for iteration in range(self.max_tool_iterations):
                remaining = self.max_tool_iterations - iteration - 1
                force_respond = remaining <= 1
                if force_respond:
                    kwargs.pop("tools", None)

                kwargs["messages"] = current_messages
                response = await self.client.messages.create(**kwargs)
                task_result.token_usage.add(TokenUsage.from_api_response(response))
                task_result.tool_iterations = iteration + 1

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

                    budget_note = self._budget_note(iteration)
                    for i, (tool_id, result) in enumerate(zip(tool_ids, results)):
                        content = str(result) if isinstance(result, Exception) else result
                        if budget_note and i == len(tool_ids) - 1:
                            content += budget_note
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
                        "Tool iteration %d/%d completed (%d tools, %d remaining)",
                        iteration + 1,
                        self.max_tool_iterations,
                        len(tool_results),
                        remaining,
                    )
                    continue

                text = _extract_text(response.content)
                if text:
                    task_result.complete(text)
                    self._last_task_result = task_result
                    logger.info("Task completed: %s", task_result.to_summary())
                    return text
                return "[Helmes] No response generated."

            logger.warning("Reached max tool iterations (%d)", self.max_tool_iterations)
            kwargs["messages"] = current_messages
            kwargs.pop("tools", None)
            try:
                final = await self.client.messages.create(**kwargs)
                task_result.token_usage.add(TokenUsage.from_api_response(final))
                text = _extract_text(final.content)
                if text:
                    task_result.complete(text)
                    self._last_task_result = task_result
                    logger.info("Task completed (max iter): %s", task_result.to_summary())
                    return text + "\n\n⚠️ [Helmes] Reached maximum tool iterations. Result may be incomplete."
            except Exception:
                logger.exception("Final summary call failed")
            task_result.fail("Max iterations exhausted")
            self._last_task_result = task_result
            return "[Helmes] Reached maximum tool iterations. Task may be incomplete."

        except Exception:
            logger.exception("AI engine error")
            return "[Helmes] An error occurred while processing your message. Please try again."
