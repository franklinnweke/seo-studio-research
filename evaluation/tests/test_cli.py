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
