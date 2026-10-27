"""Checks inside one module (faults and time from DDIA, design smells from Design Patterns),
and the project-wide inheritance check."""
from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass

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
SERIALIZERS = {f"{lib}.{fn}" for lib in ("pickle", "dill", "cloudpickle", "marshal", "joblib")
               for fn in ("load", "loads", "dump", "dumps")} | {"pickle.Pickler", "pickle.Unpickler", "shelve.open"}
QUEUES = {"queue.Queue", "queue.LifoQueue", "queue.PriorityQueue", "asyncio.Queue", "asyncio.LifoQueue",
          "asyncio.PriorityQueue", "multiprocessing.Queue", "multiprocessing.JoinableQueue"}
SINGLETON_NAMES = {"_instance", "instance", "_instances", "__instance"}


@dataclass(frozen=True)
class Scope:
    names: dict[str, str]          # local name -> qualified name it was imported as
    classes: frozenset[str]        # names of classes defined anywhere in the project


def project_classes(modules: list[Module]) -> frozenset[str]:
    return frozenset(n.name for m in modules for n in m.nodes if isinstance(n, ast.ClassDef))


def aliases(nodes: list[ast.AST]) -> dict[str, str]:
    """Local name -> qualified name it was imported as."""
    names = {}
    for node in nodes:
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


def module_checks(m: Module, classes: frozenset[str]) -> list[Finding]:
    scope = Scope(aliases(m.nodes), classes)
    found = []
    for node in m.nodes:
        for check in NODE_CHECKS:
            hit = check(node, scope)
            if hit:
                found.append(Finding(hit[0], hit[1], m.path, hit[2], hit[3]))
    return found


def _timeout(call: ast.Call, position: int | None) -> str:
    """'set', 'none' (timeout=None) or 'missing'."""
    for kw in call.keywords:
        if kw.arg == "timeout":
            return "none" if isinstance(kw.value, ast.Constant) and kw.value.value is None else "set"
    return "set" if position is not None and len(call.args) > position else "missing"


def network_timeout(node, scope):
    if not isinstance(node, ast.Call):
        return None
    q = qualname(node.func, scope.names)
    if q in NETWORK and _timeout(node, TIMEOUT_POSITION.get(q)) != "set":
        return ("network-timeout", ERROR, node.lineno, f"{q} without a timeout: an unbounded wait is a hang")
    if q in HTTPX and _timeout(node, None) == "none":
        return ("network-timeout", ERROR, node.lineno, f"{q} with timeout=None: an unbounded wait is a hang")
    return None


def _calls(node, names, wanted) -> bool:
    return isinstance(node, ast.Call) and qualname(node.func, names) in wanted


def wall_clock_duration(node, scope):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub) and \
            (_calls(node.left, scope.names, {"time.time"}) or _calls(node.right, scope.names, {"time.time"})):
        return ("wall-clock-duration", WARNING, node.lineno,
                "duration measured with time.time(): the wall clock jumps; use time.monotonic()")
    return None


def naive_datetime(node, scope):
    naive = _calls(node, scope.names, NAIVE_ALWAYS) or \
        (_calls(node, scope.names, NAIVE_WITHOUT_TZ) and not node.args and not node.keywords)
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


def swallowed_error(node, scope):
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


def _isinstance_checks(fn):
    """(checked value, names of the classes it is checked against) for each isinstance in the function's ifs."""
    for test in _if_tests(fn):
        for c in ast.walk(test):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "isinstance" and len(c.args) == 2:
                kinds = c.args[1].elts if isinstance(c.args[1], ast.Tuple) else [c.args[1]]
                yield ast.unparse(c.args[0]), {base_name(k) for k in kinds}


def type_switch(node, scope):
    """Three or more isinstance checks on one value, at least one against a project class: only then can the
    behavior move into the types. A switch over library or builtin types is parsing, not a design smell."""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    counts, owned = Counter(), set()
    for value, kinds in _isinstance_checks(node):
        counts[value] += 1
        owned |= {value} if kinds & scope.classes else set()
    switches = [(value, n) for value, n in counts.most_common() if n >= 3 and value in owned]
    if not switches:
        return None
    value, count = switches[0]
    return ("type-switch", WARNING, node.lineno,
            f"{node.name}: {count} isinstance checks on {value}; if this switch repeats, move the behavior "
            f"into the types (polymorphism, Strategy, State or Visitor)")


def global_state(node, scope):
    if isinstance(node, ast.Global):
        return ("global-state", WARNING, node.lineno,
                f"global {', '.join(node.names)}: hidden shared state; pass it in, or give it one owner")
    return None


def language_serialization(node, scope):
    name = qualname(node.func, scope.names) if isinstance(node, ast.Call) else None
    if name in SERIALIZERS:
        return ("language-serialization", WARNING, node.lineno,
                f"{name}: a language-specific format ties the data to this code version and runs code on load; "
                f"use a schema format (JSON, Avro, Protobuf, Parquet) for data that outlives the process")
    return None


def _bounded(call: ast.Call) -> bool:
    size = call.args[0] if call.args else next((k.value for k in call.keywords if k.arg == "maxsize"), None)
    return size is not None and not (isinstance(size, ast.Constant) and size.value in (0, None))


def unbounded_queue(node, scope):
    unbounded = isinstance(node, ast.Call) and (
        qualname(node.func, scope.names) == "queue.SimpleQueue"
        or (qualname(node.func, scope.names) in QUEUES and not _bounded(node)))
    if unbounded:
        return ("unbounded-queue", WARNING, node.lineno,
                "unbounded queue: when consumers fall behind it grows until memory runs out; set maxsize and "
                "choose backpressure, dropping or spilling")
    return None


def singleton(node, scope):
    if not isinstance(node, ast.ClassDef):
        return None
    cached = any(isinstance(f, ast.FunctionDef) and f.name == "__new__" for f in node.body) and \
        any(isinstance(n, ast.Attribute) and n.attr in SINGLETON_NAMES for n in ast.walk(node))
    meta = any(k.arg == "metaclass" and "singleton" in base_name(k.value).lower() for k in node.keywords)
    if cached or meta:
        return ("singleton", WARNING, node.lineno,
                f"class {node.name} is a Singleton: global access hides the dependency; create one instance in "
                f"Main and pass it in")
    return None


NODE_CHECKS = (network_timeout, wall_clock_duration, naive_datetime, swallowed_error, type_switch, global_state,
               language_serialization, unbounded_queue, singleton)


def deep_inheritance(modules: list[Module]) -> list[Finding]:
    classes: dict[str, tuple[list[str], Module, int]] = {}
    for m in modules:
        for node in m.nodes:
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
