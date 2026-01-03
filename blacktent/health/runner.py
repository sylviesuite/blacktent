from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from .check import HealthCheck, HealthCheckResult, HealthCheckStatus
from .checks.env_vars import EnvVarCheck
from .checks.runtime_version import RuntimeVersionCheck


class HealthState(str, Enum):
    HEALTHY = "HEALTHY"
    UNSTABLE = "UNSTABLE"
    BROKEN = "BROKEN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CheckReport:
    check_id: str
    description: str
    required: bool
    status: HealthCheckStatus
    details: Optional[str] = None


@dataclass(frozen=True)
class HealthReport:
    state: HealthState
    checks: List[CheckReport]


def run_health_checks(checks: List[HealthCheck]) -> HealthReport:
    reports: List[CheckReport] = []
    for check in checks:
        result = check.run()
        reports.append(
            CheckReport(
                check_id=check.id,
                description=check.description,
                required=check.required,
                status=result.status,
                details=result.details,
            )
        )

    required_statuses = [r.status for r in reports if r.required]
    optional_statuses = [r.status for r in reports if not r.required]

    if any(status == HealthCheckStatus.FAIL for status in required_statuses):
        state = HealthState.BROKEN
    elif any(status == HealthCheckStatus.UNKNOWN for status in required_statuses):
        state = HealthState.UNKNOWN
    elif any(
        status in {HealthCheckStatus.FAIL, HealthCheckStatus.UNKNOWN}
        for status in optional_statuses
    ):
        state = HealthState.UNSTABLE
    else:
        state = HealthState.HEALTHY

    return HealthReport(state=state, checks=reports)


def default_checks() -> List[HealthCheck]:
    return [RuntimeVersionCheck(), EnvVarCheck()]

