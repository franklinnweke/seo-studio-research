import argparse
import json
from pathlib import Path
import sys

from pydantic import ValidationError

from .preflight import run_preflight
from .validation import validate_run_directory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seo-studio-eval")
    commands = parser.add_subparsers(dest="command", required=True)

    preflight = commands.add_parser("preflight", help="Validate offline study configuration and dataset evidence")
    preflight.add_argument("--config", type=Path, required=True)

    validate = commands.add_parser("validate", help="Validate immutable attempt records in a run directory")
    validate.add_argument("--run-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "preflight":
            summary, output_path = run_preflight(args.config)
            print(json.dumps({**summary.model_dump(), "summary_path": str(output_path)}, sort_keys=True))
            return 0 if summary.status == "ready" else 1
        if args.command == "validate":
            summary, output_path = validate_run_directory(args.run_dir)
            print(json.dumps({**summary.model_dump(), "summary_path": str(output_path)}, sort_keys=True))
            return 0 if summary.status == "valid" else 1
    except (OSError, ValueError, ValidationError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
