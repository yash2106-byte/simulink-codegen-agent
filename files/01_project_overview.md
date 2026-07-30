# Project Overview: Simulink-to-C Code Generation Agent

**Purpose of this document:** This is your reference document. Read it once fully, keep it open while you work, and feel free to paste sections of it into any LLM (Groq, ChatGPT, Claude, whatever) when you need help with a specific part. It explains every concept from zero, and it explains *why* we're building the system the way we are — not just what to type.

---

## 1. What you are actually building (in plain English)

Your company has:
- Simulink models (visual block diagrams that represent some control logic — think of it like a flowchart that actually *computes* something).
- A library of C functions they already wrote (`ADD()`, `SUB()`, `MUL()`, `DIV()`, etc.) that do the same math the Simulink blocks do.

You need to build a tool that:
1. Reads a Simulink model file.
2. Figures out what each block does, and in what order they execute.
3. Writes a C file that calls the company's existing functions, in the correct order, so the C program behaves exactly like the Simulink model would if you ran it.

This is **not** "ask an AI to look at a diagram and write code." That approach is unreliable — LLMs are bad at precise, repeatable, structural transformations, and your company almost certainly cares about the C code being *correct every single time*, not just "usually correct." That's why the plan below treats this like a **compiler**, with the AI used only for one small, well-contained job inside it.

### Analogy
Think of a real compiler (like the one that turns C code into an `.exe`). It doesn't "guess" what your code means using intuition — it parses it into a structured form, analyzes it, and mechanically produces output. Your project is the same idea, except the "source language" is a Simulink diagram instead of text, and the "target language" is C using your company's functions.

---

## 2. The architecture (and why it looks like this)

```
   Simulink file (.slx)
          │
          ▼
   ┌─────────────────┐
   │   1. PARSER      │  ← deterministic Python code (no AI)
   └─────────────────┘
          │
          ▼
   Intermediate Representation (IR)   ← a clean JSON description of the model
          │
          ▼
   ┌─────────────────┐
   │ 2. GRAPH BUILDER │  ← deterministic (uses a graph library)
   └─────────────────┘
          │
          ▼
   Execution Order (a simple ordered list of blocks)
          │
          ▼
   ┌───────────────────────┐
   │ 3. FUNCTION MAPPER     │  ← deterministic lookup against company's
   └───────────────────────┘     documented block → function mapping
          │
          ▼
   ┌───────────────────────┐
   │ 4. LLM (Groq)          │  ← ONLY used here: turning the ordered,
   └───────────────────────┘     mapped IR into nicely formatted, commented
          │                      C code text. Not used for logic decisions.
          ▼
   ┌───────────────────────┐
   │ 5. VALIDATOR           │  ← deterministic checks on the generated C
   └───────────────────────┘
          │
          ▼
      Final .c file
```

**Why so many deterministic steps around one small AI step?**

Because LLMs are probabilistic — the same input can produce slightly different output each time (variable names, wording, sometimes even skipped steps). Your company needs the *same Simulink model to always produce the same C code*. That is a "deterministic system" requirement. So we make sure that anything that must never change — execution order, which function maps to which block, variable naming — is decided by plain Python code, using rules, not by asking an LLM to "figure it out." The LLM is used only for the parts where a small amount of natural-language-style reasoning helps (writing a comment, formatting code cleanly, handling something your rules didn't anticipate) — and even there, we constrain it heavily (temperature 0, strict instructions, and a validation step afterward) so its contribution stays predictable.

This is exactly how professional "AI-assisted" tools are built in industry right now: **deterministic pipeline + a narrow, well-fenced AI component**, not "AI does everything."

---

## 3. Simulink concepts, from zero

You've never used Simulink, so let's build this up slowly.

### 3.1 What is Simulink?
Simulink is a MATLAB tool for modeling systems using **block diagrams** instead of written code. Engineers building things like engine controllers, robotics, or automotive systems draw a diagram where:
- **Blocks** = operations (add two numbers, multiply by a constant, integrate over time, etc.)
- **Lines (signals)** = data flowing from one block's output to another block's input.

Example — a simple model:

```
Constant (value = 5)
        │
        ▼
     Gain (×2)
        │
        ▼
      Add (+3)
        │
        ▼
      Output
```

If you translated this to C yourself by hand, it would be:
```c
float temp1 = 5;        // Constant
float temp2 = temp1 * 2; // Gain
float temp3 = temp2 + 3; // Add
```

That's genuinely all Simulink "is" at the level you need for this project — a graphical way of describing a sequence of math operations, plus (in bigger models) loops, conditions, and time-based behavior like integrators.

### 3.2 Blocks have structured data
Every block, no matter what it does, is described by:
- **Type** — e.g. `Gain`, `Sum`, `Constant`, `Saturate`
- **Name** — a human-readable label, e.g. `Gain1`
- **Parameters** — block-specific settings, e.g. a Gain block has a `Gain` value (like 2), a Constant block has a `Value`
- **Input ports** — where signals come in (a Gain block has 1 input; a Sum/Add block usually has 2+)
- **Output ports** — where the result goes out
- **Connections** — which block's output feeds which block's input

This is exactly the kind of structured data a JSON object can represent cleanly — which is exactly what we do in step 4 below.

### 3.3 What blocks will you actually deal with?
Based on your scope (confirmed: basic math, limits, integration, no Stateflow, no subsystems for now), you're likely dealing with things like:

| Simulink Block | What it does |
|---|---|
| Constant | Outputs a fixed number |
| Gain | Multiplies input by a fixed number |
| Sum / Add | Adds (or subtracts) two or more inputs |
| Product / Divide | Multiplies or divides inputs |
| Saturation | Clamps a value between a min and max |
| Integrator | Accumulates a value over time (calculus-style "running total") |
| Switch | Chooses between two inputs based on a condition |
| Outport / Inport | Marks the model's overall input(s)/output(s) |

Each of these will map 1-to-1 (or occasionally 1-to-few) to a function your company already has, like `GAIN()`, `ADD()`, `SAT()`, `INT()`.

### 3.4 What is a `.slx` file, really?
This surprises everyone the first time: a `.slx` file is **just a ZIP archive** containing XML files and metadata. You do **not** need MATLAB to read it — you only need MATLAB (or Simulink) to *create, edit, or visually view* the diagram. Reading the raw structure is just file parsing, which Python can do fine.

If you rename `model.slx` to `model.zip` and extract it, you'll typically see a folder structure containing things like a `simulink/` folder with a `blockdiagram.xml` (or similar) file, plus some metadata folders. The exact internal layout can differ slightly between MATLAB versions, which is exactly why your parser needs to be written defensively (explained in the guide) rather than assuming one fixed layout.

**Because you don't have MATLAB:** your first real Simulink test files should be small, existing `.slx` files you find in public GitHub repositories (search terms like `simulink example .slx`, or look at repos that bundle MATLAB/Simulink teaching examples). You can inspect them with a text editor after unzipping — you don't need to *see* the diagram visually to understand its structure, since the structure lives in the XML regardless of whether you can render it.

### 3.5 Execution order and the dependency graph
This is the single most important concept in the whole project.

In a diagram like:
```
Constant → Gain → Add → Divide → Output
```
Each block **depends on** the block(s) feeding into it. `Gain` can't run before `Constant` produces a value. `Add` can't run before `Gain` finishes. This dependency chain is naturally represented as a **directed graph** (a network of "this depends on that" arrows).

The technique for turning a dependency graph into a valid execution sequence is called **topological sorting** — a well-known, 100%-deterministic algorithm (not AI). We'll use a Python library called `networkx` to do this rather than writing the algorithm from scratch, since this is a solved problem and there's no reason to reinvent it.

---

## 4. The Intermediate Representation (IR)

We never feed raw XML to the LLM (it's messy, huge, and full of irrelevant metadata). Instead, the parser converts the model into a clean, minimal JSON structure — this is the **IR**.

Example IR for the Constant → Gain → Add model:

```json
{
  "model_name": "toy_model_1",
  "blocks": [
    {
      "id": "1",
      "type": "Constant",
      "name": "Constant1",
      "params": { "value": 5 },
      "inputs": [],
      "outputs": ["signal_1"]
    },
    {
      "id": "2",
      "type": "Gain",
      "name": "Gain1",
      "params": { "gain": 2 },
      "inputs": ["signal_1"],
      "outputs": ["signal_2"]
    },
    {
      "id": "3",
      "type": "Add",
      "name": "Add1",
      "params": { "operands": 2 },
      "inputs": ["signal_2", "offset_signal"],
      "outputs": ["signal_3"]
    }
  ],
  "connections": [
    { "from": "1.signal_1", "to": "2.signal_1" },
    { "from": "2.signal_2", "to": "3.signal_2" }
  ]
}
```

Why this matters: this IR is small, human-readable, and something you can hand-write yourself for testing (Phase 1 of the roadmap does exactly that) *before* your real parser exists. This decouples "does my pipeline work" from "does my parser work" — a huge de-risking move, especially since you don't have MATLAB to visually verify your parser's output against.

---

## 5. The Function Mapping Knowledge Base

Your company's documentation (Block → Function) becomes a small structured file, e.g.:

```json
{
  "Gain": { "function": "GAIN", "signature": ["input", "gain"] },
  "Add": { "function": "ADD", "signature": ["a", "b"] },
  "Constant": { "function": "CONST", "signature": ["value"] },
  "Saturation": { "function": "SAT", "signature": ["input", "min", "max"] }
}
```

For your own toy version (since you're building your own mock functions first), you'll write this file yourself along with matching stub C functions like:

```c
float GAIN(float input, float gain) { return input * gain; }
float ADD(float a, float b) { return a + b; }
```

When you eventually get the real company files, only this mapping file (and the corresponding C headers) change — the rest of your pipeline stays exactly the same. That's the entire point of building it this way.

---

## 6. Where the LLM (Groq) fits in, precisely

The LLM's job, and *only* job, is:
> Given an already-ordered, already-mapped list of operations (in JSON), produce clean, well-commented C code text that calls the specified functions in the specified order.

It is explicitly **not** asked to:
- Decide execution order (Python already did that, deterministically)
- Decide which function maps to which block (Python already did that, via the lookup file)
- Infer anything about the model structure

This narrow scope is what makes "must generate identical output every time" achievable: you'll set `temperature=0`, give it a strict, example-driven prompt, and — critically — run a **validation step afterward** that checks the generated code against the IR (are all blocks present? Is the order correct? Do all called functions actually exist in the mapping file?). If validation fails, you regenerate or fall back to a fully deterministic template-based code generator (a simple Python string-formatting function that doesn't use AI at all). Many industry systems keep this deterministic fallback as the "safe default" and only use the LLM to make the *comments and formatting* nicer — that's a very reasonable place to start, and arguably a safer end-state too.

### Practical Groq notes for your build
- Free tier is roughly 30 requests/minute, with daily/token caps that vary by model (check `console.groq.com/settings/limits` for your account's live numbers, since they differ by model and can change).
- Use a small, fast model (e.g. `llama-3.1-8b-instant`) rather than a large one — smaller models get much higher daily quotas on the free tier, and your job (formatting already-decided logic) doesn't need a huge model's reasoning power.
- Keep your prompt short: send only the IR for the *current* model plus only the function-mapping entries that are actually used in it (not your whole documentation file). This keeps you well under token limits and makes the LLM's job easier and more consistent.
- Always set temperature to 0 (or the lowest the model allows) for repeatability.

---

## 7. Technology stack (and why each piece is there)

| Tool | Purpose | Why this one |
|---|---|---|
| Python 3.11+ | Everything | You're comfortable with it; it's the standard for this kind of tooling |
| `zipfile` (built-in) | Open `.slx` as an archive | No install needed, `.slx` is literally a zip |
| `lxml` or built-in `xml.etree.ElementTree` | Parse the XML inside | Standard, well-documented XML parsing |
| `networkx` | Build the dependency graph, topological sort | Solved problem — don't hand-roll graph algorithms |
| `pydantic` | Validate your IR's structure | Catches bugs early — if a field is missing or the wrong type, you find out immediately with a clear error, instead of a weird crash three steps later |
| `groq` (official Python SDK) | Call the Groq API | Official, simple |
| `pytest` | Automated tests | Industry-standard testing in Python |
| Git + GitHub | Version control | Non-negotiable for any real project, including internship ones — this is one of the most valuable habits to build now |

You do **not** need LangChain, CrewAI, or a vector database for this scope. Adding them now would add complexity that doesn't solve a problem you actually have yet (your function-mapping file is small enough to just search in Python).

---

## 8. Why this is "industry-level" and not just a script

A few practices that separate an internship prototype from an industry-grade one — all of which we'll bake in from day one:

1. **Separation of concerns** — parser, IR, graph logic, mapping, LLM call, and validation are separate modules/files, each independently testable.
2. **Testing** — every deterministic component gets unit tests (pytest). You test the parser against hand-crafted small XML, the graph logic against known graphs, etc.
3. **Logging** — every step logs what it did (which blocks were found, what order was computed) so when something goes wrong, you can see exactly where.
4. **Schema validation** — the IR is validated (via pydantic) so bad input fails loudly and early, not silently.
5. **Deterministic-first design** — AI is used narrowly and its output is checked, not trusted blindly.
6. **Version control from day one** — every phase is a commit; you can always roll back.
7. **Config, not hardcoding** — API keys, model names, and file paths live in a `.env` / config file, never hardcoded in code (this also matters for when this later runs inside your company's secure network without internet).

---

## 9. Summary — the mental model to keep

You are not building "an AI that reads Simulink." You are building a **small compiler**, where:
- Parsing is deterministic.
- Ordering is deterministic (graph theory).
- Function selection is deterministic (a lookup table).
- Only text generation/formatting uses an LLM, and even that is checked afterward.

Keep this mental model in your head through every phase — it will stop you from reaching for "let the AI figure it out" at moments where a plain Python rule is what your company actually needs.
