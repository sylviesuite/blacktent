from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, List, Optional

from . import __version__
from .core.doctor import run_doctor
from .core.env import run_env_check
from .core.models import Result
from .core.redact import run_redact
from .core.scan import run_scan
from .env_sanity import parse_env_file
from .util.formatting import print_human_result
from .util.jsonout import print_json_result
from .util.paths import cwd_context
from .util.report import write_report
from .verify import generate_secret, run_checks

EXIT_OK = 0
EXIT_ISSUES = 1
EXIT_BLOCKED = 2
EXIT_INTERNAL_ERROR = 3


def _determine_exit_code(status: str) -> int:
    normalized = status.lower()
    if normalized == "ok":
        return EXIT_OK
    if normalized in {"warning", "info"}:
        return EXIT_ISSUES
    if normalized in {"error", "blocked"}:
        return EXIT_BLOCKED
    return EXIT_INTERNAL_ERROR


def _emit_result(result: Result, args: argparse.Namespace, *, command_name: str) -> None:
    if args.json:
        print_json_result(result)
    else:
        print_human_result(
            result,
            header=f"BlackTent {command_name}",
            quiet=args.quiet,
            no_color=args.no_color,
            verbose=args.verbose,
        )

    if getattr(args, "report", None):
        report_path = Path(args.report)

        write_report(report_path, result, command=command_name)
        if not args.quiet:
            print(f"Report written to {report_path}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="blacktent")
    parser.add_argument("--version", "-V", action="version", version=__version__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of human output.")
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("--quiet", action="store_true", help="Minimize CLI output.")
    verbosity.add_argument("--verbose", action="store_true", help="Show more context in human output.")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors.")
    parser.add_argument("--cwd", type=str, default="", help="Run the command with this working directory temporarily.")
    parser.add_argument("--profile", type=str, default="", help="Reserved profile name.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="Run the doctor triage flow.")
    doctor_parser.add_argument("--scope", choices=["minimal", "standard", "deep"], default="standard")
    doctor_parser.add_argument(
        "--category",
        choices=["boot", "env", "git", "deps", "fs", "network"],
        help="Focus the doctor on a specific slice.",
    )
    doctor_parser.add_argument("--fail-fast", action="store_true", help="Stop on first issue (placeholder behavior).")
    doctor_parser.add_argument("--report", type=str, help="Write a sanitized report.")
    doctor_parser.add_argument(
        "subcommand",
        nargs="?",
        choices=["boot", "env", "git", "deps"],
        help="Run a specific doctor subcommand (placeholder).",
    )

    env_parser = subparsers.add_parser("env", help="Work with env checks.")
    env_subparsers = env_parser.add_subparsers(dest="env_command", required=True)
    env_check = env_subparsers.add_parser("check", help="Validate environment keys.")
    env_check.add_argument(
        "--source",
        choices=[".env", ".env.local", "process", "all"],
        default="all",
        help="Which sources to inspect.",
    )
    env_check.add_argument("--schema", type=str, help="Optional schema path for future enforcement.")
    env_check.add_argument("--strict", action="store_true", help="Treat missing keys as failures.")
    env_check.add_argument("--print-keys", action="store_true", help="Show the key names found (no values).")

    scan_parser = subparsers.add_parser("scan", help="Inspect common secret/config locations.")
    scan_parser.add_argument("--scope", choices=["minimal", "repo"], default="minimal")
    scan_parser.add_argument("--include", action="append", default=[], help="Additional glob to include.")
    scan_parser.add_argument("--exclude", action="append", default=[], help="Glob to exclude.")
    scan_parser.add_argument(
        "--ruleset",
        choices=["default", "strict"],
        default="default",
        help="Pretend ruleset for the scan.",
    )
    scan_parser.add_argument("--max-files", type=int, default=200, help="Max files to enumerate.")
    scan_parser.add_argument("--report", type=str, help="Write a sanitized report.")

    redact_parser = subparsers.add_parser("redact", help="Manage redact bundles.")
    redact_subparsers = redact_parser.add_subparsers(dest="redact_command", required=True)
    bundle_parser = redact_subparsers.add_parser("bundle", help="Create or preview a redact bundle.")
    bundle_parser.add_argument("--dry-run", action="store_true", help="Show what would be bundled.")
    bundle_parser.add_argument("--out", type=str, help="Write the bundle to a directory or zip.")
    bundle_parser.add_argument(
        "--policy",
        type=str,
        choices=["default", "strict"],
        default="default",
        help="Policy placeholder for bundle contents.",
    )
    bundle_parser.add_argument("--allow", action="append", default=[], help="Allowlist glob for files.")

    verify_parser = subparsers.add_parser("verify", help="Check .env keys against their services.")
    verify_parser.add_argument(
        "--env",
        dest="env_file",
        default=".env",
        help="Path to .env file (default: .env)",
    )

    subparsers.add_parser("generate-secret", help="Generate a cryptographically secure random secret.")

    return parser


def _color(text: str, code: str, *, no_color: bool = False) -> str:
    if no_color or not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def _verify_symbols() -> tuple:
    enc = sys.stdout.encoding or "ascii"
    try:
        "✓✗–".encode(enc)
        return "✓", "✗", "–"
    except (UnicodeEncodeError, LookupError):
        return "+", "x", "-"


def _handle_verify(args: argparse.Namespace) -> int:
    env_path = Path(args.env_file)
    if not env_path.exists():
        print(f"Env file not found: {env_path}", file=sys.stderr)
        return EXIT_BLOCKED

    env_map, _ = parse_env_file(env_path)
    results = run_checks(env_map)
    nc = args.no_color
    sym_pass, sym_fail, sym_skip = _verify_symbols()

    def symbol(status: str) -> str:
        if status == "pass":
            return _color(sym_pass, "32", no_color=nc)
        if status == "fail":
            return _color(sym_fail, "31", no_color=nc)
        return _color(sym_skip, "2", no_color=nc)

    print()
    for r in results:
        print(f"  {symbol(r.status)}  {r.name:<18} {r.reason}")
        if r.status == "fail" and r.name == "JWT_SECRET":
            print(f"     Suggested:  JWT_SECRET={generate_secret()}")
    print()

    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    skipped = sum(1 for r in results if r.status == "skip")

    parts = [f"{passed} passed"] if passed else []
    if failed:
        parts.append(_color(f"{failed} failed", "31", no_color=nc))
    if skipped:
        parts.append(f"{skipped} skipped")
    print("  " + ", ".join(parts))
    print()

    return EXIT_OK if failed == 0 else EXIT_ISSUES


def _handle_doctor(args: argparse.Namespace) -> Result:
    result = run_doctor(
        scope=args.scope,
        category=args.category,
        fail_fast=args.fail_fast,
        subcommand=args.subcommand,
    )
    return result


def _handle_env_check(args: argparse.Namespace) -> Result:
    return run_env_check(source=args.source, schema=args.schema, strict=args.strict)


def _handle_scan(args: argparse.Namespace) -> Result:
    return run_scan(
        scope=args.scope,
        includes=args.include,
        excludes=args.exclude,
        ruleset=args.ruleset,
        max_files=args.max_files,
    )


def _handle_redact(args: argparse.Namespace) -> Result:
    out_path = Path(args.out) if args.out else None
    return run_redact(
        policy=args.policy,
        allow=args.allow,
        dry_run=args.dry_run or not bool(out_path),
        out_path=out_path,
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Commands that manage their own output (not Result-based)
    if args.command == "verify":
        try:
            with cwd_context(args.cwd):
                return _handle_verify(args)
        except Exception as exc:  # pragma: no cover
            print(f"Internal error: {exc}", file=sys.stderr)
            return EXIT_INTERNAL_ERROR

    if args.command == "generate-secret":
        print(generate_secret())
        return EXIT_OK

    command_map = {
        "doctor": _handle_doctor,
        "env": _handle_env_check,
        "scan": _handle_scan,
        "redact": _handle_redact,
    }

    handler = command_map.get(args.command)
    if handler is None:
        parser.print_help()
        return EXIT_INTERNAL_ERROR

    try:
        with cwd_context(args.cwd):
            result = handler(args)
    except FileNotFoundError as exc:
        print(f"Invalid --cwd path: {exc}", file=sys.stderr)
        return EXIT_BLOCKED
    except Exception as exc:  # pragma: no cover
        print(f"Internal error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR

    _emit_result(result, args, command_name=args.command)
    return _determine_exit_code(result.status)

