from .base import ToolPlugin, ToolContext


_memory_store = None


def set_memory_store(store):
    global _memory_store
    _memory_store = store


def get_memory_store():
    return _memory_store


class MemorySaveTool(ToolPlugin):
    name = "memory_save"
    description = (
        "Save information to long-term memory. Use this to remember user preferences, "
        "important facts, project details, or anything that should persist across conversations. "
        "Each memory has a unique key — saving with an existing key updates it."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "Short identifier for this memory (e.g., 'user_name', 'project_stack', 'preferred_language')",
            },
            "content": {
                "type": "string",
                "description": "The information to remember",
            },
            "category": {
                "type": "string",
                "description": "Category for organization (e.g., 'user', 'project', 'preference', 'fact'). Default: 'general'",
            },
        },
        "required": ["key", "content"],
    }

    def execute(self, tool_input: dict, context: ToolContext) -> str:
        store = get_memory_store()
        if not store:
            return "Error: Memory system not initialized"
        sender = getattr(context, "sender", None)
        if not sender:
            return "Error: No sender context for memory"
        return store.save(
            sender,
            tool_input["key"],
            tool_input["content"],
            tool_input.get("category", "general"),
        )


class MemoryRecallTool(ToolPlugin):
    name = "memory_recall"
    description = (
        "Search long-term memory for previously saved information. "
        "Use this to recall user preferences, project details, or any saved facts. "
        "Searches across keys, content, and categories."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term to find relevant memories",
            },
        },
        "required": ["query"],
    }

    def execute(self, tool_input: dict, context: ToolContext) -> str:
        store = get_memory_store()
        if not store:
            return "Error: Memory system not initialized"
        sender = getattr(context, "sender", None)
        if not sender:
            return "Error: No sender context for memory"
        results = store.recall(sender, tool_input["query"])
        if not results:
            return f"No memories found matching: {tool_input['query']}"
        lines = [f"Found {len(results)} memories:\n"]
        for r in results:
            lines.append(f"[{r['category']}] {r['key']}: {r['content']}")
            lines.append(f"  (updated: {r['updated_at']})")
        return "\n".join(lines)


class MemoryDeleteTool(ToolPlugin):
    name = "memory_delete"
    description = "Delete a specific memory by its key."
    input_schema = {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "The key of the memory to delete",
            },
        },
        "required": ["key"],
    }

    def execute(self, tool_input: dict, context: ToolContext) -> str:
        store = get_memory_store()
        if not store:
            return "Error: Memory system not initialized"
        sender = getattr(context, "sender", None)
        if not sender:
            return "Error: No sender context for memory"
        deleted = store.delete(sender, tool_input["key"])
        if deleted:
            return f"Memory deleted: {tool_input['key']}"
        return f"Memory not found: {tool_input['key']}"
