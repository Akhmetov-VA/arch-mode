"""Clean Architecture: the Dependency Rule and pure inner layers."""
from __future__ import annotations

import ast

from archcheck.model import ERROR, Edge, Finding, Layer, Module

# I/O, drivers and frameworks: details that belong in outer layers.
IO = frozenset({
    "os", "subprocess", "socket", "shutil", "sqlite3", "ftplib", "smtplib", "http.client", "http.server",
    "urllib.request", "requests", "httpx", "aiohttp", "grpc",
    "sqlalchemy", "psycopg", "psycopg2", "asyncpg", "pymysql", "pymongo", "motor", "redis", "clickhouse_driver",
    "elasticsearch", "boto3", "botocore", "kafka", "aiokafka", "confluent_kafka", "pika", "celery",
    "django", "flask", "fastapi", "starlette", "aiogram", "telegram", "telebot",
})


def layer_index(layers: tuple[Layer, ...], module: str) -> int | None:
    best = max(range(len(layers)), key=lambda i: layers[i].claim(module), default=None)
    return best if best is not None and layers[best].claim(module) else None


def dependency_rule(layers: tuple[Layer, ...], edges: list[Edge]) -> list[Finding]:
    found = []
    for e in edges:
        src, dst = layer_index(layers, e.source.name), layer_index(layers, e.target)
        if src is not None and dst is not None and dst > src:
            found.append(Finding("dependency-rule", ERROR, e.source.path, e.line,
                                 f"{layers[src].name} imports {e.target} from outer layer {layers[dst].name}: "
                                 f"source dependencies must point inward"))
    return found


def pure_layer(layers: tuple[Layer, ...], modules: list[Module]) -> list[Finding]:
    found = []
    for m in modules:
        index = layer_index(layers, m.name)
        if index is not None and m.tree is not None:
            found += _banned_imports(m, layers[index]) + _file_io(m, layers[index])
    return found


def _matches(name: str, banned) -> bool:
    return any(name == b or name.startswith(b + ".") for b in banned)


def _banned_imports(m: Module, layer: Layer) -> list[Finding]:
    banned = (IO if layer.pure else frozenset()) | set(layer.forbid)
    return [Finding("pure-layer", ERROR, m.path, imp.line,
                    f"layer {layer.name} must not import {imp.name}: I/O, drivers and frameworks belong in outer layers")
            for imp in m.imports if _matches(imp.name, banned)]


def _file_io(m: Module, layer: Layer) -> list[Finding]:
    if not layer.pure:
        return []
    return [Finding("pure-layer", ERROR, m.path, node.lineno,
                    f"layer {layer.name} opens files: take the data, or a port that reads it, as an argument")
            for node in m.nodes
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open"]
