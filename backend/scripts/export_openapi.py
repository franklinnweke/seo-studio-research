import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app


def export_openapi() -> Path:
    project_root = BACKEND_ROOT.parent
    output_path = project_root / "shared" / "api-contracts" / "openapi.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
    return output_path


if __name__ == "__main__":
    path = export_openapi()
    print(f"Wrote {path}")
