from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple

from ..check import HealthCheck, HealthCheckResult, HealthCheckStatus


class RuntimeVersionCheck(HealthCheck):
    id = "runtime_version"
    description = "Ensure Python runtime matches the repository’s declared version."
    required = True

    def run(self) -> HealthCheckResult:
        current_tuple = (sys.version_info.major, sys.version_info.minor)
        current = f"{current_tuple[0]}.{current_tuple[1]}"
        requirement, source, parsed = self._detect_requirement()
        if requirement is None:
            return HealthCheckResult(
                status=HealthCheckStatus.UNKNOWN,
                details=f"Current Python {current}, but no explicit requirement was found.",
            )

        status = self._compare(current_tuple, parsed)
        if status == HealthCheckStatus.PASS:
            return HealthCheckResult(
                status=status,
                details=f"Current Python {current} satisfies requirement {requirement} ({source}).",
            )
        if status == HealthCheckStatus.FAIL:
            return HealthCheckResult(
                status=status,
                details=f"Current Python {current} does not satisfy requirement {requirement} ({source}).",
            )
        return HealthCheckResult(
            status=HealthCheckStatus.UNKNOWN,
            details=f"Could not interpret requirement {requirement} ({source}).",
        )

    def _detect_requirement(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        candidates: Sequence[Tuple[Path, str]] = [
            (Path(".python-version"), ".python-version"),
            (Path("pyproject.toml"), "pyproject.toml"),
        ]
        for path, label in candidates:
            version = self._read_requirement(path)
            if version:
                parsed = self._parse_requirement(version)
                return version, label, parsed
        return None, None, None

    def _read_requirement(self, path: Path) -> Optional[str]:
        if not path.exists():
            return None
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            return None
        if path.name == ".python-version":
            first = text.splitlines()[0].strip()
            return first or None
        try:
            import tomllib  # type: ignore
        except ImportError:
            return None
        try:
            data = tomllib.loads(text)
        except Exception:
            return None
        project = data.get("project") or data.get("tool", {}).get("poetry")
        if not project:
            return None
        raw = project.get("requires-python") or project.get("dependencies", {}).get("python")
        if isinstance(raw, dict):
            raw = raw.get("version")  # Poetry supports tables
        return raw if isinstance(raw, str) else None

    def _parse_requirement(self, raw: str) -> Optional[str]:
        raw = raw.strip()
        if raw.startswith("^"):
            return raw
        match = re.search(r"(>=|<=|>|<|==|=)?\s*(\d+\.\d+)", raw)
        if not match:
            return None
        op = match.group(1) or "=="
        version = match.group(2)
        return f"{op}{version}"

    def _compare(
        self, current: Tuple[int, int], requirement: Optional[str]
    ) -> HealthCheckStatus:
        if requirement is None:
            return HealthCheckStatus.UNKNOWN
        op_match = re.match(r"(?P<op>\^|>=|<=|>|<|==|=)?(?P<ver>\d+\.\d+)", requirement)
        if not op_match:
            return HealthCheckStatus.UNKNOWN
        op = op_match.group("op") or "=="
        ver = op_match.group("ver")
        req_major, req_minor = map(int, ver.split("."))
        if op == "^":
            if current[0] != req_major:
                return HealthCheckStatus.FAIL
            return (
                HealthCheckStatus.PASS
                if current >= (req_major, req_minor)
                else HealthCheckStatus.FAIL
            )
        operator = op
        if operator in {"==", "="}:
            return (
                HealthCheckStatus.PASS
                if current == (req_major, req_minor)
                else HealthCheckStatus.FAIL
            )
        if operator == ">=":
            return (
                HealthCheckStatus.PASS
                if current >= (req_major, req_minor)
                else HealthCheckStatus.FAIL
            )
        if operator == "<=":
            return (
                HealthCheckStatus.PASS
                if current <= (req_major, req_minor)
                else HealthCheckStatus.FAIL
            )
        if operator == ">":
            return (
                HealthCheckStatus.PASS
                if current > (req_major, req_minor)
                else HealthCheckStatus.FAIL
            )
        if operator == "<":
            return (
                HealthCheckStatus.PASS
                if current < (req_major, req_minor)
                else HealthCheckStatus.FAIL
            )
        return HealthCheckStatus.UNKNOWN

