from pathlib import Path
from src.ir.schema import load

PROJECT_ROOT = Path(__file__).resolve().parents[2]

json_path = PROJECT_ROOT / "data" / "sample_models" / "toy1.json"

model = load(json_path)
# print(model.blocks)

# Creating a graph
import networkx as nx

def build_execution_order(model) -> list[str]:
    graph = nx.DiGraph()

    for block in model.blocks:
        graph.add_node(block.id)

    for conn in model.connections:
        source_block_id = conn.from_.split(".")[0]
        target_block_id = conn.to.split(".")[0]
        graph.add_edge(source_block_id, target_block_id)

    if not nx.is_directed_acyclic_graph(graph):
        raise ValueError("Model contains a cycle — cannot determine a sequential execution order")

    return list(nx.topological_sort(graph))
