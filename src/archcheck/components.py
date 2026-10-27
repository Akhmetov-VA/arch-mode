"""Component principles: the import graph between packages, ADP (no cycles), SDP and the metrics I, A, D."""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass

from archcheck.model import ERROR, WARNING, Edge, Finding, Module

Graph = dict[str, dict[str, list[Edge]]]   # package -> package it imports -> import sites


def resolve(name: str, importer: Module, known: set[str]) -> str | None:
    """Project module that an import refers to, or None for a library."""
    return _longest_known(name, known) or _sibling(name, importer, known)


def _sibling(name: str, importer: Module, known: set[str]) -> str | None:
    """Script style: a directory on sys.path imports its sibling files by bare name."""
    found = _longest_known(f"{importer.package}.{name}", known)
    return found if found and found.startswith(importer.package + ".") else None


def _longest_known(name: str, known: set[str]) -> str | None:
    parts = name.split(".")
    return next((".".join(parts[:end]) for end in range(len(parts), 0, -1) if ".".join(parts[:end]) in known), None)


def project_edges(modules: list[Module]) -> list[Edge]:
    known = {m.name for m in modules}
    edges = []
    for m in modules:
        for imp in m.imports:
            target = resolve(imp.name, m, known)
            if target and target != m.name:
                edges.append(Edge(m, target, imp.line))
    return edges


def package_graph(modules: list[Module], edges: list[Edge]) -> Graph:
    package = {m.name: m.package for m in modules}
    graph: Graph = {m.package: {} for m in modules}
    for e in edges:
        src, dst = e.source.package, package[e.target]
        if src != dst:
            graph[src].setdefault(dst, []).append(e)
    return graph


def strongly_connected(graph: Graph) -> list[list[str]]:
    """Tarjan's algorithm."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    components: list[list[str]] = []

    def visit(v: str) -> None:
        index[v] = low[v] = len(index)
        stack.append(v)
        for w in graph[v]:
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            component = []
            while not component or component[-1] != v:
                component.append(stack.pop())
            components.append(sorted(component))

    for v in sorted(graph):
        if v not in index:
            visit(v)
    return components


def cycles(graph: Graph) -> list[Finding]:
    found = []
    for component in strongly_connected(graph):
        members = set(component)
        sites = sorted((e for p in component for q, es in graph[p].items() if q in members for e in es),
                       key=lambda e: (e.source.path, e.line))
        if not sites:
            continue
        first = sites[0]
        related = tuple(sorted({e.source.path for e in sites} - {first.source.path}))
        found.append(Finding("component-cycle", ERROR, first.source.path, first.line,
                             f"packages {' <-> '.join(component)} depend on each other: break the cycle with an "
                             f"interface owned by one side or a new package (ADP)", related))
    return found


@dataclass(frozen=True)
class PackageMetrics:
    package: str
    ca: int
    ce: int
    instability: float
    abstractness: float
    distance: float

    def as_dict(self) -> dict:
        return asdict(self)


def metrics(modules: list[Module], graph: Graph) -> dict[str, PackageMetrics]:
    afferent = {p: sum(p in deps for deps in graph.values()) for p in graph}
    classes = _abstract_flags(modules)
    result = {}
    for p in sorted(graph):
        ca, ce = afferent[p], len(graph[p])
        i = ce / (ca + ce) if ca + ce else 0.0
        flags = classes.get(p, [])
        a = sum(flags) / len(flags) if flags else 0.0
        result[p] = PackageMetrics(p, ca, ce, round(i, 3), round(a, 3), round(abs(a + i - 1), 3))
    return result


def _abstract_flags(modules: list[Module]) -> dict[str, list[bool]]:
    """Package -> is_abstract for each of its classes."""
    flags: dict[str, list[bool]] = {}
    for m in modules:
        for node in ast.walk(m.tree) if m.tree else ():
            if isinstance(node, ast.ClassDef):
                flags.setdefault(m.package, []).append(is_abstract(node))
    return flags


def is_abstract(cls: ast.ClassDef) -> bool:
    bases = {base_name(b) for b in cls.bases}
    metaclass = any(k.arg == "metaclass" and base_name(k.value) == "ABCMeta" for k in cls.keywords)
    abstract_method = any(base_name(d) == "abstractmethod" for f in cls.body
                          if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) for d in f.decorator_list)
    return bool(bases & {"ABC", "Protocol"}) or metaclass or abstract_method


def base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Subscript):
        return base_name(node.value)
    if isinstance(node, ast.Attribute):
        return node.attr
    return node.id if isinstance(node, ast.Name) else ""


def unstable_dependencies(graph: Graph, m: dict[str, PackageMetrics]) -> list[Finding]:
    found = []
    for p in sorted(graph):
        for q, sites in sorted(graph[p].items()):
            if m[q].instability > m[p].instability:
                e = min(sites, key=lambda s: (s.source.path, s.line))
                found.append(Finding("unstable-dependency", WARNING, e.source.path, e.line,
                                     f"{p} (I={m[p].instability:.2f}) depends on less stable {q} "
                                     f"(I={m[q].instability:.2f}): depend in the direction of stability (SDP)"))
    return found
