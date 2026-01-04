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
from .health.runner import HealthState, default_checks, run_health_checks

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
    print_plan: bool


def cmd_doctor_repo(args: DoctorRepoArgs) -> int:
    """
    Repo Doctor (v1): Detect + Explain.
    Repo Doctor (v2 step): Propose (dry-run only; no apply yet).
    """
    mode = "repo-doctor"
    inputs = {
        "target_repo_path": str(args.target_repo_path),
        "intent": args.intent,
        "apply": bool(args.apply),
        "print_plan": bool(args.print_plan),
        "receipt_dir": str(args.receipt_dir),
    }

    def _read_text(path: Path, max_bytes: int = 200_000) -> str:
        try:
            b = path.read_bytes()
            if len(b) > max_bytes:
                b = b[:max_bytes]
            return b.decode("utf-8", errors="replace")
        except Exception:
            return ""

    def _env_kind(env_value: str) -> str:
        v = env_value.strip().lower()
        if v.startswith("postgres://") or v.startswith("postgresql://"):
            return "postgres"
        if v.startswith("mysql://") or v.startswith("mariadb://"):
            return "mysql"
        return "unknown"

    def _extract_database_url_kind(dotenv_path: Path) -> str:
        if not dotenv_path.exists():
            return "missing"
        text = _read_text(dotenv_path)
        # super simple parse: look for DATABASE_URL=...
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if s.startswith("DATABASE_URL="):
                # do NOT store the value, only classify
                val = s.split("=", 1)[1].strip().strip('"').strip("'")
                return _env_kind(val)
        return "absent"

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
                prefix="receipt-doctor-repo",
            )
            return EXIT_USER_FIXABLE

        repo = args.target_repo_path
        pkg = repo / "package.json"
        dotenv_candidates = [
            repo / ".env",
            repo / "server" / ".env",
            repo / "apps" / "server" / ".env",
            repo / "src" / "server" / ".env",
        ]
        found_dotenv = next((p for p in dotenv_candidates if p.exists()), None)
        dotenv = found_dotenv if found_dotenv is not None else repo / ".env"

        notes: list[str] = []
        actions: list[dict[str, Any]] = []

        # Detect: package.json exists?
        if not pkg.exists():
            notes.append("No package.json found at repo root — cannot infer scripts/deps.")
        else:
            pkg_text = _read_text(pkg)
            actions.append({"detect": "package.json_found", "path": str(pkg)})

            # quick indicators (string search; safe and fast)
            has_tsx = '"tsx"' in pkg_text or " tsx " in pkg_text or "tsx/" in pkg_text
            if has_tsx:
                notes.append(
                    "Detected tsx usage in package.json scripts/deps (common crash point if version mismatched)."
                )

            # DB driver hints from package.json
            has_mysql2 = '"mysql2"' in pkg_text or "mysql2" in pkg_text
            has_pg = '"pg"' in pkg_text or '"@types/pg"' in pkg_text or " pg " in pkg_text
            if has_mysql2:
                notes.append("Detected mysql2 dependency mention in package.json.")
            if has_pg:
                notes.append("Detected pg (Postgres) dependency mention in package.json.")

        # Detect: DATABASE_URL kind (without storing secret)
        db_kind = _extract_database_url_kind(dotenv)
        if found_dotenv is not None:
            notes.append(f"Using .env at: {found_dotenv}")
        if db_kind == "missing":
            notes.append("No .env found at repo root (DATABASE_URL check skipped).")
        elif db_kind == "absent":
            notes.append(".env found but DATABASE_URL is not set (DB config likely missing).")
        else:
            notes.append(f"DATABASE_URL appears to be: {db_kind} (classified without reading value).")

        # Lightweight file scans for adapters (optional, fast)
        likely_files = [
            repo / "server" / "db.ts",
            repo / "src" / "server" / "db.ts",
            repo / "src" / "db.ts",
            repo / "drizzle.config.ts",
            repo / "drizzle.config.js",
        ]
        adapter_hits: list[str] = []
        for f in likely_files:
            if f.exists():
                t = _read_text(f, max_bytes=150_000).lower()
                if "mysql2" in t:
                    adapter_hits.append(f"{f} mentions mysql2")
                if "drizzle-orm/mysql" in t or "drizzle-orm/mysql2" in t:
                    adapter_hits.append(f"{f} mentions drizzle mysql adapter")
                if "drizzle-orm/postgres" in t or "drizzle-orm/node-postgres" in t:
                    adapter_hits.append(f"{f} mentions drizzle postgres adapter")
                if "pg" in t and "node-postgres" in t:
                    adapter_hits.append(f"{f} mentions node-postgres (pg)")
        if adapter_hits:
            notes.extend(adapter_hits)

        # Explain: flag likely mismatch
        mismatch_flags: list[str] = []
        text_notes = " ".join(notes).lower()
        if "database_url appears to be: postgres" in text_notes and "mysql2" in text_notes:
            mismatch_flags.append("Likely mismatch: DATABASE_URL is Postgres but code/deps reference mysql2.")
        if "database_url appears to be: mysql" in text_notes and ("pg" in text_notes or "postgres" in text_notes):
            mismatch_flags.append("Likely mismatch: DATABASE_URL is MySQL but code/deps reference Postgres/pg.")

        # Propose (v2 step): add a structured proposal action (dry-run only)
        if mismatch_flags:
            actions.append(
                {
                    "propose": "align_db_driver",
                    "summary": "DATABASE_URL is Postgres but mysql2 is installed/referenced.",
                    "suggested_changes": [
                        "Remove mysql2 from package.json dependencies",
                        "Ensure drizzle uses Postgres adapter exclusively",
                        "Verify server startup loads DATABASE_URL before DB init",
                    ],
                    "confidence": "high",
                    "apply_safe": False,
                }
            )

            notes.extend(mismatch_flags)
            notes.append(
                "Next step: Doctor should propose a single patch to align DB adapter with DATABASE_URL (no auto-apply yet)."
            )
            if args.print_plan and any(
                "postgres" in flag.lower() and "mysql2" in flag.lower()
                for flag in mismatch_flags
            ):
                pkg_lines = pkg_text.splitlines()
                mysql_idx = next(
                    (idx for idx, line in enumerate(pkg_lines) if '"mysql2"' in line), None
                )
                if mysql_idx is not None:
                    start = max(0, mysql_idx - 2)
                    end = min(len(pkg_lines), mysql_idx + 4)
                    context = pkg_lines[start:end]
                else:
                    context = ['    "mysql2": "<version>"', '    // remove when using Postgres']

                diff_lines = ["@@ package.json"]
                for line in context:
                    stripped = line.strip()
                    if '"mysql2"' in stripped:
                        diff_lines.append(f"-{stripped}")
                        diff_lines.append("+    // mysql2 removed to align with Postgres")
                    else:
                        diff_lines.append(f" {stripped}")
                diff_preview = "\n".join(diff_lines)

                actions.append(
                    {
                        "plan": [
                            {
                                "op": "edit",
                                "path": str(pkg),
                                "summary": "Drop mysql2 when DATABASE_URL is Postgres-only.",
                                "diff_preview": diff_preview,
                            }
                        ]
                    }
                )

        if not args.quiet:
            print("[doctor repo] detect/explain complete — receipt written")

        write_receipt(
            args.receipt_dir,
            mode=mode,
            status="ok",
            exit_code=EXIT_OK,
            inputs=inputs,
            actions=actions,
            notes=notes or ["No notable signals detected yet."],
            prefix="receipt-doctor-repo",
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
            prefix="receipt-doctor-repo",
        )
        return EXIT_INTERNAL_ERROR


def cmd_doctor_mvp(args: argparse.Namespace) -> int:
    """
    Default Doctor MVP pipeline when no subcommand is provided.
    """
    default_repo = Path(".").resolve()
    return cmd_doctor_repo(
        DoctorRepoArgs(
            target_repo_path=default_repo,
            intent=f"Default MVP run on {default_repo}",
            receipt_dir=Path(args.receipt_dir),
            quiet=bool(args.quiet),
            apply=False,
            print_plan=False,
        )
    )


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

    try:
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


def cmd_health(_args: argparse.Namespace) -> int:
    """
    Run the health contract and summarize results.
    """
    report = run_health_checks(default_checks())
    print(f"Health state: {report.state.value}")
    for check in report.checks:
        status = check.status.value.upper()
        req = "required" if check.required else "optional"
        base_line = f"[{status}] {check.check_id} ({req}) - {check.description}"
        if check.details:
            print(f"{base_line}\n    {check.details}")
        else:
            print(base_line)
    return EXIT_OK if report.state == HealthState.HEALTHY else EXIT_INTERNAL_ERROR


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
    sub_doctor = p_doctor.add_subparsers(dest="doctor_cmd", required=False)
    p_doctor.set_defaults(_handler="doctor_mvp")

    p_env = sub_doctor.add_parser("env", help="Validate an env file against a schema")
    p_env.add_argument("--env", dest="env_file", required=True, help="Path to .env file")
    p_env.add_argument(
        "--required-file",
        dest="required_file",
        required=True,
        help="Path to required env schema file",
    )
    p_env.set_defaults(_handler="doctor_env")

    p_repo = sub_doctor.add_parser("repo", help="Doctor a target repo (detect/explain)")
    p_repo.add_argument("target_repo_path", help="Path to the target repo")
    p_repo.add_argument("intent", help='Intent sentence (wrap in quotes)')
    p_repo.add_argument(
        "--apply",
        action="store_true",
        help="Apply proposed changes (default: dry-run)",
    )
    p_repo.add_argument(
        "--print-plan",
        action="store_true",
        help="Show a plan with diff previews for detected fixes",
    )
    p_repo.set_defaults(_handler="doctor_repo")

    p_health = sub.add_parser("health", help="Run local health checks (runtime-only today).")
    p_health.set_defaults(_handler="health")

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
            print_plan=bool(getattr(ns, "print_plan", False)),
        )
        return cmd_doctor_repo(args)

    if handler == "doctor_mvp":
        return cmd_doctor_mvp(ns)

    if handler == "health":
        return cmd_health(ns)

    if handler == "scan_bundle":
        args = ScanArgs(receipt_dir=receipt_dir, quiet=quiet)
        return cmd_scan_bundle(args)

        parser.print_help()
    return EXIT_USER_FIXABLE


if __name__ == "__main__":
    raise SystemExit(main())
