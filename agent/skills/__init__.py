"""Skill system — load focused prompts by task type (inspired by DeerFlow)."""

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent / "definitions"

_CLASSIFIER_RULES: list[tuple[str, re.Pattern]] = [
    ("research", re.compile(
        r"(tìm|search|tra cứu|nghiên cứu|research|look up|google|web|"
        r"tin tức|news|thông tin|information|bài viết|article|"
        r"so sánh|compare|đánh giá|review|phân tích thị trường|market)",
        re.IGNORECASE,
    )),
    ("coding", re.compile(
        r"(code|lập trình|program|debug|fix bug|refactor|function|class|"
        r"api|endpoint|database|sql|python|javascript|typescript|"
        r"deploy|docker|git|commit|pull request|test|viết code|sửa code)",
        re.IGNORECASE,
    )),
    ("sysadmin", re.compile(
        r"(server|vps|ssh|nginx|systemctl|service|process|"
        r"disk|memory|cpu|ram|log|monitor|backup|cron|"
        r"firewall|port|network|dns|ssl|certificate|chmod|chown)",
        re.IGNORECASE,
    )),
    ("data_analysis", re.compile(
        r"(phân tích|analyze|thống kê|statistic|chart|biểu đồ|graph|"
        r"csv|excel|data|dữ liệu|report|báo cáo|dashboard|trend|xu hướng)",
        re.IGNORECASE,
    )),
]


class Skill:
    """A skill loaded from a markdown file."""

    __slots__ = ("name", "content", "_tool_hints")

    def __init__(self, name: str, content: str):
        self.name = name
        self.content = content
        self._tool_hints: list[str] = []
        self._parse_tool_hints()

    def _parse_tool_hints(self):
        for line in self.content.splitlines():
            if line.strip().startswith("tools:"):
                raw = line.split(":", 1)[1].strip()
                self._tool_hints = [t.strip() for t in raw.split(",") if t.strip()]
                break

    @property
    def tool_hints(self) -> list[str]:
        return self._tool_hints


class SkillRegistry:
    """Registry for loading and classifying skills."""

    def __init__(self, skills_dir: str | Path | None = None):
        self._dir = Path(skills_dir) if skills_dir else SKILLS_DIR
        self._cache: dict[str, Skill] = {}
        self._load_all()

    def _load_all(self):
        if not self._dir.exists():
            logger.warning("Skills directory not found: %s", self._dir)
            return
        for path in sorted(self._dir.glob("*.md")):
            name = path.stem
            try:
                content = path.read_text(encoding="utf-8").strip()
                if content:
                    self._cache[name] = Skill(name, content)
                    logger.info("Loaded skill: %s", name)
            except Exception:
                logger.exception("Failed to load skill: %s", path)

    def get(self, name: str) -> Skill | None:
        return self._cache.get(name)

    def classify(self, message: str) -> Skill | None:
        """Classify a message and return the best matching skill."""
        best_name = None
        best_score = 0
        for name, pattern in _CLASSIFIER_RULES:
            matches = pattern.findall(message)
            if len(matches) > best_score:
                best_score = len(matches)
                best_name = name
        if best_name:
            return self._cache.get(best_name)
        return self._cache.get("general")

    def list_skills(self) -> list[str]:
        return list(self._cache.keys())
