import os


SIGNAL_PHONE_NUMBER = os.getenv("SIGNAL_PHONE_NUMBER", "").strip()
SIGNAL_API_URL = os.getenv("SIGNAL_API_URL", "http://signal-api:8080").rstrip("/")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "").strip() or None
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "4096"))
AI_SYSTEM_PROMPT = os.getenv(
    "AI_SYSTEM_PROMPT",
    "You are Helmes, a highly capable AI assistant communicating via Signal. "
    "You are helpful, concise, and friendly. Respond in the same language the user writes in.",
)

ADMIN_NUMBERS = [n.strip() for n in os.getenv("ADMIN_NUMBERS", "").split(",") if n.strip()]
ALLOWED_NUMBERS = os.getenv("ALLOWED_NUMBERS", "*").strip()
MAX_CONVERSATION_LENGTH = int(os.getenv("MAX_CONVERSATION_LENGTH", "50"))
RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", "30"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "2"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DB_PATH = os.getenv("DB_PATH", "/data/helmes.db")
