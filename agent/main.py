import sys
import time
import logging
import signal

import config
from signal_client import SignalClient
from ai_engine import AIEngine
from store import ConversationStore
from commands import is_command, handle_command

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("helmes")

running = True


def shutdown_handler(signum, frame):
    global running
    logger.info("Shutdown signal received, stopping...")
    running = False


signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)


BANNER = r"""
  _   _      _
 | | | | ___| |_ __ ___   ___  ___
 | |_| |/ _ \ | '_ ` _ \ / _ \/ __|
 |  _  |  __/ | | | | | |  __/\__ \
 |_| |_|\___|_|_| |_| |_|\___||___/
                            Agent
"""


def is_sender_allowed(sender: str) -> bool:
    if config.ALLOWED_NUMBERS == "*":
        return True
    allowed = [n.strip() for n in config.ALLOWED_NUMBERS.split(",")]
    return sender in allowed


def process_message(
    envelope: dict,
    signal_client: SignalClient,
    ai: AIEngine,
    store: ConversationStore,
):
    data_message = envelope.get("dataMessage")
    if not data_message:
        return

    text = data_message.get("message", "")
    if not text or not text.strip():
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
            signal_client.send(sender, "Rate limit exceeded. Please try again later.")
            logger.warning("Rate limit hit for %s (%d msgs/hr)", sender, count)
            return

    sender_name = envelope.get("sourceName", sender)
    logger.info("Message from %s: %s", sender_name, text[:100])

    if is_command(text):
        response, update = handle_command(
            text, sender, store, config.ADMIN_NUMBERS, ai.model
        )
        if update and "model" in update:
            ai.model = update["model"]
        signal_client.send(sender, response)
        return

    history = store.get_conversation(sender, config.MAX_CONVERSATION_LENGTH)
    store.add_message(sender, "user", text)
    messages = history + [{"role": "user", "content": text}]

    system_prompt = store.get_system_prompt(sender) or config.AI_SYSTEM_PROMPT
    response = ai.chat(messages, system_prompt)

    store.add_message(sender, "assistant", response)
    signal_client.send(sender, response)
    logger.info("Replied to %s (%d chars)", sender_name, len(response))


def wait_for_signal_api(signal_client: SignalClient, max_retries: int = 30):
    for i in range(max_retries):
        if signal_client.is_registered():
            logger.info("Signal API is ready")
            return True
        logger.info("Waiting for Signal API... (%d/%d)", i + 1, max_retries)
        time.sleep(2)
    logger.error("Signal API did not become ready in time")
    return False


def main():
    print(BANNER)
    logger.info("Starting Helmes Agent...")

    if not config.SIGNAL_PHONE_NUMBER:
        logger.error("SIGNAL_PHONE_NUMBER is not set")
        sys.exit(1)
    if not config.ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY is not set")
        sys.exit(1)

    signal_client = SignalClient(config.SIGNAL_API_URL, config.SIGNAL_PHONE_NUMBER)
    ai = AIEngine(config.ANTHROPIC_API_KEY, config.ANTHROPIC_MODEL, config.AI_MAX_TOKENS, config.AI_SYSTEM_PROMPT, config.ANTHROPIC_BASE_URL)
    store = ConversationStore(config.DB_PATH)

    logger.info("Phone: %s", config.SIGNAL_PHONE_NUMBER)
    logger.info("Model: %s", config.ANTHROPIC_MODEL)
    logger.info("Base URL: %s", config.ANTHROPIC_BASE_URL or "https://api.anthropic.com (default)")
    logger.info("Allowed: %s", config.ALLOWED_NUMBERS)
    logger.info("Admins: %s", config.ADMIN_NUMBERS)

    if not wait_for_signal_api(signal_client):
        logger.warning("Starting anyway - Signal API may not be registered yet")

    logger.info("Polling for messages every %ds...", config.POLL_INTERVAL)

    consecutive_errors = 0
    while running:
        try:
            messages = signal_client.receive()
            consecutive_errors = 0

            for msg in messages:
                envelope = msg.get("envelope", {})
                try:
                    process_message(envelope, signal_client, ai, store)
                except Exception:
                    logger.exception("Error processing message")

        except Exception:
            consecutive_errors += 1
            logger.exception("Error in polling loop (consecutive: %d)", consecutive_errors)
            if consecutive_errors > 10:
                logger.error("Too many consecutive errors, sleeping 30s...")
                time.sleep(30)
                consecutive_errors = 0

        time.sleep(config.POLL_INTERVAL)

    logger.info("Helmes Agent stopped.")


if __name__ == "__main__":
    main()
