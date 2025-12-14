#!/usr/bin/env python3
"""
BlackTent (MVP)
- scan-file: detect secrets, write redacted output, write .blacktent/manifest.json
- scan-dir : scan a directory, write redacted copies, write .blacktent/manifest.json
- bundle   : create AI-safe bundle folder with redacted files + manifest
- patch    : Step D (patch replay) -> apply manifest redactions to an original file safely
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Optional .gitignore support
try:
    import pathspec  # type: ignore
except Exception:
    pathspec = None


# -----------------------------
# Detection rules (MVP)
# -----------------------------
@dataclass(frozen=True)
class Rule:
    name: str
    pattern: re.Pattern


RULES: List[Rule] = [
    Rule("OPENAI_KEY", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    Rule("GITHUB_TOKEN", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    # Generic "API key-ish" tokens (keep conservative)
    Rule("GENERIC_API_KEY", re.compile(r"\b(?:api[_-]?key|token)\b\s*[:=]\s*[\"']?([A-Za-z0-9_\-]{16,})[\"']?", re.IGNORECASE)),
    Rule("PASSWORD", re.compile(r"\bpassword\b\s*[:=]\s*[\"']([^\"']{4,})[\"']", re.IGNORECASE)),
]

ENV_FILES = [".env", ".env.local", ".env.production", ".env.example"]

def _sha8(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()[:8]


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()


@dataclass
class Finding:
    rule: str
    start: int
    end: int
    replacement: str
    match_len: int
    match_sha256: str


def find_secrets(text: str) -> List[Finding]:
    findings: List[Finding] = []

    for rule in RULES:
        # Some rules have capturing groups; we want whole-secret span.
        # For those, we compute span of group 1 if present, else match span.
        for m in rule.pattern.finditer(text):
            if m.lastindex and m.lastindex >= 1 and m.group(1) is not None:
                g1 = m.group(1)
                if g1 is None:
                    continue
                start, end = m.span(1)
                secret = g1
            else:
                start, end = m.span()
                secret = m.group(0)

            if not secret:
                continue

            token = f"[REDACTED:{rule.name}:{_sha8(secret)}]"
            findings.append(
                Finding(
                    rule=rule.name,
                    start=start,
                    end=end,
                    replacement=token,
                    match_len=(end - start),
                    match_sha256=_sha256_hex(secret),
                )
            )

    # If overlaps exist, keep the longest match, and ensure stable application
    findings.sort(key=lambda f: (f.start, -(f.end - f.start)))

    merged: List[Finding] = []
    last_end = -1
    for f in findings:
        if f.start < last_end:
            # overlap; skip
            continue
        merged.append(f)
        last_end = f.end

    return merged


def apply_redactions(text: str, findings: List[Finding]) -> str:
    # apply from end → start so offsets remain valid
    out = text
    for f in sorted(findings, key=lambda x: x.start, reverse=True):
        out = out[: f.start] + f.replacement + out[f.end :]
    return out


# -----------------------------
# Manifest I/O
# -----------------------------
def blacktent_dir(root: Path) -> Path:
    d = root / ".blacktent"
    d.mkdir(parents=True, exist_ok=True)
    return d


def manifest_path(root: Path) -> Path:
    return blacktent_dir(root) / "manifest.json"


def write_manifest(root: Path, entries: List[Dict]) -> Path:
    mp = manifest_path(root)
    payload = {
        "version": "0.1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "entries": entries,
    }
    mp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return mp


def load_manifest(root: Path) -> Dict:
    mp = manifest_path(root)
    if not mp.exists():
        raise FileNotFoundError(f"Manifest not found: {mp}")
    return json.loads(mp.read_text(encoding="utf-8"))


# -----------------------------
# Gitignore helpers (optional)
# -----------------------------
def build_gitignore_spec(root: Path):
    if pathspec is None:
        return None
    gi = root / ".gitignore"
    if not gi.exists():
        return None
    lines = gi.read_text(encoding="utf-8", errors="ignore").splitlines()
    return pathspec.PathSpec.from_lines("gitwildmatch", lines)


def is_ignored(rel_path: str, spec) -> bool:
    if spec is None:
        return False
    return spec.match_file(rel_path)


# -----------------------------
# Scanning primitives
# -----------------------------
def scan_one_file(input_path: Path) -> Tuple[str, List[Finding]]:
    text = input_path.read_text(encoding="utf-8", errors="ignore")
    findings = find_secrets(text)
    redacted = apply_redactions(text, findings)
    return redacted, findings


def parse_env_example(example_path: Path) -> Set[str]:
    if not example_path.exists():
        return set()
    keys: Set[str] = set()
    for line in example_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


def write_env_report(repo_root: Path, data: Dict[str, object]) -> Path:
    path = blacktent_dir(repo_root) / "env_report.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def env_check_cmd(repo_root: Path, target_root: Path) -> Dict[str, object]:
    target_root = target_root.resolve()
    env_status = {name: (target_root / name).exists() for name in ENV_FILES}
    example_keys = parse_env_example(target_root / ".env.example")
    env_vars = set(os.environ.keys())
    present = sorted(example_keys & env_vars)
    missing = sorted(example_keys - env_vars)
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    report = {
        "timestamp": timestamp,
        "target_root": str(target_root),
        "env_files": env_status,
        "example_keys": sorted(example_keys),
        "present_keys": present,
        "missing_keys": missing,
    }
    report_path = write_env_report(repo_root, report)
    report["report_path"] = str(report_path)
    return report


def scan_file_cmd(repo_root: Path, input_path: Path, out_path: Optional[Path]) -> Dict:
    input_path = input_path.resolve()
    redacted, findings = scan_one_file(input_path)

    if out_path is None:
        out_path = Path(str(input_path) + ".redacted.txt")
    out_path = out_path.resolve()
    out_path.write_text(redacted, encoding="utf-8")

    entry = {
        "type": "file",
        "input": str(input_path),
        "output": str(out_path),
        "findings": [
            {
                "rule": f.rule,
                "start": f.start,
                "end": f.end,
                "replacement": f.replacement,
                "match_len": f.match_len,
                "match_sha256": f.match_sha256,
            }
            for f in findings
        ],
    }

    mp = write_manifest(repo_root, [entry])

    return {
        "input": str(input_path),
        "output": str(out_path),
        "total_findings": len(findings),
        "manifest": str(mp),
    }


def scan_dir_cmd(repo_root: Path, target_dir: Path, out_dir: Optional[Path]) -> Dict:
    target_dir = target_dir.resolve()
    if out_dir is None:
        out_dir = (repo_root / ".blacktent" / "redacted").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    spec = build_gitignore_spec(repo_root)

    entries: List[Dict] = []
    total_findings = 0
    files_scanned = 0

    for p in target_dir.rglob("*"):
        if not p.is_file():
            continue

        rel = str(p.relative_to(repo_root)).replace("\\", "/") if repo_root in p.parents else p.name
        if rel.startswith(".blacktent/") or rel.startswith("blacktent.bundle/"):
            continue
        if is_ignored(rel, spec):
            continue

        redacted, findings = scan_one_file(p)
        if not findings:
            continue

        files_scanned += 1
        total_findings += len(findings)

        out_path = (out_dir / rel).with_suffix((out_dir / rel).suffix + ".redacted.txt")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(redacted, encoding="utf-8")

        entries.append(
            {
                "type": "file",
                "input": str(p.resolve()),
                "output": str(out_path.resolve()),
                "findings": [
                    {
                        "rule": f.rule,
                        "start": f.start,
                        "end": f.end,
                        "replacement": f.replacement,
                        "match_len": f.match_len,
                        "match_sha256": f.match_sha256,
                    }
                    for f in findings
                ],
            }
        )

    mp = write_manifest(repo_root, entries)

    return {
        "dir": str(target_dir),
        "out_dir": str(out_dir),
        "files_with_findings": files_scanned,
        "total_findings": total_findings,
        "manifest": str(mp),
    }


def bundle_cmd(repo_root: Path, target_dir: Path, bundle_root: Optional[Path]) -> Dict:
    target_dir = target_dir.resolve()
    if bundle_root is None:
        bundle_root = (repo_root / "blacktent.bundle").resolve()
    bundle_root.mkdir(parents=True, exist_ok=True)

    spec = build_gitignore_spec(repo_root)

    entries: List[Dict] = []
    included_files = 0
    total_findings = 0

    files_out_root = bundle_root / "files"
    files_out_root.mkdir(parents=True, exist_ok=True)

    for p in target_dir.rglob("*"):
        if not p.is_file():
            continue

        rel = str(p.relative_to(repo_root)).replace("\\", "/") if repo_root in p.parents else p.name
        if rel.startswith(".blacktent/") or rel.startswith("blacktent.bundle/"):
            continue
        if is_ignored(rel, spec):
            continue

        redacted, findings = scan_one_file(p)
        if not findings:
            continue

        included_files += 1
        total_findings += len(findings)

        out_path = (files_out_root / rel).with_suffix((files_out_root / rel).suffix + ".redacted.txt")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(redacted, encoding="utf-8")

        entries.append(
            {
                "type": "file",
                "input": str(p.resolve()),
                "output": str(out_path.resolve()),
                "findings": [
                    {
                        "rule": f.rule,
                        "start": f.start,
                        "end": f.end,
                        "replacement": f.replacement,
                        "match_len": f.match_len,
                        "match_sha256": f.match_sha256,
                    }
                    for f in findings
                ],
            }
        )

    # Write manifest into bundle (and also keep a copy in repo .blacktent)
    mp_repo = write_manifest(repo_root, entries)
    mp_bundle = bundle_root / "manifest.json"
    mp_bundle.write_text(Path(mp_repo).read_text(encoding="utf-8"), encoding="utf-8")

    readme = bundle_root / "README_AI.txt"
    readme.write_text(
        "BlackTent AI-safe bundle\n\n"
        "This bundle contains redacted files only.\n"
        "Use manifest.json to understand what was redacted.\n",
        encoding="utf-8",
    )

    return {
        "bundle_path": str(bundle_root),
        "included_files": included_files,
        "total_findings": total_findings,
        "manifest_repo": str(mp_repo),
        "manifest_bundle": str(mp_bundle),
    }


# -----------------------------
# Step D: Patch replay / safe transform
# -----------------------------
def patch_from_manifest_entry(original_text: str, entry: Dict) -> Tuple[str, Dict]:
    findings = entry.get("findings", [])
    applied = 0
    skipped = 0
    reasons: List[str] = []

    # Apply in reverse offset order
    findings_sorted = sorted(findings, key=lambda f: f["start"], reverse=True)
    out = original_text

    for f in findings_sorted:
        start = int(f["start"])
        end = int(f["end"])
        repl = str(f["replacement"])
        expected_len = int(f.get("match_len", end - start))
        expected_sha = str(f.get("match_sha256", ""))

        # Validate bounds
        if start < 0 or end > len(out) or start >= end:
            skipped += 1
            reasons.append(f"skip: invalid span {start}:{end}")
            continue

        candidate = out[start:end]
        if len(candidate) != expected_len:
            skipped += 1
            reasons.append(f"skip: length mismatch at {start}:{end}")
            continue

        if expected_sha and _sha256_hex(candidate) != expected_sha:
            skipped += 1
            reasons.append(f"skip: sha mismatch at {start}:{end}")
            continue

        out = out[:start] + repl + out[end:]
        applied += 1

    report = {
        "input": entry.get("input"),
        "applied": applied,
        "skipped": skipped,
        "notes": reasons[:25],  # keep short
    }
    return out, report


def patch_cmd(repo_root: Path, input_path: Path, out_path: Path) -> Dict:
    input_path = input_path.resolve()
    out_path = out_path.resolve()

    manifest = load_manifest(repo_root)
    entries = manifest.get("entries", [])

    # Find matching entry by input path (best effort)
    match_entry = None
    input_str = str(input_path)
    for e in entries:
        if str(e.get("input", "")) == input_str:
            match_entry = e
            break

    if match_entry is None:
        # fallback: if only one entry exists, use it
        if len(entries) == 1:
            match_entry = entries[0]
        else:
            raise RuntimeError(
                "Could not find a manifest entry for this input file. "
                "Run scan-file on the same file first."
            )

    original_text = input_path.read_text(encoding="utf-8", errors="ignore")
    patched, report = patch_from_manifest_entry(original_text, match_entry)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(patched, encoding="utf-8")

    return {
        "input": str(input_path),
        "output": str(out_path),
        "applied": report["applied"],
        "skipped": report["skipped"],
        "manifest": str(manifest_path(repo_root)),
    }


# -----------------------------
# CLI
# -----------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="blacktent", description="BlackTent MVP CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    scan_file = sub.add_parser("scan-file", help="Scan one file and write a redacted copy + manifest")
    scan_file.add_argument("input", help="File to scan")
    scan_file.add_argument("--out", help="Output redacted file path (default: <input>.redacted.txt)")

    scan_dir = sub.add_parser("scan-dir", help="Scan a directory recursively and write redacted copies + manifest")
    scan_dir.add_argument("dir", help="Directory to scan")
    scan_dir.add_argument("--out-dir", help="Where to write redacted copies (default: .blacktent/redacted)")

    bundle = sub.add_parser("bundle", help="Create an AI-safe bundle folder with redacted files + manifest")
    bundle.add_argument("dir", help="Directory to bundle")
    bundle.add_argument("--bundle-root", help="Bundle output folder (default: ./blacktent.bundle)")

    patch = sub.add_parser("patch", help="Step D: Patch replay using the latest manifest entry for the file")
    patch.add_argument("input", help="Original file to patch")
    patch.add_argument("--out", required=True, help="Patched output file path")

    env_check = sub.add_parser("env-check", help="Inspect usable env vars safely")
    env_check.add_argument("path", nargs="?", default=".", help="Project root to inspect")

    return p


def main() -> None:
    repo_root = Path.cwd().resolve()
    args = build_parser().parse_args()

    if args.cmd == "scan-file":
        res = scan_file_cmd(repo_root, Path(args.input), Path(args.out) if args.out else None)
        print("\n=== BlackTent mini report ===")
        print(f"Input : {res['input']}")
        print(f"Output: {res['output']}")
        print(f"Findings: {res['total_findings']}")
        print(f"Manifest: {res['manifest']}")
        print("✅ Done.\n")
        return

    if args.cmd == "scan-dir":
        res = scan_dir_cmd(repo_root, Path(args.dir), Path(args.out_dir) if args.out_dir else None)
        print("\n=== BlackTent dir report ===")
        print(f"Dir  : {res['dir']}")
        print(f"Out  : {res['out_dir']}")
        print(f"Files w/findings: {res['files_with_findings']}")
        print(f"Total findings : {res['total_findings']}")
        print(f"Manifest       : {res['manifest']}")
        print("✅ Done.\n")
        return

    if args.cmd == "bundle":
        res = bundle_cmd(repo_root, Path(args.dir), Path(args.bundle_root) if args.bundle_root else None)
        print("\n=== BlackTent bundle created ===")
        print(f"Bundle path   : {res['bundle_path']}")
        print(f"Included files: {res['included_files']}")
        print(f"Total findings: {res['total_findings']}")
        print(f"Manifest (repo): {res['manifest_repo']}")
        print(f"Manifest (bundle): {res['manifest_bundle']}")
        print("Ready for AI handoff ✅\n")
        return

    if args.cmd == "patch":
        res = patch_cmd(repo_root, Path(args.input), Path(args.out))
        print("\n=== BlackTent patch report ===")
        print(f"Input  : {res['input']}")
        print(f"Output : {res['output']}")
        print(f"Applied: {res['applied']}")
        print(f"Skipped: {res['skipped']}")
        print(f"Manifest: {res['manifest']}")
        print("✅ Done.\n")
        return

    if args.cmd == "env-check":
        res = env_check_cmd(repo_root, Path(args.path))
        env_files = res["env_files"]
        missing = res["missing_keys"]
        present = res["present_keys"]
        print("\n=== BlackTent env-check ===")
        print(f"Root scanned       : {res['target_root']}")
        print(f".env present       : {'YES' if env_files.get('.env') else 'NO'}")
        print(f".env.local present : {'YES' if env_files.get('.env.local') else 'NO'}")
        print(f".env.production    : {'YES' if env_files.get('.env.production') else 'NO'}")
        print(f".env.example       : {'YES' if env_files.get('.env.example') else 'NO'}")
        print(f"Variables detected : {len(res['example_keys'])}")
        print(f"Missing variables  : {', '.join(missing) if missing else 'None'}")
        print(f"Present variables  : {', '.join(present) if present else 'None'}")
        print(f"Report (JSON)      : {res['report_path']}")
        print("✅ Env data safe for AI handoff\n")
        return

    raise SystemExit("Unknown command")


if __name__ == "__main__":
    main()
