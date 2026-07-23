import argparse
import json
from pathlib import Path
import sys

from pydantic import ValidationError

from .accounting import build_run_accounting
from .blinding import build_blinded_package
from .calibration import build_calibration_package
from .calibration_analysis import build_calibration_analysis
from .execution_plan import (
    build_full_study_execution_plan,
    validate_full_study_execution_plan,
)
from .full_study import collect_full_study_phase
from .normalization import normalize_metadata_pipeline, normalize_run_directories
from .pilot import run_compatibility_pilot
from .pilot_reporting import build_pilot_report
from .preflight import run_preflight
from .protocol_freeze import audit_protocol_freeze
from .reporting import build_compatibility_report
from .sample_size import build_sample_size_sensitivity
from .smoke import run_compatibility_smoke
from .truncation_repair import (
    build_truncation_repair_plan,
    build_truncation_repair_report,
    run_truncation_repair,
)
from .validation import validate_run_directory
from .writer_compatibility import build_writer_report, run_writer_compatibility
from .writer_matrix import build_writer_matrix_report, run_writer_matrix


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seo-studio-eval")
    commands = parser.add_subparsers(dest="command", required=True)

    preflight = commands.add_parser("preflight", help="Validate offline study configuration and dataset evidence")
    preflight.add_argument("--config", type=Path, required=True)

    protocol_audit = commands.add_parser(
        "protocol-audit",
        help="Validate the Gate 4 protocol contract and report every unresolved freeze blocker",
    )
    protocol_audit.add_argument("--protocol", type=Path, required=True)
    protocol_audit.add_argument("--output", type=Path, required=True)

    sample_size = commands.add_parser(
        "sample-size-plan",
        help="Generate pre-data sample-size sensitivity evidence from the approved meaningful effects",
    )
    sample_size.add_argument("--protocol", type=Path, required=True)
    sample_size.add_argument("--output", type=Path, required=True)

    full_plan = commands.add_parser(
        "full-study-plan",
        help="Generate the deterministic full-study execution plan without model inference",
    )
    full_plan.add_argument("--protocol", type=Path, required=True)
    full_plan.add_argument("--config", type=Path, required=True)
    full_plan.add_argument("--output", type=Path, required=True)
    full_plan.add_argument("--summary", type=Path, required=True)

    full_plan_validate = commands.add_parser(
        "full-study-plan-validate",
        help="Verify the full-study plan against the protocol, dataset, and frozen seed",
    )
    full_plan_validate.add_argument("--protocol", type=Path, required=True)
    full_plan_validate.add_argument("--config", type=Path, required=True)
    full_plan_validate.add_argument("--plan", type=Path, required=True)
    full_plan_validate.add_argument("--output", type=Path, required=True)

    full_collect = commands.add_parser(
        "full-study-collect",
        help="Collect one frozen full-study phase with append-only checkpoints",
    )
    full_collect.add_argument("--protocol", type=Path, required=True)
    full_collect.add_argument("--config", type=Path, required=True)
    full_collect.add_argument("--plan", type=Path, required=True)
    full_collect.add_argument(
        "--phase",
        choices=["primary_generation", "decomposed_writer", "context_ablation"],
        required=True,
    )
    full_collect.add_argument("--base-url", required=True)
    full_collect.add_argument("--run-dir", type=Path, required=True)
    full_collect.add_argument("--run-id", required=True)
    full_collect.add_argument("--system-snapshot-ref", required=True)
    full_collect.add_argument("--max-new-attempts", type=int)
    full_collect.add_argument("--vision-selection-record", type=Path)

    validate = commands.add_parser("validate", help="Validate immutable attempt records in a run directory")
    validate.add_argument("--run-dir", type=Path, required=True)

    normalize = commands.add_parser("normalize", help="Create versioned normalized records without changing raw evidence")
    normalize.add_argument("--run-dir", type=Path, action="append", required=True)
    normalize.add_argument("--repair-run-dir", type=Path, action="append")
    normalize.add_argument("--model-id", action="append")
    normalize.add_argument("--output-dir", type=Path, required=True)

    normalize_metadata = commands.add_parser(
        "normalize-metadata-pipeline",
        help="Combine source facts, bounded repairs, and fixed-writer outcomes into balanced metadata cells",
    )
    normalize_metadata.add_argument("--source-run-dir", type=Path, action="append", required=True)
    normalize_metadata.add_argument("--repair-run-dir", type=Path, action="append", required=True)
    normalize_metadata.add_argument("--writer-run-dir", type=Path, required=True)
    normalize_metadata.add_argument("--writer-criteria", type=Path, required=True)
    normalize_metadata.add_argument("--writer-run-id", required=True)
    normalize_metadata.add_argument("--model-id", action="append", required=True)
    normalize_metadata.add_argument("--output-dir", type=Path, required=True)

    blind = commands.add_parser("blind", help="Create a reviewer package and a separate private identity map")
    blind.add_argument("--normalized-records", type=Path, required=True)
    blind.add_argument("--review-dir", type=Path, required=True)
    blind.add_argument("--mapping-dir", type=Path, required=True)
    blind.add_argument("--seed", type=int, required=True)

    calibration = commands.add_parser(
        "calibration-package",
        help="Select a deterministic all-condition subset from an already blinded reviewer package",
    )
    calibration.add_argument("--review-items", type=Path, required=True)
    calibration.add_argument("--output-dir", type=Path, required=True)
    calibration.add_argument("--seed", type=int, required=True)
    calibration.add_argument("--image-count", type=int, required=True)
    calibration.add_argument("--expected-conditions", type=int, required=True)

    calibration_analysis = commands.add_parser(
        "calibration-analysis",
        help="Validate two blinded human-check calibration passes and generate agreement/workload evidence",
    )
    calibration_analysis.add_argument("--review-items", type=Path, required=True)
    calibration_analysis.add_argument("--reviewer", action="append", nargs=2, metavar=("ALIAS", "PATH"), required=True)
    calibration_analysis.add_argument("--adjudicated", type=Path, required=True)
    calibration_analysis.add_argument("--timing", action="append", nargs=2, metavar=("ALIAS", "PATH"), required=True)
    calibration_analysis.add_argument("--assigned-order", action="append", nargs=2, metavar=("ALIAS", "PATH"), required=True)
    calibration_analysis.add_argument("--rubric", type=Path, required=True)
    calibration_analysis.add_argument("--schema", type=Path, required=True)
    calibration_analysis.add_argument("--evidence", type=Path, required=True)
    calibration_analysis.add_argument("--output", type=Path, required=True)

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
    writer_matrix = commands.add_parser(
        "writer-matrix",
        help="Pass every schema-valid selected fact record through the pinned metadata writer",
    )
    writer_matrix.add_argument("--config", type=Path, required=True)
    writer_matrix.add_argument("--criteria", type=Path, required=True)
    writer_matrix.add_argument("--source-run-dir", type=Path, action="append", required=True)
    writer_matrix.add_argument("--repair-run-dir", type=Path, action="append", required=True)
    writer_matrix.add_argument("--base-url", required=True)
    writer_matrix.add_argument("--output-dir", type=Path, required=True)
    writer_matrix.add_argument("--run-id", required=True)
    writer_matrix.add_argument("--system-snapshot-ref", required=True)
    writer_matrix.add_argument("--max-new-attempts", type=int)
    writer_matrix_report = commands.add_parser(
        "writer-matrix-report",
        help="Generate sanitized non-ranking structural evidence for a complete writer matrix",
    )
    writer_matrix_report.add_argument("--summary", type=Path, required=True)
    writer_matrix_report.add_argument("--evidence", type=Path, required=True)
    writer_matrix_report.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "preflight":
            summary, output_path = run_preflight(args.config)
            print(json.dumps({**summary.model_dump(), "summary_path": str(output_path)}, sort_keys=True))
            return 0 if summary.status == "ready" else 1
        if args.command == "protocol-audit":
            summary, output_path = audit_protocol_freeze(args.protocol, args.output)
            print(json.dumps({**summary.model_dump(), "summary_path": str(output_path)}, sort_keys=True))
            return 0 if summary.status == "freeze_ready" else 1
        if args.command == "sample-size-plan":
            summary, output_path = build_sample_size_sensitivity(args.protocol, args.output)
            print(json.dumps({**summary.model_dump(), "summary_path": str(output_path)}, sort_keys=True))
            return 0
        if args.command == "full-study-plan":
            summary, plan_path = build_full_study_execution_plan(
                args.protocol,
                args.config,
                args.output,
                args.summary,
            )
            print(
                json.dumps(
                    {**summary.model_dump(), "plan_path": str(plan_path)},
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "full-study-plan-validate":
            summary, output_path = validate_full_study_execution_plan(
                args.protocol,
                args.config,
                args.plan,
                args.output,
            )
            print(
                json.dumps(
                    {**summary.model_dump(), "summary_path": str(output_path)},
                    sort_keys=True,
                )
            )
            return 0 if summary.status == "valid" else 1
        if args.command == "full-study-collect":
            summary, output_path = collect_full_study_phase(
                args.protocol,
                args.config,
                args.plan,
                phase=args.phase,
                base_url=args.base_url,
                run_dir=args.run_dir,
                run_id=args.run_id,
                system_snapshot_ref=args.system_snapshot_ref,
                max_new_attempts=args.max_new_attempts,
                vision_selection_path=args.vision_selection_record,
            )
            print(
                json.dumps(
                    {**summary.model_dump(), "summary_path": str(output_path)},
                    sort_keys=True,
                )
            )
            return 0 if summary.status == "complete" else 2
        if args.command == "validate":
            summary, output_path = validate_run_directory(args.run_dir)
            print(json.dumps({**summary.model_dump(), "summary_path": str(output_path)}, sort_keys=True))
            return 0 if summary.status == "valid" else 1
        if args.command == "normalize":
            summary, output_path = normalize_run_directories(
                args.run_dir,
                args.output_dir,
                model_ids=args.model_id,
                repair_run_dirs=args.repair_run_dir,
            )
            print(json.dumps({**summary.model_dump(), "records_path": str(output_path)}, sort_keys=True))
            return 0 if summary.status == "normalized" else 1
        if args.command == "normalize-metadata-pipeline":
            summary, output_path = normalize_metadata_pipeline(
                args.source_run_dir,
                args.repair_run_dir,
                args.writer_run_dir,
                args.output_dir,
                model_ids=args.model_id,
                writer_criteria_path=args.writer_criteria,
                writer_run_id=args.writer_run_id,
            )
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
        if args.command == "calibration-package":
            summary, package_path, timing_path = build_calibration_package(
                args.review_items,
                args.output_dir,
                seed=args.seed,
                image_count=args.image_count,
                expected_conditions=args.expected_conditions,
            )
            print(
                json.dumps(
                    {
                        **summary.model_dump(),
                        "package_path": str(package_path),
                        "timing_template_path": str(timing_path),
                    },
                    sort_keys=True,
                )
            )
            return 0 if summary.status == "ready" else 1
        if args.command == "calibration-analysis":
            summary, evidence_path, report_path = build_calibration_analysis(
                args.review_items,
                {alias: Path(path) for alias, path in args.reviewer},
                args.adjudicated,
                {alias: Path(path) for alias, path in args.timing},
                {alias: Path(path) for alias, path in args.assigned_order},
                args.rubric,
                args.schema,
                args.evidence,
                args.output,
            )
            print(
                json.dumps(
                    {
                        **summary.model_dump(mode="json"),
                        "evidence_path": str(evidence_path),
                        "report_path": str(report_path),
                    },
                    sort_keys=True,
                )
            )
            return 0 if summary.status in {"ready", "recalibration_required"} else 1
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
        if args.command == "writer-matrix":
            summary, summary_path = run_writer_matrix(
                args.config,
                args.criteria,
                args.source_run_dir,
                args.repair_run_dir,
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
        if args.command == "writer-matrix-report":
            evidence_path, report_path = build_writer_matrix_report(
                args.summary, args.evidence, args.output
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
