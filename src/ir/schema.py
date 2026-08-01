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
        try:
            temp = json.load(f)

            return ModelIR.model_validate(temp)

        except ValidationError as e:
            print(e.errors())





