import json
# from .schema import Block, Connection, ModelIR

def load_json(path: str):

    with open(path, "r") as f:
        print(json.load(f))


load_json("../../data/sample_models/toy1.json")