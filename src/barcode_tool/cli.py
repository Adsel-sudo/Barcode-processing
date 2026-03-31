"""Project CLI entrypoint.

This module intentionally keeps only lightweight command scaffolding.
Business logic should live in pipeline/services modules.
"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Barcode Processing Toolkit")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "inspect-pdf",
        help="Inspect PDF text blocks (placeholder command, implementation pending)",
    )
    subparsers.add_parser(
        "extract-labels",
        help="Extract barcode label crops (placeholder command, implementation pending)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    print(f"[TODO] command '{args.command}' is not implemented yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
