from pydantic import BaseModel,ValidationError,ConfigDict
import json
class Block(BaseModel):
    model_config = ConfigDict(strict=True)
    id: str
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

def load(model):
    try:
        temp = model

        return ModelIR.model_validate(temp)

    except ValidationError as e:
        print(e.errors())





