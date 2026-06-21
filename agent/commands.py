import logging
from store import ConversationStore
from memory import MemoryStore
from scheduler import Scheduler

logger = logging.getLogger(__name__)

HELP_TEXT = """*Helmes Agent - Commands*

/help - Show this help message
/reset - Clear conversation history
/system <prompt> - Set custom system prompt (admin)
/system - Show current system prompt
/info - Show conversation stats
/status - Show last task execution stats
/model <name> - Switch AI model (admin)
/memory - List all saved memories
/schedule - List scheduled tasks
/ping - Check if agent is alive"""

COMMANDS = {"/help", "/reset", "/system", "/info", "/status", "/model", "/memory", "/schedule", "/ping"}


def is_command(text: str) -> bool:
    return text.strip().split()[0].lower() in COMMANDS


def handle_command(
    text: str,
    sender: str,
    store: ConversationStore,
    admin_numbers: list[str],
    current_model: str,
    memory_store: MemoryStore | None = None,
    scheduler: Scheduler | None = None,
    ai_engine=None,
) -> tuple[str, dict | None]:
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    is_admin = sender in admin_numbers
    config_update = None

    if cmd == "/help":
        return HELP_TEXT, None

    if cmd == "/ping":
        return "Pong! Helmes Agent is running.", None

    if cmd == "/reset":
        store.clear_conversation(sender)
        return "Conversation history cleared. Starting fresh!", None

    if cmd == "/info":
        stats = store.get_stats(sender)
        prompt = store.get_system_prompt(sender)
        lines = [
            f"Messages in history: {stats['total_messages']}",
            f"Current model: {current_model}",
            f"Custom system prompt: {'Yes' if prompt else 'No (using default)'}",
            f"Admin: {'Yes' if is_admin else 'No'}",
        ]
        if ai_engine and hasattr(ai_engine, 'skill_registry'):
            lines.append(f"Skills loaded: {', '.join(ai_engine.skill_registry.list_skills())}")
        return "\n".join(lines), None

    if cmd == "/status":
        if not ai_engine or not hasattr(ai_engine, '_last_task_result') or not ai_engine._last_task_result:
            return "No task has been executed yet.", None
        tr = ai_engine._last_task_result
        lines = [
            "*Last Task Stats*",
            f"Status: {tr.status.value}",
            f"Duration: {tr.duration_seconds}s",
            f"Tokens: {tr.token_usage.input_tokens} in / {tr.token_usage.output_tokens} out",
            f"Tool iterations: {tr.tool_iterations}",
        ]
        if tr.skill_used:
            lines.append(f"Skill: {tr.skill_used}")
        if tr.sub_tasks:
            lines.append(f"\nSub-tasks: {len(tr.sub_tasks)}")
            for i, st in enumerate(tr.sub_tasks, 1):
                lines.append(f"  {i}. [{st.status.value}] {st.skill_used or 'general'} — {st.tool_iterations} iters, {st.token_usage.total_tokens} tokens")
        return "\n".join(lines), None

    if cmd == "/system":
        if not arg:
            prompt = store.get_system_prompt(sender)
            if prompt:
                return f"Current system prompt:\n{prompt}", None
            return "Using default system prompt. Use /system <prompt> to set a custom one.", None
        if not is_admin:
            return "Only admins can change the system prompt.", None
        store.set_system_prompt(sender, arg)
        return f"System prompt updated!", None

    if cmd == "/model":
        if not arg:
            return f"Current model: {current_model}", None
        if not is_admin:
            return "Only admins can change the model.", None
        config_update = {"model": arg}
        return f"Model switched to: {arg}", config_update

    if cmd == "/memory":
        if not memory_store:
            return "Memory system not available.", None
        memories = memory_store.list_all(sender)
        if not memories:
            return "No memories saved yet. The AI will save important info automatically.", None
        lines = [f"*Saved Memories ({len(memories)})*\n"]
        current_cat = None
        for m in memories:
            if m["category"] != current_cat:
                current_cat = m["category"]
                lines.append(f"\n📂 {current_cat}")
            lines.append(f"  • {m['key']}: {m['content']}")
        return "\n".join(lines), None

    if cmd == "/schedule":
        if not scheduler:
            return "Scheduler not available.", None
        tasks = scheduler.list_tasks(sender)
        if not tasks:
            return "No scheduled tasks. Ask the AI to schedule tasks for you.", None
        lines = [f"*Scheduled Tasks ({len(tasks)})*\n"]
        for t in tasks:
            status = "✅" if t["enabled"] else "⏸️"
            lines.append(f"{status} {t['name']}")
            lines.append(f"   Cron: {t['cron_expr']}")
            lines.append(f"   Task: {t['task_prompt'][:80]}")
            if t["last_run"]:
                lines.append(f"   Last: {t['last_run']}")
        return "\n".join(lines), None

    return f"Unknown command: {cmd}\nType /help for available commands.", None
