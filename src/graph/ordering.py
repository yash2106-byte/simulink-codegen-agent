import networkx as nx


class Block:
    def __init__(self, id):
        self.id = id


class Connection:
    def __init__(self, from_, to):
        self.from_ = from_
        self.to = to


class Model:
    def __init__(self, blocks, connections):
        self.blocks = blocks
        self.connections = connections


def build_execution_order(model) -> list[str]:
    graph = nx.DiGraph()

    for block in model.blocks:
        graph.add_node(block.id)

    for conn in model.connections:
        source_block_id = conn.from_.split(".")[0]
        target_block_id = conn.to.split(".")[0]
        graph.add_edge(source_block_id, target_block_id)

    if not nx.is_directed_acyclic_graph(graph):
        raise ValueError(
            "Model contains a cycle — cannot determine a sequential execution order"
        )

    return list(nx.topological_sort(graph))


# ---------------- Sample Model ----------------

blocks = [
    Block("1"),   # Constant1
    Block("2"),   # Constant2
    Block("3"),   # Add
    Block("4"),   # Gain
]

connections = [
    Connection("1.out", "3.in1"),
    Connection("2.out", "3.in2"),
    Connection("3.out", "4.in"),
]
model = Model(blocks, connections)

order = build_execution_order(model)
print(order)