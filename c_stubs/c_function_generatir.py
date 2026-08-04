def generate_c_code(model, execution_order, mapping) -> str:
    lines = ["#include \"company_functions.h\"", "", "void run_model(void) {"]
    var_names = {}

    for block_id in execution_order:
        block = next(b for b in model.blocks if b.id == block_id)
        func_info = mapping[block.type]
        var_name = block.name.lower()
        var_names[block_id] = var_name

        args = []
        for param_value in block.params.values():
            args.append(str(param_value))
        for input_signal in block.inputs:
            source_block_id = input_signal.split("_")[0]  # depends on your IR's naming
            args.append(var_names.get(source_block_id, input_signal))

        lines.append(f"    float {var_name} = {func_info['function']}({', '.join(args)});")

    lines.append("}")
    return "\n".join(lines)