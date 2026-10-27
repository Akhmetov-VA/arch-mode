"""Finds the project's Python files, names their modules, parses them and lists their imports."""
from __future__ import annotations

import ast
import fnmatch
import os
from pathlib import Path

from archcheck.model import ERROR, Config, Finding, Import, Module

SKIP_DIRS = {"node_modules", "__pycache__", "build", "dist", "target", "site-packages", "venv", "env",
             "tests", "test"}


def is_test_file(name: str) -> bool:
    return name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"


def source_roots(root: Path, config: Config) -> list[Path]:
    if config.roots:
        return [root / r for r in config.roots]
    return [root / "src"] if (root / "src").is_dir() else [root]


def load_modules(root: Path, config: Config) -> tuple[list[Module], list[Finding]]:
    modules, problems = [], []
    for src in source_roots(root, config):
        for path in _python_files(src, root, config.exclude):
            module, problem = _load(path, src, root)
            modules.append(module)
            problems += [problem] if problem else []
    return modules, problems


def _python_files(src: Path, root: Path, exclude: tuple[str, ...]):
    for dirpath, dirnames, filenames in os.walk(src):
        here = Path(dirpath)
        dirnames[:] = sorted(d for d in dirnames if not _skip_dir(here / d))
        for name in sorted(filenames):
            path = here / name
            if name.endswith(".py") and not is_test_file(name) and not _excluded(path, root, exclude):
                yield path


def _skip_dir(path: Path) -> bool:
    return path.name in SKIP_DIRS or path.name.startswith(".") or (path / "pyvenv.cfg").exists()


def _excluded(path: Path, root: Path, patterns: tuple[str, ...]) -> bool:
    rel = path.relative_to(root).as_posix()
    return any(fnmatch.fnmatch(rel, p) for p in patterns)


def module_name(rel: Path) -> tuple[str, bool]:
    """'a/b/c.py' -> ('a.b.c', False); 'a/b/__init__.py' -> ('a.b', True)."""
    parts = list(rel.with_suffix("").parts)
    is_init = parts[-1] == "__init__"
    return ".".join(parts[:-1] if is_init else parts), is_init


def _load(path: Path, src: Path, root: Path) -> tuple[Module, Finding | None]:
    name, is_init = module_name(path.relative_to(src))
    package = (name if is_init else name.rpartition(".")[0]) or "."
    rel = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    module = Module(name, rel, package, None, text.splitlines())
    try:
        module.tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        return module, Finding("parse-error", ERROR, rel, exc.lineno, f"cannot parse: {exc.msg}")
    module.nodes = list(ast.walk(module.tree))
    module.imports = list(_imports(module.nodes, package))
    return module, None


def _imports(nodes: list[ast.AST], package: str):
    for node in nodes:
        if isinstance(node, ast.Import):
            yield from (Import(alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _absolute(node, package)
            for alias in node.names:
                name = base if alias.name == "*" else f"{base}.{alias.name}".lstrip(".")
                yield Import(name, node.lineno)


def _absolute(node: ast.ImportFrom, package: str) -> str:
    if not node.level:
        return node.module or ""
    parts = [] if package == "." else package.split(".")
    keep = parts[:len(parts) - node.level + 1]
    return ".".join(keep + ([node.module] if node.module else []))
