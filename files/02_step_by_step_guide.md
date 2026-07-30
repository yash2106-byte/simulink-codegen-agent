# Step-by-Step Build Guide

Read `01_project_overview.md` first if you haven't — this guide assumes you understand the concepts (IR, execution order, function mapping) and just walks through building it.

Each phase below has: **goal**, **why this order**, **what to build**, and **how you'll know it works**. Do them in order — do not skip to Phase 6 (LLM) early. That's the single most common mistake in projects like this.

---

## Project folder structure (set this up first)

```
simulink-codegen-agent/
├── .env                        # GROQ_API_KEY lives here, never in code
├── .gitignore                  # ignore .env, __pycache__, etc.
├── requirements.txt
├── README.md
├── data/
│   ├── sample_models/           # downloaded/hand-made .slx or IR json files
│   └── function_mapping.json    # block -> C function lookup
├── src/
│   ├── parser/
│   │   └── slx_parser.py
│   ├── ir/
│   │   ├── schema.py             # pydantic models for the IR
│   │   └── builder.py
│   ├── graph/
│   │   └── ordering.py           # dependency graph + topological sort
│   ├── mapping/
│   │   └── function_mapper.py
│   ├── codegen/
│   │   ├── deterministic_gen.py  # non-AI fallback generator
│   │   └── llm_gen.py            # Groq-based generator
│   ├── validation/
│   │   └── validator.py
│   └── pipeline.py               # wires all steps together
├── c_stubs/
│   └── company_functions.c       # your own toy versions of ADD, GAIN, etc.
└── tests/
    ├── test_parser.py
    ├── test_ordering.py
    ├── test_mapper.py
    └── test_validator.py
```

Set this up with git from the very first commit:
```bash
mkdir simulink-codegen-agent && cd simulink-codegen-agent
git init
python -m venv venv
venv\Scripts\activate        # Windows activation
pip install networkx pydantic groq python-dotenv pytest lxml
pip freeze > requirements.txt
git add . && git commit -m "Initial project scaffold"
```

---

## Phase 1 — Hand-write the IR, skip the parser entirely (start here)

**Goal:** Build and test everything *downstream* of parsing — graph ordering, function mapping, code generation, validation — using a hand-written JSON IR. This works around not having MATLAB, and it means your very first working end-to-end pipeline can exist within a day or two.

**Why this order:** The parser is actually the hardest, most fragile part (real-world XML formats vary). If you build the parser first, you can't test anything else until it works. By hand-writing the IR first, you decouple "is my logic correct" from "can I read this exact file format" — a classic engineering trick: mock your hardest dependency first.

**What to build:**

1. `data/sample_models/toy1.json` — hand-write the IR for the Constant→Gain→Add model shown in the overview doc.
2. `src/ir/schema.py` — pydantic models describing what a valid IR looks like:

```python
from pydantic import BaseModel
from typing import Dict, List, Any

class Block(BaseModel):
    id: str
    type: str
    name: str
    params: Dict[str, Any] = {}
    inputs: List[str] = []
    outputs: List[str] = []

class Connection(BaseModel):
    from_: str
    to: str

class Model(BaseModel):
    model_name: str
    blocks: List[Block]
    connections: List[Connection]
```

3. A small loader function that reads the JSON file and validates it against this schema, raising a clear error if something's wrong.

**How you'll know it works:** You can load `toy1.json` and get back a validated `Model` object with no errors, and a deliberately broken JSON (e.g. missing `type` field) raises a clear pydantic validation error instead of a cryptic crash.

---

## Phase 2 — Build the dependency graph and execution order

**Goal:** Take the `Model` object and produce a definite, ordered list of blocks to execute.

**What to build** (`src/graph/ordering.py`):

```python
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
```

This gives you a list like `["1", "2", "3"]` meaning: run block 1, then block 2, then block 3.

**How you'll know it works:** Write a `tests/test_ordering.py` with a few hand-made small graphs (including one with a cycle, to check your error handling) and assert the output order is correct.

---

## Phase 3 — Function mapping

**Goal:** For each block in the execution order, look up which C function to call.

**What to build:**

1. `data/function_mapping.json` — your own toy version:
```json
{
  "Constant": { "function": "CONST", "signature": ["value"] },
  "Gain": { "function": "GAIN", "signature": ["input", "gain"] },
  "Add": { "function": "ADD", "signature": ["a", "b"] }
}
```

2. `src/mapping/function_mapper.py` — a function that, given a block, returns the function name + arguments to call, and **raises an explicit error if a block type has no mapping** (never silently skip a block — that's exactly the kind of silent failure that would embarrass you in front of your company).

**How you'll know it works:** Feed it each block from `toy1.json` and confirm you get back the right function name and arguments; feed it an unmapped block type and confirm it errors clearly rather than silently producing wrong code.

---

## Phase 4 — Deterministic code generator (build this before touching the LLM)

**Goal:** A plain Python function that takes the ordered, mapped blocks and produces valid C code — **no AI involved**. This is your safety net and baseline.

```python
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
```

(This is a simplified sketch — you'll refine argument-matching logic once you see real IR shapes. The point of this phase is having *something* that produces correct, if unpolished, C code with zero AI dependency.)

**How you'll know it works:** Run it on `toy1.json` and manually verify the output C code is logically correct (right function calls, right order, right values) — you can literally trace through it by hand since it's a 3-block model.

At this point — **this is a genuine milestone.** You have a working Simulink-IR-to-C pipeline with zero AI. Everything from here just makes the output nicer and more flexible.

---

## Phase 5 — Real parser (now tackle `.slx` parsing)

**Goal:** Replace "hand-written IR" with "IR extracted from a real `.slx` file," without touching anything downstream.

**What to build** (`src/parser/slx_parser.py`):

1. Download 2-3 small sample `.slx` files from public sources (search GitHub for small teaching-example Simulink models with just a handful of blocks).
2. Rename one to `.zip`, extract it, and manually look at the XML inside with a text editor — get a feel for how blocks, parameters, and connections (called "lines" in Simulink's XML) are represented. This replaces the "open it in MATLAB" step you don't have.
3. Write code using Python's `zipfile` to open the `.slx` directly (no need to extract to disk):

```python
import zipfile
from lxml import etree

def load_slx_xml(slx_path: str, xml_path_inside: str):
    with zipfile.ZipFile(slx_path, 'r') as z:
        with z.open(xml_path_inside) as f:
            return etree.parse(f)
```

4. Write extraction functions that pull out block type, name, parameters, and connections into the same IR shape you defined in Phase 1. This is the part most likely to need iteration — expect to print/inspect the raw XML a lot as you figure out the exact tags used for each of your handful of supported block types.

**How you'll know it works:** Running your parser on a real downloaded `.slx` produces an IR that, when fed through Phases 2-4 (which already work), produces sensible C code. Compare the block types/values in your generated IR against what you saw manually in the unzipped XML.

**Important scoping note:** don't try to handle every possible block type Simulink supports. Handle only the ones your company's documentation covers (per your own scoping answer: basic math, saturation limits, integration). If the parser hits a block type it doesn't recognize, it should raise a clear error naming the unknown block — never guess.

---

## Phase 6 — Bring in Groq (only now)

**Goal:** Replace the plain-Python code generator's *output text* with LLM-generated code — same inputs, same guarantees, nicer formatting/comments.

**What to build** (`src/codegen/llm_gen.py`):

```python
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.environ["GROQ_API_KEY"])

SYSTEM_PROMPT = """You are a strict C code generator. You will be given:
1. An ordered list of operations (block type, function to call, arguments, output variable name)
2. Nothing else is relevant.

Rules you MUST follow exactly:
- Generate ONLY valid C code, calling exactly the functions given, in exactly the order given.
- Do not invent, skip, reorder, or rename anything.
- Add a short comment above each line explaining what it does in plain English.
- Do not add any explanation outside the code.
"""

def generate_c_code_llm(ordered_operations: list[dict]) -> str:
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": str(ordered_operations)},
        ],
    )
    return response.choices[0].message.content
```

Note what's being sent: not the raw Simulink file, not the full documentation — just the already-ordered, already-mapped list of operations. This is the "narrow prompt" discussed in the overview, and it's what keeps you well within Groq's free-tier token limits per call.

**How you'll know it works:** Run it on the same `toy1.json` operations three separate times and confirm the *logic* (function calls, order, arguments) is identical each time, even if comments/wording vary slightly.

---

## Phase 7 — Validation layer

**Goal:** Automatically check the LLM's output before trusting it.

**What to build** (`src/validation/validator.py`) — checks such as:
- Every block in the execution order has a corresponding function call in the generated code.
- The function calls appear in the same order as `execution_order`.
- Every function name used actually exists in `function_mapping.json`.
- No extra/unexpected function calls appear.

If validation fails, fall back to the deterministic generator from Phase 4 (which is always correct, just less polished) and log a warning. This fallback is not a "cop-out" — it's a legitimate, industry-standard safety pattern: **never ship unverified AI output when a verified deterministic alternative exists.**

**How you'll know it works:** Deliberately feed the validator a broken/reordered fake LLM output and confirm it catches the problem.

---

## Phase 8 — Wire it all together (`src/pipeline.py`)

```python
def run_pipeline(ir_path: str) -> str:
    model = load_and_validate_ir(ir_path)          # Phase 1
    execution_order = build_execution_order(model)  # Phase 2
    mapping = load_function_mapping()                # Phase 3
    operations = build_operations_list(model, execution_order, mapping)

    try:
        code = generate_c_code_llm(operations)       # Phase 6
        if not validate_generated_code(code, operations):
            raise ValueError("LLM output failed validation")
    except Exception as e:
        log.warning(f"Falling back to deterministic generator: {e}")
        code = generate_c_code(model, execution_order, mapping)  # Phase 4

    return code
```

---

## Phase 9 — Testing strategy

- **Unit tests** for every deterministic component (Phases 1-4, 7) — these should be fast and need no internet/API calls.
- **Golden-file tests**: save known-good output for `toy1.json` and assert future runs match it exactly for the deterministic path (the LLM path only needs "logic matches," not byte-identical text).
- **Manual verification tests**: for each new sample `.slx` you add, manually trace through what the C code *should* be, and compare.

---

## Phase 10 — What "done" looks like for your prototype

By the end of these phases you should be able to:
1. Point the pipeline at a small `.slx` file.
2. Get back a `.c` file that compiles (test this with a simple C compiler like MinGW/gcc on Windows) and produces correct results when you manually calculate what the model should output.
3. Run it multiple times and get logically identical results.
4. Only then — bring this same pipeline to your mentor/team, demonstrate it on the toy models, and ask for a small real (sanitized) company model to test the parser's robustness against real-world block types you haven't seen yet.

---

## A note on pacing

Don't rush to Phase 6. The deterministic pipeline (Phases 1-4) is genuinely the valuable, hard-to-get-wrong part of this project, and it's also the part that will most impress whoever reviews your work — because it shows you understood *why* the system needs to be reliable, not just that you can call an LLM API. Take the time to get Phases 1-4 solid before adding AI on top.
