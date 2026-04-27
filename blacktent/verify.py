from __future__ import annotations

import collections
import math
import secrets
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, List


KNOWN_DEFAULTS = {
    "dev-secret-123", "secret", "changeme", "your-secret-key",
    "mysecret", "password", "development", "test", "example",
    "jwt-secret", "jwt_secret", "supersecret", "replace-me",
    "your_jwt_secret", "change_me", "insecure", "unsafe",
    "abc123", "123456", "qwerty", "letmein",
}

_MIN_LENGTH = 32
_MIN_ENTROPY = 3.0


@dataclass(frozen=True)
class VerifyResult:
    name: str
    status: str   # "pass" | "fail" | "skip"
    reason: str


def generate_secret() -> str:
    """Return a cryptographically secure URL-safe random secret (64 chars, 384 bits)."""
    return secrets.token_urlsafe(48)


def _http_get(url: str, headers: Dict[str, str], timeout: int = 5) -> int:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except urllib.error.URLError:
        return 0


def _entropy_bits_per_char(s: str) -> float:
    if not s:
        return 0.0
    counts = collections.Counter(s)
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def check_supabase(env: Dict[str, str]) -> VerifyResult:
    name = "Supabase"
    url = env.get("SUPABASE_URL", "").strip()
    key = env.get("SUPABASE_ANON_KEY", "").strip()

    if not url or not key:
        missing = ", ".join(k for k, v in [("SUPABASE_URL", url), ("SUPABASE_ANON_KEY", key)] if not v)
        return VerifyResult(name=name, status="skip", reason=f"not set: {missing}")

    code = _http_get(
        f"{url.rstrip('/')}/rest/v1/",
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )

    if code == 200:
        return VerifyResult(name=name, status="pass", reason="connected")
    if code == 401:
        return VerifyResult(name=name, status="fail", reason="invalid key (HTTP 401)")
    if code == 0:
        return VerifyResult(name=name, status="fail", reason="unreachable — check SUPABASE_URL")
    return VerifyResult(name=name, status="fail", reason=f"unexpected response (HTTP {code})")


def check_anthropic(env: Dict[str, str]) -> VerifyResult:
    name = "Anthropic/Claude"
    key = env.get("CLAUDE_API_KEY", "").strip()

    if not key:
        return VerifyResult(name=name, status="skip", reason="CLAUDE_API_KEY not set")

    code = _http_get(
        "https://api.anthropic.com/v1/models",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
    )

    if code == 200:
        return VerifyResult(name=name, status="pass", reason="valid key")
    if code == 401:
        return VerifyResult(name=name, status="fail", reason="invalid key (HTTP 401)")
    if code == 0:
        return VerifyResult(name=name, status="fail", reason="unreachable — check network")
    return VerifyResult(name=name, status="fail", reason=f"unexpected response (HTTP {code})")


def check_jwt_secret(env: Dict[str, str]) -> VerifyResult:
    name = "JWT_SECRET"
    value = env.get("JWT_SECRET", "").strip()

    if not value:
        return VerifyResult(name=name, status="skip", reason="JWT_SECRET not set")

    if value.lower() in KNOWN_DEFAULTS or value in KNOWN_DEFAULTS:
        return VerifyResult(name=name, status="fail", reason="known default value -- rotate before production")

    if len(value) < _MIN_LENGTH:
        return VerifyResult(
            name=name,
            status="fail",
            reason=f"too short ({len(value)} chars, minimum {_MIN_LENGTH})",
        )

    entropy = _entropy_bits_per_char(value)
    if entropy < _MIN_ENTROPY:
        return VerifyResult(
            name=name,
            status="fail",
            reason=f"low entropy ({entropy:.1f} bits/char, minimum {_MIN_ENTROPY})",
        )

    return VerifyResult(name=name, status="pass", reason="meets strength requirements")


def run_checks(env: Dict[str, str]) -> List[VerifyResult]:
    return [
        check_supabase(env),
        check_anthropic(env),
        check_jwt_secret(env),
    ]
