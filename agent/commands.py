import logging
from store import ConversationStore

logger = logging.getLogger(__name__)

HELP_TEXT = """*Helmes Agent - Commands*

/help - Show this help message
/reset - Clear conversation history
/system <prompt> - Set custom system prompt (admin)
/system - Show current system prompt
/info - Show conversation stats
/model <name> - Switch AI model (admin)
/ping - Check if agent is alive"""

COMMANDS = {"/help", "/reset", "/system", "/info", "/model", "/ping"}


def is_command(text: str) -> bool:
    return text.strip().split()[0].lower() in COMMANDS


def handle_command(
    text: str,
    sender: str,
    store: ConversationStore,
    admin_numbers: list[str],
    current_model: str,
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

    return f"Unknown command: {cmd}\nType /help for available commands.", None
