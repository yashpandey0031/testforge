"""Stage 2: spec -> prompt -> LLM -> test file -> validate (throw away bad tests)."""
import ast
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

CONTRACT = """You write pytest API tests for a web service.

RULES (follow exactly):
- Output ONE complete Python file, nothing else. A ```python fence is fine.
- Start with: import pytest, requests
- Only top-level functions named test_*. No classes.
- Use ONLY the pytest fixture `base_url` (str, root URL of the running server). The database is EMPTY at the start of every test.
- Every test is independent: create the data it needs through the API itself.
- Cover for each endpoint: success, validation errors (use the schema: required fields, min/max length, enums, types),
  not-found, boundary values (exactly at and just past each limit), and that a failed request saved nothing.
- Assert the status code AND the important fields of the body. Also re-read data after writes to prove it persisted.
- Only assert behaviour the spec states or that follows from it. Do NOT invent fields, endpoints or status codes.
- No sleeps, no randomness, no external network."""


def slim_spec(spec: dict) -> str:
    """Keep only what the model needs: paths, params, request/response schemas."""
    return json.dumps({"paths": spec.get("paths", {}),
                       "schemas": spec.get("components", {}).get("schemas", {})}, indent=1)


def build_generation_prompt(spec: dict) -> str:
    return f"{CONTRACT}\n\nAPI SPEC (OpenAPI):\n{slim_spec(spec)}\n"


def extract_code(text: str) -> str:
    m = re.search(r"```(?:python)?\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip() + "\n"


# ---------- validation ----------
def _run_pytest(project, test_file, timeout=180):
    with tempfile.TemporaryDirectory() as td:
        xml = os.path.join(td, "r.xml")
        cmd = [sys.executable, "-m", "pytest", test_file, "-q", "--tb=no", f"--junitxml={xml}", "-p", "no:cacheprovider"]
        p = subprocess.run(cmd, cwd=project, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        if not os.path.exists(xml):
            return None, p.stdout + p.stderr
        return ET.parse(xml).getroot(), p.stdout + p.stderr


def _bad_test_names(root):
    bad = set()
    for tc in root.iter("testcase"):
        if tc.find("failure") is not None or tc.find("error") is not None:
            bad.add(tc.get("name").split("[")[0])  # parametrized id -> function name
    return bad


def _drop_functions(code: str, names: set) -> str:
    tree = ast.parse(code)
    tree.body = [n for n in tree.body if not (isinstance(n, ast.FunctionDef) and n.name in names)]
    return ast.unparse(tree) + "\n"


def validate(project: str, test_path: str) -> dict:
    """Run generated tests on the UNTOUCHED app. A test that fails here is wrong (it hallucinated
    a field/status code), not a bug-finder. Discard those and confirm what's left is green."""
    code = open(test_path, encoding="utf-8").read()
    try:
        ast.parse(code)
    except SyntaxError as e:
        return {"generated": 0, "kept": 0, "discarded": [], "error": f"generated file is not valid Python: {e}"}
    rel = os.path.relpath(test_path, project)
    total = sum(isinstance(n, ast.FunctionDef) and n.name.startswith("test_") for n in ast.parse(code).body)

    root, out = _run_pytest(project, rel)
    if root is None:
        return {"generated": total, "kept": 0, "discarded": [], "error": "pytest could not collect the file:\n" + out[-800:]}
    bad = _bad_test_names(root)
    if bad:
        code = _drop_functions(code, bad)
        open(test_path, "w", encoding="utf-8").write(code)
        root, out = _run_pytest(project, rel)
        if root is None or _bad_test_names(root):  # flaky or order-dependent: refuse
            return {"generated": total, "kept": 0, "discarded": sorted(bad),
                    "error": "tests still failing after pruning (flaky or order-dependent)"}
    kept = sum(isinstance(n, ast.FunctionDef) and n.name.startswith("test_") for n in ast.parse(code).body)
    return {"generated": total, "kept": kept, "discarded": sorted(bad), "error": None}


def generate_tests(provider, spec: dict, project: str, out_rel="tests/generated/test_generated.py") -> dict:
    code = extract_code(provider.complete(build_generation_prompt(spec)))
    path = os.path.join(project, out_rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(os.path.join(os.path.dirname(path), "__init__.py"), "a").close()
    open(path, "w", encoding="utf-8").write(code)
    return {"path": path, **validate(project, path)}
