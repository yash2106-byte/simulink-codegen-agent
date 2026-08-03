# First load all the json object here
from pathlib import Path
from src.ir.builder import load_json
PROJECT_ROOT = Path(__file__).resolve().parent
json_path = PROJECT_ROOT / "data" / "sample_models" / "toy1.json"
model = load_json(json_path)

# Then give it to the schema.py to check weather the json we have recived is correct or not
from src.ir.schema import load
print(load(model))


