from pathlib import Path
import sys


EVALUATION_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVALUATION_ROOT / "src"))

from seo_studio_eval.schemas import export_schemas


if __name__ == "__main__":
    output = EVALUATION_ROOT / "schemas"
    export_schemas(output)
    print(f"Wrote schemas to {output}")
