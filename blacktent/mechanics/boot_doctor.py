from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Iterable

DEFAULT_PORTS = range(5173, 5181)
REQUEST_TIMEOUT = 0.5

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

