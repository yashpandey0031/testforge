"""End-to-end test of the runner on a tiny fake project (no network, no LLM)."""
import textwrap
import pytest
from testforge.runner import run_mutation


@pytest.fixture
def project(tmp_path):
    (tmp_path / "calc.py").write_text("def is_adult(age):\n    return age >= 18\n")
    return tmp_path


def write_tests(project, body):
    (project / "test_calc.py").write_text("from calc import is_adult\n" + textwrap.dedent(body))


def test_weak_tests_let_mutants_survive_strong_tests_kill_them(project):
    write_tests(project, "def test_a():\n    assert is_adult(30)\n")
    weak = run_mutation(project, "calc.py", "pytest -x -q", progress=lambda *_: None)
    write_tests(project, """
        def test_a():
            assert is_adult(30)
        def test_boundary():
            assert is_adult(18) and not is_adult(17)
    """)
    strong = run_mutation(project, "calc.py", "pytest -x -q", progress=lambda *_: None)
    assert weak["score"] < strong["score"] == 100.0


def test_refuses_to_score_when_baseline_fails(project):
    write_tests(project, "def test_bad():\n    assert is_adult(1)\n")
    with pytest.raises(RuntimeError, match="Baseline"):
        run_mutation(project, "calc.py", "pytest -x -q", progress=lambda *_: None)


def test_users_source_file_is_never_modified(project):
    write_tests(project, "def test_a():\n    assert is_adult(30)\n")
    before = (project / "calc.py").read_text()
    run_mutation(project, "calc.py", "pytest -x -q", progress=lambda *_: None)
    assert (project / "calc.py").read_text() == before
