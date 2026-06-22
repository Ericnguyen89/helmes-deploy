"""Complexity-based model routing.

Two tiers per provider:
- LIGHT  — fast/cheap model (e.g. Sonnet) for Q&A, simple chat, and the
           orchestration role ("quản gia": task decomposition + synthesis).
- HEAVY  — deep-reasoning model (e.g. Opus) for complex analysis, coding,
           design, multi-step problems.

The router classifies each task by the skill it matched and lightweight
heuristics on the message, then returns the model ID to use. No extra LLM call —
classification is regex + length based, so it's free and instant.
"""

import re
from enum import Enum


class ModelTier(Enum):
    LIGHT = "light"
    HEAVY = "heavy"


# Each skill's default tier. Coding and data analysis lean on deep reasoning;
# research / sysadmin / general chat are usually fine on the light model.
SKILL_TIERS = {
    "research": ModelTier.LIGHT,
    "general": ModelTier.LIGHT,
    "sysadmin": ModelTier.LIGHT,
    "coding": ModelTier.HEAVY,
    "data_analysis": ModelTier.HEAVY,
}

# Signals that a task needs deep reasoning (Vietnamese + English).
_HEAVY_PATTERN = re.compile(
    r"(phân tích|suy luận|lập luận|chứng minh|t[aạ]i sao|vì sao|so sánh|đánh giá|"
    r"thiết kế|kiến trúc|tối ưu|thuật toán|chiến lược|nghiên cứu sâu|gỡ lỗi|"
    r"viết (chương trình|code|hàm|class)|"
    r"refactor|debug|optimi[sz]e|algorithm|architect|analy[sz]e|design|implement|"
    r"\bprove\b|\bderive\b|reasoning|step[- ]by[- ]step)",
    re.IGNORECASE,
)

# Above this length a single message usually carries enough scope to warrant
# the heavy model.
_LONG_MESSAGE_CHARS = 500


class ModelRouter:
    """Resolves a model ID for a task based on complexity."""

    def __init__(self, tier_models: dict[str, str]):
        # tier_models = {"light": "<model id>", "heavy": "<model id>"}
        self.tier_models = tier_models

    def model_for(self, tier: ModelTier) -> str:
        return self.tier_models.get(tier.value) or self.tier_models.get("heavy") \
            or next(iter(self.tier_models.values()))

    def classify(self, message: str, skill_name: str | None = None) -> ModelTier:
        """Decide which tier a task belongs to."""
        # 1. Skill default — coding / data_analysis go heavy outright.
        if skill_name and SKILL_TIERS.get(skill_name) == ModelTier.HEAVY:
            return ModelTier.HEAVY

        text = message or ""

        # 2. Deep-reasoning keywords.
        if _HEAVY_PATTERN.search(text):
            return ModelTier.HEAVY

        # 3. Long prompt = likely complex / multi-part.
        if len(text) > _LONG_MESSAGE_CHARS:
            return ModelTier.HEAVY

        # 4. Numbered multi-step request (>= 3 steps).
        if len(re.findall(r"(?m)^\s*\d+[\.\)]", text)) >= 3:
            return ModelTier.HEAVY

        return ModelTier.LIGHT

    def model_for_message(self, message: str, skill_name: str | None = None) -> str:
        return self.model_for(self.classify(message, skill_name))
