"""Mutation engine: make small, deliberate bugs in a Python source file.

How it works (the whole idea in 4 lines):
  1. Parse the file into an AST (a tree of the code's structure).
  2. Walk the tree and list every place a mutation operator applies.
  3. For each place, make a fresh copy of the tree with ONLY that one change.
  4. Turn the tree back into source code -> that's one "mutant".
"""
import ast
import copy
import random
from dataclasses import dataclass

# comparison operator swaps: each is a classic off-by-one / inverted-logic bug
CMP_SWAPS = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Lt: ast.LtE, ast.LtE: ast.Lt,
    ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.Is: ast.IsNot, ast.IsNot: ast.Is,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
}
ARITH_SWAPS = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div}
PRAGMA = "pragma: no mutate"


@dataclass
class Mutant:
    id: int
    operator: str      # e.g. "compare", "constant"
    line: int
    original: str      # the code before
    mutated: str       # the code after
    source: str        # full mutated file


def _skipped_lines(source: str, tree: ast.AST) -> set:
    """Lines inside any statement whose first line has '# pragma: no mutate'."""
    lines = source.splitlines()
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt) and PRAGMA in lines[node.lineno - 1]:
            skip.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return skip


def _docstring_nodes(tree) -> set:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _apply(node, kind):
    """Mutate `node` in place according to `kind`. Returns operator name."""
    if kind == "compare":
        node.ops[0] = CMP_SWAPS[type(node.ops[0])]()
    elif kind == "boolop":
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
    elif kind == "arith":
        node.op = ARITH_SWAPS[type(node.op)]()
    elif kind == "constant_int":
        node.value = node.value + 1
    elif kind == "constant_bool":
        node.value = not node.value
    return kind


def _candidates(tree, skip_lines, doc_ids):
    """Yield (path_index, kind) for every mutable node, in a stable order."""
    for i, node in enumerate(ast.walk(tree)):
        if getattr(node, "lineno", None) in skip_lines:
            continue
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in CMP_SWAPS:
            yield i, "compare"
        elif isinstance(node, ast.BoolOp) and len(node.values) == 2:
            yield i, "boolop"
        elif isinstance(node, ast.BinOp) and type(node.op) in ARITH_SWAPS:
            yield i, "arith"
        elif isinstance(node, ast.Constant) and id(node) not in doc_ids:
            if isinstance(node.value, bool):
                yield i, "constant_bool"
            elif isinstance(node.value, int) and node.value != 0:
                yield i, "constant_int"
        elif isinstance(node, ast.If):
            yield i, "negate_if"
        # (negate_if handled in _mutate_nth)


def generate_mutants(source: str, max_mutants: int = 0, seed: int = 0) -> list:
    tree = ast.parse(source)
    skip = _skipped_lines(source, tree)
    doc_ids = _docstring_nodes(tree)
    cands = list(_candidates(tree, skip, doc_ids))
    if max_mutants and len(cands) > max_mutants:
        cands = sorted(random.Random(seed).sample(cands, max_mutants))  # reproducible sample

    mutants = []
    for n, (idx, kind) in enumerate(cands, start=1):
        t = copy.deepcopy(tree)
        node = list(ast.walk(t))[idx]
        line = node.lineno
        before = ast.unparse(node).splitlines()[0][:90]
        if kind == "negate_if":
            node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
        else:
            _apply(node, kind)
        after = ast.unparse(node).splitlines()[0][:90]
        ast.fix_missing_locations(t)
        mutants.append(Mutant(n, kind, line, before, after, ast.unparse(t)))
    return mutants
