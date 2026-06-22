import os


SIGNAL_PHONE_NUMBER = os.getenv("SIGNAL_PHONE_NUMBER", "").strip()
SIGNAL_API_URL = os.getenv("SIGNAL_API_URL", "http://signal-api:8080").rstrip("/")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "").strip() or None
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# OpenAI (GPT) provider
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").strip() or None
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# Google Gemini provider (via OpenAI-compatible endpoint)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "").strip() or None
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Active provider: "anthropic" (default) | "openai" | "gemini".
# If unset, inferred from the configured model name.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").strip().lower()


def _resolve_active_provider() -> str:
    if LLM_PROVIDER in ("anthropic", "openai", "gemini"):
        return LLM_PROVIDER
    return "anthropic"


# Per-provider credentials, used by the engine to build the active provider and
# to support switching providers at runtime via /model.
PROVIDER_CONFIGS = {
    "anthropic": {"api_key": ANTHROPIC_API_KEY, "base_url": ANTHROPIC_BASE_URL, "model": ANTHROPIC_MODEL},
    "openai": {"api_key": OPENAI_API_KEY, "base_url": OPENAI_BASE_URL, "model": OPENAI_MODEL},
    "gemini": {"api_key": GEMINI_API_KEY, "base_url": GEMINI_BASE_URL, "model": GEMINI_MODEL},
}

ACTIVE_PROVIDER = _resolve_active_provider()
# The model used at startup = the active provider's configured model.
ACTIVE_MODEL = PROVIDER_CONFIGS[ACTIVE_PROVIDER]["model"]

# --- Tiered models (complexity-based routing) ---
# light = fast/cheap (Q&A, orchestration); heavy = deep reasoning.
# HEAVY defaults to each provider's base *_MODEL when its *_HEAVY is unset.
ANTHROPIC_MODEL_LIGHT = os.getenv("ANTHROPIC_MODEL_LIGHT", "claude-sonnet-4-6").strip()
ANTHROPIC_MODEL_HEAVY = os.getenv("ANTHROPIC_MODEL_HEAVY", "").strip() or ANTHROPIC_MODEL
OPENAI_MODEL_LIGHT = os.getenv("OPENAI_MODEL_LIGHT", "gpt-4o-mini").strip()
OPENAI_MODEL_HEAVY = os.getenv("OPENAI_MODEL_HEAVY", "").strip() or OPENAI_MODEL
GEMINI_MODEL_LIGHT = os.getenv("GEMINI_MODEL_LIGHT", "gemini-2.0-flash").strip()
GEMINI_MODEL_HEAVY = os.getenv("GEMINI_MODEL_HEAVY", "").strip() or GEMINI_MODEL

MODEL_TIERS = {
    "anthropic": {"light": ANTHROPIC_MODEL_LIGHT, "heavy": ANTHROPIC_MODEL_HEAVY},
    "openai": {"light": OPENAI_MODEL_LIGHT, "heavy": OPENAI_MODEL_HEAVY},
    "gemini": {"light": GEMINI_MODEL_LIGHT, "heavy": GEMINI_MODEL_HEAVY},
}

# Enable complexity-based routing (light <-> heavy). If false, always use ACTIVE_MODEL.
MODEL_ROUTING = os.getenv("MODEL_ROUTING", "true").lower() in ("true", "1", "yes")

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
SUMMARIZE_MODEL = os.getenv("SUMMARIZE_MODEL", "").strip() or None

# Gmail settings
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "").strip()
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").strip()

# Search engine: "duckduckgo" (default, no key needed) or "google"
SEARCH_ENGINE = os.getenv("SEARCH_ENGINE", "duckduckgo").lower()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "").strip()

# Browser automation (Puppeteer/Chromium)
BROWSER_ENABLED = os.getenv("BROWSER_ENABLED", "true").lower() in ("true", "1", "yes")
BROWSER_NODE_BIN = os.getenv("BROWSER_NODE_BIN", "node").strip() or "node"
