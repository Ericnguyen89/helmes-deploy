import logging

logger = logging.getLogger(__name__)

PLANNING_PROMPT_ADDON = """

## Task Planning

When the user gives you a complex or multi-step task, follow this approach:

1. **Analyze**: Understand what the user wants and break it into clear steps.
2. **Plan**: Before executing, briefly outline your plan (2-5 steps).
3. **Execute**: Work through each step, using tools as needed.
4. **Report**: Summarize what you did and the results.

For simple questions or single-step tasks, respond directly without planning.

When you create a plan, format it as:
📋 Plan:
1. [step 1]
2. [step 2]
...

Then execute each step and mark them done:
✅ Step 1: [result]
✅ Step 2: [result]

If a step fails, explain why and adjust the plan.
"""


def get_enhanced_system_prompt(base_prompt: str) -> str:
    return base_prompt + PLANNING_PROMPT_ADDON
