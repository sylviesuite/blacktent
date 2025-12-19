from __future__ import annotations

import argparse
import errno
import importlib
import json
import socket
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

try:
    _docker_module = importlib.import_module(".docker", __package__)
    DockerError = _docker_module.DockerError
    start_sandbox = _docker_module.start_sandbox
except ImportError:
    class DockerError(RuntimeError):
        """Placeholder when Docker support is unavailable."""


    def start_sandbox(*_args, **_kwargs) -> int:
        raise DockerError("Docker integration is not available.")

from .redaction import scan_and_bundle

# Where we store session metadata (NOT code)
RUNTIME_DIR = Path(".blacktent")
SESSION_FILE = RUNTIME_DIR / "session.json"


def ensure_runtime_dir() -> None:
    """Ensure the .blacktent runtime directory exists."""
    RUNTIME_DIR.mkdir(exist_ok=True)


def load_session() -> dict | None:
    """Return the current session dict if it exists, else None."""
    if not SESSION_FILE.exists():
        return None

    try:
        with SESSION_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # If it's corrupted, treat as no session
        return None


def save_session(session: dict) -> None:
    """Persist the current session metadata."""
    with SESSION_FILE.open("w", encoding="utf-8") as f:
        json.dump(session, f, indent=2)


def clear_session() -> None:
    """Remove any existing session metadata."""
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


def cmd_open(args: argparse.Namespace) -> int:
    """
    Handle `blacktent open <file>`.

    For now this:
      - validates the file
      - records a session in .blacktent/session.json
      - prints friendly status
    """
    ensure_runtime_dir()

    target_path = Path(args.path).expanduser().resolve()

    if not target_path.exists():
        print(f"[blacktent] ❌ File not found: {target_path}", file=sys.stderr)
        return 1

    if not target_path.is_file():
        print(f"[blacktent] ❌ Not a file: {target_path}", file=sys.stderr)
        return 1

    existing = load_session()
    if existing is not None:
        print(
            "[blacktent] ⚠ A session is already open.\n"
            f"  session_id: {existing.get('session_id')}\n"
            f"  file:       {existing.get('target_file')}\n"
            "Use `blacktent close` to end it before opening another.",
            file=sys.stderr,
        )
        return 1

    try:
        bundle_result = scan_and_bundle(target_path)
    except Exception as exc:
        print(
            f"[blacktent] ❌ Failed to build safe bundle: {exc}",
            file=sys.stderr,
        )
        return 1

    session_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"

    session = {
        "session_id": session_id,
        "target_file": str(target_path),
        "created_at": now,
        "status": "open",
        "notes": "Docker sandbox not yet attached — CLI skeleton only.",
        "bundle_id": bundle_result["id"],
        "bundle_root": bundle_result["bundle_root"],
        "redacted_file": bundle_result["redacted_path"],
        "num_redactions": bundle_result["num_redactions"],
    }

    save_session(session)

    print(
        "[blacktent] ✅ Safe tent opened\n"
        f"  session_id: {session_id}\n"
        f"  file:       {target_path}\n"
        f"  bundle_id:  {bundle_result['id']}\n"
        f"  redacted:   {bundle_result['redacted_path']}\n"
        f"  redactions: {bundle_result['num_redactions']}\n"
        "You are now ready to wire this session into an ephemeral Docker sandbox."
    )

    return 0


def cmd_close(_args: argparse.Namespace) -> int:
    """
    Handle `blacktent close`.
    """
    session = load_session()
    if session is None:
        print("[blacktent] ℹ No active session found. Nothing to close.")
        return 0

    clear_session()

    print(
        "[blacktent] 🧹 Tent closed and session cleared\n"
        f"  previous_session_id: {session.get('session_id')}\n"
        f"  file:                 {session.get('target_file')}"
    )

    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    """
    Handle `blacktent status`.
    """
    session = load_session()
    if session is None:
        print("[blacktent] 💤 No active session.")
        return 0

    print(
        "[blacktent] 🏕 Active session\n"
        f"  session_id: {session.get('session_id')}\n"
        f"  file:       {session.get('target_file')}\n"
        f"  created_at: {session.get('created_at')}\n"
        f"  status:     {session.get('status')}"
    )
    return 0


def cmd_shell(_args: argparse.Namespace) -> int:
    """
    Handle `blacktent shell`.
    """
    session = load_session()
    if session is None:
        print("[blacktent] ℹ No active session found. Use `blacktent open` first.")
        return 1

    bundle_root = session.get("bundle_root")
    if not bundle_root:
        print(
            "[blacktent] ⚠ This session lacks bundle metadata. "
            "Re-open the file with the latest CLI to proceed.",
            file=sys.stderr,
        )
        return 1

    bundle_id = session.get("bundle_id", "<unknown>")

    print(
        "[blacktent] 🧪 Launching sandbox\n"
        f"  session_id: {session.get('session_id')}\n"
        f"  bundle_id:  {bundle_id}\n"
        f"  bundle_dir: {bundle_root}"
    )

    try:
        exit_code = start_sandbox(Path(bundle_root))
    except DockerError as exc:
        print(f"[blacktent] ❌ {exc}", file=sys.stderr)
        return 1

    if exit_code != 0:
        print(
            f"[blacktent] ⚠ Sandbox exited with code {exit_code}",
            file=sys.stderr,
        )

    return exit_code


def _windows_listening_pids(port: int) -> list[str]:
    if sys.platform != "win32":
        return []

    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    pids: set[str] = set()
    for line in result.stdout.splitlines():
        if "LISTENING" not in line.upper():
            continue

        parts = [part for part in line.split() if part]
        if len(parts) < 5:
            continue

        local_address = parts[1]
        if not local_address.endswith(f":{port}"):
            continue

        pid = parts[-1]
        if pid.isdigit():
            pids.add(pid)

    return sorted(pids)


def cmd_doctor(_args: argparse.Namespace) -> int:
    """
    Handle `blacktent doctor`.
    """
    ports = {
        5432: "PostgreSQL",
        5173: "frontend",
        3001: "API",
    }
    results = []

    for port, label in ports.items():
        explanation = ""
        explanation = ""
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                reachable = True
        except OSError as exc:
            reachable = False
            err = getattr(exc, "errno", None)
            if err in {
                errno.ECONNREFUSED,
                errno.EADDRNOTAVAIL,
                errno.EHOSTUNREACH,
                errno.ENETUNREACH,
            }:
                explanation = (
                    "→ Nothing is listening on this port. "
                    "This usually means the service is not running."
                )
            else:
                explanation = (
                    "→ A process is listening on this port. "
                    "This may be a stale or different service."
                )
                pids = _windows_listening_pids(port)
                if pids:
                    explanation = (
                        "→ A process is listening on this port "
                        f"(PID(s): {', '.join(pids)}). "
                        "Often a stale or different service."
                    )

        symbol = "✓" if reachable else "✗"
        print(f"{symbol} {label} (localhost:{port})")
        results.append(reachable)
        if not reachable and explanation:
            print(explanation)

    print("No changes were made. This was a read-only diagnosis.")
    return 0 if all(results) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="blacktent",
        description=(
            "BlackTent — a safe AI debugging tent.\n\n"
            "This CLI manages sessions that will be connected to "
            "ephemeral Docker sandboxes in later versions."
        ),
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # blacktent open <file>
    p_open = subparsers.add_parser(
        "open", help="Open a safe BlackTent session for a given file."
    )
    p_open.add_argument(
        "path",
        metavar="PATH",
        help="Path to the file you want to work on safely.",
    )
    p_open.set_defaults(func=cmd_open)

    # blacktent close
    p_close = subparsers.add_parser(
        "close", help="Close the current BlackTent session."
    )
    p_close.set_defaults(func=cmd_close)

    # blacktent status
    p_status = subparsers.add_parser(
        "status", help="Show the current BlackTent session, if any."
    )
    p_status.set_defaults(func=cmd_status)

    # blacktent shell
    p_shell = subparsers.add_parser(
        "shell", help="Launch an ephemeral Docker sandbox for the active bundle."
    )
    p_shell.set_defaults(func=cmd_shell)

    # blacktent doctor
    p_doctor = subparsers.add_parser(
        "doctor", help="Check local services without making changes."
    )
    p_doctor.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    """
    Main entrypoint for the BlackTent CLI.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 1

    return func(args)


if __name__ == "__main__":
    raise SystemExit(main())
