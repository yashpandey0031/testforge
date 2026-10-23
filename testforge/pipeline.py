"""Stage 3: the full loop.
generate -> validate -> score (before) -> show survivors to the LLM -> new tests -> validate -> score (after)."""
import json
import os

from .generate import CONTRACT, extract_code, generate_tests, slim_spec, validate
from .report import write
from .runner import run_mutation


def build_improvement_prompt(spec, target_src, survivors, existing_names):
    lines = target_src.splitlines()
    blocks = []
    for s in survivors:
        lo, hi = max(0, s["line"] - 4), min(len(lines), s["line"] + 3)
        ctx = "\n".join(f"{i + 1:>4}| {lines[i]}" for i in range(lo, hi))
        blocks.append(f"BUG #{s['id']} (line {s['line']}): `{s['original']}` was changed to `{s['mutated']}` "
                      f"and ALL existing tests still passed.\n{ctx}")
    return (f"{CONTRACT}\n\nA bug-injection tool changed the service's code in small ways. For the changes below, "
            f"your existing tests did NOT fail, so they are missing coverage.\n"
            f"Write NEW tests (same rules) so that each change below would make at least one test fail. "
            f"Put a comment `# targets bug #N` above each test. Do not repeat these existing tests: "
            f"{', '.join(existing_names) or 'none'}.\n\nSURVIVING BUGS:\n\n" + "\n\n".join(blocks) +
            f"\n\nAPI SPEC (OpenAPI):\n{slim_spec(spec)}\n")


def _test_names(path):
    import ast
    return [n.name for n in ast.parse(open(path, encoding="utf-8").read()).body
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]


def auto(provider, project, target, spec, max_mutants=0, seed=0, report_path="testforge_report.html",
         extra_runs=None, progress=print):
    project = os.path.abspath(project)
    cmd = "pytest -x -q tests/generated"
    summary = {}

    progress("[1/5] generating tests")
    g1 = generate_tests(provider, spec, project)
    summary["round1"] = {k: g1[k] for k in ("generated", "kept", "discarded", "error")}
    if g1["error"] or g1["kept"] == 0:
        raise RuntimeError(f"no usable tests generated: {g1['error'] or 'all discarded'}")
    progress(f"      kept {g1['kept']}/{g1['generated']}, discarded {g1['discarded']}")

    progress("[2/5] scoring (before feedback)")
    before = run_mutation(project, target, cmd, max_mutants=max_mutants, seed=seed, progress=lambda *_: None)
    progress(f"      score {before['score']}%")
    survivors = [r for r in before["results"] if r["status"] == "survived"]
    runs = {**(extra_runs or {}), "AI-generated (round 1)": before}

    after = None
    if survivors:
        progress(f"[3/5] asking the model to cover {len(survivors)} surviving bugs")
        src = open(os.path.join(project, target), encoding="utf-8").read()
        names = _test_names(g1["path"])
        code = extract_code(provider.complete(build_improvement_prompt(spec, src, survivors, names)))
        p2 = os.path.join(project, "tests/generated/test_generated_round2.py")
        open(p2, "w", encoding="utf-8").write(code)
        v2 = validate(project, p2)
        summary["round2"] = {k: v2[k] for k in ("generated", "kept", "discarded", "error")}
        progress(f"      kept {v2['kept']}/{v2['generated']}, discarded {v2['discarded']}")
        progress("[4/5] scoring (after feedback)")
        after = run_mutation(project, target, cmd, max_mutants=max_mutants, seed=seed, progress=lambda *_: None)
        progress(f"      score {after['score']}%")
        runs["AI + feedback (round 2)"] = after
    else:
        progress("[3/5] no survivors, nothing to improve")

    progress("[5/5] writing report")
    write(runs, report_path)
    summary.update(before=before["score"], after=after["score"] if after else before["score"], report=report_path)
    return summary
