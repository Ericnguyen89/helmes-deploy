import asyncio
import os
import sys
import signal
import logging

import config
from signal_client import SignalClient, encode_image_base64
from ai_engine import AIEngine
from store import ConversationStore
from commands import is_command, handle_command
from memory import MemoryStore
from plugins.memory_tools import set_memory_store
from scheduler import Scheduler
from plugins.scheduler_tools import set_scheduler

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("helmes")

BANNER = r"""
  _   _      _
 | | | | ___| |_ __ ___   ___  ___
 | |_| |/ _ \ | '_ ` _ \ / _ \/ __|
 |  _  |  __/ | | | | | |  __/\__ \
 |_| |_|\___|_|_| |_| |_|\___||___/
                            Agent (async)
"""

MAX_CONCURRENT = 10

_user_locks: dict[str, asyncio.Lock] = {}


def _get_user_lock(sender: str) -> asyncio.Lock:
    if sender not in _user_locks:
        _user_locks[sender] = asyncio.Lock()
    return _user_locks[sender]


def is_sender_allowed(sender: str) -> bool:
    if config.ALLOWED_NUMBERS == "*":
        return True
    allowed = [n.strip() for n in config.ALLOWED_NUMBERS.split(",")]
    return sender in allowed


def can_use_tools(sender: str) -> bool:
    if not config.TOOLS_ENABLED:
        return False
    if config.TOOLS_ADMIN_ONLY:
        return sender in config.ADMIN_NUMBERS
    return True


async def process_message(
    envelope: dict,
    signal_client: SignalClient,
    ai: AIEngine,
    store: ConversationStore,
    memory_store: MemoryStore | None = None,
    scheduler: Scheduler | None = None,
):
    data_message = envelope.get("dataMessage")
    if not data_message:
        return

    text = data_message.get("message", "")
    attachments = data_message.get("attachments", [])

    if (not text or not text.strip()) and not attachments:
        return

    sender = envelope.get("sourceNumber") or envelope.get("source", "")
    if not sender:
        return

    if not is_sender_allowed(sender):
        logger.info("Blocked message from unauthorized sender: %s", sender)
        return

    if config.RATE_LIMIT_PER_HOUR > 0:
        count = store.get_message_count_last_hour(sender)
        if count >= config.RATE_LIMIT_PER_HOUR:
            await signal_client.send(sender, "Rate limit exceeded. Please try again later.")
            logger.warning("Rate limit hit for %s (%d msgs/hr)", sender, count)
            return

    sender_name = envelope.get("sourceName", sender)
    logger.info("Message from %s: %s (attachments: %d)", sender_name, (text or "")[:100], len(attachments))

    async with _get_user_lock(sender):
        if text and is_command(text):
            response, update = handle_command(
                text, sender, store, config.ADMIN_NUMBERS, ai.model, memory_store, scheduler
            )
            if update and "model" in update:
                ai.model = update["model"]
            await signal_client.send(sender, response)
            return

        image_content = await _process_attachments(attachments, signal_client)

        if image_content:
            content_blocks = []
            for img in image_content:
                content_blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img["media_type"],
                        "data": img["data"],
                    },
                })
            if text and text.strip():
                content_blocks.append({"type": "text", "text": text})
            else:
                content_blocks.append({"type": "text", "text": "What is in this image?"})
            user_message = {"role": "user", "content": content_blocks}
        else:
            user_message = {"role": "user", "content": text}

        history = store.get_conversation(sender, config.MAX_CONVERSATION_LENGTH)
        store.add_message(sender, "user", text or "[image]")
        messages = history + [user_message]

        system_prompt = store.get_system_prompt(sender) or config.AI_SYSTEM_PROMPT
        use_tools = can_use_tools(sender)
        response = await ai.chat(messages, system_prompt, use_tools=use_tools, sender=sender)

        store.add_message(sender, "assistant", response)
        await signal_client.send(sender, response)
        logger.info("Replied to %s (%d chars, tools=%s)", sender_name, len(response), use_tools)


async def _process_attachments(attachments: list[dict], signal_client: SignalClient) -> list[dict]:
    images = []
    for att in attachments:
        content_type = att.get("contentType", "")
        if not content_type.startswith("image/"):
            continue
        att_id = att.get("id")
        if not att_id:
            continue
        file_path = await signal_client.download_attachment(att_id)
        if not file_path:
            continue
        result = encode_image_base64(file_path)
        if result:
            media_type, data = result
            images.append({"media_type": media_type, "data": data})
            try:
                os.remove(file_path)
            except Exception:
                pass
    return images


async def wait_for_signal_api(signal_client: SignalClient, max_retries: int = 30) -> bool:
    for i in range(max_retries):
        if await signal_client.is_registered():
            logger.info("Signal API is ready")
            return True
        logger.info("Waiting for Signal API... (%d/%d)", i + 1, max_retries)
        await asyncio.sleep(2)
    logger.error("Signal API did not become ready in time")
    return False


async def main():
    print(BANNER)
    logger.info("Starting Helmes Agent (async)...")

    if not config.SIGNAL_PHONE_NUMBER:
        logger.error("SIGNAL_PHONE_NUMBER is not set")
        sys.exit(1)
    if not config.ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY is not set")
        sys.exit(1)

    signal_client = SignalClient(config.SIGNAL_API_URL, config.SIGNAL_PHONE_NUMBER)
    ai = AIEngine(
        api_key=config.ANTHROPIC_API_KEY,
        model=config.ANTHROPIC_MODEL,
        max_tokens=config.AI_MAX_TOKENS,
        default_system_prompt=config.AI_SYSTEM_PROMPT,
        base_url=config.ANTHROPIC_BASE_URL,
        tools_enabled=config.TOOLS_ENABLED,
        workspace_dir=config.WORKSPACE_DIR,
        thinking_budget=config.THINKING_BUDGET,
        max_tool_iterations=config.MAX_TOOL_ITERATIONS,
        tool_timeout=config.TOOL_TIMEOUT,
        context_summarize_threshold=config.CONTEXT_SUMMARIZE_THRESHOLD,
        context_keep_recent=config.CONTEXT_KEEP_RECENT,
    )
    store = ConversationStore(config.DB_PATH)
    memory_store = MemoryStore(config.DB_PATH)
    ai.memory_store = memory_store
    set_memory_store(memory_store)

    async def scheduled_task_callback(sender: str, prompt: str):
        system_prompt = store.get_system_prompt(sender) or config.AI_SYSTEM_PROMPT
        messages = [{"role": "user", "content": prompt}]
        use_tools = can_use_tools(sender)
        response = await ai.chat(messages, system_prompt, use_tools=use_tools, sender=sender)
        await signal_client.send(sender, f"⏰ [Scheduled Task]\n{response}")

    scheduler = Scheduler(config.DB_PATH, callback=scheduled_task_callback)
    set_scheduler(scheduler)

    logger.info("Phone: %s", config.SIGNAL_PHONE_NUMBER)
    logger.info("Model: %s", config.ANTHROPIC_MODEL)
    logger.info("Base URL: %s", config.ANTHROPIC_BASE_URL or "https://api.anthropic.com (default)")
    logger.info("Tools: %s (admin_only=%s)", config.TOOLS_ENABLED, config.TOOLS_ADMIN_ONLY)
    logger.info("Workspace: %s", config.WORKSPACE_DIR)
    logger.info("Allowed: %s", config.ALLOWED_NUMBERS)
    logger.info("Admins: %s", config.ADMIN_NUMBERS)
    logger.info("Max concurrent: %d", MAX_CONCURRENT)

    if not await wait_for_signal_api(signal_client):
        logger.warning("Starting anyway - Signal API may not be registered yet")

    logger.info("Polling for messages every %ds...", config.POLL_INTERVAL)
    scheduler.start()

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    active_tasks: set[asyncio.Task] = set()
    running = True

    def shutdown_handler(signum, frame):
        nonlocal running
        logger.info("Shutdown signal received, stopping...")
        running = False

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    consecutive_errors = 0

    try:
        while running:
            try:
                received = await signal_client.receive()
                consecutive_errors = 0

                for msg in received:
                    envelope = msg.get("envelope", {})

                    async def _handle(env=envelope):
                        async with semaphore:
                            try:
                                await process_message(
                                    env, signal_client, ai, store, memory_store, scheduler
                                )
                            except Exception:
                                logger.exception("Error processing message")

                    task = asyncio.create_task(_handle())
                    active_tasks.add(task)
                    task.add_done_callback(active_tasks.discard)

            except Exception:
                consecutive_errors += 1
                logger.exception("Error in polling loop (consecutive: %d)", consecutive_errors)
                if consecutive_errors > 10:
                    logger.error("Too many consecutive errors, sleeping 30s...")
                    await asyncio.sleep(30)
                    consecutive_errors = 0

            await asyncio.sleep(config.POLL_INTERVAL)

    finally:
        logger.info("Shutting down... waiting for %d active tasks", len(active_tasks))
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)
        await scheduler.stop()
        await signal_client.close()
        logger.info("Helmes Agent stopped.")


if __name__ == "__main__":
    asyncio.run(main())
