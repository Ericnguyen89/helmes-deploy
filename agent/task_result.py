"""Structured task result types with status tracking and token counting."""

import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"

    @property
    def is_terminal(self) -> bool:
        return self in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMED_OUT}


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def add(self, other: "TokenUsage"):
        self.input_tokens += other.input_tokens or 0
        self.output_tokens += other.output_tokens or 0
        self.cache_read_tokens += other.cache_read_tokens or 0
        self.cache_creation_tokens += other.cache_creation_tokens or 0

    @classmethod
    def from_api_response(cls, response) -> "TokenUsage":
        usage = getattr(response, "usage", None)
        if usage is None:
            return cls()
        return cls(
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class TaskResult:
    """Structured result of an agent task execution."""

    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    error: str | None = None
    skill_used: str | None = None
    model_used: str | None = None
    tool_iterations: int = 0
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    sub_tasks: list["TaskResult"] = field(default_factory=list)
    started_at: float = 0.0
    completed_at: float = 0.0

    @property
    def duration_seconds(self) -> float:
        if self.started_at and self.completed_at:
            return round(self.completed_at - self.started_at, 2)
        return 0.0

    @property
    def total_tokens(self) -> int:
        total = self.token_usage.total_tokens
        for sub in self.sub_tasks:
            total += sub.total_tokens
        return total

    def start(self):
        self.status = TaskStatus.RUNNING
        self.started_at = time.time()

    def complete(self, result: str):
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.completed_at = time.time()

    def fail(self, error: str):
        self.status = TaskStatus.FAILED
        self.error = error
        self.completed_at = time.time()

    def to_summary(self) -> str:
        parts = [
            f"Status: {self.status.value}",
            f"Duration: {self.duration_seconds}s",
            f"Tokens: {self.token_usage.input_tokens}in/{self.token_usage.output_tokens}out",
            f"Tool iterations: {self.tool_iterations}",
        ]
        if self.skill_used:
            parts.append(f"Skill: {self.skill_used}")
        if self.model_used:
            parts.append(f"Model: {self.model_used}")
        if self.sub_tasks:
            parts.append(f"Sub-tasks: {len(self.sub_tasks)}")
        return " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "task_id": self.task_id,
            "status": self.status.value,
            "duration": self.duration_seconds,
            "tokens": self.token_usage.to_dict(),
            "tool_iterations": self.tool_iterations,
        }
        if self.skill_used:
            d["skill"] = self.skill_used
        if self.model_used:
            d["model"] = self.model_used
        if self.sub_tasks:
            d["sub_tasks"] = [s.to_dict() for s in self.sub_tasks]
        if self.error:
            d["error"] = self.error
        return d
