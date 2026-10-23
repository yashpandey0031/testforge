"""Run a project's tests against each mutant and record killed / survived."""
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, asdict

from .mutate import Mutant, generate_mutants


@dataclass
class Result:
    id: int
    operator: str
    line: int
    original: str
    mutated: str
    status: str        # killed | survived | timeout
    seconds: float


def _run_tests(cwd, test_cmd, timeout):
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}  # never reuse stale .pyc between mutants
    cmd = shlex.split(test_cmd)
    if cmd[0] == "pytest":
        cmd = [sys.executable, "-m", "pytest"] + cmd[1:]
    start = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        return p.returncode, time.time() - start, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return None, time.time() - start, "timeout"


def _clean_pycache(root):
    for d, dirs, _ in os.walk(root):
        for x in list(dirs):
            if x == "__pycache__":
                shutil.rmtree(os.path.join(d, x), ignore_errors=True)
                dirs.remove(x)


def run_mutation(project, target, test_cmd="pytest -x -q", timeout=60, max_mutants=0, seed=0, progress=print):
    """Returns dict with baseline info, per-mutant results and the mutation score."""
    project = os.path.abspath(project)
    target_path = os.path.join(project, target)
    original = open(target_path, encoding="utf-8").read()

    work = tempfile.mkdtemp(prefix="testforge_")
    try:
        # work on a throwaway copy: the user's code is never modified
        shutil.copytree(project, work, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".git", "*.db", ".venv"))
        work_target = os.path.join(work, target)

        # 1) baseline: tests MUST pass on the untouched code, otherwise scores are meaningless
        code, secs, out = _run_tests(work, test_cmd, timeout * 3)
        if code != 0:
            raise RuntimeError(f"Baseline tests do not pass (exit {code}). Fix them first.\n{out[-1500:]}")
        progress(f"baseline green in {secs:.1f}s")

        mutants = generate_mutants(original, max_mutants, seed)
        progress(f"{len(mutants)} mutants to test")
        results = []
        for m in mutants:
            _clean_pycache(work)
            with open(work_target, "w", encoding="utf-8") as f:
                f.write(m.source)
            code, secs, _ = _run_tests(work, test_cmd, timeout)
            status = "timeout" if code is None else ("survived" if code == 0 else "killed")
            results.append(Result(m.id, m.operator, m.line, m.original, m.mutated, status, round(secs, 2)))
            progress(f"  #{m.id:<3} line {m.line:<4} {m.operator:<13} {status}")
        killed = sum(r.status in ("killed", "timeout") for r in results)  # timeout = test noticed a hang
        score = round(100 * killed / len(results), 1) if results else 0.0
        return {"target": target, "test_cmd": test_cmd, "total": len(results), "killed": killed,
                "survived": len(results) - killed, "score": score, "results": [asdict(r) for r in results]}
    finally:
        shutil.rmtree(work, ignore_errors=True)
