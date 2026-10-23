import ast
import pytest
from testforge.mutate import generate_mutants

SRC = '''
def check(age, name):
    """docstring 5 should be ignored"""
    if age >= 18 and name:
        return 200
    return 403
'''


def test_every_mutant_is_valid_python_and_differs():
    ms = generate_mutants(SRC)
    assert ms
    for m in ms:
        ast.parse(m.source)                      # still compiles
        assert m.source != ast.unparse(ast.parse(SRC))  # and actually changed


def test_expected_operators_are_found():
    ops = {m.operator for m in generate_mutants(SRC)}
    assert {"compare", "boolop", "constant_int", "negate_if"} <= ops


def test_compare_mutant_flips_ge_to_gt():
    m = next(m for m in generate_mutants(SRC) if m.operator == "compare")
    assert ">=" in m.original and ">" in m.mutated and ">=" not in m.mutated


def test_docstrings_are_not_mutated():
    assert all("docstring" not in m.original for m in generate_mutants(SRC))


def test_pragma_skips_whole_statement():
    src = "def f(x):\n    if x > 1:  # pragma: no mutate\n        return 5\n    return 6\n"
    lines = {m.line for m in generate_mutants(src)}
    assert 2 not in lines and 3 not in lines


def test_sampling_is_reproducible_and_capped():
    a = generate_mutants(SRC, max_mutants=3, seed=1)
    b = generate_mutants(SRC, max_mutants=3, seed=1)
    assert len(a) == 3 and [m.source for m in a] == [m.source for m in b]


def test_zero_is_not_mutated_as_constant():
    assert not any(m.operator == "constant_int" for m in generate_mutants("x = 0\n"))
