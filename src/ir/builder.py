# This file will read the json data from the "/data/sample_models/toy1.json" and then return the json data in the form of an object 
# And later this file will process the data then parse it

import json
# from .schema import Block, Connection, ModelIR

def load_json(path: str):

    with open(path, "r") as f:
        return(json.load(f))


# load_json("../../data/sample_models/toy1.json")