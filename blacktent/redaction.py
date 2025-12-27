from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Tuple


BUNDLE_DEFAULT_ROOT = Path("blacktent.bundle")
FILES_SUBDIR = "files"
MANIFEST_NAME = "manifest.json"


@dataclass
class RedactionRecord:
    """Single redaction operation applied to the file."""

    kind: str          # e.g. "email", "token"
    original: str      # the original string we redacted
    replacement: str   # what we replaced it with
    start: int         # start index in original text
    end: int           # end index in original text


def _detect_redactions(text: str) -> List[RedactionRecord]:
    """
    Very simple, transparent secret detector.

    This is intentionally conservative and explainable.
    Later you can plug in a more advanced engine, but
    the manifest format should stay stable.
    """
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

    # Sort by start index so we can apply deterministically
    redactions.sort(key=lambda r: r.start)
    return redactions


def _apply_redactions(text: str, redactions: List[RedactionRecord]) -> str:
    """
    Apply redactions to the text, preserving non-redacted content.
    """
    if not redactions:
        return text

    out_parts: List[str] = []
    cursor = 0

    for r in redactions:
        # Add text before this redaction
        if r.start > cursor:
            out_parts.append(text[cursor : r.start])

        # Add replacement
        out_parts.append(r.replacement)
        cursor = r.end

    # Tail
    if cursor < len(text):
        out_parts.append(text[cursor:])

    return "".join(out_parts)


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest(manifest_path: Path) -> Dict[str, Any]:
    if not manifest_path.exists():
        created = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return {"version": 1, "created_at": created, "files": []}

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # If it's corrupted, start fresh but keep the old file around
        backup = manifest_path.with_suffix(".corrupt.json")
        manifest_path.rename(backup)
        created = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return {"version": 1, "created_at": created, "files": []}


def scan_and_bundle(
    source_path: Path,
    bundle_root: Path | None = None,
) -> Dict[str, Any]:
    """
    Scan `source_path` for secrets, write a redacted copy into bundle_root,
    and update the manifest.

    Returns a small summary dict with IDs and paths.
    """
    if bundle_root is None:
        bundle_root = BUNDLE_DEFAULT_ROOT

    bundle_root = bundle_root.expanduser().resolve()
    files_dir = bundle_root / FILES_SUBDIR
    manifest_path = bundle_root / MANIFEST_NAME

    bundle_root.mkdir(exist_ok=True)
    files_dir.mkdir(exist_ok=True)

    text = source_path.read_text(encoding="utf-8", errors="replace")
    redactions = _detect_redactions(text)
    redacted_text = _apply_redactions(text, redactions)
    file_id = uuid.uuid4().hex

    # Write redacted file
    redacted_filename = f"{file_id}.txt.redacted"
    redacted_path = files_dir / redacted_filename
    redacted_path.write_text(redacted_text, encoding="utf-8")

    # Update manifest
    manifest = _load_manifest(manifest_path)
    file_entry = {
        "id": file_id,
        "source_path": str(source_path.resolve()),
        "redacted_path": str(redacted_path),
        "sha256_original": _sha256_of_file(source_path),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "redactions": [asdict(r) for r in redactions],
    }
    manifest.setdefault("files", []).append(file_entry)

    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return {
        "id": file_id,
        "bundle_root": str(bundle_root),
        "redacted_path": str(redacted_path),
        "num_redactions": len(redactions),
    }
