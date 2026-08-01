from pathlib import Path
from src.ir.schema import load

PROJECT_ROOT = Path(__file__).resolve().parents[2]

json_path = PROJECT_ROOT / "data" / "sample_models" / "toy1.json"

model = load(json_path)
print(model.blocks)