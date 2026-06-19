import logging

from anthropic import Anthropic

logger = logging.getLogger(__name__)

SUMMARIZE_PROMPT = (
    "Summarize the conversation so far into a concise paragraph. "
    "Preserve key facts, decisions, user preferences, and any ongoing tasks. "
    "Keep technical details that would be needed to continue the conversation. "
    "Write in the same language the user has been using."
)


def count_tokens_estimate(messages: list[dict]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += len(content) // 4
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    for v in block.values():
                        if isinstance(v, str):
                            total += len(v) // 4
    return total


def summarize_conversation(
    client: Anthropic,
    model: str,
    messages: list[dict],
    keep_recent: int = 6,
) -> list[dict]:
    if len(messages) <= keep_recent + 2:
        return messages

    old_messages = messages[:-keep_recent]
    recent_messages = messages[-keep_recent:]

    summary_input = []
    for msg in old_messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            summary_input.append({"role": msg["role"], "content": content})
        elif isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        text_parts.append(f"[Used tool: {block.get('name', '?')}]")
                    elif block.get("type") == "tool_result":
                        text_parts.append(f"[Tool result: {str(block.get('content', ''))[:200]}]")
            if text_parts:
                summary_input.append({"role": msg["role"], "content": "\n".join(text_parts)})

    if not summary_input:
        return messages

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SUMMARIZE_PROMPT,
            messages=summary_input + [
                {"role": "user", "content": "Please summarize the conversation above."}
            ],
        )
        summary_text = response.content[0].text
        logger.info(
            "Summarized %d messages into %d chars, keeping %d recent",
            len(old_messages),
            len(summary_text),
            len(recent_messages),
        )

        return [
            {"role": "user", "content": f"[Previous conversation summary]\n{summary_text}"},
            {"role": "assistant", "content": "Understood, I have the context from our previous conversation. How can I help you?"},
        ] + recent_messages

    except Exception:
        logger.exception("Failed to summarize conversation")
        return messages
