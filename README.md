# TestForge

**Tests that write tests, and then get graded.**
An LLM can write API tests in seconds, but it can also write tests that look right and catch nothing.
TestForge generates tests from an OpenAPI spec, throws away the wrong ones, then measures how good the rest are by
injecting bugs into the code and counting how many the tests catch (the **mutation score**). Missed bugs are fed back
to the model to write better tests.

## How it works
```
OpenAPI spec ──► LLM writes pytest tests ──► VALIDATE on the real app (discard tests that fail = hallucinations)
                                                    │
         ┌──────────────────────────────────────────┘
         ▼
   MUTATE: inject small bugs one at a time (>= to >, constant+1, negate an if, and<->or, ...)
         │   run the tests against each broken copy
         ▼
   killed (a test failed: good)  /  survived (all tests passed: a gap)
         │
         ├──► score = killed / total
         └──► survivors + code context go back to the LLM ──► new tests ──► validate ──► re-score ──► report
```

## Use it
```bash
pip install -r requirements.txt

# 1) Score ANY existing pytest suite (no LLM needed)
python -m testforge mutate --project examples/taskapp --target app/main.py \
       --test-cmd "pytest -x -q -m api" --html report.html

# 2) Full AI loop (needs a free Groq key, or an Anthropic key)
export GROQ_API_KEY=...
python -m testforge auto --project examples/taskapp --target app/main.py \
       --spec examples/taskapp/openapi.json --provider groq --html report.html
```
Your project needs a `base_url` pytest fixture that starts the app and returns its URL (see `examples/taskapp/conftest.py`).
`--max N` samples N mutants for a quick run. Your source files are never modified: mutants run in a temp copy.

## Design decisions
- **Baseline must be green.** Scores mean nothing if tests fail on the original code, so the run aborts.
- **Generated tests are validated before they count.** A test that fails on the unmodified app is wrong, not insightful. It is discarded.
- **One mutation at a time**, so a failing test points at exactly one bug.
- **Mutation operators are classic bug shapes:** off-by-one comparisons, flipped booleans, changed constants (status codes, limits),
  inverted conditions, `and`/`or` swaps. `# pragma: no mutate` skips test-support code.
- **LLM calls are cached** by prompt hash, so reruns are free and reproducible. `temperature=0`.
- **Provider interface is ~10 lines** (`complete(prompt) -> str`): Groq, Anthropic, or your own.
- **Stale bytecode is disabled** (`PYTHONDONTWRITEBYTECODE`), otherwise a rewritten file with the same size and timestamp can run the old code and fake a "survived".

## Results so far
Measured on the Task App (`examples/`), API tests only:

| Suite | Mutation score |
|---|---|
| Hand-written v1 | **82.6%** (19/23 bugs caught) |
| Hand-written v2, after writing tests for the 4 survivors | **100%** (23/23) |

The survivors exposed real gaps in my own tests: no test updated a task without sending `done`, and title length
limits were only tested on create, not on update. Open `examples/demo_report_hand_written.html` to see the report.

The AI loop is covered by tests using a **fake LLM** (so CI needs no key): it checks that a deliberately wrong generated
test is discarded, that survivors reach the model's prompt, and that the score rises after feedback.
*Real-model numbers: run `auto` with your key and paste them here.*

## Limitations
- Small mutation set (5 operators). Real tools like mutmut/Cosmic Ray have more.
- **Equivalent mutants:** some changes don't alter behavior (e.g. storing `True` vs `1` in SQLite), so they survive and look like gaps.
- Tests run as a subprocess per mutant: fine for small apps, slow for big ones (sampling with `--max` helps).
- Generated tests assume the `base_url` fixture contract above, and only Python/pytest targets are supported.
- It runs the target's code, so only point it at code you trust.

## Tests for the tool itself
`python -m pytest -q`: mutation operators, pragma/sampling, runner behavior on a toy project (weak vs strong tests, baseline refusal,
source untouched), and the full generate/validate/improve loop with a fake LLM.
