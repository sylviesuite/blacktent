from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Tuple


BUNDLE_DEFAULT_ROOT = Path("blacktent.bundle")
MANIFEST_NAME = "manifest.json"
NAMESPACES = ("system", "runtime", "project", "logs")


@dataclass
class RedactionRecord:
    """Single redaction operation applied to the file."""

    kind: str
    original: str
    replacement: str
    start: int
    end: int


def _detect_redactions(text: str) -> List[RedactionRecord]:
    patterns: List[Tuple[str, re.Pattern[str]]] = [
        (
            "email",
            re.compile(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
                re.UNICODE,
            ),
        ),
        (
            "aws_access_key",
            re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        ),
        (
            "long_alnum_token",
            re.compile(r"\b[0-9A-Za-z]{20,}\b"),
        ),
    ]

    redactions: List[RedactionRecord] = []

    for kind, pattern in patterns:
        for m in pattern.finditer(text):
            original = m.group(0)
            replacement = f"[REDACTED_{kind.upper()}]"
            redactions.append(
                RedactionRecord(
                    kind=kind,
                    original=original,
                    replacement=replacement,
                    start=m.start(),
                    end=m.end(),
                )
            )

    redactions.sort(key=lambda r: r.start)
    return redactions


def _apply_redactions(text: str, redactions: List[RedactionRecord]) -> str:
    if not redactions:
        return text

    out_parts: List[str] = []
    cursor = 0

    for r in redactions:
        if r.start > cursor:
            out_parts.append(text[cursor : r.start])
        out_parts.append(r.replacement)
        cursor = r.end

    if cursor < len(text):
        out_parts.append(text[cursor:])

    return "".join(out_parts)


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _default_manifest() -> Dict[str, Any]:
    created = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "version": 1,
        "created_at": created,
        "contents": {ns: [] for ns in NAMESPACES},
    }


def _load_manifest(manifest_path: Path) -> Dict[str, Any]:
    if not manifest_path.exists():
        return _default_manifest()

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        backup = manifest_path.with_suffix(".corrupt.json")
        manifest_path.rename(backup)
        return _default_manifest()

    contents = manifest.get("contents", {})
    for ns in NAMESPACES:
        contents.setdefault(ns, [])
    manifest["contents"] = contents
    return manifest


def scan_and_bundle(
    source_path: Path,
    bundle_root: Path | None = None,
) -> Dict[str, Any]:
    if bundle_root is None:
        bundle_root = BUNDLE_DEFAULT_ROOT

    bundle_root = bundle_root.expanduser().resolve()
    manifest_path = bundle_root / MANIFEST_NAME
    namespace_paths = {ns: bundle_root / ns for ns in NAMESPACES}

    bundle_root.mkdir(exist_ok=True)
    for path in namespace_paths.values():
        path.mkdir(exist_ok=True)

    text = source_path.read_text(encoding="utf-8", errors="replace")
    redactions = _detect_redactions(text)
    redacted_text = _apply_redactions(text, redactions)
    file_id = uuid.uuid4().hex

    redacted_filename = f"{file_id}.txt.redacted"
    redacted_path = namespace_paths["project"] / redacted_filename
    redacted_path.write_text(redacted_text, encoding="utf-8")

    manifest = _load_manifest(manifest_path)
    entry = {
        "id": file_id,
        "namespace": "project",
        "path": str(redacted_path.relative_to(bundle_root)),
        "source_name": source_path.name,
        "sha256_original": _sha256_of_file(source_path),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "redaction_count": len(redactions),
        "redactions": [
            {
                "kind": r.kind,
                "replacement": r.replacement,
                "start": r.start,
                "end": r.end,
            }
            for r in redactions
        ],
    }
    manifest["contents"].setdefault("project", []).append(entry)

    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return {
        "id": file_id,
        "bundle_root": str(bundle_root),
        "redacted_path": str(redacted_path),
        "num_redactions": len(redactions),
    }

