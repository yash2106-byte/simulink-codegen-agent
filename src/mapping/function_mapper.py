# This file imports the function_mapping.json file and returns
# the function name and required arguments for each block.

from pathlib import Path
import json

from src.ir.builder import load_json
from src.ir.schema import load


# Load Model
PROJECT_ROOT = Path(__file__).resolve().parents[2]

json_path = PROJECT_ROOT / "data" / "sample_models" / "toy1.json"

model = load_json(json_path)
model = load(model)


# Load Function Mapping
def load_mapper(path: Path):
    with open(path, "r") as f:
        return json.load(f)


mapping_path = PROJECT_ROOT / "data" / "sample_models" / "function_mapping.json"

mapper = load_mapper(mapping_path)


# Get Function Mapping
def get_function_call(block, mapper):
    """
    Returns:
        function_name (str)
        arguments (list)

    Raises:
        KeyError if the block type is not present in the mapping.
    """

    # Check whether mapping exists
    if block.type not in mapper:
        raise KeyError(
            f"No mapping found for block type '{block.type}'. "
            f"Please add it to function_mapping.json."
        )

    mapping = mapper[block.type]

    # Validate required fields
    if "function" not in mapping:
        raise KeyError(
            f"Block type '{block.type}' is missing the 'function' field."
        )

    if "signature" not in mapping:
        raise KeyError(
            f"Block type '{block.type}' is missing the 'signature' field."
        )

    function_name = mapping["function"]
    arguments = mapping["signature"]

    return function_name, arguments


# Print Function Calls
for block in model.blocks:
    function_name, arguments = get_function_call(block, mapper)

    print(f"Block Name : {block.name}")
    print(f"Block Type : {block.type}")
    print(f"Function   : {function_name}")
    print(f"Arguments  : {arguments}")
    print("-" * 40)