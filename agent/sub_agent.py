"""Sub-agent executor for task decomposition (inspired by DeerFlow).

When a complex task is detected, the lead agent decomposes it into focused
sub-tasks. Each sub-task runs with its own system prompt (skill), scoped
tools, and iteration budget — preventing any single sub-task from exhausting
the full budget.
"""

import asyncio
import logging
import uuid

from anthropic import AsyncAnthropic

from task_result import TaskResult, TaskStatus, TokenUsage
from skills import Skill

logger = logging.getLogger(__name__)

MAX_CONCURRENT_SUBAGENTS = 3

DECOMPOSE_PROMPT = """Analyze the user's request and determine if it needs to be broken into sub-tasks.

If the task is SIMPLE (can be done in 1-5 tool calls), respond with:
{"decompose": false}

If the task is COMPLEX (requires research + analysis, multiple unrelated steps, or would need 10+ tool calls), break it into 2-4 focused sub-tasks. Respond with:
{"decompose": true, "sub_tasks": [
  {"task": "description of sub-task 1", "type": "research|coding|sysadmin|data_analysis|general"},
  {"task": "description of sub-task 2", "type": "research|coding|sysadmin|data_analysis|general"}
]}

Rules:
- Each sub-task should be self-contained and independently executable
- Prefer fewer sub-tasks (2-3) over many small ones
- Use the type field to match the appropriate skill
- For sequential dependencies, number them: "1. First do X", "2. Then do Y"

Respond ONLY with the JSON, no other text."""


class SubAgentExecutor:
    """Executes focused sub-tasks with scoped prompts and tools."""

    def __init__(
        self,
        client: AsyncAnthropic,
        model: str,
        max_tokens: int,
        tools_enabled: bool,
        tool_definitions: list[dict],
        workspace_dir: str,
        tool_timeout: int,
        thinking_budget: int,
        execute_tool_fn,
    ):
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.tools_enabled = tools_enabled
        self.tool_definitions = tool_definitions
        self.workspace_dir = workspace_dir
        self.tool_timeout = tool_timeout
        self.thinking_budget = thinking_budget
        self.execute_tool_fn = execute_tool_fn

    async def try_decompose(self, message: str) -> list[dict] | None:
        """Try to decompose a complex task into sub-tasks.

        Returns list of sub-task dicts or None if task is simple.
        """
        try:
            kwargs = {
                "model": self.model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": message}],
                "system": DECOMPOSE_PROMPT,
            }
            if "thinking" in self.model.lower():
                kwargs["thinking"] = {"type": "enabled", "budget_tokens": 2048}
                kwargs["max_tokens"] = 4096
            response = await self.client.messages.create(**kwargs)
            text = ""
            for block in response.content:
                if block.type == "text":
                    text += block.text

            import json
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            result = json.loads(text)

            if result.get("decompose") and result.get("sub_tasks"):
                sub_tasks = result["sub_tasks"]
                if len(sub_tasks) >= 2:
                    logger.info("Task decomposed into %d sub-tasks", len(sub_tasks))
                    return sub_tasks
        except Exception:
            logger.debug("Decomposition failed, treating as simple task", exc_info=True)
        return None

    async def execute_subtask(
        self,
        task_desc: str,
        skill: Skill | None,
        max_iterations: int,
        sender: str = "",
        context: str = "",
    ) -> TaskResult:
        """Execute a single sub-task with focused prompt and iteration budget."""
        from ai_engine import _serialize_content, _extract_text

        task_id = str(uuid.uuid4())[:8]
        result = TaskResult(task_id=task_id, skill_used=skill.name if skill else None)
        result.start()

        system_prompt = "You are Helmes, executing a focused sub-task."
        if skill:
            system_prompt += f"\n\n{skill.content}"
        if context:
            system_prompt += f"\n\n## Context from previous steps\n{context}"

        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
        }

        if "thinking" in self.model.lower():
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": self.thinking_budget}
            if self.max_tokens < self.thinking_budget + 4096:
                kwargs["max_tokens"] = self.thinking_budget + 4096

        if self.tools_enabled:
            if skill and skill.tool_hints:
                hint_set = set(skill.tool_hints)
                kwargs["tools"] = [
                    t for t in self.tool_definitions
                    if t["name"] in hint_set
                ] or self.tool_definitions
            else:
                kwargs["tools"] = self.tool_definitions

        messages = [{"role": "user", "content": task_desc}]

        try:
            for iteration in range(max_iterations):
                remaining = max_iterations - iteration - 1
                if remaining <= 1:
                    kwargs.pop("tools", None)

                kwargs["messages"] = messages
                response = await self.client.messages.create(**kwargs)
                result.tool_iterations = iteration + 1
                result.token_usage.add(TokenUsage.from_api_response(response))

                if response.stop_reason == "tool_use":
                    messages.append({
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
                                self.execute_tool_fn(
                                    block.name, block.input,
                                    self.workspace_dir, self.tool_timeout,
                                    sender=sender,
                                )
                            )

                    results = await asyncio.gather(*tool_tasks, return_exceptions=True)

                    for i, (tool_id, tool_result) in enumerate(zip(tool_ids, results)):
                        content = str(tool_result) if isinstance(tool_result, Exception) else tool_result
                        if remaining <= 3 and i == len(tool_ids) - 1:
                            content += f"\n\n[Sub-task budget: {remaining} iterations remaining. Wrap up.]"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": content,
                        })

                    messages.append({"role": "user", "content": tool_results})
                    continue

                text = _extract_text(response.content)
                result.complete(text or "No response generated.")
                return result

            # Exhausted iterations — force final response
            kwargs["messages"] = messages
            kwargs.pop("tools", None)
            try:
                final = await self.client.messages.create(**kwargs)
                result.token_usage.add(TokenUsage.from_api_response(final))
                text = _extract_text(final.content)
                result.complete(text or "Sub-task completed but no summary generated.")
            except Exception:
                result.complete("Sub-task completed (max iterations reached).")

        except Exception as e:
            logger.exception("Sub-task execution failed: %s", task_id)
            result.fail(str(e))

        return result

    async def execute_decomposed(
        self,
        sub_tasks: list[dict],
        skill_registry,
        sender: str = "",
        total_budget: int = 30,
    ) -> tuple[str, TaskResult]:
        """Execute decomposed sub-tasks and synthesize results.

        Sequential sub-tasks (numbered) run in order with context passing.
        Independent sub-tasks run concurrently (up to MAX_CONCURRENT_SUBAGENTS).
        """
        from ai_engine import _extract_text

        parent_result = TaskResult(task_id=str(uuid.uuid4())[:8])
        parent_result.start()

        per_task_budget = max(5, total_budget // len(sub_tasks))
        context_so_far = ""
        results: list[tuple[str, TaskResult]] = []

        has_sequential = any(
            task_desc.get("task", "").strip()[:2].rstrip(".").isdigit()
            for task_desc in sub_tasks
        )

        if has_sequential:
            for sub in sub_tasks:
                desc = sub.get("task", "")
                task_type = sub.get("type", "general")
                skill = skill_registry.get(task_type)

                task_result = await self.execute_subtask(
                    desc, skill, per_task_budget,
                    sender=sender, context=context_so_far,
                )
                results.append((desc, task_result))
                parent_result.sub_tasks.append(task_result)

                if task_result.result:
                    context_so_far += f"\n\n### {desc}\n{task_result.result}"
        else:
            sem = asyncio.Semaphore(MAX_CONCURRENT_SUBAGENTS)

            async def run_with_sem(sub):
                async with sem:
                    desc = sub.get("task", "")
                    task_type = sub.get("type", "general")
                    skill = skill_registry.get(task_type)
                    return desc, await self.execute_subtask(
                        desc, skill, per_task_budget, sender=sender,
                    )

            task_results = await asyncio.gather(
                *(run_with_sem(s) for s in sub_tasks),
                return_exceptions=True,
            )
            for tr in task_results:
                if isinstance(tr, Exception):
                    logger.error("Sub-task failed: %s", tr)
                    continue
                results.append(tr)
                parent_result.sub_tasks.append(tr[1])

        # Synthesize
        synthesis_parts = []
        for desc, tr in results:
            status_icon = "done" if tr.status == TaskStatus.COMPLETED else "failed"
            synthesis_parts.append(f"**[{status_icon}] {desc}**\n{tr.result or tr.error or 'No output'}")

        combined = "\n\n---\n\n".join(synthesis_parts)

        try:
            synth_kwargs = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "system": "Synthesize the following sub-task results into a coherent, well-structured response for the user. Respond in the same language as the content.",
                "messages": [{"role": "user", "content": combined}],
            }
            if "thinking" in self.model.lower():
                synth_kwargs["thinking"] = {"type": "enabled", "budget_tokens": self.thinking_budget}
                if self.max_tokens < self.thinking_budget + 4096:
                    synth_kwargs["max_tokens"] = self.thinking_budget + 4096
            synth_response = await self.client.messages.create(**synth_kwargs)
            parent_result.token_usage.add(TokenUsage.from_api_response(synth_response))
            text = _extract_text(synth_response.content)
            final_text = text or combined
        except Exception:
            logger.exception("Synthesis failed, returning raw results")
            final_text = combined

        parent_result.complete(final_text)
        return final_text, parent_result
