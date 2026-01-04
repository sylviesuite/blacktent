"""Canonical entrypoint for running BlackTent as a package."""

from .cli import main


if __name__ == "__main__":
    # This module exists so `python -m blacktent` always runs the CLI from the package root.
    raise SystemExit(main())

