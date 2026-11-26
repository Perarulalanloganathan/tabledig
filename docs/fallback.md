# Fallback resolvers: semantic matching and bring-your-own model

When no row matches lexically, tabledig can ask a *resolver* to pick among the row labels it already
found. A resolver chooses a row; it can never supply a value, so every number still comes from the PDF.
Records it produces have `method` set to the resolver's name (`semantic`, `llm`, ...), a score capped at
75 and a confidence reduced by 20%, so they are easy to filter or review. Resolvers are consulted only for
attributes that otherwise come back `not_found`.

## Local embeddings

```bash
pip install "tabledig[semantic]"        # fastembed + a small ONNX model, downloaded on first use
tabledig extract report.pdf --attr Revenue --semantic
```

How much does it help? `benchmarks/semantic_eval.py` (25 synthetic cases, run in CI) measures it against
the lexical matcher:

| threshold | synonyms found (of 15) | false matches (of 10 absent) |
|---|---|---|
| lexical only | 0 | 0 |
| 0.70 | 9 | 6 |
| 0.75 | 6 | 1 |
| **0.80 (default)** | 2 | 0 |
| 0.85 | 2 | 0 |
| 0.90 | 0 | 0 |

So embeddings recover some wordings the packs and fuzzy matching miss ("Takings" for revenue), at a real
risk of wrong rows when you lower the threshold. The default is the highest-recall setting with no false
matches on that set; the set is small, so prefer `SemanticResolver(threshold=...)` tuned on your own
documents, and keep `--validate` on.

## Bring your own model

```python
from tabledig import extract

def ask_model(attribute, labels):
    """Return (index into labels, score 0-100), or None."""
    prompt = f"Which of these row labels means '{attribute.name}'? Answer with its number, or NONE.\n"
    prompt += "\n".join(f"{i}: {l}" for i, l in enumerate(labels))
    answer = my_llm(prompt).strip()          # your model call
    return (int(answer), 70.0) if answer.isdigit() else None

ask_model.method = "llm"
rows = extract("report.pdf", ["Revenue"], fallback=ask_model, validate=True)
```

Out-of-range answers are ignored. Nothing is sent anywhere unless your function sends it.
