"""Command-line entry point: ``grace-hw`` prints the report as JSON."""

from __future__ import annotations

import argparse
import json
import sys

from grace_hw.collector import collect


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grace-hw",
        description=(
            "Read-only hardware probe for GraceOS. "
            "Prints CPU, memory, GPU and disk info as JSON."
        ),
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Indent the JSON output for humans.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = collect()
    json.dump(report, sys.stdout, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
