from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .env_sanity import (
    format_report,
    load_required_keys,
    parse_env_file,
    validate_env,
)

# Optional feature: redaction/bundling. Core commands (like doctor env/repo) must run without it.
try:
    from .redaction import scan_and_bundle  # type: ignore
except ImportError:
    scan_and_bundle = None  # type: ignore


# ----------------------------
# Exit codes (v1 contract)
# ----------------------------
EXIT_OK = 0
EXIT_INTERNAL_ERROR = 1
EXIT_USER_FIXABLE = 2


# ----------------------------
# Runtime + receipts
# ----------------------------
DEFAULT_RECEIPT_DIR = Path(".blacktent")


def _utc_timestamp() -> str:
    # Example: 2025-12-25T19:14:22Z
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _receipt_filename(prefix: str = "receipt") -> str:
    # Example: receipt-20251225T191422Z.json
    now = datetime.now(timezone.utc)
    return f"{prefix}-{now.strftime('%Y%m%dT%H%M%SZ')}.json"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_receipt(
    receipt_dir: Path,
    *,
    mode: str,
    status: str,
    exit_code: int,
    inputs: dict[str, Any],
    actions: Optional[list[dict[str, Any]]] = None,
    notes: Optional[list[str]] = None,
    prefix: str = "receipt",
) -> Path:
    """
    Write a JSON receipt for the command invocation.
    Never write secrets. Paths are okay; env contents are not.
    """
    ensure_dir(receipt_dir)
    payload: dict[str, Any] = {
        "timestamp": _utc_timestamp(),
        "mode": mode,
        "status": status,  # ok | invalid | error
        "exit_code": exit_code,
        "inputs": inputs,
        "actions": actions or [],
        "notes": notes or [],
    }

    out = receipt_dir / _receipt_filename(prefix=prefix)
    with out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return out


# ----------------------------
# Args + handlers
# ----------------------------
@dataclass(frozen=True)
class DoctorEnvArgs:
    env_file: Path
    required_file: Path
    receipt_dir: Path
    quiet: bool


def cmd_doctor_env(args: DoctorEnvArgs) -> int:
    """
    Validate env file against a required-keys schema file and write a receipt.
    Exit codes:
      0 = ok
      2 = invalid/missing (user-fixable)
      1 = internal error (unexpected exception)
    Receipt is written for every run.
    """
    mode = "env-doctor"
    inputs = {
        "env_file": str(args.env_file),
        "schema_file": str(args.required_file),
        "receipt_dir": str(args.receipt_dir),
    }

    try:
        # Missing files are user-fixable
        if not args.env_file.exists():
            msg = f"Env file not found: {args.env_file}"
            if not args.quiet:
                print(msg)
            write_receipt(
                args.receipt_dir,
                mode=mode,
                status="invalid",
                exit_code=EXIT_USER_FIXABLE,
                inputs=inputs,
                notes=[msg],
            )
            return EXIT_USER_FIXABLE

        if not args.required_file.exists():
            msg = f"Required schema file not found: {args.required_file}"
            if not args.quiet:
                print(msg)
            write_receipt(
                args.receipt_dir,
                mode=mode,
                status="invalid",
                exit_code=EXIT_USER_FIXABLE,
                inputs=inputs,
                notes=[msg],
            )
            return EXIT_USER_FIXABLE

        required_keys = load_required_keys(args.required_file)
        env_map = parse_env_file(args.env_file)

        report = validate_env(env_map, required_keys)
        if not args.quiet:
            print(format_report(report))

        ok = bool(getattr(report, "ok", False))
        status = "ok" if ok else "invalid"
        exit_code = EXIT_OK if ok else EXIT_USER_FIXABLE

        write_receipt(
            args.receipt_dir,
            mode=mode,
            status=status,
            exit_code=exit_code,
            inputs=inputs,
        )
        return exit_code

    except Exception as e:
        msg = f"Internal error running doctor env: {e.__class__.__name__}: {e}"
        if not args.quiet:
            print(msg, file=sys.stderr)
        write_receipt(
            args.receipt_dir,
            mode=mode,
            status="error",
            exit_code=EXIT_INTERNAL_ERROR,
            inputs=inputs,
            notes=[msg],
        )
        return EXIT_INTERNAL_ERROR


@dataclass(frozen=True)
class DoctorRepoArgs:
    target_repo_path: Path
    intent: str
    receipt_dir: Path
    quiet: bool
    apply: bool


def cmd_doctor_repo(args: DoctorRepoArgs) -> int:
    """
    Repo Doctor (v0 stub): accept intent + target repo path and write a receipt.
    Next slice: Detect -> Explain -> Propose -> Apply -> Verify.
    """
    mode = "repo-doctor"
    inputs = {
        "target_repo_path": str(args.target_repo_path),
        "intent": args.intent,
        "apply": bool(args.apply),
        "receipt_dir": str(args.receipt_dir),
    }

    try:
        if not args.target_repo_path.exists():
            msg = f"Target repo path not found: {args.target_repo_path}"
            if not args.quiet:
                print(msg)
            write_receipt(
                args.receipt_dir,
                mode=mode,
                status="invalid",
                exit_code=EXIT_USER_FIXABLE,
                inputs=inputs,
                notes=[msg],
            )
            return EXIT_USER_FIXABLE

        # Minimal success receipt
        notes = [
            "Stub OK: repo doctor entrypoint created.",
            "Next: implement detect/explain/propose/apply/verify loop.",
        ]

        if not args.quiet:
            print("[doctor repo] stub ok — receipt written")

        write_receipt(
            args.receipt_dir,
            mode=mode,
            status="ok",
            exit_code=EXIT_OK,
            inputs=inputs,
            notes=notes,
        )
        return EXIT_OK

    except Exception as e:
        msg = f"Internal error running doctor repo: {e.__class__.__name__}: {e}"
        if not args.quiet:
            print(msg, file=sys.stderr)
        write_receipt(
            args.receipt_dir,
            mode=mode,
            status="error",
            exit_code=EXIT_INTERNAL_ERROR,
            inputs=inputs,
            notes=[msg],
        )
        return EXIT_INTERNAL_ERROR


@dataclass(frozen=True)
class ScanArgs:
    receipt_dir: Path
    quiet: bool


def cmd_scan_bundle(args: ScanArgs) -> int:
    """
    Optional scan/bundle feature.
    If the optional module isn't available, return 2 (user-fixable / feature unavailable).
    """
    mode = "scan-bundle"
    inputs = {"receipt_dir": str(args.receipt_dir)}

    if scan_and_bundle is None:
        msg = "Redaction/bundling is not available in this build."
        if not args.quiet:
            print(msg)
        write_receipt(
            args.receipt_dir,
            mode=mode,
            status="invalid",
            exit_code=EXIT_USER_FIXABLE,
            inputs=inputs,
            notes=["Feature unavailable: blacktent.redaction not installed/present."],
        )
        return EXIT_USER_FIXABLE

    # If present, run it (or keep as placeholder if scan_and_bundle expects args later)
    try:
        # Minimal “present” path — don’t assume its signature; just acknowledge availability.
        msg = "scan_and_bundle is available, but this command is not wired to inputs yet."
        if not args.quiet:
            print(msg)
        write_receipt(
            args.receipt_dir,
            mode=mode,
            status="ok",
            exit_code=EXIT_OK,
            inputs=inputs,
            notes=[msg],
        )
        return EXIT_OK
    except Exception as e:
        msg = f"Internal error running scan: {e.__class__.__name__}: {e}"
        if not args.quiet:
            print(msg, file=sys.stderr)
        write_receipt(
            args.receipt_dir,
            mode=mode,
            status="error",
            exit_code=EXIT_INTERNAL_ERROR,
            inputs=inputs,
            notes=[msg],
        )
        return EXIT_INTERNAL_ERROR


# ----------------------------
# Parser
# ----------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="blacktent", description="BlackTent CLI")

    p.add_argument(
        "--receipt-dir",
        default=str(DEFAULT_RECEIPT_DIR),
        help="Directory to write JSON receipts (default: .blacktent/)",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress human-readable output; still writes receipts",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    # doctor
    p_doctor = sub.add_parser("doctor", help="Diagnostics and sanity checks")
    sub_doctor = p_doctor.add_subparsers(dest="doctor_cmd", required=True)

    p_env = sub_doctor.add_parser("env", help="Validate an env file against a schema")
    p_env.add_argument("--env", dest="env_file", required=True, help="Path to .env file")
    p_env.add_argument(
        "--required-file",
        dest="required_file",
        required=True,
        help="Path to required env schema file",
    )
    p_env.set_defaults(_handler="doctor_env")

    p_repo = sub_doctor.add_parser("repo", help="Doctor a target repo (stub)")
    p_repo.add_argument("target_repo_path", help="Path to the target repo")
    p_repo.add_argument("intent", help='Intent sentence (wrap in quotes)')
    p_repo.add_argument(
        "--apply",
        action="store_true",
        help="Apply proposed changes (default: dry-run)",
    )
    p_repo.set_defaults(_handler="doctor_repo")

    # scan (optional)
    p_scan = sub.add_parser("scan", help="(Optional) scan/bundle/redaction helpers")
    p_scan.set_defaults(_handler="scan_bundle")

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)

    receipt_dir = Path(ns.receipt_dir)
    quiet = bool(ns.quiet)

    handler = getattr(ns, "_handler", None)

    if handler == "doctor_env":
        args = DoctorEnvArgs(
            env_file=Path(ns.env_file),
            required_file=Path(ns.required_file),
            receipt_dir=receipt_dir,
            quiet=quiet,
        )
        return cmd_doctor_env(args)

    if handler == "doctor_repo":
        args = DoctorRepoArgs(
            target_repo_path=Path(ns.target_repo_path),
            intent=str(ns.intent),
            receipt_dir=receipt_dir,
            quiet=quiet,
            apply=bool(ns.apply),
        )
        return cmd_doctor_repo(args)

    if handler == "scan_bundle":
        args = ScanArgs(receipt_dir=receipt_dir, quiet=quiet)
        return cmd_scan_bundle(args)

    parser.print_help()
    return EXIT_USER_FIXABLE


if __name__ == "__main__":
    raise SystemExit(main())
