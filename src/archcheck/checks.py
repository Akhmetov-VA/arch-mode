"""Checks inside one module (faults and time from DDIA, design smells from Design Patterns),
and the project-wide inheritance check."""
from __future__ import annotations

import ast
from collections import Counter

from archcheck.components import base_name
from archcheck.model import ERROR, WARNING, Finding, Module

NETWORK = {f"requests.{verb}" for verb in ("get", "post", "put", "patch", "delete", "head", "options", "request")}
NETWORK |= {"urllib.request.urlopen", "socket.create_connection"}
TIMEOUT_POSITION = {"urllib.request.urlopen": 2, "socket.create_connection": 1}
HTTPX = {f"httpx.{name}" for name in ("get", "post", "put", "patch", "delete", "head", "options", "request",
                                      "stream", "Client", "AsyncClient")}
NAIVE_ALWAYS = {"datetime.datetime.utcnow", "datetime.datetime.utcfromtimestamp", "datetime.datetime.today"}
NAIVE_WITHOUT_TZ = {"datetime.datetime.now"}
BROAD = {"Exception", "BaseException"}


def aliases(tree: ast.Module) -> dict[str, str]:
    """Local name -> qualified name it was imported as."""
    names = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(_import_aliases(node))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.update({a.asname or a.name: f"{node.module}.{a.name}" for a in node.names})
    return names


def _import_aliases(node: ast.Import) -> dict[str, str]:
    """'import a.b' binds a; 'import a.b as c' binds c to a.b."""
    return {a.asname: a.name for a in node.names if a.asname} | \
        {a.name.split(".")[0]: a.name.split(".")[0] for a in node.names if not a.asname}


def qualname(node: ast.expr, names: dict[str, str]) -> str | None:
    chain = []
    while isinstance(node, ast.Attribute):
        chain.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name) or node.id not in names:
        return None
    return ".".join([names[node.id], *reversed(chain)])


def module_checks(m: Module) -> list[Finding]:
    if m.tree is None:
        return []
    names = aliases(m.tree)
    found = []
    for node in ast.walk(m.tree):
        for check in NODE_CHECKS:
            hit = check(node, names)
            if hit:
                found.append(Finding(hit[0], hit[1], m.path, hit[2], hit[3]))
    return found


def _timeout(call: ast.Call, position: int | None) -> str:
    """'set', 'none' (timeout=None) or 'missing'."""
    for kw in call.keywords:
        if kw.arg == "timeout":
            return "none" if isinstance(kw.value, ast.Constant) and kw.value.value is None else "set"
    return "set" if position is not None and len(call.args) > position else "missing"


def network_timeout(node, names):
    if not isinstance(node, ast.Call):
        return None
    q = qualname(node.func, names)
    if q in NETWORK and _timeout(node, TIMEOUT_POSITION.get(q)) != "set":
        return ("network-timeout", ERROR, node.lineno, f"{q} without a timeout: an unbounded wait is a hang")
    if q in HTTPX and _timeout(node, None) == "none":
        return ("network-timeout", ERROR, node.lineno, f"{q} with timeout=None: an unbounded wait is a hang")
    return None


def _calls(node, names, wanted) -> bool:
    return isinstance(node, ast.Call) and qualname(node.func, names) in wanted


def wall_clock_duration(node, names):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub) and \
            (_calls(node.left, names, {"time.time"}) or _calls(node.right, names, {"time.time"})):
        return ("wall-clock-duration", WARNING, node.lineno,
                "duration measured with time.time(): the wall clock jumps; use time.monotonic()")
    return None


def naive_datetime(node, names):
    naive = _calls(node, names, NAIVE_ALWAYS) or \
        (_calls(node, names, NAIVE_WITHOUT_TZ) and not node.args and not node.keywords)
    if naive:
        return ("naive-datetime", WARNING, node.lineno,
                "naive datetime: keep time in UTC with tzinfo, e.g. datetime.now(timezone.utc)")
    return None


def _broad(node: ast.expr | None) -> bool:
    if node is None:
        return True
    if isinstance(node, ast.Tuple):
        return any(_broad(e) for e in node.elts)
    return base_name(node) in BROAD


def _empty(stmt: ast.stmt) -> bool:
    return isinstance(stmt, (ast.Pass, ast.Continue)) or (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant))


def swallowed_error(node, names):
    if isinstance(node, ast.ExceptHandler) and _broad(node.type) and all(_empty(s) for s in node.body):
        return ("swallowed-error", WARNING, node.lineno,
                "broad exception swallowed: a hidden fault becomes a later failure; handle it, log it or re-raise")
    return None


def _if_tests(fn):
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.If):
            yield node.test
        stack.extend(ast.iter_child_nodes(node))


def type_switch(node, names):
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    checked = Counter(ast.unparse(c.args[0]) for test in _if_tests(node) for c in ast.walk(test)
                      if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "isinstance" and c.args)
    if not checked:
        return None
    value, count = checked.most_common(1)[0]
    if count >= 3:
        return ("type-switch", WARNING, node.lineno,
                f"{node.name}: {count} isinstance checks on {value}; if this switch repeats, move the behavior "
                f"into the types (polymorphism, Strategy, State or Visitor)")
    return None


def global_state(node, names):
    if isinstance(node, ast.Global):
        return ("global-state", WARNING, node.lineno,
                f"global {', '.join(node.names)}: hidden shared state; pass it in, or give it one owner")
    return None


NODE_CHECKS = (network_timeout, wall_clock_duration, naive_datetime, swallowed_error, type_switch, global_state)


def deep_inheritance(modules: list[Module]) -> list[Finding]:
    classes: dict[str, tuple[list[str], Module, int]] = {}
    for m in modules:
        for node in ast.walk(m.tree) if m.tree else ():
            if isinstance(node, ast.ClassDef):
                classes.setdefault(node.name, ([base_name(b) for b in node.bases], m, node.lineno))
    found = []
    for name, (_, m, line) in classes.items():
        chain = _chain(name, classes, ())
        if len(chain) > 3:
            found.append(Finding("deep-inheritance", WARNING, m.path, line,
                                 f"class {name} inherits through {len(chain) - 1} project classes "
                                 f"({' -> '.join(chain)}): favor composition over inheritance"))
    return found


def _chain(name: str, classes: dict, seen: tuple[str, ...]) -> list[str]:
    """Longest line of project ancestors: [name, parent, grandparent, ...]."""
    parents = [_chain(base, classes, seen + (name,)) for base in classes[name][0]
               if base in classes and base not in seen and base != name]
    return [name, *max(parents, key=len, default=[])]
