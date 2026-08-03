from pathlib import Path
from src.ir.builder import load_json
from src.ir.schema import load
from src.graph.ordering import build_execution_order

PROJECT_ROOT = Path(__file__).resolve().parent
json_path = PROJECT_ROOT / "data" / "sample_models" / "toy1.json"

# Step 1: Read JSON
model = load_json(json_path)

# Step 2: Validate and convert to ModelIR
model = load(model)

# print(model)
# print(type(model))   # print ModelIR

# Step 3: Build execution order
print(build_execution_order(model))