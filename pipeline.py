from pathlib import Path
from src.ir.builder import load_json
from src.ir.schema import load
from src.graph.ordering import build_execution_order
from src.mapping.function_mapper import get_function_call
from src.mapping.function_mapper import load_mapper
from c_stubs.c_function_generatir import generate_c_code

PROJECT_ROOT = Path(__file__).resolve().parent
json_path = PROJECT_ROOT / "data" / "sample_models" / "toy1.json"

# Step 1: Read JSON
model = load_json(json_path)

# Step 2: Validate and convert to ModelIR
model = load(model)

# print(type(model))   # print ModelIR

# Step 3: Build execution order
order = build_execution_order(model)

# Step 4 : Load function mapper
mapping_path = PROJECT_ROOT / "data" / "sample_models" / "function_mapping.json"
mapper = load_mapper(mapping_path)

# Step 5: Mapping each id with its function
for block in model.blocks:
    function_name, arguments = get_function_call(block, mapper)

    print(f"Block Name : {block.name}")
    print(f"Block Type : {block.type}")
    print(f"Function   : {function_name}")
    print(f"Arguments  : {arguments}")
    print("-" * 40)


# Step 6: Generated the c code
# print(generate_c_code(model=model,execution_order=order,mapping=mapper))

print(order)