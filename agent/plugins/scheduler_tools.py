from .base import ToolPlugin, ToolContext

_scheduler = None


def set_scheduler(scheduler):
    global _scheduler
    _scheduler = scheduler


def get_scheduler():
    return _scheduler


class ScheduleAddTool(ToolPlugin):
    name = "schedule_add"
    description = (
        "Schedule a recurring task using cron syntax. "
        "The task prompt will be executed automatically at the specified times. "
        "Cron format: 'minute hour day_of_month month day_of_week'. "
        "Examples: '0 9 * * *' = daily at 9am, '*/30 * * * *' = every 30 min, "
        "'0 9 * * 1-5' = weekdays at 9am."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Unique name for this scheduled task",
            },
            "cron": {
                "type": "string",
                "description": "Cron expression (min hour dom month dow)",
            },
            "prompt": {
                "type": "string",
                "description": "The task/instruction to execute on schedule",
            },
        },
        "required": ["name", "cron", "prompt"],
    }

    def execute(self, tool_input: dict, context: ToolContext) -> str:
        scheduler = get_scheduler()
        if not scheduler:
            return "Error: Scheduler not initialized"
        sender = getattr(context, "sender", None)
        if not sender:
            return "Error: No sender context"
        return scheduler.add_task(
            sender,
            tool_input["name"],
            tool_input["cron"],
            tool_input["prompt"],
        )


class ScheduleListTool(ToolPlugin):
    name = "schedule_list"
    description = "List all scheduled tasks for the current user."
    input_schema = {
        "type": "object",
        "properties": {},
    }

    def execute(self, tool_input: dict, context: ToolContext) -> str:
        scheduler = get_scheduler()
        if not scheduler:
            return "Error: Scheduler not initialized"
        sender = getattr(context, "sender", None)
        if not sender:
            return "Error: No sender context"
        tasks = scheduler.list_tasks(sender)
        if not tasks:
            return "No scheduled tasks."
        lines = [f"Scheduled tasks ({len(tasks)}):\n"]
        for t in tasks:
            status = "enabled" if t["enabled"] else "disabled"
            lines.append(f"• {t['name']} [{status}]")
            lines.append(f"  Cron: {t['cron_expr']}")
            lines.append(f"  Task: {t['task_prompt'][:100]}")
            if t["last_run"]:
                lines.append(f"  Last run: {t['last_run']}")
            lines.append("")
        return "\n".join(lines)


class ScheduleRemoveTool(ToolPlugin):
    name = "schedule_remove"
    description = "Remove a scheduled task by name."
    input_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name of the scheduled task to remove",
            },
        },
        "required": ["name"],
    }

    def execute(self, tool_input: dict, context: ToolContext) -> str:
        scheduler = get_scheduler()
        if not scheduler:
            return "Error: Scheduler not initialized"
        sender = getattr(context, "sender", None)
        if not sender:
            return "Error: No sender context"
        removed = scheduler.remove_task(sender, tool_input["name"])
        if removed:
            return f"Scheduled task removed: {tool_input['name']}"
        return f"Task not found: {tool_input['name']}"
