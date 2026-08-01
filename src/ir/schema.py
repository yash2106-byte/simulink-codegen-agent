from pydantic import BaseModel,ValidationError
import json


class Block(BaseModel):
    id: int
    type: str
    name: str
    params: dict

class Connection(BaseModel):
    from_: str
    to: str

class ModelIR(BaseModel):
    model_name: str
    blocks: list[Block]
    connections: list[Connection]

def load(path:str):
    with open(path,"r") as f:
        temp = json.load(f)
        try:
            temp = json.load(f)

            model = ModelIR.model_validate(temp)

            print(model)
        except ValidationError as e:
            print(e.errors())
        print(temp)


load("../../data/sample_models/toy1.json")



