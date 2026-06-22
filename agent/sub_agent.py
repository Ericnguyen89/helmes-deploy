"""Sub-agent executor for task decomposition (inspired by DeerFlow).

When a complex task is detected, the lead agent decomposes it into focused
sub-tasks. Each sub-task runs with its own system prompt (skill), scoped
tools, and iteration budget — preventing any single sub-task from exhausting
the full budget.

Provider-agnostic: works with any LLMProvider (Anthropic, OpenAI, Gemini).
"""

import asyncio
import json
import logging
import uuid

from task_result import TaskResult, TaskStatus
from skills import Skill
from providers import LLMProvider
from model_router import ModelRouter, ModelTier

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

SYNTHESIS_PROMPT = (
    "Synthesize the following sub-task results into a coherent, well-structured "
    "response for the user. Respond in the same language as the content."
)


class SubAgentExecutor:
    """Executes focused sub-tasks with scoped prompts and tools."""

    def __init__(
        self,
        provider: LLMProvider,
        tools_enabled: bool,
        tool_definitions: list[dict],
        workspace_dir: str,
        tool_timeout: int,
        execute_tool_fn,
        router: ModelRouter | None = None,
    ):
        self.provider = provider
        self.tools_enabled = tools_enabled
        self.tool_definitions = tool_definitions
        self.workspace_dir = workspace_dir
        self.tool_timeout = tool_timeout
        self.execute_tool_fn = execute_tool_fn
        self.router = router

    def _light(self) -> str | None:
        """Model for the orchestration role (decompose + synthesis)."""
        return self.router.model_for(ModelTier.LIGHT) if self.router else None

    def _route(self, desc: str, skill_name: str | None) -> str | None:
        """Model for a sub-task, chosen by its complexity."""
        return self.router.model_for_message(desc, skill_name) if self.router else None

    async def try_decompose(self, message: str) -> list[dict] | None:
        """Try to decompose a complex task into sub-tasks.

        Returns list of sub-task dicts or None if task is simple.
        """
        try:
            response = await self.provider.create(
                [{"role": "user", "content": message}],
                system=DECOMPOSE_PROMPT,
                max_tokens=1024,
                model=self._light(),  # orchestration runs on the light model
            )
            text = response.text.strip()
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

    def _scoped_tools(self, skill: Skill | None) -> list[dict] | None:
        if not self.tools_enabled:
            return None
        if skill and skill.tool_hints:
            # Always allow delivery tools through the skill filter.
            hint_set = set(skill.tool_hints) | {"send_file"}
            scoped = [t for t in self.tool_definitions if t["name"] in hint_set]
            return scoped or self.tool_definitions
        return self.tool_definitions

    async def execute_subtask(
        self,
        task_desc: str,
        skill: Skill | None,
        max_iterations: int,
        sender: str = "",
        context: str = "",
        model: str | None = None,
    ) -> TaskResult:
        """Execute a single sub-task with focused prompt and iteration budget."""
        task_id = str(uuid.uuid4())[:8]
        result = TaskResult(task_id=task_id, skill_used=skill.name if skill else None)
        result.model_used = model
        result.start()

        system_prompt = "You are Helmes, executing a focused sub-task."
        if skill:
            system_prompt += f"\n\n{skill.content}"
        if context:
            system_prompt += f"\n\n## Context from previous steps\n{context}"

        tools = self._scoped_tools(skill)
        messages = [{"role": "user", "content": task_desc}]

        try:
            for iteration in range(max_iterations):
                remaining = max_iterations - iteration - 1
                active_tools = None if remaining <= 1 else tools

                response = await self.provider.create(
                    messages, system=system_prompt, tools=active_tools, model=model,
                )
                result.tool_iterations = iteration + 1
                result.token_usage.add(response.usage)

                if response.has_tool_calls:
                    messages.append({
                        "role": "assistant",
                        "content": response.assistant_content,
                    })

                    tool_ids = [tc.id for tc in response.tool_calls]
                    tool_tasks = [
                        self.execute_tool_fn(
                            tc.name, tc.input,
                            self.workspace_dir, self.tool_timeout,
                            sender=sender,
                        )
                        for tc in response.tool_calls
                    ]

                    results = await asyncio.gather(*tool_tasks, return_exceptions=True)

                    tool_results = []
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

                result.complete(response.text or "No response generated.")
                return result

            # Exhausted iterations — force final response
            try:
                final = await self.provider.create(messages, system=system_prompt, model=model)
                result.token_usage.add(final.usage)
                result.complete(final.text or "Sub-task completed but no summary generated.")
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
                model = self._route(desc, task_type)

                task_result = await self.execute_subtask(
                    desc, skill, per_task_budget,
                    sender=sender, context=context_so_far, model=model,
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
                    model = self._route(desc, task_type)
                    return desc, await self.execute_subtask(
                        desc, skill, per_task_budget, sender=sender, model=model,
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
            synth_response = await self.provider.create(
                [{"role": "user", "content": combined}],
                system=SYNTHESIS_PROMPT,
                model=self._light(),  # synthesis runs on the light model
            )
            parent_result.token_usage.add(synth_response.usage)
            final_text = synth_response.text or combined
        except Exception:
            logger.exception("Synthesis failed, returning raw results")
            final_text = combined

        parent_result.complete(final_text)
        return final_text, parent_result
