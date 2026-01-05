from __future__ import annotations

import socket
from dataclasses import dataclass
import subprocess
from pathlib import Path
from typing import Iterable

DEFAULT_PORTS = range(5173, 5181)
REQUEST_TIMEOUT = 0.5


def _read_nvmrc(cwd: Path) -> str | None:
    path = cwd / ".nvmrc"
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def _node_major_version() -> int | None:
    try:
        completed = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    version = completed.stdout.strip()
    if version.startswith("v"):
        version = version[1:]
    if not version:
        return None
    try:
        return int(version.split(".")[0])
    except ValueError:
        return None

def check_node_dependencies(cwd: Path) -> tuple[str, str]:
    pkg = cwd / "package.json"
    node_modules = cwd / "node_modules"
    if not pkg.exists():
        return ("ok", "No package.json detected; dependency check skipped.")
    if not node_modules.exists():
        return (
            "warning",
            "package.json is present but node_modules/ missing. Run `npm install` or `pnpm install` to fetch dependencies.",
        )
    return ("ok", "node_modules/ is present.")


@dataclass(frozen=True)
class BootDoctorStatus:
    running: bool
    port: int | None = None
    url: str | None = None


def _probe_port(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(REQUEST_TIMEOUT)
        try:
            sock.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


def scan_dev_server(ports: Iterable[int] = DEFAULT_PORTS) -> BootDoctorStatus:
    for port in ports:
        if _probe_port(port):
            return BootDoctorStatus(
                running=True,
                port=port,
                url=f"http://localhost:{port}/",
            )
    return BootDoctorStatus(running=False)


def check_node_version(cwd: Path) -> tuple[str, str]:
    required = _read_nvmrc(cwd)
    if not required:
        return ("ok", "No .nvmrc detected; Node version check skipped.")
    try:
        required_major = int(required.split(".")[0])
    except ValueError:
        return ("warning", "Could not parse Node major version from .nvmrc.")
    detected_major = _node_major_version()
    if detected_major is None:
        return (
            "warning",
            "Node.js is not available in PATH; install it or use nvm before running Boot Doctor.",
        )
    if detected_major != required_major:
        return (
            "warning",
            f".nvmrc requires Node {required_major} but detected Node {detected_major}. Use `nvm use {required}`.",
        )
    return ("ok", f"Node major version {detected_major} matches .nvmrc.")

