# This file will work as a first check point for the json file to ensure it doesnt break later
from pydantic import BaseModel
from typing import Dict, List, Any

class Block(BaseModel):
    id: str
    type: str
    name: str
    params: Dict[str, Any] = {}


class Connection(BaseModel):
    from_: str
    to: str


class Model(BaseModel):
    model_name: str
    blocks: List[Block]
    connections: List[Connection]