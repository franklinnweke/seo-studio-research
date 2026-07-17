import argparse
import json
from pathlib import Path
import sys

from pydantic import ValidationError

from .accounting import build_run_accounting
from .blinding import build_blinded_package
from .normalization import normalize_run_directories
from .pilot import run_compatibility_pilot
from .pilot_reporting import build_pilot_report
from .preflight import run_preflight
from .reporting import build_compatibility_report
from .smoke import run_compatibility_smoke
from .truncation_repair import (
    build_truncation_repair_plan,
    build_truncation_repair_report,
    run_truncation_repair,
)
from .validation import validate_run_directory
from .writer_compatibility import build_writer_report, run_writer_compatibility


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seo-studio-eval")
    commands = parser.add_subparsers(dest="command", required=True)

    preflight = commands.add_parser("preflight", help="Validate offline study configuration and dataset evidence")
    preflight.add_argument("--config", type=Path, required=True)

    validate = commands.add_parser("validate", help="Validate immutable attempt records in a run directory")
    validate.add_argument("--run-dir", type=Path, required=True)

    normalize = commands.add_parser("normalize", help="Create versioned normalized records without changing raw evidence")
    normalize.add_argument("--run-dir", type=Path, action="append", required=True)
    normalize.add_argument("--output-dir", type=Path, required=True)

    blind = commands.add_parser("blind", help="Create a reviewer package and a separate private identity map")
    blind.add_argument("--normalized-records", type=Path, required=True)
    blind.add_argument("--review-dir", type=Path, required=True)
    blind.add_argument("--mapping-dir", type=Path, required=True)
    blind.add_argument("--seed", type=int, required=True)

    account = commands.add_parser("account", help="Account for every planned model, image, and repeat")
    account.add_argument("--config", type=Path, required=True)
    account.add_argument("--run-dir", type=Path, action="append", required=True)
    account.add_argument("--output", type=Path, required=True)
    account.add_argument("--model-id", action="append")
    account.add_argument("--image-id", action="append")

    smoke = commands.add_parser("compatibility-smoke", help="Run one schema-constrained image through installed models")
    smoke.add_argument("--config", type=Path, required=True)
    smoke.add_argument("--model-id", action="append", required=True)
    smoke.add_argument("--image-id", required=True)
    smoke.add_argument("--base-url", required=True)
    smoke.add_argument("--output-dir", type=Path, required=True)
    smoke.add_argument("--timeout-seconds", type=float, default=240.0)

    pilot = commands.add_parser(
        "compatibility-pilot",
        help="Run the predeclared warm compatibility matrix with append-only checkpoints",
    )
    pilot.add_argument("--config", type=Path, required=True)
    pilot.add_argument("--criteria", type=Path, required=True)
    pilot.add_argument("--base-url", required=True)
    pilot.add_argument("--output-dir", type=Path, required=True)
    pilot.add_argument("--run-id", required=True)
    pilot.add_argument("--system-snapshot-ref", required=True)
    pilot.add_argument("--max-new-attempts", type=int)

    repair = commands.add_parser(
        "truncation-repair",
        help="Run one explicit larger-output recovery for each frozen length-truncated source outcome",
    )
    repair.add_argument("--config", type=Path, required=True)
    repair.add_argument("--criteria", type=Path, required=True)
    repair.add_argument("--source-run-dir", type=Path, action="append", required=True)
    repair.add_argument("--base-url", required=True)
    repair.add_argument("--output-dir", type=Path, required=True)
    repair.add_argument("--run-id", required=True)
    repair.add_argument("--system-snapshot-ref", required=True)
    repair.add_argument("--max-new-attempts", type=int)

    repair_plan = commands.add_parser(
        "truncation-repair-plan",
        help="Freeze the deterministic length-truncation repair population without live inference",
    )
    repair_plan.add_argument("--config", type=Path, required=True)
    repair_plan.add_argument("--criteria", type=Path, required=True)
    repair_plan.add_argument("--source-run-dir", type=Path, action="append", required=True)
    repair_plan.add_argument("--output", type=Path, required=True)

    repair_report = commands.add_parser(
        "truncation-repair-report",
        help="Combine immutable one-shot outcomes with explicit truncation repairs",
    )
    repair_report.add_argument("--source-config", type=Path, action="append", required=True)
    repair_report.add_argument("--source-run-dir", type=Path, action="append", required=True)
    repair_report.add_argument("--repair-run-dir", type=Path, required=True)
    repair_report.add_argument("--criteria", type=Path, required=True)
    repair_report.add_argument("--evidence", type=Path, required=True)
    repair_report.add_argument("--output", type=Path, required=True)

    report = commands.add_parser("compatibility-report", help="Render a non-ranking compatibility evidence report")
    report.add_argument("--evidence", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    pilot_report = commands.add_parser(
        "pilot-report", help="Generate sanitized non-ranking evidence from a complete pilot block"
    )
    pilot_report.add_argument("--config", type=Path, required=True)
    pilot_report.add_argument("--criteria", type=Path, required=True)
    pilot_report.add_argument("--run-dir", type=Path, required=True)
    pilot_report.add_argument("--evidence", type=Path, required=True)
    pilot_report.add_argument("--output", type=Path, required=True)
    pilot_report.add_argument("--deviation-reference", default="")
    writer = commands.add_parser(
        "writer-compatibility", help="Pass deterministic candidate facts through the pinned writer"
    )
    writer.add_argument("--config", type=Path, required=True)
    writer.add_argument("--criteria", type=Path, required=True)
    writer.add_argument("--source-run-dir", type=Path, required=True)
    writer.add_argument("--base-url", required=True)
    writer.add_argument("--output-dir", type=Path, required=True)
    writer.add_argument("--run-id", required=True)
    writer.add_argument("--system-snapshot-ref", required=True)
    writer_report = commands.add_parser(
        "writer-report", help="Generate sanitized evidence from a complete writer pass"
    )
    writer_report.add_argument("--summary", type=Path, required=True)
    writer_report.add_argument("--evidence", type=Path, required=True)
    writer_report.add_argument("--output", type=Path, required=True)
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
        if args.command == "normalize":
            summary, output_path = normalize_run_directories(args.run_dir, args.output_dir)
            print(json.dumps({**summary.model_dump(), "records_path": str(output_path)}, sort_keys=True))
            return 0 if summary.status == "normalized" else 1
        if args.command == "blind":
            summary, package_path, mapping_path = build_blinded_package(
                args.normalized_records,
                args.review_dir,
                args.mapping_dir,
                args.seed,
            )
            print(
                json.dumps(
                    {
                        **summary.model_dump(),
                        "package_path": str(package_path),
                        "mapping_path": str(mapping_path),
                    },
                    sort_keys=True,
                )
            )
            return 0 if summary.status == "ready" else 1
        if args.command == "account":
            summary = build_run_accounting(
                args.config,
                args.run_dir,
                args.output,
                model_ids=args.model_id,
                image_ids=args.image_id,
            )
            print(json.dumps({**summary.model_dump(), "summary_path": str(args.output)}, sort_keys=True))
            return 0 if summary.status == "complete" else 1
        if args.command == "compatibility-smoke":
            summary, summary_path = run_compatibility_smoke(
                args.config,
                args.model_id,
                args.image_id,
                args.base_url,
                args.output_dir,
                args.timeout_seconds,
            )
            print(json.dumps({**summary.model_dump(), "summary_path": str(summary_path)}, sort_keys=True))
            return 0 if summary.status == "compatible" else 1
        if args.command == "compatibility-pilot":
            summary, summary_path = run_compatibility_pilot(
                args.config,
                args.criteria,
                args.base_url,
                args.output_dir,
                args.run_id,
                args.system_snapshot_ref,
                progress=lambda payload: print(json.dumps(payload, sort_keys=True), flush=True),
                max_new_attempts=args.max_new_attempts,
            )
            print(
                json.dumps(
                    {**summary.model_dump(mode="json"), "summary_path": str(summary_path)},
                    sort_keys=True,
                )
            )
            if summary.status == "paused":
                return 0
            return 0 if summary.status == "complete" and summary.all_models_meet_threshold else 1
        if args.command == "truncation-repair":
            summary, summary_path = run_truncation_repair(
                args.config,
                args.criteria,
                args.source_run_dir,
                args.base_url,
                args.output_dir,
                args.run_id,
                args.system_snapshot_ref,
                progress=lambda payload: print(json.dumps(payload, sort_keys=True), flush=True),
                max_new_attempts=args.max_new_attempts,
            )
            print(
                json.dumps(
                    {**summary.model_dump(mode="json"), "summary_path": str(summary_path)},
                    sort_keys=True,
                )
            )
            return 0 if summary.status in {"paused", "complete"} else 1
        if args.command == "truncation-repair-plan":
            plan = build_truncation_repair_plan(
                args.config, args.criteria, args.source_run_dir, args.output
            )
            print(
                json.dumps(
                    {
                        "status": "ready",
                        "expected_repairs": plan["expected_repairs"],
                        "output_path": str(args.output),
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "truncation-repair-report":
            evidence_path, report_path = build_truncation_repair_report(
                args.source_config,
                args.source_run_dir,
                args.repair_run_dir,
                args.criteria,
                args.evidence,
                args.output,
            )
            print(
                json.dumps(
                    {
                        "status": "written",
                        "evidence_path": str(evidence_path),
                        "report_path": str(report_path),
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "compatibility-report":
            output_path = build_compatibility_report(args.evidence, args.output)
            print(json.dumps({"status": "written", "report_path": str(output_path)}, sort_keys=True))
            return 0
        if args.command == "pilot-report":
            evidence_path, report_path = build_pilot_report(
                args.config,
                args.criteria,
                args.run_dir,
                args.evidence,
                args.output,
                args.deviation_reference,
            )
            print(
                json.dumps(
                    {
                        "status": "written",
                        "evidence_path": str(evidence_path),
                        "report_path": str(report_path),
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "writer-compatibility":
            summary, summary_path = run_writer_compatibility(
                args.config,
                args.criteria,
                args.source_run_dir,
                args.base_url,
                args.output_dir,
                args.run_id,
                args.system_snapshot_ref,
            )
            print(
                json.dumps(
                    {**summary.model_dump(mode="json"), "summary_path": str(summary_path)},
                    sort_keys=True,
                )
            )
            return 0 if summary.status == "complete" and summary.threshold_met else 1
        if args.command == "writer-report":
            evidence_path, report_path = build_writer_report(
                args.summary,
                args.evidence,
                args.output,
            )
            print(
                json.dumps(
                    {
                        "status": "written",
                        "evidence_path": str(evidence_path),
                        "report_path": str(report_path),
                    },
                    sort_keys=True,
                )
            )
            return 0
    except (OSError, RuntimeError, ValueError, ValidationError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
