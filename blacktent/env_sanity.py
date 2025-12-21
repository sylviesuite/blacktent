from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class EnvIssue:
    key: str
    issue: str  # e.g., "missing", "empty", "whitespace", "malformed_line"
    detail: str = ""


def _strip_quotes(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
        return v[1:-1]
    return v


def parse_env_file(env_path: Path) -> Tuple[Dict[str, str], List[EnvIssue]]:
    """
    Deterministic .env parser:
    - supports KEY=VALUE
    - ignores blank lines and comments starting with #
    - does NOT attempt shell expansion
    - preserves content except stripping outer quotes
    """
    issues: List[EnvIssue] = []
    data: Dict[str, str] = {}

    if not env_path.exists():
        issues.append(EnvIssue(key="(file)", issue="missing", detail=f"{env_path} not found"))
        return data, issues

    text = env_path.read_text(encoding="utf-8", errors="replace").splitlines()

    for i, raw_line in enumerate(text, start=1):
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            issues.append(EnvIssue(key="(line)", issue="malformed_line", detail=f"Line {i}: '{raw_line}'"))
            continue

        key, value = line.split("=", 1)
        key = key.strip()

        if not key:
            issues.append(EnvIssue(key="(line)", issue="malformed_line", detail=f"Line {i}: empty key"))
            continue

        value_clean = _strip_quotes(value)
        data[key] = value_clean

    return data, issues


def load_required_keys(require_csv: Optional[str], require_file: Optional[Path]) -> List[str]:
    required: List[str] = []

    if require_csv:
        required.extend([k.strip() for k in require_csv.split(",") if k.strip()])

    if require_file:
        if not require_file.exists():
            raise FileNotFoundError(f"Require file not found: {require_file}")
        for raw in require_file.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            required.append(line)

    seen = set()
    out: List[str] = []
    for k in required:
        if k not in seen:
            out.append(k)
            seen.add(k)
    return out


def validate_env(env: Dict[str, str], required_keys: Iterable[str]) -> List[EnvIssue]:
    issues: List[EnvIssue] = []

    for key in required_keys:
        if key not in env:
            issues.append(EnvIssue(key=key, issue="missing"))
            continue

        value = env[key]
        if value == "":
            issues.append(EnvIssue(key=key, issue="empty"))
        elif value.strip() == "":
            issues.append(EnvIssue(key=key, issue="whitespace"))

    return issues


def format_report(env_path: Path, parse_issues: List[EnvIssue], validation_issues: List[EnvIssue]) -> str:
    lines: List[str] = []
    lines.append("BlackTent Doctor — Environment Sanity (Mode 3)")
    lines.append(f"Env file: {env_path}")
    lines.append("")

    if not parse_issues and not validation_issues:
        lines.append("✅ ENV OK")
        return "\n".join(lines)

    lines.append("❌ ENV INVALID")
    lines.append("")

    if parse_issues:
        lines.append("Parse issues:")
        for iss in parse_issues:
            detail = f" — {iss.detail}" if iss.detail else ""
            lines.append(f"  - {iss.issue}{detail}")
        lines.append("")

    if validation_issues:
        missing = [i.key for i in validation_issues if i.issue == "missing"]
        empty = [i.key for i in validation_issues if i.issue == "empty"]
        whitespace = [i.key for i in validation_issues if i.issue == "whitespace"]

        if missing:
            lines.append("Missing required keys:")
            for k in missing:
                lines.append(f"  - {k}")
            lines.append("")

        if empty:
            lines.append("Empty values (KEY=):")
            for k in empty:
                lines.append(f"  - {k}")
            lines.append("")

        if whitespace:
            lines.append("Whitespace-only values:")
            for k in whitespace:
                lines.append("  - " + k)
            lines.append("")

    lines.append("Tip: Fix the items above, then re-run the Doctor command.")
    return "\n".join(lines)

