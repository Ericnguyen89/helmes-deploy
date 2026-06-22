import asyncio
import logging

from tools import TOOL_DEFINITIONS, execute_tool_async
from summarizer import summarize_conversation
from memory import MemoryStore
from planner import get_enhanced_system_prompt
from skills import SkillRegistry
from task_result import TaskResult, TokenUsage
from sub_agent import SubAgentExecutor
from providers import create_provider, detect_provider

logger = logging.getLogger(__name__)


class AIEngine:
    def __init__(
        self,
        provider_name: str,
        model: str,
        max_tokens: int,
        default_system_prompt: str,
        provider_configs: dict[str, dict] | None = None,
        tools_enabled: bool = False,
        workspace_dir: str = "/workspace",
        thinking_budget: int = 10000,
        max_tool_iterations: int = 30,
        tool_timeout: int = 120,
        context_summarize_threshold: int = 20,
        context_keep_recent: int = 6,
        summarize_model: str | None = None,
    ):
        self.provider_name = provider_name
        self.model = model
        self.max_tokens = max_tokens
        self.default_system_prompt = default_system_prompt
        # Per-provider credentials, used to switch providers at runtime.
        self.provider_configs = provider_configs or {}
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
        self.provider = self._build_provider(provider_name, model)
        self.sub_agent = self._build_sub_agent()
        self._last_task_result: TaskResult | None = None

    def _build_provider(self, provider_name: str, model: str):
        cfg = self.provider_configs.get(provider_name, {})
        return create_provider(
            provider_name,
            api_key=cfg.get("api_key", ""),
            model=model,
            base_url=cfg.get("base_url"),
            max_tokens=self.max_tokens,
            thinking_budget=self.thinking_budget,
        )

    def _build_sub_agent(self) -> SubAgentExecutor:
        return SubAgentExecutor(
            provider=self.provider,
            tools_enabled=self.tools_enabled,
            tool_definitions=TOOL_DEFINITIONS,
            workspace_dir=self.workspace_dir,
            tool_timeout=self.tool_timeout,
            execute_tool_fn=execute_tool_async,
        )

    def set_model(self, model: str) -> tuple[bool, str]:
        """Switch model (and provider, if the model belongs to another one).

        Returns (success, message). The provider is inferred from the model name;
        switching requires that provider's API key to be configured.
        """
        provider_name = detect_provider(model) or self.provider_name
        cfg = self.provider_configs.get(provider_name, {})
        if not cfg.get("api_key"):
            return False, (
                f"Cannot switch to {model}: no API key configured for provider "
                f"'{provider_name}'. Set the corresponding *_API_KEY in .env."
            )
        try:
            self.provider_name = provider_name
            self.model = model
            self.provider = self._build_provider(provider_name, model)
            self.sub_agent = self._build_sub_agent()
        except Exception as e:
            logger.exception("Failed to switch model")
            return False, f"Failed to switch model: {e}"
        return True, f"Model switched to: {model} (provider: {provider_name})"

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
                    self.provider,
                    summary_model,
                    messages,
                    keep_recent=self.context_keep_recent,
                )
                logger.info("Context summarized: %d messages remaining", len(messages))

            tools = TOOL_DEFINITIONS if use_tools else None
            current_messages = list(messages)
            task_result = TaskResult(task_id="main")
            task_result.start()
            if skill:
                task_result.skill_used = skill.name

            for iteration in range(self.max_tool_iterations):
                remaining = self.max_tool_iterations - iteration - 1
                force_respond = remaining <= 1
                active_tools = None if force_respond else tools

                response = await self.provider.create(
                    current_messages, system=system_prompt, tools=active_tools,
                )
                task_result.token_usage.add(response.usage)
                task_result.tool_iterations = iteration + 1

                if response.has_tool_calls:
                    current_messages.append({
                        "role": "assistant",
                        "content": response.assistant_content,
                    })

                    tool_ids = [tc.id for tc in response.tool_calls]
                    tool_tasks = [
                        execute_tool_async(
                            tc.name, tc.input,
                            self.workspace_dir, self.tool_timeout,
                            sender=sender,
                        )
                        for tc in response.tool_calls
                    ]

                    results = await asyncio.gather(*tool_tasks, return_exceptions=True)

                    budget_note = self._budget_note(iteration)
                    tool_results = []
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

                text = response.text
                if text:
                    task_result.complete(text)
                    self._last_task_result = task_result
                    logger.info("Task completed: %s", task_result.to_summary())
                    return text
                return "[Helmes] No response generated."

            logger.warning("Reached max tool iterations (%d)", self.max_tool_iterations)
            try:
                final = await self.provider.create(current_messages, system=system_prompt)
                task_result.token_usage.add(final.usage)
                text = final.text
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
