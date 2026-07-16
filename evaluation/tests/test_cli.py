import json
from pathlib import Path

from seo_studio_eval.cli import main


def test_validate_command_returns_nonzero_and_machine_readable_summary(
    tmp_path: Path,
    capsys,
) -> None:
    exit_code = main(["validate", "--run-dir", str(tmp_path)])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert output["status"] == "invalid"
    assert output["records_checked"] == 0
    assert Path(output["summary_path"]).is_file()


def test_compatibility_report_command_writes_non_ranking_report(tmp_path: Path, capsys) -> None:
    evaluation_root = Path(__file__).resolve().parents[1]
    report_path = tmp_path / "compatibility.md"

    exit_code = main(
        [
            "compatibility-report",
            "--evidence",
            str(evaluation_root / "results" / "compatibility-20260716.json"),
            "--output",
            str(report_path),
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["status"] == "written"
    assert "must not be used to rank" in report_path.read_text()
