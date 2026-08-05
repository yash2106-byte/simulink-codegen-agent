def generate_c_code(model, execution_order, mapping):
    lines = [
        '#include "company_functions.h"',
        "",
        "void run_model(void) {"
    ]

    var_names = {}

    # Build incoming connection map
    connection_map = {}

    for conn in model.connections:
        block_id, port = conn.to.split(".")
        src_block, _ = conn.from_.split(".")

        connection_map.setdefault(block_id, {})[port] = src_block

    for block_id in execution_order:

        block = next(b for b in model.blocks if b.id == block_id)

        info = mapping[block.type]

        function = info["function"]
        signature = info["signature"]

        var_name = block.name.lower()
        var_names[block_id] = var_name

        args = []

        for arg in signature:

            # parameter
            if arg in block.params:
                args.append(str(block.params[arg]))

            # connected input
            elif arg in connection_map.get(block.id, {}):
                src = connection_map[block.id][arg]
                args.append(var_names[src])

            else:
                raise ValueError(
                    f"Missing argument '{arg}' for block {block.name}"
                )

        lines.append(
            f"    float {var_name} = {function}({', '.join(args)});"
        )

    lines.append("}")

    return "\n".join(lines)