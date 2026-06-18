import logging
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class AIEngine:
    def __init__(self, api_key: str, model: str, max_tokens: int, default_system_prompt: str, base_url: str | None = None):
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = Anthropic(**kwargs)
        self.model = model
        self.max_tokens = max_tokens
        self.default_system_prompt = default_system_prompt

    def chat(self, messages: list[dict], system_prompt: str | None = None) -> str:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt or self.default_system_prompt,
                messages=messages,
            )
            return response.content[0].text
        except Exception:
            logger.exception("Claude API error")
            return "[Helmes] An error occurred while processing your message. Please try again."
