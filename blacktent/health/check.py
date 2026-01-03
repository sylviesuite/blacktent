from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Protocol


class HealthCheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HealthCheckResult:
    status: HealthCheckStatus
    details: Optional[str] = None


class HealthCheck(Protocol):
    id: str
    description: str
    required: bool

    def run(self) -> HealthCheckResult:
        ...

