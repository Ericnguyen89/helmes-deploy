import os


SIGNAL_PHONE_NUMBER = os.getenv("SIGNAL_PHONE_NUMBER", "").strip()
SIGNAL_API_URL = os.getenv("SIGNAL_API_URL", "http://signal-api:8080").rstrip("/")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "").strip() or None
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "4096"))
AI_SYSTEM_PROMPT = os.getenv(
    "AI_SYSTEM_PROMPT",
    "You are Helmes, a highly capable AI assistant running on a Linux server, "
    "communicating via Signal. You have access to tools: bash commands, "
    "file read/write, and Python execution on the server. "
    "Use these tools proactively to help the user with coding, system administration, "
    "and automation tasks. Working directory is /workspace. "
    "Respond in the same language the user writes in.",
)

ADMIN_NUMBERS = [n.strip() for n in os.getenv("ADMIN_NUMBERS", "").split(",") if n.strip()]
ALLOWED_NUMBERS = os.getenv("ALLOWED_NUMBERS", "*").strip()
MAX_CONVERSATION_LENGTH = int(os.getenv("MAX_CONVERSATION_LENGTH", "50"))
RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", "30"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "2"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DB_PATH = os.getenv("DB_PATH", "/data/helmes.db")

# Tool settings
TOOLS_ENABLED = os.getenv("TOOLS_ENABLED", "true").lower() in ("true", "1", "yes")
TOOLS_ADMIN_ONLY = os.getenv("TOOLS_ADMIN_ONLY", "false").lower() in ("true", "1", "yes")
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", "/workspace")
TOOL_TIMEOUT = int(os.getenv("TOOL_TIMEOUT", "120"))
MAX_TOOL_ITERATIONS = int(os.getenv("MAX_TOOL_ITERATIONS", "30"))
THINKING_BUDGET = int(os.getenv("THINKING_BUDGET", "10000"))
CONTEXT_SUMMARIZE_THRESHOLD = int(os.getenv("CONTEXT_SUMMARIZE_THRESHOLD", "20"))
CONTEXT_KEEP_RECENT = int(os.getenv("CONTEXT_KEEP_RECENT", "6"))

# Gmail settings
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip()

# Search engine: "duckduckgo" (default, no key needed) or "google"
SEARCH_ENGINE = os.getenv("SEARCH_ENGINE", "duckduckgo").lower()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "").strip()
